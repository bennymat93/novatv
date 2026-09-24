# -*- coding: utf-8 -*-
"""Backup / restore of everything personal: accounts, history, favourites, IPTV, settings."""
import os
import time
import zipfile

import xbmc
import xbmcgui
import xbmcvfs

from .common import T, PROFILE, log

USERDATA = xbmcvfs.translatePath('special://profile/')
ADDON_DATA = ['plugin.video.nova', 'plugin.video.pov', 'pvr.iptvsimple', 'service.subtitles.All_Subs',
              'service.subtitles.all_subs_plus', 'plugin.video.youtube', 'skin.fentastic', 'script.module.magneto']
FILES = ['favourites.xml', 'sources.xml', 'passwords.xml', 'mediasources.xml']
SKIP = ('cache', 'cache.db', 'Thumbnails', 'temp', 'packages', '.tmp')
AUTO_DIR = os.path.join(PROFILE, 'backups')


def _members():
    for a in ADDON_DATA:
        base = os.path.join(USERDATA, 'addon_data', a)
        for d, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in SKIP and not (a == 'plugin.video.nova' and x == 'backups')]
            for fn in files:
                if not fn.endswith(SKIP):
                    full = os.path.join(d, fn)
                    yield full, os.path.relpath(full, USERDATA)
    for fn in FILES:
        p = os.path.join(USERDATA, fn)
        if os.path.exists(p):
            yield p, fn


def make_zip(path):
    n = 0
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('bn_backup.txt', 'BN Stream backup %s\n' % time.ctime())
        for full, arc in _members():
            try:
                z.write(full, arc.replace(os.sep, '/'))
                n += 1
            except Exception as e:
                log('backup skip %s: %s' % (arc, e), xbmc.LOGWARNING)
    return n


def backup():
    d = xbmcgui.Dialog()
    dest = d.browse(3, T('bk_where'), 'files', '', False, False, '')   # 3 = writeable folder
    if not dest:
        return
    name = 'BN-backup-%s.zip' % time.strftime('%Y%m%d-%H%M')
    tmp = os.path.join(xbmcvfs.translatePath('special://temp/'), name)
    n = make_zip(tmp)
    target = dest.rstrip('/\\') + ('/' if '://' in dest else os.sep) + name
    ok = xbmcvfs.copy(tmp, target)
    os.remove(tmp)
    if ok:
        d.ok('BN', '%s\n%s\n(%d %s)' % (T('bk_done'), target, n, T('bk_files')))
    else:
        d.ok('BN', '%s\n%s' % (T('bk_fail'), target))


def auto_backup(keep=3, every_days=7):
    """Weekly local safety copy (called by the service)."""
    os.makedirs(AUTO_DIR, exist_ok=True)
    existing = sorted(f for f in os.listdir(AUTO_DIR) if f.endswith('.zip'))
    if existing and time.time() - os.path.getmtime(os.path.join(AUTO_DIR, existing[-1])) < every_days * 86400:
        return
    make_zip(os.path.join(AUTO_DIR, 'BN-auto-%s.zip' % time.strftime('%Y%m%d-%H%M')))
    for old in sorted(f for f in os.listdir(AUTO_DIR) if f.endswith('.zip'))[:-keep]:
        os.remove(os.path.join(AUTO_DIR, old))


def restore():
    d = xbmcgui.Dialog()
    autos = sorted((f for f in os.listdir(AUTO_DIR) if f.endswith('.zip')), reverse=True) if os.path.isdir(AUTO_DIR) else []
    choices = [T('bk_pick')] + ['%s  (%s)' % (T('bk_auto'), f[8:21]) for f in autos]
    i = d.select(T('restore'), choices)
    if i < 0:
        return
    if i == 0:
        src = d.browse(1, T('restore'), 'files', '.zip', False, False, '')
        if not src:
            return
        local = os.path.join(xbmcvfs.translatePath('special://temp/'), 'bn_restore.zip')
        if not xbmcvfs.copy(src, local):
            d.ok('BN', T('bk_fail'))
            return
    else:
        local = os.path.join(AUTO_DIR, autos[i - 1])
    try:
        with zipfile.ZipFile(local) as z:
            if 'bn_backup.txt' not in z.namelist():
                d.ok('BN', T('bk_invalid'))
                return
            if not d.yesno('BN', T('bk_confirm')):
                return
            for m in z.namelist():
                if m == 'bn_backup.txt' or m.startswith('/') or '..' in m:
                    continue
                z.extract(m, USERDATA)
    except zipfile.BadZipFile:
        d.ok('BN', T('bk_invalid'))
        return
    d.ok('BN', T('bk_restored'))
    os._exit(1)     # restart without Kodi rewriting the restored files
