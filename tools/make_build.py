# -*- coding: utf-8 -*-
"""Assemble the NovaTV build zip.

Base: the Kodi-POV-IL FENtastic build (tested on Kodi 21) -> strip its wizard and
extras -> add NovaTV add-ons -> rewrite the home menu to
Movies / Series / TV Channels / Radio / NovaTV -> enable everything in Addons33.db.

  python tools/make_build.py [--version 0.1.0] [--gh-user USER]
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
STAGE = os.path.join(WORK, 'stage')
DIST = os.path.join(ROOT, 'dist')
BASE_TXT = 'https://raw.githubusercontent.com/MoranTheKing/Kodi-POV-IL/main/wizard/assets/build.txt'

REMOVE = ['repository.burekasKodi', 'repository.KodiRealDebridIsrael',   # dead: old schema / HTTP 404 at every start
          'plugin.program.kodipovilwizard', 'service.subtitles.kodipovilai', 'plugin.program.orderfavourites-hebrew',
          'service.xbmc.versioncheck', 'game.controller.snes', 'plugin.video.otaku', 'context.otaku', 'repository.otaku']
OUR_ADDONS = ['plugin.video.nova', 'repository.nova', 'plugin.program.novawizard', 'resource.uisounds.nova']
NOVA = 'plugin://plugin.video.nova/'

MENU = {  # include name -> (file, label, nova path, icon, id)
    'MoviesMainMenu': ('script-fentastic-main_menu_movies.xml', '$LOCALIZE[342]', '?a=media_root&amp;m=movie', 'movies.png', 'movies', 19000),
    'TVShowsMainMenu': ('script-fentastic-main_menu_tvshows.xml', '$LOCALIZE[20343]', '?a=media_root&amp;m=tv', 'tv.png', 'tvshows', 22000),
    'Custom1MainMenu': ('script-fentastic-main_menu_custom1.xml', '$LOCALIZE[19020]', '?a=tv_root', 'livetv.png', 'custom1', 23000),
    'Custom2MainMenu': ('script-fentastic-main_menu_custom2.xml', '$LOCALIZE[19021]', '?a=radio_root', 'radio.png', 'custom2', 24000),
    'Custom3MainMenu': ('script-fentastic-main_menu_custom3.xml', 'BN', '', 'favourites.png', 'custom3', 25000),
}
HIDE = ['homemenunomusicbutton', 'homemenunomusicvideobutton', 'homemenunotvbutton', 'homemenunoradiobutton',
        'homemenunogamesbutton', 'homemenunopicturesbutton', 'homemenunovideosbutton', 'homemenunoweatherbutton',
        'homemenunofavbutton']
SHOW = ['homemenunocustom1button', 'homemenunocustom2button', 'homemenunocustom3button',
        'homemenunomoviesbutton', 'homemenunotvshowsbutton']


# Kodi's mirror redirector sometimes sends to a mirror that times out: retry, then try fixed mirrors directly
KODI_MIRRORS = ['https://mirrors.kodi.tv', 'https://ftp.fau.de/xbmc', 'https://www.mirrorservice.org/sites/mirrors.xbmc.org',
                'https://mirror.accum.se/mirror/xbmc.org']


def download(url, timeout=60):
    urls = [url] + ([url.replace('https://mirrors.kodi.tv', m) for m in KODI_MIRRORS[1:]] if 'mirrors.kodi.tv' in url else [])
    err = None
    for attempt in range(2):
        for u in urls:
            try:
                return urllib.request.urlopen(u, timeout=timeout).read()
            except Exception as e:
                err = e
                print('   retry (%s): %s' % (e, u))
        time.sleep(10)
    raise err


def fetch(url, dest):
    if not os.path.exists(dest):
        print('download', url)
        data = download(url, timeout=120)
        with open(dest + '.part', 'wb') as f:
            f.write(data)
        os.replace(dest + '.part', dest)
    return dest


def base_zip():
    os.makedirs(WORK, exist_ok=True)
    txt = download(BASE_TXT).decode()
    url = re.search(r'url="([^"]+\.zip)"', txt).group(1)
    return fetch(url, os.path.join(WORK, os.path.basename(url))), url


def patch_menu(skin):
    xml = os.path.join(skin, 'xml')
    for inc, (fn, label, path, ic, mid, num) in MENU.items():
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n<includes>\n    <include name="%s">\n        <item>\n'
                '            <label>%s</label>\n'
                '            <onclick>ActivateWindow(Videos,%s%s,return)</onclick>\n'
                '            <property name="menu_id">$NUMBER[%d]</property>\n'
                '            <thumb>icons/sidemenu/%s</thumb>\n'
                '            <property name="id">%s</property>\n'
                '        </item>\n    </include>\n</includes>\n') % (inc, label, NOVA, path, num, ic, mid)
        with open(os.path.join(xml, fn), 'w', encoding='utf-8') as f:
            f.write(body)


def patch_skin_settings(path):
    with open(path, encoding='utf-8') as f:
        s = f.read()
    for sid, val in [(h, 'true') for h in HIDE] + [(h, 'false') for h in SHOW]:
        rx = re.compile(r'<setting id="%s" type="bool">[^<]*</setting>' % sid, re.I)
        line = '<setting id="%s" type="bool">%s</setting>' % (sid, val)
        s = rx.sub(line, s) if rx.search(s) else s.replace('<settings>', '<settings>\n    ' + line, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)


def patch_guisettings(path):
    with open(path, encoding='utf-8') as f:
        s = f.read()
    def setv(sid, val):
        nonlocal s
        rx = re.compile(r'<setting id="%s"[^>]*>[^<]*</setting>' % re.escape(sid))
        line = '<setting id="%s">%s</setting>' % (sid, val)
        s = rx.sub(line, s) if rx.search(s) else s.replace('</settings>', '    %s\n</settings>' % line)
    setv('lookandfeel.soundskin', 'resource.uisounds.nova')
    setv('pvrmanager.usebackendchannelnumbers', 'true')
    setv('pvrplayback.switchtofullscreenchanneltypes', '3')
    setv('videoplayer.autoplaynextitem', '0,1,2,3,4')      # continuous playback of episodes
    setv('subtitles.languages', 'Hebrew,English,Russian')
    setv('subtitles.charset', 'UTF-8')
    # a new video starts without subtitles: they are chosen (or generated) for that video, never carried over
    s = re.sub(r'<showsubtitles>\w+</showsubtitles>', '<showsubtitles>false</showsubtitles>', s)
    setv('locale.keyboardlayouts', 'Hebrew QWERTY|English QWERTY|Russian ЙЦУКЕН')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)


POV_SETTINGS = {
    'subtitles.subs_action': '0',           # base build stored "2" (invalid: Off|Auto) -> 7 warnings per start
    'auto_play_movie': 'true', 'auto_play_episode': 'true',          # calculated link choice, no list
    'autoplay_quality_movie': '720p, 1080p, 4K', 'autoplay_quality_episode': '720p, 1080p, 4K',
    'autoplay_next_episode': 'true', 'autoplay_next_show_window': 'true',
    'autoplay_next_check_threshold': '0',                             # keep playing; history logs each episode
    'autoscrape_next_episode': 'true',
    'results.language_filter': 'true', 'results.language': 'Hebrew',  # Hebrew-tagged releases first
    'results.size_filter': '1', 'results.size.speed': '25',           # skip files too heavy to start fast
    'results.include.unknown.size': 'true', 'filter.undesirables': 'true',
}


def patch_pov(path):
    with open(path, encoding='utf-8') as f:
        s = f.read()
    for sid, val in POV_SETTINGS.items():
        rx = re.compile(r'<setting id="%s"[^>]*?(?:/>|>[^<]*</setting>)' % re.escape(sid))
        line = '<setting id="%s">%s</setting>' % (sid, val)
        s = rx.sub(line, s) if rx.search(s) else s.replace('</settings>', '    %s\n</settings>' % line)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)


BRAND = os.path.join(ROOT, 'brand')

OMEGA = 'https://mirrors.kodi.tv/addons/omega'
PROVIDERS_PY = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'lib', 'providers.py')
STATUS_JSON = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'providers_status.json')
ON_DEMAND = {'plugin.video.plutotv'}      # pulls service.iptv.manager, which would take over our IPTV Simple set-up


def patch_pov_hub(stage):
    """POV tells NovaTV when it found nothing, so NovaTV can search every other source."""
    p = os.path.join(stage, 'addons', 'plugin.video.pov', 'resources', 'lib', 'modules', 'sources.py')
    s = open(p, encoding='utf-8').read()
    old = '\tdef _no_results(self):\n\t\thide_busy_dialog()\n'
    assert old in s, 'POV _no_results changed'
    s = s.replace(old, old + "\t\tset_property('nova.pov_noresults', '1')\n", 1)
    open(p, 'w', encoding='utf-8').write(s)


def patch_skin_search(skin):
    """the home-screen search button searches every source through NovaTV"""
    p = os.path.join(skin, 'xml', 'Home.xml')
    s = open(p, encoding='utf-8').read()
    hub = 'ActivateWindow(Videos,plugin://plugin.video.nova/?a=hub_search,return)'
    n = 0
    for old in ('ActivateWindow(1107)', 'RunScript(script.fentastic.helper,mode=search_input)',
                'RunScript(script.fentastic.helper,mode=open_search_window)'):
        n += s.count('value="%s"' % old)
        s = s.replace('value="%s"' % old, 'value="%s"' % hub)
    assert n >= 3, 'skin search buttons not found'
    open(p, 'w', encoding='utf-8').write(s)


PRESETS = {   # first-run prompts would block the hub's background searches
    'plugin.video.youtube': {'kodion.setup_wizard': 'false', 'kodion.setup_wizard.forced_runs': '1767970800',
                             'kodion.http.listen': '127.0.0.1'},   # 0.0.0.0 picks a link-local IP -> 403 on streams
    'plugin.video.archive.org': {'context': 'video'},
    'service.subtitles.All_Subs': {'telegram': 'false'},   # needs a personal Telegram login; opened a blocking dialog
}


def preset_settings(stage):
    for aid, vals in PRESETS.items():
        d = os.path.join(stage, 'userdata', 'addon_data', aid)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'settings.xml')
        s = open(p, encoding='utf-8').read() if os.path.exists(p) else '<settings version="2">\n</settings>\n'
        for sid, val in vals.items():
            rx = re.compile(r'<setting id="%s"[^>]*?(?:/>|>[^<]*</setting>)' % re.escape(sid))
            line = '<setting id="%s">%s</setting>' % (sid, val)
            s = rx.sub(line, s) if rx.search(s) else s.replace('</settings>', '    %s\n</settings>' % line)
        open(p, 'w', encoding='utf-8').write(s)


SKIN_SRC = os.path.join(ROOT, 'brand', 'skin')


def fix_startup(stage):
    """errors/warnings Kodi logged on every start of the base build"""
    xml = os.path.join(stage, 'addons', 'skin.fentastic', 'xml')
    for n in ('2', '3'):                      # empty include -> "Skin has invalid include"
        p = os.path.join(xml, 'script-fentastic-widget_custom%s.xml' % n)
        s = open(p, encoding='utf-8').read()
        s = re.sub(r'(<include name="Custom%sWidgets">)\s*(</include>)' % n,
                   lambda m: m.group(1) + '<control type="group" id="2%s999"><visible>false</visible></control>' % n + m.group(2), s)
        open(p, 'w', encoding='utf-8').write(s)
    inc = os.path.join(xml, 'Includes.xml')
    s = open(inc, encoding='utf-8').read()
    # windows listed as include files ("Root element <includes> required") and an include file named like a window
    for w in ('Custom_1118_SetupGuideViewer.xml', 'Custom_1119_ChangelogViewer.xml', 'Custom_1121_SearchResults.xml'):
        s = re.sub(r'\s*<include file="%s"\s*/>' % re.escape(w), '', s)
    if os.path.exists(os.path.join(xml, 'Custom_1117_ExtraInfoContent.xml')):
        os.replace(os.path.join(xml, 'Custom_1117_ExtraInfoContent.xml'), os.path.join(xml, 'Includes_ExtraInfoContent.xml'))
    s = s.replace('<include file="Custom_1117_ExtraInfoContent.xml"/>', '<include file="Includes_ExtraInfoContent.xml"/>')
    open(inc, 'w', encoding='utf-8').write(s)
    # All_Subs crashes a thread per source when a video has no IMDb id (YouTube, Archive, live TV)
    subs = os.path.join(stage, 'addons', 'service.subtitles.All_Subs', 'resources', 'sources')
    for d, _, files in os.walk(subs):
        for fn in files:
            if fn.endswith('.py'):
                p = os.path.join(d, fn)
                t = open(p, encoding='utf-8').read()
                t2 = re.sub(r'(?<![\w.(])imdb_id\.startswith\(', "(imdb_id or '').startswith(", t)
                if t2 != t:
                    open(p, 'w', encoding='utf-8').write(t2)
    adv = os.path.join(stage, 'userdata', 'advancedsettings.xml')
    if os.path.exists(adv):
        a = open(adv, encoding='utf-8').read()
        if '<advancedsettings>' in a:
            open(adv, 'w', encoding='utf-8').write(a.replace('<advancedsettings>', '<advancedsettings version="1.0">', 1))


def bn_skin(stage):
    """BN Details view (id 60) + modern background"""
    skin = os.path.join(stage, 'addons', 'skin.fentastic')
    xml = os.path.join(skin, 'xml')
    for f in ('View_60_BN.xml', 'Variables_BN.xml'):
        shutil.copy(os.path.join(SKIN_SRC, f), xml)
    shutil.copy(os.path.join(SKIN_SRC, 'bn_modern.jpg'), os.path.join(skin, 'extras', 'backgrounds'))
    inc = os.path.join(xml, 'Includes.xml')
    s = open(inc, encoding='utf-8').read()
    anchor = '<include file="script-fentastic-widget_movies.xml" />'
    if 'View_60_BN.xml' not in s:
        s = s.replace(anchor, '<include file="View_60_BN.xml" />\n\t<include file="Variables_BN.xml" />\n\t' + anchor, 1)
    open(inc, 'w', encoding='utf-8').write(s)
    for win in ('MyVideoNav.xml', 'MyPrograms.xml'):
        p = os.path.join(xml, win)
        if not os.path.exists(p):
            continue
        w = open(p, encoding='utf-8').read()
        w = re.sub(r'<views>([^<]*)</views>',
                   lambda m: m.group(0) if '60' in m.group(1).split(',') else '<views>60,%s</views>' % m.group(1), w, 1)
        if '<include>View_60_BN</include>' not in w:
            w = w.replace('<include>View_50_List</include>', '<include>View_60_BN</include>\n\t\t\t<include>View_50_List</include>', 1)
        open(p, 'w', encoding='utf-8').write(w)
    var = os.path.join(xml, 'Variables.xml')
    v = open(var, encoding='utf-8').read()
    bg = '<value>special://skin/extras/backgrounds/bn_modern.jpg</value>'
    v = v.replace('<value>special://skin/media/kodirdil/skin_backgrounds/lightning_bg1.jpg</value>', bg)
    home = v.index('<variable name="HomeFanartVar">')
    end = v.index('</variable>', home)
    if bg not in v[home:end]:
        v = v[:end] + '\t' + bg + '\n\t' + v[end:]
    open(var, 'w', encoding='utf-8').write(v)


def all_subs_guards(stage):
    """All_Subs never places a subtitle into another video and stops when Kodi quits (shared with the service)"""
    sys.path.insert(0, os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'lib'))
    import subspatch
    return subspatch.apply(os.path.join(stage, 'addons', 'service.subtitles.All_Subs')) + \
        subspatch.apply_plus(os.path.join(stage, 'addons', 'service.subtitles.all_subs_plus'))


def youtube_keystore(stage):
    """YouTube logged an OSError traceback on the first start (api_keys.json missing): ship its own default"""
    d = os.path.join(stage, 'userdata', 'addon_data', 'plugin.video.youtube')
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, 'api_keys.json')
    if not os.path.exists(p):
        json.dump({'keys': {'user': {'api_key': '', 'client_id': '', 'client_secret': ''}, 'developer': {}}},
                  open(p, 'w', encoding='utf-8'), indent=4)


def ai_subs_buttons(stage):
    """'AI Subtitle Generation' in every player style and in the subtitle window (shared with the service)"""
    sys.path.insert(0, os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'lib'))
    import skinpatch
    return skinpatch.apply(os.path.join(stage, 'addons', 'skin.fentastic', 'xml'))


def provider_addons():
    ids = re.findall(r"^\s+\('[\w]+', '(plugin\.video\.[\w.\-]+)'", open(PROVIDERS_PY, encoding='utf-8').read(), re.M)
    st = json.load(open(STATUS_JSON, encoding='utf-8')) if os.path.exists(STATUS_JSON) else {}
    bad = {v['addon'] for v in st.values() if not v.get('stable', True)}
    return [i for i in ids if i not in bad and i not in ON_DEMAND]


def add_providers(stage):
    """pre-install the stable providers + their dependencies from the official Kodi repository"""
    import gzip
    import xml.etree.ElementTree as ET
    cache = os.path.join(WORK, 'omega')
    os.makedirs(os.path.join(cache, 'zips'), exist_ok=True)
    idx = os.path.join(cache, 'addons.xml')
    if not os.path.exists(idx) or os.path.getsize(idx) < 1000 or time.time() - os.path.getmtime(idx) > 86400:
        data = gzip.decompress(download(OMEGA + '/addons.xml.gz'))     # download first: a failed one left an empty file
        with open(idx, 'wb') as f:
            f.write(data)
    repo = {a.get('id'): a for a in ET.parse(idx).getroot().findall('addon')}
    have = set(os.listdir(os.path.join(stage, 'addons')))
    added, todo = [], list(provider_addons())
    while todo:
        aid = todo.pop()
        if aid in have or aid.startswith('xbmc.') or aid.startswith('kodi.'):
            continue
        a = repo.get(aid)
        if a is None:
            print('   not in repo:', aid)
            continue
        meta = a.find("extension[@point='xbmc.addon.metadata']")
        plat = ((meta.findtext('platform') if meta is not None else '') or 'all').split()
        if 'all' not in plat and not ({'windows', 'windx', 'win64'} & set(plat) and {'android'} & set(plat)):
            print('   skipped (platforms %s): %s' % (','.join(plat), aid))
            continue
        ext = a.find("extension[@point='kodi.inputstream']")
        if ext is not None or a.find("extension[@point='xbmc.pvrclient']") is not None:
            continue            # binary add-ons are platform specific: Kodi installs them itself
        z = fetch('%s/%s/%s-%s.zip' % (OMEGA, aid, aid, a.get('version')),
                  os.path.join(cache, 'zips', '%s-%s.zip' % (aid, a.get('version'))))
        with zipfile.ZipFile(z) as zf:
            zf.extractall(os.path.join(stage, 'addons'))
        have.add(aid)
        added.append(aid)
        req = a.find('requires')
        for r in (req if req is not None else []):
            if r.get('optional') != 'true':
                todo.append(r.get('addon'))
    print('   providers + dependencies added:', len(added))
    return added


def apply_brand(stage):
    """BN logo everywhere: splash, skin logos, our add-on icons/fanart."""
    from shutil import copyfile
    skin = os.path.join(stage, 'addons', 'skin.fentastic', 'media')
    copyfile(os.path.join(BRAND, 'splash.jpg'), os.path.join(stage, 'media', 'splash.jpg'))
    copyfile(os.path.join(BRAND, 'bn_wordmark.png'), os.path.join(skin, 'kodirdil', 'group_logo', 'kodirdil-vendor_logo.png'))
    copyfile(os.path.join(BRAND, 'bn_mark_941.png'), os.path.join(skin, 'logos', 'K-logo.png'))
    copyfile(os.path.join(BRAND, 'icon.png'), os.path.join(skin, 'kodirdil', 'group_logo', 'kodirdil-logo.png'))
    copyfile(os.path.join(BRAND, 'bn_wordmark.png'), os.path.join(skin, 'logos', 'letters.png'))
    for ad in OUR_ADDONS:
        d = os.path.join(stage, 'addons', ad)
        copyfile(os.path.join(BRAND, 'icon_solid.png'), os.path.join(d, 'icon.png'))   # Kodi rule: solid icon
        copyfile(os.path.join(BRAND, 'fanart.jpg'), os.path.join(d, 'fanart.jpg'))


BINARY = ('pvr.iptvsimple', 'inputstream.adaptive')      # platform-specific: shipped per platform, never downloaded on the box
BINARY_OFF = ('pvr.iptvsimple',)          # NovaTV writes its settings first, then switches it on (iptv.configure_pvr)


def binary_zip(aid, platform):
    """download (with mirror fallback) the official build of a binary add-on for one platform"""
    import xml.etree.ElementTree as ET
    idx = os.path.join(WORK, 'omega', 'addons.xml')
    for a in ET.parse(idx).getroot().findall('addon'):
        if a.get('id') != aid:
            continue
        meta = a.find("extension[@point='xbmc.addon.metadata']")
        if meta is not None and (meta.findtext('platform') or '').strip() == platform:
            path = meta.findtext('path') or '%s+%s/%s-%s.zip' % (aid, platform, aid, a.get('version'))
            os.makedirs(os.path.join(WORK, 'omega', 'bin'), exist_ok=True)
            return fetch('%s/%s' % (OMEGA, path), os.path.join(WORK, 'omega', 'bin', path.replace('/', '_')))
    raise RuntimeError('%s: no %s build in the official repository' % (aid, platform))


def bundle_binary(stage, platform='windows-x86_64'):
    """Kodi's mirrors time out now and then: a box whose first start had to download the TV add-on stayed without TV.
    The build carries them (Windows here; make_apk swaps in the Android builds)."""
    for aid in BINARY:
        shutil.rmtree(os.path.join(stage, 'addons', aid), ignore_errors=True)
        with zipfile.ZipFile(binary_zip(aid, platform)) as z:
            z.extractall(os.path.join(stage, 'addons'))
    return list(BINARY)


def _ver(v):
    return tuple(int(x) for x in re.findall(r'\d+', v.split('+')[0])[:4])


def update_official(stage):
    """Every add-on of the base build that the official repository has in a newer version is updated here.
    Otherwise a new install downloads ~12 updates on its first start: slow start, and Kodi waits for them before it
    quits (40 s when a mirror hangs). Platform-independent add-ons only; binary ones come from bundle_binary."""
    import gzip
    import xml.etree.ElementTree as ET
    idx = os.path.join(WORK, 'omega', 'addons.xml')
    if not os.path.exists(idx) or os.path.getsize(idx) < 1000:
        with open(idx, 'wb') as f:
            f.write(gzip.decompress(download(OMEGA + '/addons.xml.gz')))
    repo = {}
    for a in ET.parse(idx).getroot().findall('addon'):
        meta = a.find("extension[@point='xbmc.addon.metadata']")
        plat = (meta.findtext('platform') if meta is not None else '') or 'all'
        if plat.strip() == 'all':
            repo[a.get('id')] = a.get('version')
    done = []
    # Kodi installs these itself on the first start when they are missing: ship them
    for aid in ('service.xbmc.versioncheck',):
        if aid in repo and not os.path.isdir(os.path.join(stage, 'addons', aid)):
            z = fetch('%s/%s/%s-%s.zip' % (OMEGA, aid, aid, repo[aid]),
                      os.path.join(WORK, 'omega', 'zips', '%s-%s.zip' % (aid, repo[aid])))
            with zipfile.ZipFile(z) as zf:
                zf.extractall(os.path.join(stage, 'addons'))
            done.append('%s (added) %s' % (aid, repo[aid]))
    for aid in sorted(os.listdir(os.path.join(stage, 'addons'))):
        ax = os.path.join(stage, 'addons', aid, 'addon.xml')
        if aid not in repo or aid in OUR_ADDONS or not os.path.exists(ax):
            continue
        m = re.search(r'<addon[^>]*\bversion="([^"]+)"', open(ax, encoding='utf-8', errors='ignore').read())
        if not m or _ver(repo[aid]) <= _ver(m.group(1)):
            continue
        z = fetch('%s/%s/%s-%s.zip' % (OMEGA, aid, aid, repo[aid]),
                  os.path.join(WORK, 'omega', 'zips', '%s-%s.zip' % (aid, repo[aid])))
        shutil.rmtree(os.path.join(stage, 'addons', aid))
        with zipfile.ZipFile(z) as zf:
            zf.extractall(os.path.join(stage, 'addons'))
        done.append('%s %s -> %s' % (aid, m.group(1), repo[aid]))
    print('   official add-ons updated in the build: %d' % len(done))
    for d in done:
        print('     ' + d)
    return done


def enable_addons(db, ids):
    c = sqlite3.connect(db)
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for a in REMOVE:
        c.execute('delete from installed where addonID=?', (a,))
    for a in ids:
        c.execute('insert or replace into installed (addonID, enabled, installDate, origin, disabledReason) '
                  'values (?, ?, ?, ?, 0)', (a, 0 if a in BINARY_OFF else 1, now,
                                             'repository.xbmc.org' if a in BINARY else 'repository.nova' if a != 'repository.nova' else ''))
    # drop the cached repository listings: they were fetched on Windows and point binary add-ons
    # (pvr.iptvsimple, inputstream.*) at Windows packages - Android then fails to install them.
    # Kodi re-reads every repository for its own platform on first start.
    for t in ('addons', 'addonlinkrepo', 'repo', 'package'):
        c.execute('delete from %s' % t)
    c.commit()
    c.execute('vacuum')
    c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='0.1.0')
    a = ap.parse_args()
    zpath, url = base_zip()
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(STAGE)
    for r in REMOVE:
        shutil.rmtree(os.path.join(STAGE, 'addons', r), ignore_errors=True)
        shutil.rmtree(os.path.join(STAGE, 'userdata', 'addon_data', r), ignore_errors=True)
    update_official(STAGE)
    for ad in OUR_ADDONS:
        dst = os.path.join(STAGE, 'addons', ad)
        shutil.copytree(os.path.join(ROOT, 'addons', ad), dst,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    patch_menu(os.path.join(STAGE, 'addons', 'skin.fentastic'))
    patch_skin_search(os.path.join(STAGE, 'addons', 'skin.fentastic'))
    fix_startup(STAGE)
    bn_skin(STAGE)
    ai_subs_buttons(STAGE)
    all_subs_guards(STAGE)
    youtube_keystore(STAGE)
    patch_pov_hub(STAGE)
    extra = add_providers(STAGE) + bundle_binary(STAGE)
    preset_settings(STAGE)
    apply_brand(STAGE)
    patch_skin_settings(os.path.join(STAGE, 'userdata', 'addon_data', 'skin.fentastic', 'settings.xml'))
    patch_guisettings(os.path.join(STAGE, 'userdata', 'guisettings.xml'))
    patch_pov(os.path.join(STAGE, 'userdata', 'addon_data', 'plugin.video.pov', 'settings.xml'))
    enable_addons(os.path.join(STAGE, 'userdata', 'Database', 'Addons33.db'), OUR_ADDONS + extra)
    with open(os.path.join(STAGE, 'userdata', 'novatv_build.txt'), 'w') as f:
        f.write('NovaTV %s\nbase: %s\nbuilt: %s\n' % (a.version, url, time.ctime()))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, 'NovaTV-%s.zip' % a.version)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, _, files in os.walk(STAGE):
            for fn in files:
                full = os.path.join(d, fn)
                z.write(full, os.path.relpath(full, STAGE).replace(os.sep, '/'))
    print('built', out, '%.1f MB' % (os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
