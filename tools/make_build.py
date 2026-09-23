# -*- coding: utf-8 -*-
"""Assemble the NovaTV build zip.

Base: the Kodi-POV-IL FENtastic build (tested on Kodi 21) -> strip its wizard and
extras -> add NovaTV add-ons -> rewrite the home menu to
Movies / Series / TV Channels / Radio / NovaTV -> enable everything in Addons33.db.

  python tools/make_build.py [--version 0.1.0] [--gh-user USER]
"""
import argparse
import os
import re
import shutil
import sqlite3
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
STAGE = os.path.join(WORK, 'stage')
DIST = os.path.join(ROOT, 'dist')
BASE_TXT = 'https://raw.githubusercontent.com/MoranTheKing/Kodi-POV-IL/main/wizard/assets/build.txt'

REMOVE = ['plugin.program.kodipovilwizard', 'service.subtitles.kodipovilai', 'plugin.program.orderfavourites-hebrew',
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


def fetch(url, dest):
    if not os.path.exists(dest):
        print('download', url)
        urllib.request.urlretrieve(url, dest)
    return dest


def base_zip():
    os.makedirs(WORK, exist_ok=True)
    txt = urllib.request.urlopen(BASE_TXT).read().decode()
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
    setv('locale.keyboardlayouts', 'Hebrew QWERTY|English QWERTY|Russian ЙЦУКЕН')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)


POV_SETTINGS = {
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
        copyfile(os.path.join(BRAND, 'icon.png'), os.path.join(d, 'icon.png'))
        copyfile(os.path.join(BRAND, 'fanart.jpg'), os.path.join(d, 'fanart.jpg'))


def enable_addons(db, ids):
    c = sqlite3.connect(db)
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for a in REMOVE:
        c.execute('delete from installed where addonID=?', (a,))
    for a in ids:
        c.execute('insert or replace into installed (addonID, enabled, installDate, origin, disabledReason) '
                  'values (?, 1, ?, ?, 0)', (a, now, 'repository.nova' if a != 'repository.nova' else ''))
    c.commit()
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
    for ad in OUR_ADDONS:
        dst = os.path.join(STAGE, 'addons', ad)
        shutil.copytree(os.path.join(ROOT, 'addons', ad), dst,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    patch_menu(os.path.join(STAGE, 'addons', 'skin.fentastic'))
    apply_brand(STAGE)
    patch_skin_settings(os.path.join(STAGE, 'userdata', 'addon_data', 'skin.fentastic', 'settings.xml'))
    patch_guisettings(os.path.join(STAGE, 'userdata', 'guisettings.xml'))
    patch_pov(os.path.join(STAGE, 'userdata', 'addon_data', 'plugin.video.pov', 'settings.xml'))
    enable_addons(os.path.join(STAGE, 'userdata', 'Database', 'Addons33.db'), OUR_ADDONS)
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
