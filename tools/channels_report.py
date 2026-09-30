# -*- coding: utf-8 -*-
"""reports/channels_report.md from work/streams.json (tools/stream_check.py) + the free guides (resources/lib/epg.py):
channel, status, source host, number of sources (failover), EPG source, hours of guide ahead, notes.

    python tools/channels_report.py
"""
import datetime
import gzip
import json
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import conftest  # noqa: E402,F401
from resources.lib import epg, livefail  # noqa: E402

CACHE = os.path.join(ROOT, 'work', 'epg_cache')


def guide(code):
    import requests
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, code + '.xml')
    if not os.path.exists(p) or os.path.getmtime(p) < datetime.datetime.now().timestamp() - 12 * 3600:
        print('downloading guide', code, flush=True)
        raw = requests.get(epg.BASE % code, timeout=120).content
        open(p, 'wb').write(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
    return open(p, encoding='utf-8', errors='ignore').read()


def hours_ahead(text, gid, now):
    ends = re.findall(r'<programme[^>]*stop="(\d{14}) ([+-]\d{4})"[^>]*channel="%s"' % re.escape(gid), text)
    best = None
    for t, off in ends:
        dt = datetime.datetime.strptime(t, '%Y%m%d%H%M%S')
        sign = 1 if off[0] == '+' else -1
        dt -= sign * datetime.timedelta(hours=int(off[1:3]), minutes=int(off[3:]))
        best = dt if best is None or dt > best else best
    return max(0, int((best - now).total_seconds() // 3600)) if best else 0


def main():
    res = json.load(open(os.path.join(ROOT, 'work', 'streams.json'), encoding='utf-8'))
    now = datetime.datetime.utcnow()
    rows, guides = [], {}
    by_cc = {}
    for key, r in res.items():
        by_cc.setdefault(r['cc'], []).append((key, r))
    for cc, items in sorted(by_cc.items(), key=lambda kv: (kv[0] != 'IL', kv[0] != 'IL-radio', kv[0])):
        files = epg.FILES.get(cc, [])
        texts = []
        for f in files:
            try:
                texts.append((f, guide(f)))
            except Exception as e:
                print('guide %s: %s' % (f, e))
        for key, r in sorted(items, key=lambda kv: kv[1]['name'].lower()):
            url = key.split(':', 1)[1]
            host = urlparse(url.split('|')[0]).netloc
            name = r['name']
            lf = livefail.key_for(name)
            restream = livefail.is_restream(url)
            if lf:
                status, sources, note = 'OK (licensed failover)', len(livefail.candidates(lf)), 'official stream / Idan+'
            elif restream:
                status, sources, note = 'REMOVED', 0, 'unlicensed restream (%s)' % host
            else:
                status = ('OK' if r.get('stable', r['ok']) else 'UNSTABLE') if r['ok'] else 'DEAD'
                sources, note = 1, r.get('error', '')
            if r['kind'] == 'deep' and r['ok']:
                note = 'start %ss, %s kbps, max lag %ss' % (r.get('start'), r.get('kbps') or '?', r.get('max_lag'))
            src, hrs = '-', 0
            for f, text in texts:
                m = epg.match([name], epg.channels_of(text))
                if m:
                    src, hrs = 'epgshare01 %s (%s)' % (f, m[name]), hours_ahead(text, m[name], now)
                    break
            if cc == 'IL-radio':
                src = 'n/a (radio)'
            rows.append((cc, name, status, host, sources, src, hrs, note, r['kind']))
    os.makedirs(os.path.join(ROOT, 'reports'), exist_ok=True)
    tv = [x for x in rows if x[0] != 'IL-radio']
    ok = sum(1 for x in rows if x[2].startswith('OK'))
    epg_n = sum(1 for x in tv if x[6] > 0)
    out = ['# Channels report – %s UTC' % now.strftime('%Y-%m-%d %H:%M'), '',
           'Checked: %d (TV %d, radio %d). Playing: %d. With a guide: %d of %d TV channels.' %
           (len(rows), len(tv), len(rows) - len(tv), ok, epg_n, len(tv)),
           'Deep = 60 s real playback; quick = opens within 12 s. Status REMOVED = unlicensed restream, not offered.', '',
           '| Country | Channel | Status | Source | Sources | EPG | EPG hours ahead | Check | Notes |', '|---|---|---|---|---|---|---|---|---|']
    for cc, name, status, host, n, src, hrs, note, kind in rows:
        out.append('| %s | %s | %s | %s | %d | %s | %s | %s | %s |' % (cc, name.replace('|', '/'), status, host, n, src,
                                                                     hrs or '-', kind, (note or '').replace('|', '/')[:80]))
    open(os.path.join(ROOT, 'reports', 'channels_report.md'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(out[2])


if __name__ == '__main__':
    main()
