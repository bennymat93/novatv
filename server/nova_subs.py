# -*- coding: utf-8 -*-
"""NovaTV AI Subtitle Server (runs on the PC).

  speech  -> faster-whisper large-v3-turbo on the GPU (CPU fallback)
  text    -> Hebrew: Gemini (context + gender aware) -> Google free endpoint fallback
  timing  -> taken from the audio itself, so subtitles are in sync by construction

HTTP API (for Kodi):
  GET  /health
  POST /jobs            {"url", "title", "season", "episode", "tmdb", "position", "gemini_key"}
  GET  /jobs/<id>       progress / state / ready_until
  GET  /jobs/<id>/srt   current Hebrew SRT (grows while processing)

CLI (batch, e.g. a whole series overnight):
  python nova_subs.py batch <file-or-url> [...] --title "Кухня"
  python nova_subs.py serve [--port 8765]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import site
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
os.makedirs(CACHE, exist_ok=True)
CHUNK = 240          # seconds of audio per step
MODEL_NAME = 'mobiuslabsgmbh/faster-whisper-large-v3-turbo'
GEMINI_MODELS = ['gemini-3.1-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash']

# CUDA 11 DLLs from pip wheels (works with older laptop drivers)
for sp in site.getsitepackages():
    for d in glob.glob(os.path.join(sp, 'nvidia', '*', 'bin')):
        os.environ['PATH'] = d + os.pathsep + os.environ['PATH']
        try:
            os.add_dll_directory(d)
        except Exception:
            pass

_model, _model_lock, _gpu_lock = None, threading.Lock(), threading.Lock()
_device = '?'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def model():
    global _model, _device
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            try:
                _model = WhisperModel(MODEL_NAME, device='cuda', compute_type='int8')
                _device = 'cuda'
            except Exception as e:
                log('GPU unavailable (%s) - using CPU' % e)
                _model = WhisperModel(MODEL_NAME, device='cpu', compute_type='int8')
                _device = 'cpu'
        return _model


# ------------------------------------------------------------------ audio
def duration(src):
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def audio_chunk(src, start, length):
    """Decode [start, start+length) to 16 kHz mono float32 via ffmpeg (seeks over HTTP)."""
    import numpy as np
    cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', str(start), '-t', str(length), '-i', src,
           '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-']
    raw = subprocess.run(cmd, capture_output=True, timeout=900).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


# ------------------------------------------------------------------ translation
GENDER_NOTE = ('Hebrew is gendered: choose masculine/feminine verb, adjective and "you" forms from who is speaking '
               'and who is addressed (use the dialogue context and the cast list). ')


def gemini_translate(lines, src_lang, key, context):
    if not key:
        raise RuntimeError('no gemini key')
    prompt = ('You are a professional subtitle translator from %s to Hebrew for the show/movie "%s". %s'
              'Translate slang and idioms to natural spoken Israeli Hebrew (not literal). Keep names consistent. '
              'Keep each line short. Return ONLY a JSON array of strings with exactly %d items, same order.\n'
              'Previous context (do not translate): %s\nLines:\n%s'
              % (src_lang, context.get('title', ''), GENDER_NOTE + context.get('cast', ''), len(lines),
                 json.dumps(context.get('prev', []), ensure_ascii=False), json.dumps(lines, ensure_ascii=False)))
    last = None
    for m in GEMINI_MODELS:
        r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent' % m,
                          params={'key': key}, timeout=120,
                          json={'contents': [{'parts': [{'text': prompt}]}],
                                'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'}})
        if r.status_code == 404:
            last = 'model %s not found' % m
            continue
        if r.status_code == 429:
            raise RuntimeError('gemini quota')
        r.raise_for_status()
        text = r.json()['candidates'][0]['content']['parts'][0]['text']
        out = json.loads(text)
        if isinstance(out, list) and len(out) == len(lines):
            return [str(x) for x in out]
        last = 'length mismatch %d/%d' % (len(out), len(lines))
    raise RuntimeError(last or 'gemini failed')


def google_translate(lines, src_lang):
    """Free endpoint, no key. Lines are joined so context is kept, then split back."""
    out = []
    batch, size = [], 0
    def flush():
        if not batch:
            return
        joined = '\n'.join(batch)
        r = requests.get('https://translate.googleapis.com/translate_a/single', timeout=60,
                         params={'client': 'gtx', 'sl': src_lang or 'auto', 'tl': 'iw', 'dt': 't', 'q': joined})
        r.raise_for_status()
        text = ''.join(p[0] for p in r.json()[0] if p[0])
        parts = text.split('\n')
        if len(parts) != len(batch):   # safety: translate one by one
            parts = []
            for b in batch:
                rr = requests.get('https://translate.googleapis.com/translate_a/single', timeout=30,
                                  params={'client': 'gtx', 'sl': src_lang or 'auto', 'tl': 'iw', 'dt': 't', 'q': b})
                parts.append(''.join(p[0] for p in rr.json()[0] if p[0]))
        out.extend(p.strip() for p in parts)
        batch.clear()
    for ln in lines:
        if size + len(ln) > 3500:
            flush(); size = 0
        batch.append(ln.replace('\n', ' ')); size += len(ln) + 1
    flush()
    return out


NLLB_REPO = 'OpenNMT/nllb-200-distilled-1.3B-ct2-int8'
NLLB_CODES = {'ru': 'rus_Cyrl', 'en': 'eng_Latn', 'uk': 'ukr_Cyrl', 'es': 'spa_Latn', 'fr': 'fra_Latn',
              'de': 'deu_Latn', 'it': 'ita_Latn', 'pt': 'por_Latn', 'ar': 'arb_Arab', 'tr': 'tur_Latn',
              'ja': 'jpn_Jpan', 'ko': 'kor_Hang', 'zh': 'zho_Hans', 'pl': 'pol_Latn', 'be': 'bel_Cyrl',
              'kk': 'kaz_Cyrl', 'hi': 'hin_Deva', 'nl': 'nld_Latn', 'sv': 'swe_Latn', 'el': 'ell_Grek'}
_nllb = None


def local_translate(lines, src_lang):
    """Offline NLLB-200 on the GPU - no key, no quota, never stops."""
    global _nllb
    import ctranslate2
    from huggingface_hub import snapshot_download
    from tokenizers import Tokenizer
    with _model_lock:
        if _nllb is None:
            p = snapshot_download(NLLB_REPO)
            try:
                tr = ctranslate2.Translator(p, device='cuda', compute_type='int8')
            except Exception:
                tr = ctranslate2.Translator(p, device='cpu', compute_type='int8')
            _nllb = (tr, Tokenizer.from_file(os.path.join(p, 'tokenizer.json')))
    tr, tok = _nllb
    code = NLLB_CODES.get(src_lang, 'eng_Latn')
    src = [[code] + tok.encode(l, add_special_tokens=False).tokens + ['</s>'] for l in lines]
    with _gpu_lock:
        res = tr.translate_batch(src, target_prefix=[['heb_Hebr']] * len(src), beam_size=4, max_batch_size=32)
    return [tok.decode([tok.token_to_id(x) for x in r.hypotheses[0][1:]]) for r in res]


def translate(lines, src_lang, ctx, stats):
    if src_lang in ('he', 'iw'):
        return lines
    if ctx.get('gemini_key') and not stats.get('gemini_off'):
        try:
            res = gemini_translate(lines, src_lang, ctx['gemini_key'], ctx)
            stats['engine'] = 'gemini'
            return res
        except Exception as e:
            log('gemini -> local fallback:', e)
            if 'quota' in str(e) or 'key' in str(e):
                stats['gemini_off'] = True
    try:
        stats['engine'] = 'nllb-local'
        return local_translate(lines, src_lang)
    except Exception as e:
        log('local translate failed -> google:', e)
        stats['engine'] = 'google'
        return google_translate(lines, src_lang)


# ------------------------------------------------------------------ srt
def ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return '%02d:%02d:%02d,%03d' % (h, m, s, ms)


def wrap(text, width=42):
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= width:
        return text
    mid = len(text) // 2
    cut = min((i for i in range(len(text)) if text[i] == ' '), key=lambda i: abs(i - mid), default=mid)
    return text[:cut].strip() + '\n' + text[cut:].strip()


RTL = '‫'   # right-to-left embedding keeps punctuation on the correct side


def to_srt(cues):
    out = []
    for i, c in enumerate(sorted(cues, key=lambda c: c['start']), 1):
        body = '\n'.join(RTL + l for l in wrap(c['he']).split('\n'))
        out.append('%d\n%s --> %s\n%s\n' % (i, ts(c['start']), ts(c['end']), body))
    return '\n'.join(out)


# ------------------------------------------------------------------ jobs
JOBS = {}


def job_key(j):
    if j.get('tmdb') and int(j.get('episode') or 0) > 0:
        return 'tmdb%s_s%se%s' % (j['tmdb'], j.get('season'), j.get('episode'))
    if j.get('tmdb'):
        return 'tmdb%s' % j['tmdb']
    base = re.sub(r'[?#].*$', '', j['url'])     # debrid links carry changing tokens
    return 'u' + hashlib.md5(base.encode()).hexdigest()[:16]


class Job:
    def __init__(self, spec):
        self.spec = spec
        self.id = job_key(spec)
        self.state, self.stage, self.progress, self.error = 'queued', 'queued', 0, ''
        self.cues, self.ready_until, self.stats = [], 0.0, {}
        self.cache_file = os.path.join(CACHE, self.id + '.json')

    def info(self):
        return {'id': self.id, 'state': self.state, 'stage': self.stage, 'progress': self.progress,
                'ready_until': self.ready_until, 'error': self.error, 'engine': self.stats.get('engine', ''),
                'lang': self.stats.get('lang', '')}

    def srt(self):
        return to_srt(self.cues)

    def run(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, encoding='utf-8') as f:
                    cached = json.load(f)
                self.cues = cached['cues']
                self.state, self.progress, self.ready_until, self.stage = 'done', 100, 1e9, 'cache'
                return
            self.state, self.stage = 'running', 'probe'
            src = self.spec['url']
            total = duration(src) or 3 * 3600
            starts = list(range(0, int(total) + 1, CHUNK))
            pos = float(self.spec.get('position') or 0)
            first = max(0, int(pos // CHUNK))
            order = starts[first:] + starts[:first][::-1]      # from where the viewer is, then backfill
            m = model()
            ctx = {'title': self.spec.get('title', ''), 'gemini_key': self.spec.get('gemini_key', ''), 'prev': []}
            lang = None
            done_chunks = set()
            for n, st in enumerate(order):
                self.stage = 'transcribe %s' % ts(st)[:8]
                audio = audio_chunk(src, st, CHUNK)
                if not len(audio):
                    done_chunks.add(st)
                    continue
                with _gpu_lock:
                    segs, info = m.transcribe(  # noqa
audio, language=lang, beam_size=5, vad_filter=True,
                                              condition_on_previous_text=False)
                    segs = [s for s in segs if s.text.strip()]
                lang = lang or info.language
                self.stats['lang'] = lang
                if segs:
                    self.stage = 'translate %s' % ts(st)[:8]
                    lines = [s.text.strip() for s in segs]
                    he = translate(lines, lang, ctx, self.stats)
                    ctx['prev'] = lines[-6:]
                    for s, h in zip(segs, he):
                        self.cues.append({'start': st + s.start, 'end': st + max(s.end, s.start + 0.8),
                                          'src': s.text.strip(), 'he': h})
                done_chunks.add(st)
                c = starts[first]
                while c in done_chunks:
                    c += CHUNK
                self.ready_until = min(c, total)
                self.progress = int(100 * len(done_chunks) / len(starts))
            self.cues.sort(key=lambda c: c['start'])
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({'spec': {k: v for k, v in self.spec.items() if k != 'gemini_key'}, 'lang': lang,
                           'cues': self.cues}, f, ensure_ascii=False)
            self.state, self.stage, self.progress, self.ready_until = 'done', 'done', 100, 1e9
        except Exception as e:
            traceback.print_exc()
            self.state, self.error = 'error', str(e)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False).encode() if ctype == 'application/json' else body.encode('utf-8'))
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.strip('/').split('/')
        if p == ['health']:
            return self._send(200, {'ok': True, 'device': _device, 'model': MODEL_NAME.split('/')[-1],
                                    'jobs': len(JOBS)})
        if len(p) >= 2 and p[0] == 'jobs' and p[1] in JOBS:
            j = JOBS[p[1]]
            if len(p) == 3 and p[2] == 'srt':
                return self._send(200, j.srt(), 'application/x-subrip')
            return self._send(200, j.info())
        self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path.strip('/') != 'jobs':
            return self._send(404, {'error': 'not found'})
        spec = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if not spec.get('url'):
            return self._send(400, {'error': 'url required'})
        jid = job_key(spec)
        if jid not in JOBS or JOBS[jid].state == 'error':
            JOBS[jid] = Job(spec)
            threading.Thread(target=JOBS[jid].run, daemon=True).start()
            log('job', jid, spec.get('title'), 'S%sE%s' % (spec.get('season'), spec.get('episode')))
        self._send(200, JOBS[jid].info())


DISCOVERY_PORT = 8766


def discovery_responder(http_port):
    """Answer 'NOVASUBS?' broadcasts from Kodi boxes on the LAN with our HTTP port."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', DISCOVERY_PORT))
    while True:
        data, addr = s.recvfrom(64)
        if data.strip() == b'NOVASUBS?':
            s.sendto(b'NOVASUBS %d' % http_port, addr)


def serve(port):
    threading.Thread(target=model, daemon=True).start()     # warm up the model
    threading.Thread(target=discovery_responder, args=(port,), daemon=True).start()
    log('NovaTV subtitle server on port %d' % port)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


def batch(items, title, gemini_key, out_dir):
    for i, src in enumerate(items, 1):
        m = re.search(r'[sS](\d+)[eE](\d+)', os.path.basename(src))
        spec = {'url': src, 'title': title, 'gemini_key': gemini_key}
        if m:
            spec.update(season=int(m.group(1)), episode=int(m.group(2)))
        j = Job(spec)
        j.id = 'file_' + hashlib.md5(os.path.abspath(src).encode()).hexdigest()[:16] if os.path.exists(src) else j.id
        j.cache_file = os.path.join(CACHE, j.id + '.json')
        t = time.time()
        log('[%d/%d] %s' % (i, len(items), src))
        th = threading.Thread(target=j.run)
        th.start()
        while th.is_alive():
            th.join(15)
            log('   %3d%% %s' % (j.progress, j.stage))
        if j.state != 'done':
            log('   FAILED:', j.error)
            continue
        target = os.path.join(out_dir or os.path.dirname(os.path.abspath(src)) if os.path.exists(src) else (out_dir or HERE),
                              os.path.splitext(os.path.basename(src.split('?')[0]))[0] + '.he.srt')
        with open(target, 'w', encoding='utf-8-sig') as f:
            f.write(j.srt())
        log('   -> %s (%d lines, %s, %.0fs)' % (target, len(j.cues), j.stats.get('engine', '-'), time.time() - t))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('serve'); s.add_argument('--port', type=int, default=8765)
    b = sub.add_parser('batch'); b.add_argument('items', nargs='+'); b.add_argument('--title', default='')
    b.add_argument('--out', default=''); b.add_argument('--gemini-key', default=os.environ.get('GEMINI_API_KEY', ''))
    a = ap.parse_args()
    if a.cmd == 'serve':
        serve(a.port)
    else:
        items = []
        for it in a.items:
            items.extend(sorted(glob.glob(it)) if any(ch in it for ch in '*?') else [it])
        key = a.gemini_key
        kf = os.path.join(HERE, '..', 'gemini.key')
        if not key and os.path.exists(kf):
            key = open(kf).read().strip()
        batch(items, a.title, key, a.out)
