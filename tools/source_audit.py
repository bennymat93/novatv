"""Deep audit of every NovaTV media source. Stdlib only.
Usage: python tools/source_audit.py [--out report.json]
"""
import concurrent.futures as cf, gzip, json, re, ssl, sys, time, urllib.request, urllib.error

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}  
FREE_M3U = [
    ('iptv-org IL', 'https://iptv-org.github.io/iptv/countries/il.m3u'),
    ('iptv-org Hebrew', 'https://iptv-org.github.io/iptv/languages/heb.m3u'),
    ('iptv-org Russian', 'https://iptv-org.github.io/iptv/languages/rus.m3u'),
    ('iptv-org Movies', 'https://iptv-org.github.io/iptv/categories/movies.m3u'),
    ('iptv-org Kids', 'https://iptv-org.github.io/iptv/categories/kids.m3u'),
    ('iptv-org Documentary', 'https://iptv-org.github.io/iptv/categories/documentary.m3u'),
    ('iptv-org News', 'https://iptv-org.github.io/iptv/categories/news.m3u'),
    ('iptv-org Music', 'https://iptv-org.github.io/iptv/categories/music.m3u'),
    ('iptv-org English', 'https://iptv-org.github.io/iptv/languages/eng.m3u'),
]
LIBS = ['plugin.video.plutotv', 'plugin.video.crackle', 'plugin.video.archive.org',
        'plugin.video.composite_for_plex', 'plugin.video.youtube', 'plugin.video.dailymotion_com',
        'plugin.video.vimeo', 'plugin.video.twitch', 'plugin.video.ted.talks', 'plugin.video.nasa',
        'plugin.video.redbull.tv', 'plugin.video.nhklive', 'plugin.video.arteplussept', 'plugin.video.pbskids']
CTX = ssl.create_default_context()


def get(url, n=None, timeout=10, headers=None):
    h = dict(UA, **(headers or {}))
    if n:
        h['Range'] = 'bytes=0-%d' % n
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout, context=CTX)
    return r.status, r.headers.get('Content-Type', ''), (r.read(n + 1) if n else r.read()), r.geturl()


def parse_m3u(text):
    out, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF'):
            m = re.match(r'(#EXTINF[^"]*(?:"[^"]*"[^"]*?)*?),([^"]*)$', line)
            cur = {'name': (m.group(2) if m else line.rsplit(',', 1)[-1]).strip(),
                   'group': (re.search(r'group-title="([^"]*)"', line) or [None, ''])[1]}
        elif line and not line.startswith('#') and cur:
            cur['url'] = line; out.append(cur); cur = None
    return out


def probe_stream(url):
    t = time.time()
    try:
        st, ct, body, final = get(url, 4096, timeout=10)
        dt = round(time.time() - t, 2)
        txt = body[:4096].decode('utf-8', 'ignore')
        if '#EXTM3U' in txt:
            # follow first variant / segment to confirm playable
            lines = [l for l in txt.splitlines() if l and not l.startswith('#')]
            if lines:
                sub = urllib.request.urljoin(final, lines[0])
                try:
                    get(sub, 2048, timeout=10)
                    return 'OK', 'HLS playlist + segment reachable', dt
                except Exception as e:
                    return 'PARTIAL', 'playlist OK, segment failed: %s' % str(e)[:60], dt
            return 'PARTIAL', 'empty HLS playlist', dt
        if any(k in ct for k in ('video', 'mpegurl', 'octet', 'audio', 'mp2t', 'dash')) or body[:1] == b'G':
            return 'OK', ct or 'binary stream', dt
        if 'html' in ct:
            return 'FAIL', 'returned HTML page (geo-block / dead)', dt
        return 'PARTIAL', 'unknown content-type %s' % ct, dt
    except urllib.error.HTTPError as e:
        return 'FAIL', 'HTTP %s' % e.code, round(time.time() - t, 2)
    except Exception as e:
        m = str(e)
        if any(k in m for k in ('timed out', '502', 'Errno 97', 'Errno 104', 'TLSV1_ALERT')) or isinstance(e, TimeoutError):
            return 'UNVERIFIED', 'no route from test server (geo-lock/IPv6/timeout) - test on the TV box', round(time.time() - t, 2)
        return 'FAIL', type(e).__name__ + ': ' + m[:60], round(time.time() - t, 2)


def main():
    rep = {'time': time.strftime('%Y-%m-%d %H:%M'), 'sections': {}}
    # 1. IPTV
    chans, lists = [], []
    for name, u in FREE_M3U:
        try:
            _, _, b, _ = get(u, timeout=20)
            c = parse_m3u(b.decode('utf-8', 'ignore'))
            for x in c: x['list'] = name
            chans += c; lists.append({'name': name, 'url': u, 'status': 'OK', 'channels': len(c)})
        except Exception as e:
            lists.append({'name': name, 'url': u, 'status': 'FAIL', 'detail': str(e)})
    seen, uniq = set(), []
    for c in chans:
        if c['url'] not in seen:
            seen.add(c['url']); uniq.append(c)
    with cf.ThreadPoolExecutor(96) as ex:
        for c, r in zip(uniq, ex.map(lambda c: probe_stream(c['url']), uniq)):
            c['status'], c['detail'], c['secs'] = r
    rep['sections']['iptv_lists'] = lists
    rep['sections']['iptv_channels'] = uniq
    # 2. Radio
    radio = []
    for label, path in [('Israel', 'stations/bycountrycodeexact/IL'), ('Russia', 'stations/bycountrycodeexact/RU'),
                        ('Hebrew', 'stations/bylanguageexact/hebrew'), ('Top world', 'stations/topclick/40')]:
        try:
            _, _, b, _ = get('https://all.api.radio-browser.info/json/%s?hidebroken=true&limit=40&order=clickcount&reverse=true' % path, timeout=20)
            for s in json.loads(b):
                radio.append({'name': s['name'].strip(), 'group': label, 'url': s.get('url_resolved') or s['url']})
        except Exception as e:
            radio.append({'name': 'radio-browser API ' + label, 'group': label, 'url': path, 'status': 'FAIL', 'detail': str(e)})
    todo = [r for r in radio if 'status' not in r]
    with cf.ThreadPoolExecutor(96) as ex:
        for s, r in zip(todo, ex.map(lambda s: probe_stream(s['url']), todo)):
            s['status'], s['detail'], s['secs'] = r
    rep['sections']['radio'] = radio
    # 3. Official Kodi libraries (Omega repo)
    libs = []
    try:
        _, _, b, _ = get('https://mirrors.kodi.tv/addons/omega/addons.xml.gz', timeout=30)
        xml = gzip.decompress(b).decode('utf-8', 'ignore')
        for a in LIBS:
            m = re.search(r'<addon id="%s"[^>]*version="([^"]+)"' % re.escape(a), xml)
            libs.append({'name': a, 'status': 'OK' if m else 'FAIL',
                         'detail': 'v%s in Omega repo' % m[1] if m else 'NOT in Kodi 21 repo - install will fail'})
    except Exception as e:
        libs.append({'name': 'Kodi Omega repo', 'status': 'FAIL', 'detail': str(e)})
    rep['sections']['libraries'] = libs
    # 4. Service APIs (no credentials -> reachability only)
    apis = []
    for name, u, ok in [('TMDB (metadata)', 'https://api.themoviedb.org/3/configuration', (200, 401)),
                        ('Real-Debrid (movies/series streams)', 'https://api.real-debrid.com/rest/1.0/time', (200, 206)),
                        ('Trakt', 'https://api.trakt.tv/', (200, 403, 404, 412)),
                        ('Gemini (subtitle translation)', 'https://generativelanguage.googleapis.com/v1beta/models', (200, 400, 403)),
                        ('NovaTV repo (GitHub Pages)', 'https://bennymat93.github.io/novatv/', (200, 206)),
                        ('POV add-on base (Kodi-POV-IL)', 'https://raw.githubusercontent.com/kodifitzwell/repo/master/README.md', (200, 206, 404))]:
        try:
            st = get(u, 512, timeout=15)[0]
        except urllib.error.HTTPError as e:
            st = e.code
        except Exception as e:
            st = str(e)[:50]
        apis.append({'name': name, 'status': 'OK' if st in ok else 'FAIL', 'detail': 'HTTP %s (endpoint up; needs your key)' % st if st in ok else st})
    rep['sections']['apis'] = apis
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'source_audit.json'
    if '--dead' in sys.argv:   # refresh the add-on's dead-stream filter (confirmed failures only)
        json.dump(sorted(c['url'] for c in uniq if c['detail'] in ('HTTP 404', 'HTTP 410')),
                  open(sys.argv[sys.argv.index('--dead') + 1], 'w'), indent=0)
    json.dump(rep, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in rep['sections'].items():
        c = {}
        for x in v: c[x.get('status')] = c.get(x.get('status'), 0) + 1
        print(k, c)


if __name__ == '__main__':
    main()
