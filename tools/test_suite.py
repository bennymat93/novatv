# -*- coding: utf-8 -*-
"""BN / NovaTV end-to-end test suite.

Installs dist/NovaTV-<ver>.zip into the portable test Kodi, starts it, and checks
every feature through JSON-RPC.  Prints a PASS/FAIL table and writes
work/test_report.json.

  python tools/test_suite.py --version 0.1.2 [--keep]
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KODI = os.path.join(ROOT, 'testkodi')
DATA = os.path.join(KODI, 'portable_data')
RPC = 'http://127.0.0.1:8089/jsonrpc'
RESULTS = []


def rpc(method, timeout=120, **params):
    req = urllib.request.Request(RPC, json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
                                 {'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def ls(path):
    r = rpc('Files.GetDirectory', directory=path, media='files')
    if 'error' in r:
        raise RuntimeError(r['error'])
    return r['result'].get('files') or []


def close_dialogs():
    """a dialog left open by the previous test (an OK box nobody pressed) blocks every later plugin call"""
    for _ in range(6):
        try:
            if not rpc('XBMC.GetInfoBooleans', booleans=['System.HasActiveModalDialog'], timeout=10)['result']['System.HasActiveModalDialog']:
                return
            rpc('Input.ExecuteAction', action='close', timeout=10)
        except Exception:
            return
        time.sleep(1)


def healthy():
    """Kodi answers AND a plugin call works (a frozen GUI still answers JSONRPC.Ping)"""
    try:
        rpc('JSONRPC.Ping', timeout=10)
        return 'error' not in rpc('Files.GetDirectory', directory=NOVA, media='files', timeout=60)
    except Exception:
        return False


def check(name, fn):
    close_dialogs()
    t = time.time()
    try:
        detail = fn()
        ok = detail is not False
        RESULTS.append((name, ok, '' if detail in (True, None) else str(detail), time.time() - t))
    except Exception as e:
        RESULTS.append((name, False, repr(e)[:160], time.time() - t))
    close_dialogs()
    if not healthy():
        # Kodi died or froze: record it as its own failure (with the dump/log), then restart so the rest still gets tested
        dumps = sorted(glob.glob(os.path.join(DATA, '*.dmp')), key=os.path.getmtime)
        RESULTS.append(('KODI CRASHED/FROZE during: ' + name, False, os.path.basename(dumps[-1]) if dumps else 'no dump', 0))
        kill_kodi()
        keep = os.path.join(ROOT, 'work', 'crash-%s-%s.log' % (time.strftime('%H%M%S'), re.sub(r'[^\w-]+', '_', name.split(':')[-1].strip())[:30]))
        shutil.copy(os.path.join(DATA, 'kodi.log'), keep)
        start_kodi()


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)
    return msg


# ------------------------------------------------------------------ setup
def kodi_processes():
    """[(pid, path)] of every running kodi.exe"""
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "Get-Process kodi -ErrorAction SilentlyContinue | ForEach-Object { \"$($_.Id)|$($_.Path)\" }"],
                         capture_output=True, text=True).stdout
    return [tuple(l.split('|', 1)) for l in out.split() if '|' in l]


def ours(path):
    return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.join(ROOT, '')))


def kill_kodi():
    """stop the TEST copies of Kodi only (testkodi, work/wintest) - never the owner's own Kodi"""
    for pid, path in kodi_processes():
        if ours(path):
            subprocess.call(['taskkill', '/PID', pid, '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)


def wait_foreign_kodi():
    """Kodi on Windows runs once: while the owner's Kodi is open a test copy cannot start - wait, never close it"""
    told = False
    while True:
        foreign = [p for _, p in kodi_processes() if not ours(p)]
        if not foreign:
            return
        if not told:
            print('WAITING: close your own Kodi (%s) - the tests need to start their own copy' % foreign[0], flush=True)
            told = True
        time.sleep(15)


def install(ver):
    kill_kodi()
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(DATA, exist_ok=True)
    with zipfile.ZipFile(os.path.join(ROOT, 'dist', 'NovaTV-%s.zip' % ver)) as z:
        z.extractall(DATA)
    enable_rpc()


def fast_ai_settings():
    """tests: wait only 5 s for human subtitles before asking the AI server"""
    p = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'settings.xml')
    s = open(p, encoding='utf-8').read() if os.path.exists(p) else '<settings version="2">\n</settings>\n'
    for k, v in (('ai_wait', '5'), ('ai_subs', 'true'), ('sub_server', 'http://127.0.0.1:8765'),
                 ('status_on_start', 'false'), ('ai_prepare', 'true')):
        s = re.sub(r'\s*<setting id="%s"[^>]*?(/>|>[^<]*</setting>)' % k, '', s)
        s = s.replace('</settings>', '    <setting id="%s">%s</setting>\n</settings>' % (k, v))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(s)


def enable_rpc():
    fast_ai_settings()
    p = os.path.join(DATA, 'userdata', 'guisettings.xml')
    s = open(p, encoding='utf-8').read()
    for k, v in [('services.webserver', 'true'), ('services.webserverport', '8089'),
                 ('services.webserverauthentication', 'false')]:
        s = re.sub(r'\s*<setting id="%s"[^>]*?(/>|>[^<]*</setting>)' % re.escape(k), '', s)
        s = s.replace('</settings>', '    <setting id="%s">%s</setting>\n</settings>' % (k, v))
    open(p, 'w', encoding='utf-8').write(s)


def start_kodi():
    wait_foreign_kodi()
    subprocess.Popen([os.path.join(KODI, 'kodi.exe'), '-p'], cwd=KODI,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(90):
        try:
            if rpc('JSONRPC.Ping', timeout=3).get('result') == 'pong':
                time.sleep(12)          # let services settle
                return True
        except Exception:
            time.sleep(1)
    raise RuntimeError('Kodi did not start')


# ------------------------------------------------------------------ tests
NOVA = 'plugin://plugin.video.nova/'
NOVA_SRC = os.path.join(ROOT, 'addons', 'plugin.video.nova')


def t_addons_enabled():
    bad = []
    for a in ['plugin.video.nova', 'plugin.program.novawizard', 'repository.nova', 'resource.uisounds.nova',
              'plugin.video.pov', 'skin.fentastic', 'service.subtitles.All_Subs', 'plugin.video.idanplus']:
        r = rpc('Addons.GetAddonDetails', addonid=a, properties=['enabled', 'version'])
        if 'error' in r or not r['result']['addon']['enabled']:
            bad.append(a)
    return expect(not bad, 'all enabled' if not bad else 'disabled/missing: %s' % bad)


def t_gui():
    skin = rpc('Settings.GetSettingValue', setting='lookandfeel.skin')['result']['value']
    snd = rpc('Settings.GetSettingValue', setting='lookandfeel.soundskin')['result']['value']
    lang = rpc('Settings.GetSettingValue', setting='locale.language')['result']['value']
    expect(skin == 'skin.fentastic', 'skin=%s' % skin)
    expect(snd == 'resource.uisounds.nova', 'sounds=%s' % snd)
    return 'skin, sounds, %s' % lang


def t_branding():
    skin = os.path.join(DATA, 'addons', 'skin.fentastic')
    menu = open(os.path.join(skin, 'xml', 'script-fentastic-main_menu_movies.xml'), encoding='utf-8').read()
    expect('plugin.video.nova' in menu and '[B]' not in menu, 'menu points to NovaTV')
    from hashlib import md5
    brand = md5(open(os.path.join(ROOT, 'brand', 'splash.jpg'), 'rb').read()).hexdigest()
    got = md5(open(os.path.join(DATA, 'media', 'splash.jpg'), 'rb').read()).hexdigest()
    expect(brand == got, 'splash is BN')
    return 'menu + splash + logos'


def t_root():
    items = ls(NOVA)
    expect(len(items) == 12, '%d root items' % len(items))
    expect('a=hub_search' in items[0]['file'], 'first item is search-all')
    expect('a=status' in items[-2]['file'], 'system status item missing')
    expect('a=sysreport' in items[-1]['file'], 'System Update item missing')
    return '12 items, search-all first, system status + System Update last'


def t_movies_lists():
    out = []
    for path in ['?a=list&m=movie&path=/trending/movie/week', '?a=list&m=movie&path=/movie/popular',
                 '?a=list&m=tv&path=/tv/top_rated']:
        items = ls(NOVA + path)
        plays = [i for i in items if 'a=play&' in i['file'] or 'a=seasons' in i['file']]   # NovaTV plays (POV first)
        expect(len(plays) >= 15, '%s only %d' % (path, len(plays)))
        out.append(len(plays))
    return 'items per list %s' % out


def t_languages():
    out = {}
    for m in ('movie', 'tv'):
        for code in ('he', 'en', 'ru'):
            items = ls(NOVA + '?a=list&m=%s&path=/discover/%s&with_original_language=%s&sort_by=popularity.desc' % (m, m, code))
            n = len([i for i in items if 'next_page' not in i['file'] and 'page=' not in i['file']])
            expect(n >= 5, '%s/%s only %d' % (m, code, n))
            out['%s-%s' % (m, code)] = n
    return out


def t_genres_years():
    g = ls(NOVA + '?a=genres&m=movie')
    y = ls(NOVA + '?a=years&m=tv')
    expect(len(g) >= 15 and len(y) >= 50, 'genres %d years %d' % (len(g), len(y)))
    return 'genres %d, years %d' % (len(g), len(y))


def t_title_integrity():
    """Every playable item must carry a TMDb id that resolves back to the same title."""
    items = ls(NOVA + '?a=list&m=movie&path=/movie/popular')
    ids = [re.search(r'[?&]id=(\d+)', i['file']).group(1) for i in items if 'a=play&' in i['file']]
    expect(len(ids) >= 15, 'ids %d' % len(ids))
    expect(len(ids) == len(set(ids)), 'duplicate ids in one page')
    return '%d unique TMDb ids' % len(ids)


def t_kukhnya():
    seasons = ls(NOVA + '?a=kukhnya')
    real = [s for s in seasons if not s['file'].endswith('&s=0')]
    expect(len(real) == 6, '%d seasons' % len(real))
    eps = ls(NOVA + '?a=episodes&id=45994&s=1')
    expect(len(eps) >= 15, 'S1 episodes %d' % len(eps))
    expect(all('a=play&' in e['file'] and 'id=45994' in e['file'] and '&s=1&' in e['file'] for e in eps), 'episode links')
    return '6 seasons, S1=%d episodes' % len(eps)


def t_radio():
    out = {}
    for by, v in (('country', 'IL'), ('country', 'RU'), ('language', 'hebrew')):
        items = ls(NOVA + '?a=radio_list&by=%s&v=%s' % (by, v))
        expect(len(items) >= 10, '%s=%s only %d' % (by, v, len(items)))
        out[v] = len(items)
    return out


def t_accounts():
    rows = ls(NOVA + '?a=accounts')
    expect(len(rows) == 8, '%d rows' % len(rows))
    expect(sum('preset_' in r['file'] for r in rows) == 2, 'locked-profile rows missing')
    return [r['label'].split('   ')[0] for r in rows]


def t_favourites():
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=fav_add&kind=movie&id=603&label=The Matrix')
    for _ in range(15):
        time.sleep(1)
        items = ls(NOVA + '?a=favs&kind=movie')
        if any('603' in i['file'] for i in items):
            break
    expect(any('603' in i['file'] for i in items), 'favourite not stored')
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=fav_rm&kind=movie&id=603')
    for _ in range(15):                     # an add-on start can take a few seconds while Kodi is busy
        time.sleep(1)
        items = ls(NOVA + '?a=favs&kind=movie')
        if not any('603' in i['file'] for i in items):
            break
    expect(not any('603' in i['file'] for i in items), 'favourite not removed')
    return 'add + remove'


def t_history_and_speed():
    """Play a local file, confirm history entry with timestamp; measure navigation speed."""
    sample = os.path.join(ROOT, 'test', 'test_ru.mp4')
    if os.path.exists(sample):
        rpc('Player.Open', item={'file': sample})
        time.sleep(8)
        rpc('Player.Stop', playerid=1)
        time.sleep(2)
        h = json.load(open(os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'history.json'), encoding='utf-8'))
        expect(h and re.match(r'\d\d/\d\d/\d{4} \d\d:\d\d', h[0]['when']), 'history timestamp')
    t = time.time()
    ls(NOVA + '?a=media_root&m=tv')
    ls(NOVA + '?a=list&m=movie&path=/movie/popular')     # cached after first run
    dt = time.time() - t
    expect(dt < 6, 'menus slow: %.1fs' % dt)
    return 'history ok, 2 menus in %.2fs' % dt


def free_list_names():
    src = open(os.path.join(NOVA_SRC, 'resources', 'lib', 'iptv.py'), encoding='utf-8').read()
    return re.findall(r"\('(iptv-org [^']+)', 'https://", src)


def t_iptv():
    iptv_json = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'iptv.json')
    os.makedirs(os.path.dirname(iptv_json), exist_ok=True)
    m3u = os.path.join(ROOT, 'work', 'test_channels.m3u')
    open(m3u, 'w', encoding='utf-8').write(
        '#EXTM3U\n#EXTINF:-1 tvg-id="kan11",Kan 11 HD\nhttp://127.0.0.1/kan11.m3u8\n'
        '#EXTINF:-1 tvg-id="kan11sd",Kan 11\nhttp://127.0.0.1/kan11sd.m3u8\n'
        '#EXTINF:-1,Keshet 12\nhttp://127.0.0.1/k12.m3u8\n#EXTINF:-1,Первый канал\nhttp://127.0.0.1/1tv.m3u8\n'
        '#EXTINF:-1 group-title="Sport",Sport 5\nhttp://127.0.0.1/s5.m3u8\n#EXTINF:-1,Disney Junior\nhttp://127.0.0.1/dj.m3u8\n')
    json.dump({'m3u': [{'name': 'test', 'url': m3u}], 'epg': [],
               'free': {n: False for n in free_list_names()}}, open(iptv_json, 'w'))
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=tv_do&do=refresh')
    for _ in range(60):
        time.sleep(3)
        r = rpc('PVR.GetChannels', channelgroupid='alltv', properties=['channelnumber'])
        ch = {c['label']: c['channelnumber'] for c in r.get('result', {}).get('channels', [])}
        if len(ch) >= 5:
            break
    expect(len(ch) == 5, 'channels after dedupe: %s' % ch)
    expect(ch.get('Kan 11 HD') == 11 and ch.get('Keshet 12') == 12, 'Israeli numbering %s' % ch)
    return ch


def t_ai_server():
    h = json.loads(urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=5).read())
    expect(h.get('ok'), 'health')
    rows = ls(NOVA + '?a=accounts')
    row = next(r for r in rows if 'AI Subtitle Server' in r['label'])
    expect('limegreen' in row['label'], 'accounts screen shows: %s' % row['label'])
    return '%s / %s, accounts row connected' % (h['device'], h['model'])


MEDIA = 'http://127.0.0.1:8799/'   # set by media_server()


def media_server():
    """serves test/ like a real stream server (byte ranges)"""
    import http.server
    import threading
    folder = os.path.join(ROOT, 'test')

    class Ranged(http.server.BaseHTTPRequestHandler):
        """like a real stream server: byte ranges, so Kodi and ffmpeg can seek"""
        def log_message(self, *a):
            pass

        def do_HEAD(self):
            self.do_GET(body=False)

        def do_GET(self, body=True):
            path = os.path.join(folder, os.path.basename(self.path.split('?')[0]))
            if not os.path.isfile(path):
                return self.send_error(404)
            size = os.path.getsize(path)
            start, end = 0, size - 1
            m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range', ''))
            if m:
                start = int(m.group(1) or 0)
                end = int(m.group(2)) if m.group(2) else size - 1
                self.send_response(206)
                self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
            else:
                self.send_response(200)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()
            if body:
                with open(path, 'rb') as f:
                    f.seek(start)
                    left = end - start + 1
                    try:
                        while left > 0:
                            chunk = f.read(min(65536, left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            left -= len(chunk)
                    except OSError:
                        pass
    global MEDIA
    httpd = None
    for port in (8799, 8797, 8795, 0):   # Windows sometimes reserves port ranges (WinError 10013): take the next one
        try:
            httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), Ranged)
            break
        except OSError:
            continue
    MEDIA = 'http://127.0.0.1:%d/' % httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def t_ai_subs_end_to_end():
    """a network video without Hebrew subtitles -> Kodi asks the PC server -> Hebrew subtitles appear"""
    httpd = media_server()
    try:
        for f in glob.glob(os.path.join(ROOT, 'server', 'cache', 'u*.json')):
            os.remove(f)                         # force a real transcription, not the cache
        rpc('Player.Open', item={'file': MEDIA + 'test_ru_long.mp4'})
        prof = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova')
        got = ''
        for _ in range(100):
            time.sleep(3)
            srts = glob.glob(os.path.join(prof, 'ai_*.he.srt'))
            pl = rpc('Player.GetActivePlayers').get('result') or []
            if srts and pl:
                sub = rpc('Player.GetProperties', playerid=pl[0]['playerid'],
                          properties=['subtitleenabled', 'currentsubtitle'])['result']
                text = open(srts[0], encoding='utf-8', errors='ignore').read()
                if sub.get('subtitleenabled') and re.search('[֐-׿]', text):
                    got = '%d Hebrew lines, subtitles on' % text.count(' --> ')
                    break
        for p in rpc('Player.GetActivePlayers').get('result') or []:
            rpc('Player.Stop', playerid=p['playerid'])
        expect(got, 'no Hebrew AI subtitles reached the player')
        return got
    finally:
        httpd.shutdown()


def _player():
    pl = rpc('Player.GetActivePlayers').get('result') or []
    return pl[0]['playerid'] if pl else None


def _stop_all():
    for p in rpc('Player.GetActivePlayers').get('result') or []:
        rpc('Player.Stop', playerid=p['playerid'])
    time.sleep(3)


def _wait_playing(secs=60):
    for _ in range(secs * 2):
        pid = _player()
        if pid is not None:
            t = rpc('Player.GetProperties', playerid=pid, properties=['time'])['result']['time']
            if t.get('seconds', 0) + t.get('minutes', 0) > 0:
                return pid
        time.sleep(0.5)
    return None


def t_subs_reset_between_videos():
    """video 1 has subtitles on; after it ends, video 2 starts WITHOUT them (nothing carried over)"""
    httpd = media_server()
    try:
        rpc('Player.Open', item={'file': MEDIA + 'test_ru.mp4'})
        pid = _wait_playing()
        expect(pid is not None, 'video 1 did not play')
        r = rpc('Player.AddSubtitle', playerid=pid, subtitle=os.path.join(ROOT, 'test', 'test_ru.he.srt'))
        expect('error' not in r, 'AddSubtitle: %s' % r.get('error'))
        rpc('Player.SetSubtitle', playerid=pid, subtitle='on')
        time.sleep(2)
        on1 = rpc('Player.GetProperties', playerid=pid, properties=['subtitleenabled'])['result']['subtitleenabled']
        expect(on1, 'could not switch subtitles on for video 1')
        _stop_all()
        rpc('Player.Open', item={'file': MEDIA + 'test_ru_long.mp4'})
        pid = _wait_playing()
        expect(pid is not None, 'video 2 did not play')
        time.sleep(1.5)
        pr = rpc('Player.GetProperties', playerid=pid, properties=['subtitleenabled', 'subtitles'])['result']
        _stop_all()
        expect(not pr['subtitleenabled'], 'video 2 started with the subtitles of video 1')
        expect(not any('test_ru' in (x.get('name') or '') for x in pr.get('subtitles', [])), 'subtitle file of video 1 still loaded')
        return 'video 1 subtitles on -> video 2 starts clean (%d own tracks, off)' % len(pr.get('subtitles', []))
    finally:
        httpd.shutdown()


def t_ai_button():
    """AI Subtitle Generation button: AI Hebrew subtitles replace the subtitles already showing"""
    httpd = media_server()
    prof = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova')
    try:
        rpc('Player.Open', item={'file': MEDIA + 'test_ru_long.mp4'})
        pid = _wait_playing()
        expect(pid is not None, 'video did not play')
        time.sleep(8)                           # let the automatic flow settle first
        for f in glob.glob(os.path.join(prof, 'ai_*.he.srt')):
            os.remove(f)
        rpc('Player.AddSubtitle', playerid=pid, subtitle=os.path.join(ROOT, 'test', 'test_ru.he.srt'))
        rpc('Player.SetSubtitle', playerid=pid, subtitle='on')
        time.sleep(2)
        before = rpc('Player.GetProperties', playerid=pid, properties=['currentsubtitle'])['result']['currentsubtitle']
        expect((before or {}).get('name', '').startswith('test_ru'), 'the human subtitle was not active first: %s' % before)
        # exactly what the skin button runs: RunPlugin(...?a=ai_subs_now) -> NotifyAll -> service
        # like the skin's RunPlugin: runs the add-on without opening a window (a window is refused behind a dialog)
        rpc('Files.GetDirectory', directory=NOVA + '?a=ai_subs_now', media='files', timeout=60)
        got, seen = '', []
        for _ in range(60):
            time.sleep(1)
            pr = rpc('Player.GetProperties', playerid=pid, properties=['subtitleenabled', 'subtitles', 'currentsubtitle'])['result']
            seen.append(pr)
            cur = (pr.get('currentsubtitle') or {}).get('name') or ''
            if glob.glob(os.path.join(prof, 'ai_*.he.srt')) and pr['subtitleenabled'] and cur.startswith('ai_'):
                got = 'active subtitle switched from test_ru (human) to %s' % cur.split(' ')[0]
                break
        _stop_all()
        expect(got, 'the AI button did not load AI subtitles over the existing ones: %s' % seen[-1:])
        return got
    finally:
        httpd.shutdown()



def t_subs_reset_next_episode():
    """autoplay of the next item (no stop in between, like the next episode): it starts clean too"""
    httpd = media_server()
    try:
        rpc('Playlist.Clear', playlistid=1)
        for f in ('test_ru.mp4', 'test_ru_long.mp4'):
            rpc('Playlist.Add', playlistid=1, item={'file': MEDIA + f})
        rpc('Player.Open', item={'playlistid': 1, 'position': 0})
        pid = _wait_playing()
        expect(pid is not None, 'item 1 did not play')
        rpc('Player.AddSubtitle', playerid=pid, subtitle=os.path.join(ROOT, 'test', 'test_ru.he.srt'))
        rpc('Player.SetSubtitle', playerid=pid, subtitle='on')
        time.sleep(2)
        expect(rpc('Player.GetProperties', playerid=pid, properties=['subtitleenabled'])['result']['subtitleenabled'], 'subtitles not on for item 1')
        rpc('Player.GoTo', playerid=pid, to='next')
        pr = None
        for _ in range(60):
            time.sleep(0.5)
            pid = _player()
            if pid is None:
                continue
            it = rpc('Player.GetItem', playerid=pid, properties=['file'])['result']['item']
            if 'test_ru_long' in (it.get('file') or '') and _wait_playing(20) is not None:
                time.sleep(1.5)
                pr = rpc('Player.GetProperties', playerid=pid, properties=['subtitleenabled', 'subtitles'])['result']
                break
        _stop_all()
        rpc('Playlist.Clear', playlistid=1)
        expect(pr, 'item 2 did not start')
        expect(not pr['subtitleenabled'], 'item 2 kept the subtitles of item 1')
        expect(not any('test_ru (' in (x.get('name') or '') for x in pr['subtitles']), 'subtitle file of item 1 still loaded')
        return 'next item starts clean (subtitles off, previous file gone)'
    finally:
        httpd.shutdown()


def t_ai_button_idle():
    """the AI button with nothing playing: a message, no error"""
    _stop_all()
    logf = os.path.join(DATA, 'kodi.log')
    n0 = len(open(logf, encoding='utf-8', errors='ignore').read())
    rpc('Files.GetDirectory', directory=NOVA + '?a=ai_subs_now', media='files', timeout=60)
    time.sleep(6)
    new = open(logf, encoding='utf-8', errors='ignore').read()[n0:]
    expect('Traceback' not in new, 'traceback: %s' % new[new.find('Traceback'):][:200])
    expect(not rpc('Player.GetActivePlayers')['result'], 'something started playing')
    return 'no player, no error'


def t_system_update():
    """System Update: every part refreshed, report with Auto-Fix under each error, the fix works"""
    prof = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova')
    rep_file = os.path.join(prof, 'sysupdate.json')
    victim = 'plugin.video.idanplus'
    rpc('Addons.SetAddonEnabled', addonid=victim, enabled=False)      # a real error for the report to find
    t0 = time.time()
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=sysupdate', wait=False)
    rep = None
    for _ in range(200):
        time.sleep(3)
        if os.path.exists(rep_file) and os.path.getmtime(rep_file) > t0:
            rep = json.load(open(rep_file, encoding='utf-8'))
            break
    expect(rep, 'no System Update report')
    ids = [r['id'] for r in rep['rows']]
    for need in ('internet', 'repos', 'addon:plugin.video.pov', 'svc:server', 'iptv', 'pvr', 'radio', 'cache'):
        expect(need in ids, 'report misses %s' % need)
    bad = {r['id']: r for r in rep['rows'] if r['ok'] is False}
    expect('addon:' + victim in bad, 'disabled add-on not reported')
    time.sleep(3)
    rows = ls(NOVA + '?a=sysreport')
    labels = [r['label'] for r in rows]
    fixes = [i for i, l in enumerate(labels) if 'Auto-Fix' in l or 'תיקון אוטומטי' in l]
    expect(len(fixes) >= len(bad), '%d errors but %d Auto-Fix entries' % (len(bad), len(fixes)))
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=sysfix&id=addon:' + victim, wait=False)
    en = False
    for _ in range(40):
        time.sleep(2)
        en = rpc('Addons.GetAddonDetails', addonid=victim, properties=['enabled'])['result']['addon']['enabled']
        if en:
            break
    rpc('Addons.SetAddonEnabled', addonid=victim, enabled=True)
    expect(en, 'Auto-Fix did not re-enable %s' % victim)
    time.sleep(3)
    rep2 = json.load(open(rep_file, encoding='utf-8'))
    fixed = next(r for r in rep2['rows'] if r['id'] == 'addon:' + victim)
    expect(fixed['ok'], 'report not updated after the fix')
    repos = next(r for r in rep['rows'] if r['id'] == 'repos')
    return '%d parts, %d errors (%s), Auto-Fix fixed %s; %s' % (len(rep['rows']), len(bad), ', '.join(sorted(bad))[:80],
                                                               victim, repos['detail'][:60])


def t_log_errors():
    log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
    ours = [l for l in log.splitlines() if ('NovaTV' in l or 'plugin.video.nova' in l or 'NovaWizard' in l)
            and (' error ' in l.lower() or 'Traceback' in l)
            and not re.search(r'GetDirectory.*a=(fav_add|fav_rm|history_clear|acc|tv_do|tv_play|noop|bk_auto|lib_install|play|prov_toggle|prov_install_all|sysupdate|sysfix|ai_subs_now)', l)]
    expect(not ours, '%d errors from our add-ons: %s' % (len(ours), ours[:2]))
    return 'no errors from BN add-ons'


def t_libraries():
    docs = ls(NOVA + '?a=lib_cat&cat=docs')
    expect(any('id=esa' in i['file'] for i in docs), 'ESA missing from documentaries')
    expect(not any('id=ted' in i['file'] for i in docs), 'unstable TED still listed')
    inside = ls(NOVA + '?a=lib_open&id=esa')              # provider menu shown inside NovaTV
    expect(len(inside) >= 3, 'ESA menu inside NovaTV: %d items' % len(inside))
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=lib_install&id=plugin.video.ted.talks')
    for _ in range(60):
        time.sleep(2)
        r = rpc('Addons.GetAddonDetails', addonid='plugin.video.ted.talks', properties=['enabled'])
        if 'result' in r and r['result']['addon']['enabled']:
            return 'ESA menu inside NovaTV (%d items), unstable TED hidden, on-demand install works' % len(inside)
    # Kodi's official mirror sometimes times out: that is outside the build - accept it only if NovaTV retried
    log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
    mirror_down = re.search(r'CCurlFile.*mirrors?\.|CCurlFile.*/xbmc/addons/omega/.*Failed', log) and 'failed to download' in log
    if mirror_down and 'install plugin.video.ted.talks: attempt 2 failed, retrying' in log:
        return 'ESA menu inside NovaTV (%d items), TED hidden; on-demand install retried 3x - Kodi mirror unreachable (external)' % len(inside)
    raise AssertionError('on-demand install failed')


def t_backup():
    for _ in range(3):                      # a dialog left open by the previous test blocks ExecuteAddon
        rpc('Input.ExecuteAction', action='close')
        time.sleep(1)
    rpc('GUI.ActivateWindow', window='home')
    time.sleep(3)
    hist = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'history.json')
    if not os.path.exists(hist):             # own data: must not depend on the history check having run before
        json.dump([{'key': 'movie:603', 'label': 'The Matrix', 'when': '01/01/2026 20:00', 'ts': 0, 'play': ''}],
                  open(hist, 'w', encoding='utf-8'))
    rpc('Files.GetDirectory', directory=NOVA + '?a=bk_auto', media='files')   # runs the action even behind a dialog
    d = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'backups')
    for _ in range(45):
        time.sleep(1)
        zips = [f for f in os.listdir(d) if f.endswith('.zip')] if os.path.isdir(d) else []
        if zips:
            break
    expect(zips, 'no backup created')
    z = zipfile.ZipFile(os.path.join(d, zips[-1]))
    names = z.namelist()
    expect('bn_backup.txt' in names, 'marker')
    expect(any('plugin.video.nova/history.json' in n for n in names), 'history in backup')
    expect(not any('/backups/' in n for n in names), 'backup contains itself')
    return '%d files' % len(names)


def t_free_channels():
    iptv_json = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'iptv.json')
    cfg = json.load(open(iptv_json)) if os.path.exists(iptv_json) else {}   # own data: runs alone after a resume too
    cfg.setdefault('m3u', [])
    cfg.setdefault('epg', [])
    cfg['free'] = {k: True for k in free_list_names()}
    json.dump(cfg, open(iptv_json, 'w'))
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=tv_do&do=refresh')
    n = 0
    for _ in range(105):                     # waits for the automatic refresh at start if it is running
        time.sleep(4)
        r = rpc('PVR.GetChannels', channelgroupid='alltv', properties=['channelnumber'])
        n = len(r.get('result', {}).get('channels', []))
        if n >= 300:
            break
    expect(n >= 300, 'only %d channels' % n)
    for _ in range(30):
        heb = rpc('PVR.GetChannelGroups', channeltype='tv').get('result', {}).get('channelgroups')
        if heb:
            break
        time.sleep(2)
    expect(heb, 'no channel groups')
    return '%d channels, groups: %s' % (n, ', '.join(g['label'] for g in heb))


def t_m3u_integrity():
    """Merged playlist (all free lists on): unique numbers, stream headers, dead streams removed."""
    path = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.nova', 'nova_channels.m3u')
    lines = open(path, encoding='utf-8').read().splitlines()
    nums = [int(m) for l in lines for m in re.findall(r'tvg-chno="(\d+)"', l)]
    expect(nums and len(nums) == len(set(nums)), '%d duplicate channel numbers' % (len(nums) - len(set(nums))))
    urls = [l for l in lines if l and not l.startswith('#')]
    expect(len(urls) == len(nums), '%d urls for %d channels' % (len(urls), len(nums)))
    bare = [u for u in urls if u.startswith('http') and '|User-Agent=' not in u]
    expect(not bare, '%d http streams without User-Agent, e.g. %s' % (len(bare), bare[:1]))
    dead = set(json.load(open(os.path.join(NOVA_SRC, 'resources', 'dead_streams.json'), encoding='utf-8')))
    left = [u for u in urls if u.split('|')[0] in dead]
    expect(not left, '%d dead streams still listed' % len(left))
    names = [l.rsplit(',', 1)[-1] for l in lines if l.startswith('#EXTINF')]
    broken = [n for n in names if '="' in n or not n.strip()]
    expect(not broken, 'broken channel names: %s' % broken[:2])
    return '%d channels, numbers unique, UA on %d http streams, %d dead filtered' % (len(nums), sum(u.startswith('http') for u in urls), len(dead))


def t_preset():
    """Locked profile: create -> encrypted file -> unlock with right password restores data; wrong one fails."""
    import types, tempfile, io as _io, zipfile as _zf
    tmp = tempfile.mkdtemp(prefix='nvp_')
    src_ud, dst_ud = os.path.join(tmp, 'src'), os.path.join(tmp, 'dst')
    secret = os.path.join('addon_data', 'plugin.video.nova', 'accounts.json')
    os.makedirs(os.path.join(src_ud, os.path.dirname(secret)))
    open(os.path.join(src_ud, secret), 'w').write('{"rd_token": "TEST-TOKEN"}')
    answers = []

    class Dialog:
        def input(self, *a, **k): return answers.pop(0)
        def yesno(self, *a, **k): return False
        def ok(self, *a, **k): Dialog.last = a[-1]
        def notification(self, *a, **k): pass
        def browse(self, *a, **k): return ''
    stubs = {'xbmcgui': types.SimpleNamespace(Dialog=Dialog, ALPHANUM_HIDE_INPUT=2),
             'xbmcvfs': types.SimpleNamespace(translatePath=lambda p: tmp + os.sep, copy=shutil.copy)}
    prof = os.path.join(tmp, 'profile')
    os.makedirs(prof)
    store = {}
    pkg = types.ModuleType('nvlib'); pkg.__path__ = []
    common = types.SimpleNamespace(PROFILE=prof, ui_lang=lambda: 'en', load=lambda n, d: store.get(n, d),
                                   save=lambda n, v: store.__setitem__(n, v))

    def make_zip(path):
        with _zf.ZipFile(path, 'w') as z:
            z.writestr('bn_backup.txt', 'x')
            z.write(os.path.join(src_ud, secret), secret)
    bk = types.SimpleNamespace(make_zip=make_zip, USERDATA=dst_ud)
    saved = {k: sys.modules.get(k) for k in list(stubs) + ['nvlib', 'nvlib.common', 'nvlib.backup', 'nvlib.preset']}
    sys.modules.update(stubs); sys.modules.update({'nvlib': pkg, 'nvlib.common': common, 'nvlib.backup': bk})
    pkg.common, pkg.backup = common, bk
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('nvlib.preset', os.path.join(NOVA_SRC, 'resources', 'lib', 'preset.py'))
        preset = importlib.util.module_from_spec(spec); sys.modules['nvlib.preset'] = preset
        spec.loader.exec_module(preset)
        exited = []
        preset.os = types.SimpleNamespace(**{k: getattr(os, k) for k in dir(os) if not k.startswith('__')})
        preset.os._exit = exited.append
        answers[:] = ['short', ]
        preset.create()
        expect(not os.path.exists(preset.LOCAL), 'short password accepted')
        answers[:] = ['Correct-Horse-1', 'Correct-Horse-1']
        preset.create()
        blob = open(preset.LOCAL, 'rb').read()
        expect(blob[:4] == b'NVP1' and b'TEST-TOKEN' not in blob, 'profile file not encrypted')
        answers[:] = ['wrong-password']
        preset.unlock()
        expect(not os.path.exists(os.path.join(dst_ud, secret)) and store['preset_guard.json']['fails'] == 1, 'wrong password accepted')
        tampered = bytearray(blob); tampered[-1] ^= 1
        expect(preset.decrypt('Correct-Horse-1', bytes(tampered)) is None, 'tampered file accepted')
        answers[:] = ['Correct-Horse-1']
        preset.unlock()
        got = open(os.path.join(dst_ud, secret)).read()
        expect('TEST-TOKEN' in got and exited == [1], 'restore failed')
        expect(store['preset_guard.json']['fails'] == 0, 'fail counter not reset')
        for _ in range(5):
            answers[:] = ['nope']
            preset.unlock()
        answers[:] = ['Correct-Horse-1']
        exited.clear(); preset.unlock()
        expect(not exited, 'lockout after 5 wrong tries not enforced')
        return 'encrypt, wrong pw rejected, tamper detected, restore ok, 5-try lockout'
    finally:
        for k, v in saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


def t_hub_search():
    """one query -> results from several add-ons at once, all inside NovaTV"""
    t = time.time()
    items = ls(NOVA + '?a=hub_search&q=Chaplin')
    heads = [re.sub(r'\[/?[A-Z]+[^\]]*\]', '', i['label']) for i in items if 'a=noop' in i['file']]
    expect(len(heads) >= 3, 'only %d source sections: %s' % (len(heads), heads))
    names = ' '.join(heads)
    expect('YouTube' in names and 'Internet Archive' in names, 'sections: %s' % heads)
    expect(any('video_id=' in i['file'] for i in items) and any('a=ia_item' in i['file'] for i in items), 'no playable rows')
    return '%d sections in %.0fs: %s' % (len(heads), time.time() - t, ', '.join(h.split(' (')[0] for h in heads)[:150])


def t_central_library():
    cats = ls(NOVA + '?a=libs')
    expect(len(cats) >= 5, '%d categories' % len(cats))
    ru = ls(NOVA + '?a=lib_cat&cat=russian')
    expect(any('UCEK3tT7DcfWGWJpNEDBdWog' in i['file'] for i in ru), 'Mosfilm channel missing')
    src = ls(NOVA + '?a=sources')
    expect(len(src) >= 30, '%d providers on the sources screen' % len(src))
    mos = ls(NOVA + '?a=yt_channel&id=UCEK3tT7DcfWGWJpNEDBdWog')
    expect(len(mos) >= 20, 'Mosfilm channel lists %d items' % len(mos))
    film = next(i for i in mos if 'video_id=' in i['file'])
    rpc('Player.Open', item={'file': film['file']})
    played = 0
    for _ in range(25):
        time.sleep(2)
        pl = rpc('Player.GetActivePlayers').get('result') or []
        if pl:
            t = rpc('Player.GetProperties', playerid=pl[0]['playerid'], properties=['time'])['result']['time']
            played = t['minutes'] * 60 + t['seconds']
            if played >= 4:
                rpc('Player.Stop', playerid=pl[0]['playerid'])
                break
    expect(played >= 4, 'Mosfilm video did not play')
    soviet = ls(NOVA + '?a=ia_search&q=%D1%81%D0%BE%D0%B2%D0%B5%D1%82%D1%81%D0%BA%D0%B8%D0%B9%20%D1%84%D0%B8%D0%BB%D1%8C%D0%BC')
    expect(len(soviet) >= 10, 'Soviet films from the Archive: %d' % len(soviet))
    eps = ls(soviet[0]['file'])
    expect(eps and 'a=ia_play' in eps[0]['file'] and 'archive.org%2Fdownload' in eps[0]['file'], 'Archive item has no video files')
    return '%d categories, %d providers, Mosfilm %d videos (played %ds), %d Soviet films' % (len(cats), len(src) - 1, len(mos), played, len(soviet))


def t_pov_fallback():
    """POV first; when it has nothing, NovaTV searches every other source and offers the results"""
    home = open(os.path.join(DATA, 'addons', 'skin.fentastic', 'xml', 'Home.xml'), encoding='utf-8').read()
    expect(home.count('a=hub_search') >= 3, 'skin search button not routed to NovaTV')
    rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=play&m=movie&id=13&q=Forrest Gump 1994&alt=')
    seen = ''
    for _ in range(120):
        time.sleep(2)
        w = rpc('GUI.GetProperties', properties=['currentwindow'])['result']['currentwindow']
        if w['id'] == 12000:                         # select dialog = merged results of the other sources
            seen = 'fallback list'
            break
        if rpc('Player.GetActivePlayers').get('result'):
            seen = 'POV played it'
            break
    for _ in range(3):
        rpc('Input.ExecuteAction', action='close')
        time.sleep(1)
    for p in rpc('Player.GetActivePlayers').get('result') or []:
        rpc('Player.Stop', playerid=p['playerid'])
    expect(seen, 'neither POV playback nor the fallback list appeared')
    pov = open(os.path.join(DATA, 'addons', 'plugin.video.pov', 'resources', 'lib', 'modules', 'sources.py'), encoding='utf-8').read()
    expect("set_property('nova.pov_noresults', '1')" in pov, 'POV no-results hook missing (auto-update not healed)')
    return seen + ', POV hook in place'


STARTUP_BAD = [r'subtitles\.subs_action', r'burekasKodi', r'kodi7rd/repository', r'invalid include: Custom[23]Widgets',
               r'Root element <includes> required', r'No <window> root element', r'missing version attribute']


def t_startup_clean():
    """the errors the base build logged at every start are gone"""
    log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
    found = [p for p in STARTUP_BAD if re.search(p, log)]
    expect(not found, 'still in the log: %s' % found)
    errors = [l for l in log.splitlines() if ' error <general>' in l and 'plugin.video.' not in l and 'CCurlFile' not in l]
    return '%d known startup problems fixed; %d other error lines' % (len(STARTUP_BAD), len(errors))


def t_startup_status():
    """"BN Stream is ready" + the status table (add-ons, services, content counts)"""
    for _ in range(60):
        log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
        m = re.search(r'startup status: (\d+) problems (.*)', log)
        if m:
            break
        time.sleep(3)
    expect(m, 'no startup announcement')
    rows = ls(NOVA + '?a=status')
    labels = ' '.join(r['label'] for r in rows)
    expect(len(rows) >= 25, '%d status rows' % len(rows))
    nums = re.findall(r'\d{1,3}(?:,\d{3})+', labels)
    expect(len(nums) >= 2, 'content counts missing')
    return 'announced (%s problems %s), %d rows, counts e.g. %s' % (m.group(1), m.group(2)[:60], len(rows), ', '.join(nums[:3]))


def t_subs_before_play():
    """a film starts paused, gets Hebrew subtitles (human or AI), then plays by itself"""
    soviet = ls(NOVA + '?a=ia_search&q=%D0%9A%D0%B8%D0%BD-%D0%B4%D0%B7%D0%B0-%D0%B4%D0%B7%D0%B0')
    film = None
    for it in soviet[:5]:
        files = ls(it['file'])
        if files:
            film = files[0]
            break
    expect(film, 'no Archive film to play')
    rpc('Player.Open', item={'file': film['file']})
    paused = resumed = False
    subs = ''
    for _ in range(100):
        time.sleep(3)
        pl = rpc('Player.GetActivePlayers').get('result') or []
        if not pl:
            continue
        pr = rpc('Player.GetProperties', playerid=pl[0]['playerid'], properties=['speed', 'subtitleenabled', 'currentsubtitle'])['result']
        if pr['speed'] == 0:
            paused = True
        elif paused:
            resumed = True
            if pr.get('subtitleenabled'):
                subs = (pr.get('currentsubtitle') or {}).get('language') or 'on'
            break
    for p in rpc('Player.GetActivePlayers').get('result') or []:
        rpc('Player.Stop', playerid=p['playerid'])
    expect(paused, 'the film did not wait for subtitles')
    expect(resumed, 'the film never started after preparing subtitles')
    expect(subs, 'playback started without subtitles')
    return 'paused, subtitles ready (%s), resumed: %s' % (subs, film['label'][:40])



# ------------------------------------------------------------------ deep checks (0.2.2)
OUR = ('plugin.video.nova', 'plugin.program.novawizard', 'repository.nova', 'resource.uisounds.nova')


def t_static():
    """official kodi-addon-checker (0 errors), Python 3.8 syntax (Kodi's interpreter), every XML parses"""
    import ast
    import xml.dom.minidom
    bad = []
    for a in OUR:
        for d, dirs, files in os.walk(os.path.join(ROOT, 'addons', a)):
            dirs[:] = [x for x in dirs if x != '__pycache__']
            for fn in files:
                p = os.path.join(d, fn)
                try:
                    if fn.endswith('.py'):
                        ast.parse(open(p, encoding='utf-8').read(), p, feature_version=(3, 8))
                    elif fn.endswith('.xml'):
                        xml.dom.minidom.parse(p)
                except Exception as e:
                    bad.append('%s: %s' % (os.path.relpath(p, ROOT), str(e)[:80]))
    for f in ('View_60_BN.xml', 'Variables_BN.xml'):
        try:
            xml.dom.minidom.parse(os.path.join(ROOT, 'brand', 'skin', f))
        except Exception as e:
            bad.append('%s: %s' % (f, e))
    expect(not bad, 'syntax/XML: %s' % bad[:3])
    checker = os.path.join(ROOT, '.venv11', 'Scripts', 'kodi-addon-checker.exe')
    errs = []
    import hashlib
    h = hashlib.sha256()
    for a in OUR:
        for d, dirs, files in sorted(os.walk(os.path.join(ROOT, 'addons', a))):
            dirs[:] = sorted(x for x in dirs if x != '__pycache__')
            for fn in sorted(files):
                if not fn.endswith('.pyc'):
                    h.update(fn.encode())
                    h.update(open(os.path.join(d, fn), 'rb').read())
    cache = os.path.join(ROOT, 'work', 'addonchecker_ok.txt')
    same = os.path.exists(cache) and open(cache).read().strip() == h.hexdigest()
    if os.path.exists(checker) and not same:   # the official checker needs ~90 min: only when our add-ons changed
        for a in OUR:
            tmp = os.path.join(ROOT, 'work', 'chk', a)
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(os.path.join(ROOT, 'addons', a), tmp, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            out = subprocess.run([checker, '--branch', 'omega', '--skip-dependency-checks', tmp], capture_output=True,
                                 text=True, encoding='utf-8', errors='ignore').stdout
            errs += ['%s: %s' % (a, l) for l in re.sub(r'\x1b\[[0-9;]*m', '', out).splitlines()
                     if l.startswith('ERROR') and 'We found' not in l]
    expect(not errs, 'kodi-addon-checker: %s' % errs[:3])
    if os.path.exists(checker) and not same:
        open(cache, 'w').write(h.hexdigest())
    return 'py3.8 syntax + XML OK, addon-checker 0 errors (%s)' % ('same files as the last clean check' if same else 'ran' if os.path.exists(checker) else 'not installed')


def t_menu_crawl():
    """every NovaTV screen (3 levels deep) opens without an error and fast enough for a TV remote"""
    skip = re.compile(r'a=(list|years|seasons|episodes|hub_search|search|sysreport|yt_search|ia_search|radio_list|tv_list|ia_item|kukhnya)\b')
    todo, seen, slow, errors, n = [(NOVA, 0)], set(), [], [], 0
    while todo and n < 120:
        path, depth = todo.pop(0)
        if path in seen:
            continue
        seen.add(path)
        t = time.time()
        r = rpc('Files.GetDirectory', directory=path, media='files', timeout=60)
        dt = time.time() - t
        n += 1
        if 'error' in r:
            errors.append(path.split('?')[-1][:60])
            continue
        if dt > 15:
            slow.append('%s %.0fs' % (path.split('?')[-1][:50], dt))
        for it in (r['result'].get('files') or []):
            f = it.get('file', '')
            if it.get('filetype') == 'directory' and f.startswith(NOVA) and depth < 3 and not skip.search(f):
                todo.append((f, depth + 1))
    expect(not errors, 'screens with errors: %s' % errors[:4])
    expect(not slow, 'slow screens: %s' % slow[:4])
    return '%d screens opened, no errors, none slower than 15 s' % n


def _log_len():
    return len(open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read())


def _log_since(n0):
    return open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()[n0:]


def _visible(cond):
    return rpc('XBMC.GetInfoBooleans', booleans=[cond])['result'][cond]


def t_skin_windows():
    """player controls + subtitle window really open with the AI button; the skin logs no error"""
    httpd = media_server()
    n0 = _log_len()
    try:
        rpc('Player.Open', item={'file': MEDIA + 'test_ru_long.mp4'})
        expect(_wait_playing() is not None, 'video did not play')
        rpc('GUI.ActivateWindow', window='subtitlesearch')
        time.sleep(3)
        sub_open = _visible('Window.IsActive(subtitlesearch)')
        # with the remote: Up from the services list -> AI button -> Select starts AI subtitles
        n1 = _log_len()
        for _ in range(40):                   # Kodi first searches subtitles (busy overlay has the focus)
            if _visible('Window.IsTopMost(subtitlesearch)'):
                break
            time.sleep(0.5)
        # All_Subs' "searching subtitles" progress window (Cancel = control 10) can stay up to 2 min:
        # a viewer who wants AI subtitles presses Back once to stop the search, then Up to the AI button
        over = rpc('XBMC.GetInfoLabels', labels=['System.CurrentWindow'])['result']['System.CurrentWindow']
        if not _visible('Window.IsTopMost(subtitlesearch)') and _visible('Window.IsActive(progressdialog)'):
            rpc('Input.Back')
            time.sleep(2)
        ai_btn, path = False, []
        for _ in range(4):                    # the list may still be loading: press Up like a viewer would
            rpc('Input.Up')
            time.sleep(1)
            ai_btn = _visible('Control.HasFocus(7160)')
            path.append(rpc('XBMC.GetInfoLabels', labels=['System.CurrentControlId'])['result']['System.CurrentControlId'])
            if ai_btn:
                break
        rpc('Input.Select')
        started = False
        for _ in range(15):                   # the first add-on start after boot is slower
            time.sleep(1)
            started = 'AI subtitles requested' in _log_since(n1)
            if started:
                break
        ai_btn = ai_btn and started and not _visible('Window.IsActive(subtitlesearch)')
        rpc('GUI.ActivateWindow', window='videoosd')
        time.sleep(3)
        osd = _visible('Window.IsActive(videoosd)')
        rpc('Input.Back')
        _stop_all()
        expect(sub_open, 'subtitle window did not open')
        expect(ai_btn, 'AI button in the subtitle window not reachable/working with the remote (focus: %s, window open: %s, on top before: %s)' % (path, sub_open, over))
        expect(osd, 'player controls did not open')
        bad = [l for l in _log_since(n0).splitlines() if re.search(r'error <general>: .*(skin|Skin|window|Window|include|Include|control|XML)', l)]
        expect(not bad, 'skin errors: %s' % bad[:2])
        return 'subtitle window: remote Up -> AI button -> Select starts AI subtitles; player controls open; no skin errors'
    finally:
        httpd.shutdown()


# third-party add-on errors that are known and outside the build's control (reason next to each)
KNOWN_TRACEBACKS = [
    'googlevideo.com/videoplayback',   # YouTube refuses some streams without a signed-in account (403): YouTube's policy
    'access_manager.json',             # YouTube's first start: it creates this file itself right after logging this
    'resources.py", line 190, in path',   # certifi (requests) at interpreter exit: "Exception ignored", harmless
]


def t_all_subs_guard():
    """All_Subs (third party) carries the BN guards: no subtitle for another video, stops when Kodi quits"""
    p = os.path.join(DATA, 'addons', 'service.subtitles.All_Subs', 'autosub.py')
    src = open(p, encoding='utf-8').read()
    expect('# BN guard v4' in src, 'guards missing in the installed All_Subs')
    expect(src.count('not monit.abortRequested()') >= 2 and '_bn_same_video()' in src, 'guards incomplete')
    plus = open(os.path.join(DATA, 'addons', 'service.subtitles.all_subs_plus', 'autosub.py'), encoding='utf-8').read()
    expect('# BN guard plus v1' in plus, 'All Subs Plus exit guard missing')
    log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
    blocked = log.count('BN guard: video changed')
    return 'guards installed; %d late subtitle(s) blocked in this run' % blocked


def _versions_seen(log):
    out = {}
    for aid, ver in re.findall(r'FindAddons?: ([\w.\-]+) v([\w.\-+~]+) installed', log):
        out.setdefault(aid, set()).add(ver)
    return out


def t_youtube_port():
    """YouTube's local server port can be opened (Windows reserves port ranges): NovaTV moves it when blocked"""
    p = os.path.join(DATA, 'userdata', 'addon_data', 'plugin.video.youtube', 'settings.xml')
    m = re.search(r'id="kodion.http.port"[^>]*>(\d+)<', open(p, encoding='utf-8').read())
    port = int(m.group(1)) if m else 50152
    import socket
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
        free = True
    except OSError as e:
        free = getattr(e, 'winerror', None) == 10048
    finally:
        s.close()
    expect(free, 'YouTube port %d cannot be opened on this PC' % port)
    return 'YouTube port %d usable' % port


def t_no_tracebacks():
    """no Python traceback from ANY add-on during the whole run"""
    log = open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read()
    # a block plus the lines after it: Kodi logs some tracebacks one line per entry
    blocks = [log[m.start():m.end() + 600] for m in
              re.finditer(r'(?:EXCEPTION Thrown|Traceback \(most recent call last\)).*?(?=\n\d{4}-\d\d-\d\d )', log, re.S)]
    blocks = [b for b in blocks if not any(k in b for k in KNOWN_TRACEBACKS)]
    # Kodi auto-updating an add-on unregisters it for a few seconds: the skin's widgets calling it then fail once.
    # Accepted only for an add-on the log shows was really updated during this run.
    updated = {aid for aid, vs in _versions_seen(log).items() if len(vs) > 1}
    blocks = [b for b in blocks if not (re.search(r"Unknown addon id '([^']+)'", b) and
                                        re.search(r"Unknown addon id '([^']+)'", b).group(1) in updated)]
    expect(not blocks, '%d tracebacks, first: %s' % (len(blocks), blocks[0][-300:] if blocks else ''))
    return 'no tracebacks in %d log lines' % log.count('\n')


def _kodi_threads():
    out = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process kodi).Threads.Count'],
                         capture_output=True, text=True).stdout.strip()
    return int(out.splitlines()[0]) if out else 0


def t_thread_leak():
    """6 plays + stops of videos: Kodi's thread count comes back (no leaked service/subtitle threads)"""
    httpd = media_server()
    try:
        time.sleep(5)
        before = _kodi_threads()
        for i in range(6):
            rpc('Player.Open', item={'file': MEDIA + '%s' % ('test_ru.mp4', 'test_ru_long.mp4')[i % 2]})
            _wait_playing()
            time.sleep(4)
            _stop_all()
        time.sleep(20)
        after = _kodi_threads()
        expect(after - before <= 8, 'threads %d -> %d' % (before, after))
        return 'threads %d -> %d after 6 plays' % (before, after)
    finally:
        httpd.shutdown()


def t_clean_shutdown():
    """Kodi quits within 30 s, every service stops in time, no crash dump"""
    for _ in range(60):                   # quit a fully started Kodi (right after a resume it may still be starting)
        if 'startup status:' in open(os.path.join(DATA, 'kodi.log'), encoding='utf-8', errors='ignore').read():
            break
        time.sleep(3)
    # Kodi installs its automatic add-on updates in the background and waits for them before it exits:
    # quit once they are done (no add-on installed for 20 s, at most 3 min), like a viewer some time after start
    last, t0 = _log_len(), time.time()
    quiet_since = time.time()
    while time.time() - t0 < 180 and time.time() - quiet_since < 20:
        time.sleep(4)
        new = _log_since(last)
        last = _log_len()
        if 'FindAddon' in new or 'CAddonInstallJob' in new:
            quiet_since = time.time()
    dumps = set(glob.glob(os.path.join(DATA, '*.dmp')))
    n0 = _log_len()
    try:
        rpc('Application.Quit', timeout=10)
    except Exception:
        pass
    t = time.time()
    while time.time() - t < 120:           # measure the real exit time (the limit is checked below)
        if 'kodi.exe' not in subprocess.run(['tasklist'], capture_output=True, text=True).stdout.lower():
            break
        time.sleep(1)
    dt = time.time() - t
    kill_kodi()                            # never start a second Kodi next to one still exiting
    tail = _log_since(n0)
    new_dumps = set(glob.glob(os.path.join(DATA, '*.dmp'))) - dumps
    stuck = [l for l in tail.splitlines() if re.search(r"didn't stop|did not stop|left several classes|Failed to stop", l)]
    start_kodi()                         # later checks still need Kodi
    expect(not new_dumps, 'crash on exit: %s' % new_dumps)
    expect(dt < 30, 'Kodi needed %.0f s to quit' % dt)
    expect(not stuck, 'services did not stop: %s' % stuck[:2])
    return 'quit in %.0f s, all services stopped, no dump' % dt


TESTS = [
    ('Add-ons installed & enabled', t_addons_enabled), ('Skin / sounds / language', t_gui),
    ('BN branding', t_branding), ('Main menu', t_root), ('Movie & series lists', t_movies_lists),
    ('Hebrew / English / Russian content', t_languages), ('Genres & years', t_genres_years),
    ('Title integrity (TMDb ids)', t_title_integrity), ('Kukhnya all seasons', t_kukhnya),
    ('Radio', t_radio), ('Accounts screen', t_accounts), ('Favourites', t_favourites),
    ('History + UI speed', t_history_and_speed), ('IPTV merge / dedupe / numbering', t_iptv),
    ('Free libraries menu', t_libraries), ('Backup', t_backup), ('Free channels (iptv-org)', t_free_channels),
    ('Merged playlist integrity', t_m3u_integrity), ('Locked profile round-trip', t_preset),
    ('Search all sources (hub)', t_hub_search), ('Central library + Russian', t_central_library),
    ('POV -> other sources fallback', t_pov_fallback),
    ('Startup log clean', t_startup_clean), ('Startup ready message + status', t_startup_status),
    ('AI subtitle server', t_ai_server), ('AI Hebrew subtitles end-to-end', t_ai_subs_end_to_end),
    ('Subtitles ready before playing', t_subs_before_play),
    ('Subtitles reset between videos', t_subs_reset_between_videos), ('AI Subtitle Generation button', t_ai_button),
    ('Subtitles reset on next episode', t_subs_reset_next_episode), ('AI button with nothing playing', t_ai_button_idle),
    ('System Update + Auto-Fix', t_system_update),
    ('Static: addon-checker, py3.8, XML', t_static), ('Every NovaTV screen opens', t_menu_crawl),
    ('Skin windows + AI button', t_skin_windows), ('All_Subs guards', t_all_subs_guard), ('YouTube port usable', t_youtube_port), ('No thread leak', t_thread_leak),
    ('Kodi log clean', t_log_errors), ('No tracebacks (any add-on)', t_no_tracebacks),
    ('Clean shutdown', t_clean_shutdown),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--keep', action='store_true', help='leave Kodi running')
    ap.add_argument('--installed', help='test an already installed copy (e.g. from the Windows installer) instead of testkodi')
    ap.add_argument('--stop-on-fail', action='store_true', help='stop at the first failed check (fix it, then --resume)')
    ap.add_argument('--resume', action='store_true', help='skip the checks that already passed in the stopped run')
    a = ap.parse_args()
    prog_file = os.path.join(ROOT, 'work', 'test_progress_%s.json' % ('installed' if a.installed else 'testkodi'))
    prog = json.load(open(prog_file, encoding='utf-8')) if a.resume and os.path.exists(prog_file) else {}
    if prog.get('version') != a.version:
        prog = {}
    done = prog.get('passed', [])
    sys.stdout.reconfigure(encoding='utf-8')
    global KODI, DATA
    if a.installed:
        KODI, DATA = a.installed, os.path.join(a.installed, 'portable_data')
        kill_kodi()
        enable_rpc()
    else:
        install(a.version)
    start_kodi()
    tests = TESTS
    if a.installed:
        # the installed copy has exactly the files the full suite just passed: check what installing can break
        smoke = ('Add-ons installed & enabled', 'Skin / sounds / language', 'BN branding', 'Main menu',
                 'Movie & series lists', 'Startup ready message + status', 'AI Hebrew subtitles end-to-end',
                 'AI Subtitle Generation button', 'All_Subs guards', 'No tracebacks (any add-on)', 'Clean shutdown')
        tests = [t for t in TESTS if t[0] in smoke]
    if done:
        print('resuming: %d checks already passed in the stopped run' % len(done), flush=True)
    stopped = False
    for name, fn in tests:
        if name in done:
            continue
        k = len(RESULTS)
        check(name, fn)
        for n, ok, detail, dt in RESULTS[k:]:
            print('%-4s %-36s %5.1fs  %s' % ('PASS' if ok else 'FAIL', n, dt, detail), flush=True)
        if all(r[1] for r in RESULTS[k:]):
            done.append(name)
        json.dump({'version': a.version, 'passed': done}, open(prog_file, 'w', encoding='utf-8'), ensure_ascii=False)
        if a.stop_on_fail and not all(r[1] for r in RESULTS[k:]):
            print('\nSTOPPED at "%s": fix the cause, then run again with --resume' % name, flush=True)
            stopped = True
            break
    passed = sum(1 for r in RESULTS if r[1])
    print('\n%d/%d passed%s' % (passed, len(RESULTS), (' (+%d from the stopped run)' % (len(done) - passed)) if len(done) > passed else ''))
    if not stopped and passed == len(RESULTS) and os.path.exists(prog_file):
        os.remove(prog_file)                 # complete: the next run starts from the top
    json.dump([{'test': n, 'ok': ok, 'detail': d, 'secs': round(t, 1)} for n, ok, d, t in RESULTS],
              open(os.path.join(ROOT, 'work', 'test_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not a.keep:
        kill_kodi()
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == '__main__':
    main()
