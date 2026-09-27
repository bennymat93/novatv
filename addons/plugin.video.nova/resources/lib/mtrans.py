# -*- coding: utf-8 -*-
"""Machine translation without AI, for subtitles that must always exist.

Several free engines, best first; every batch is checked (same number of lines, the target script present) and a
batch an engine fails on goes to the next one, so one blocked or rate-limited service never stops the result:
  1. Google (dict-chrome-ex endpoint)  - batches of lines in one request, the best quality of the free services
  2. Google (gtx endpoint)             - same quality, another endpoint (answers "Sorry" when it throttles an IP)
  3. MyMemory                          - line by line, slower, daily quota
The last resort keeps the source line: a subtitle in the original language is better than none.

Standard library + requests only: used by NovaTV on the box AND by the PC subtitle server.
"""
import re
import time

try:
    import requests
except ImportError:          # the server imports this file with its own interpreter
    requests = None

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
HEB = re.compile(r'[֐-׿]')
MAX_CHARS = 3500             # per request
MAX_LINES = 60


def _ok(src, out, dst):
    if not isinstance(out, list) or len(out) != len(src):
        return False
    if dst in ('iw', 'he'):
        texty = [o for s, o in zip(src, out) if re.search(r'[A-Za-zЀ-ӿ]{3}', s)]
        return not texty or sum(1 for o in texty if HEB.search(o or '')) >= max(1, len(texty) * 0.6)
    return True


def google_dict(lines, src, dst):
    r = requests.post('https://clients5.google.com/translate_a/t',
                      params={'client': 'dict-chrome-ex', 'sl': src or 'auto', 'tl': dst},
                      data=[('q', l) for l in lines], headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for item in r.json():
        out.append(item[0] if isinstance(item, list) else item)
    return out


def google_gtx(lines, src, dst):
    out = []
    for l in lines:                                      # gtx has no batch form: one line per call
        r = requests.get('https://translate.googleapis.com/translate_a/single',
                         params={'client': 'gtx', 'sl': src or 'auto', 'tl': dst, 'dt': 't', 'q': l},
                         headers=UA, timeout=15)
        r.raise_for_status()
        if r.text.lstrip().startswith('<'):
            raise RuntimeError('google gtx: throttled')
        out.append(''.join(part[0] for part in r.json()[0] if part and part[0]))
    return out


def mymemory(lines, src, dst):
    out = []
    pair = '%s|%s' % ((src if src and src != 'auto' else 'en'), 'he' if dst == 'iw' else dst)
    for l in lines:
        r = requests.get('https://api.mymemory.translated.net/get', params={'q': l[:480], 'langpair': pair},
                         headers=UA, timeout=15)
        r.raise_for_status()
        j = r.json()
        if j.get('quotaFinished'):
            raise RuntimeError('mymemory: daily quota')
        out.append(j['responseData']['translatedText'])
        time.sleep(0.2)
    return out


ENGINES = [('google', google_dict), ('google-gtx', google_gtx), ('mymemory', mymemory)]


def _batches(lines):
    b, n = [], 0
    for l in lines:
        if b and (n + len(l) > MAX_CHARS or len(b) >= MAX_LINES):
            yield b
            b, n = [], 0
        b.append(l)
        n += len(l) + 1
    if b:
        yield b


def translate(lines, src='auto', dst='iw', stats=None, deadline=None):
    """lines -> translated lines (same length). stats counts which engine did how many lines."""
    if requests is None:
        raise RuntimeError('requests is not available')
    out, dead = [], set()
    for batch in _batches([l.replace('\n', ' ').strip() for l in lines]):
        res = None
        for name, fn in ENGINES:
            if name in dead or (deadline and time.time() > deadline and name != 'google'):
                continue
            try:
                r = fn(batch, src, dst)
                if _ok(batch, r, dst):
                    res = r
                    if stats is not None:
                        stats[name] = stats.get(name, 0) + len(batch)
                    break
            except Exception:
                dead.add(name)                           # blocked / quota: skip it for the rest of this job
        if res is None:                                  # every engine failed: the original is better than nothing
            res = batch
            if stats is not None:
                stats['untranslated'] = stats.get('untranslated', 0) + len(batch)
        out.extend(res)
    return out


# ------------------------------------------------------------------ subtitle text helpers
TS = re.compile(r'(\d+):(\d\d):(\d\d)[,.](\d{1,3})')


def _sec(t):
    h, m, s, ms = TS.match(t).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, '0')) / 1000.0


def parse_srt(text):
    """SRT or WebVTT -> [{'start','end','text'}]"""
    cues = []
    for block in re.split(r'\n\s*\n', text.replace('\r', '').replace('﻿', '')):
        lines = [l for l in block.split('\n') if l.strip()]
        for i, l in enumerate(lines):
            if '-->' in l:
                a, b = [x.strip().split(' ')[0] for x in l.split('-->')]
                if TS.match(a if a.count(':') == 2 else '00:' + a) and TS.match(b if b.count(':') == 2 else '00:' + b):
                    txt = re.sub(r'<[^>]+>|\{[^}]+\}', '', ' '.join(lines[i + 1:])).strip()
                    if txt:
                        cues.append({'start': _sec(a if a.count(':') == 2 else '00:' + a),
                                     'end': _sec(b if b.count(':') == 2 else '00:' + b), 'text': txt})
                break
    return cues


def unroll(cues):
    """YouTube's automatic captions 'roll': every cue repeats the previous one and adds words, with 10 ms cues in
    between. Keep each sentence once: drop flash cues, merge a cue into the next one that continues it, and
    split the text to at most two lines of ~42 characters."""
    out = []
    for c in cues:
        if c['end'] - c['start'] < 0.2:
            continue
        t = c['text']
        if out:
            prev = out[-1]
            if t.startswith(prev['text']) or prev['text'] in t:
                prev['text'], prev['end'] = t, max(prev['end'], c['end'])
                continue
            words = prev['text'].split()
            for k in range(min(len(words), 12), 0, -1):          # the new cue starts with the old cue's tail
                tail = ' '.join(words[-k:])
                if t.startswith(tail + ' ') or t == tail:
                    t = t[len(tail):].strip()
                    break
            if not t:
                prev['end'] = max(prev['end'], c['end'])
                continue
        out.append({'start': c['start'], 'end': c['end'], 'text': t})
    for a, b in zip(out, out[1:]):                             # no overlap after merging
        a['end'] = min(a['end'], b['start'])
    return [c for c in out if c['end'] - c['start'] >= 0.3]


def ts(sec):
    ms = int(round(sec * 1000))
    return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def to_srt(cues, key='he'):
    out = []
    for n, c in enumerate(cues, 1):
        t = c.get(key) or c.get('text') or ''
        if HEB.search(t):
            t = '\n'.join('‫' + x for x in t.split('\n'))        # right-to-left on every player
        out.append('%d\n%s --> %s\n%s\n' % (n, ts(c['start']), ts(c['end']), t))
    return '\n'.join(out)


def translate_cues(cues, src='auto', stats=None, deadline=None):
    he = translate([c['text'] for c in cues], src, 'iw', stats, deadline)
    return [dict(c, he=h) for c, h in zip(cues, he)]
