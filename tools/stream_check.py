# -*- coding: utf-8 -*-
"""Phase 3 stream checker: every TV channel and radio station the TV & Radio menus show.

Depth (owner decision 30/09): DEEP = Israeli channels + the first 10 channels of every country (the order the
country screen shows) + Israeli radio: 60 s of real playback through ffmpeg (start time, sustained bitrate, stalls
= media time falling behind wall time, HTTP errors, redirects). QUICK = every other channel: ffprobe opens the
stream within 12 s. Results -> work/streams.json (resumable: finished URLs are skipped) and
reports/channels_report.md; dead URLs -> resources/dead_streams.json is left to fallback.py.

    python tools/stream_check.py --m3u <nova_channels.m3u> [--deep-only] [--workers 24] [--deep-workers 12] [--limit N]
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import conftest  # noqa: E402,F401  (Kodi stubs so the add-on's own parser/country logic is used)
from resources.lib import iptv  # noqa: E402

OUT = os.path.join(ROOT, 'work', 'streams.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
RADIO_API = 'https://de1.api.radio-browser.info/json/stations/bycountrycodeexact/IL'
LOCK = threading.Lock()


def split_url(u):
    """'url|User-Agent=x&Referer=y' (Kodi header syntax) -> (url, {headers})"""
    if '|' not in u:
        return u, {}
    from urllib.parse import unquote
    base, h = u.split('|', 1)
    return base, {k: unquote(v) for k, v in (kv.split('=', 1) for kv in h.split('&') if '=' in kv)}


def ff_headers(h):
    args = ['-user_agent', h.get('User-Agent', UA)]
    extra = ''.join('%s: %s\r\n' % (k, v) for k, v in h.items() if k != 'User-Agent')
    return args + (['-headers', extra] if extra else [])


def quick(url):
    base, h = split_url(url)
    t = time.time()
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-rw_timeout', '10000000'] + ff_headers(h) +
                           ['-show_entries', 'format=bit_rate:stream=codec_type,width,height', '-of', 'json', base],
                           capture_output=True, timeout=15, text=True, errors='replace')
        ok = r.returncode == 0 and '"codec_type"' in r.stdout
        info = json.loads(r.stdout or '{}') if ok else {}
        v = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
        return {'ok': ok, 'start': round(time.time() - t, 1), 'height': v[0].get('height') if v else None,
                'error': '' if ok else _err(r.stderr)}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'start': None, 'error': 'timeout'}


def variant(base, h):
    """HLS master playlist -> the one variant a player picks (highest bandwidth up to 1080p); ffmpeg on the master
    downloads every variant at once and looks falsely slow. Also returns the redirect count."""
    import requests
    from urllib.parse import urljoin
    try:
        r = requests.get(base, headers={'User-Agent': h.get('User-Agent', UA), **{k: v for k, v in h.items() if k != 'User-Agent'}},
                         timeout=10)
    except Exception:
        return base, 0
    hops = len(r.history)
    if r.status_code != 200 or '#EXT-X-STREAM-INF' not in r.text:
        return (r.url if r.status_code == 200 else base), hops
    best, lines = None, r.text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('#EXT-X-STREAM-INF'):
            bw = int((re.search(r'BANDWIDTH=(\d+)', line) or [0, 0])[1])
            height = int((re.search(r'RESOLUTION=\d+x(\d+)', line) or [0, 0])[1])
            uri = next((x.strip() for x in lines[i + 1:i + 3] if x.strip() and not x.startswith('#')), '')
            if uri and height <= 1080 and (best is None or bw > best[0]):
                best = (bw, urljoin(r.url, uri))
    return (best[1] if best else r.url), hops


def deep(url, seconds=60):
    """play for `seconds`: start delay, average kbps, worst lag of media time behind wall time (stalls)"""
    base, h = split_url(url)
    hops = 0
    if '.m3u8' in base.lower():
        base, hops = variant(base, h)
    cmd = (['ffmpeg', '-hide_banner', '-nostats', '-loglevel', 'error', '-rw_timeout', '10000000'] + ff_headers(h) +
           ['-i', base, '-t', str(seconds), '-map', '0:v:0?', '-map', '0:a:0?', '-c', 'copy', '-f', 'null', '-',
            '-progress', 'pipe:1'])
    t0 = time.time()
    first = None
    media = size = 0
    lag = 0.0
    err = ''
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors='replace')
        dog = threading.Timer(seconds + 45, p.kill)        # a silent hang (no progress lines at all) ends too
        dog.daemon = True
        dog.start()
        for line in p.stdout:
            k, _, v = line.strip().partition('=')
            if k == 'out_time_us' and v.isdigit():
                media = int(v) / 1e6
                if media > 0 and first is None:
                    first = time.time() - t0
                if first is not None:
                    lag = max(lag, (time.time() - t0 - first) - media)
            elif k == 'total_size' and v.isdigit():
                size = int(v)
            elif k == 'bitrate' and v.endswith('kbits/s'):
                try:
                    size = max(size, int(float(v[:-7]) * 1000 / 8 * max(media, 1)))
                except ValueError:
                    pass
            if time.time() - t0 > seconds + 45:
                p.kill()
                err = 'too slow (media time far behind)'
                break
        p.wait(timeout=10)
        dog.cancel()
        if p.returncode != 0 and not err:
            err = 'no data (killed after %d s)' % (seconds + 45) if time.time() - t0 >= seconds + 44 else                 _err(subprocess.run(['ffprobe', '-v', 'error', '-rw_timeout', '8000000'] + ff_headers(h) + [base],
                                    capture_output=True, text=True, errors='replace', timeout=20).stderr)
    except Exception as e:
        err = str(e)[:120]
    played = media
    ok = first is not None and played >= seconds * 0.9 and lag < 8
    return {'ok': ok, 'start': round(first, 1) if first else None, 'played': round(played, 1), 'redirects': hops,
            'kbps': int(size * 8 / 1000 / played) if played else 0, 'max_lag': round(lag, 1),
            'stable': ok and lag < 3, 'error': err if not ok else ''}


def _err(text):
    text = (text or '').strip().splitlines()
    for line in text:
        m = re.search(r'(Server returned [^\r\n]+|HTTP error \d+|Connection refused|timed out|Invalid data[^\r\n]*|'
                      r'No such host|Failed to resolve[^\r\n]*|403 Forbidden|404 Not Found)', line)
        if m:
            return m.group(1)[:80]
    return (text[-1] if text else 'failed')[:80]


def channels(m3u):
    """[(key, name, url, country, deep?)] in the order the menus show them"""
    text = open(m3u, encoding='utf-8', errors='replace').read()
    out, per = [], {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('#EXTINF'):
            continue
        url = next((x.strip() for x in lines[i + 1:i + 4] if x.strip() and not x.startswith('#')), '')
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
        name = line.rsplit(',', 1)[1].strip()
        cc = iptv.ALIAS.get(iptv.country(attrs), iptv.country(attrs)) or ''
        israel = cc == 'IL' or attrs.get('group-title', '').startswith('Israel')
        per[cc] = per.get(cc, 0) + 1
        out.append(('tv:' + url, name, url, 'IL' if israel else cc, israel or per[cc] <= 10))
    return out


def radios():
    import requests
    data = requests.get(RADIO_API, params={'hidebroken': 'true', 'order': 'votes', 'reverse': 'true', 'limit': 300},
                        headers={'User-Agent': 'BNStream-check/1.0'}, timeout=30).json()
    seen, out = set(), []
    for s in data:
        name = ' '.join((s.get('name') or '').split())
        u = s.get('url_resolved') or s.get('url')
        if name and u and name.lower() not in seen:
            seen.add(name.lower())
            out.append(('radio:' + u, name, u, 'IL-radio', True))
    return out


def save(res):
    with LOCK:
        tmp = OUT + '.tmp'
        json.dump(res, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        os.replace(tmp, OUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--m3u', required=True)
    ap.add_argument('--deep-only', action='store_true')
    ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--deep-workers', type=int, default=12)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    res = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    items = channels(a.m3u) + radios()
    if a.limit:
        items = items[:a.limit]
    todo_deep = [x for x in items if x[4] and x[0] not in res]
    todo_quick = [] if a.deep_only else [x for x in items if not x[4] and x[0] not in res]
    print('items %d: deep %d, quick %d (already done %d)' % (len(items), len(todo_deep), len(todo_quick), len(res)), flush=True)
    done = [0]

    def run(item, fn, kind):
        key, name, url, cc, _ = item
        try:
            r = fn(url)
        except Exception as e:                 # never lose a result silently (a timeout inside the check)
            r = {'ok': False, 'start': None, 'error': ('check failed: %s' % e)[:80]}
        r.update({'name': name, 'cc': cc, 'kind': kind, 'when': int(time.time())})
        res[key] = r
        done[0] += 1
        if done[0] % 10 == 0 or kind == 'deep':
            save(res)
            print('%d done' % done[0], flush=True)
    with cf.ThreadPoolExecutor(a.deep_workers) as dx, cf.ThreadPoolExecutor(a.workers) as qx:
        fs = [dx.submit(run, x, deep, 'deep') for x in todo_deep] + [qx.submit(run, x, quick, 'quick') for x in todo_quick]
        for f in cf.as_completed(fs):
            f.result()
    save(res)
    ok = sum(1 for r in res.values() if r['ok'])
    print('finished: %d/%d ok' % (ok, len(res)))


if __name__ == '__main__':
    main()
