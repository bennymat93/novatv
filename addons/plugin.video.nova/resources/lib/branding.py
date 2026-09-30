# -*- coding: utf-8 -*-
"""BN Stream name and logo when the build was installed into a plain Kodi (file-manager link / repository).

What an add-on can and cannot do: the launcher name and icon belong to the Kodi app (on Android they are fixed in
its APK), so they cannot be renamed from inside. What this does, once per version, from the service:
  1. every device: the BN splash screen (Kodi shows special://home/media/splash.jpg instead of its own)
  2. Windows: "BN Stream" shortcuts with the BN icon on the desktop and in the Start menu, opening this Kodi
  3. Android (a plain Kodi, not our org.bn.stream app): one offer to install the BN Stream app (BN name + icon on
     the home screen); the viewer decides, a backup is made first so nothing is lost
The APK and the Windows installer already carry the name and logo; there only step 1 runs (harmless).
"""
import os
import shutil
import subprocess

import xbmc
import xbmcgui
import xbmcvfs

from .common import ADDON, MEDIA, log

SITE = 'https://bennymat93.github.io/novatv/'
STR = {
    'offer_t': ('BN Stream', 'BN Stream'),
    'offer': ('הבילד מותקן בתוך Kodi רגיל, ולכן במסך הבית של המכשיר מופיעים השם והסמל של Kodi.[CR]'
              'להתקין את אפליקציית BN Stream (אותו תוכן, עם השם והלוגו של BN)?[CR]'
              'לפני המעבר יבוצע גיבוי של ההגדרות, המועדפים וההיסטוריה.',
              'The build runs inside plain Kodi, so the device home screen shows the Kodi name and icon.[CR]'
              'Install the BN Stream app (same content, with the BN name and logo)?[CR]'
              'Your settings, favourites and history are backed up first.'),
    'yes': ('התקן', 'Install'), 'no': ('לא עכשיו', 'Not now'),
    'how': ('דף ההורדה נפתח. הורידו את BN Stream לאנדרואיד והתקינו. הגיבוי נמצא ב-BN > גיבוי ושחזור.',
            'The download page is open. Download BN Stream for Android and install it. The backup is in BN > Backup & restore.'),
}


def _s(k):
    from .common import ui_lang
    return STR[k][0 if ui_lang() == 'he' else 1]


def splash():
    """Kodi prefers special://home/media/splash.jpg over its own"""
    dst = xbmcvfs.translatePath('special://home/media')
    os.makedirs(dst, exist_ok=True)
    src = os.path.join(MEDIA, 'bn_splash.jpg')
    for name in ('splash.jpg', 'splash.png'):
        target = os.path.join(dst, name)
        if name.endswith('.png'):
            try:
                from PIL import Image                  # not always available inside Kodi: jpg alone is enough
                Image.open(src).save(target)
            except Exception:
                pass
        elif not os.path.exists(target) or os.path.getsize(target) != os.path.getsize(src):
            shutil.copyfile(src, target)


def _is_our_app():
    """our APK (org.bn.stream) or our Windows installer (folder "BN Stream"): the name and logo are already BN"""
    xbmc_path = xbmcvfs.translatePath('special://xbmc')
    return 'org.bn.stream' in xbmc_path or 'bn stream' in xbmc_path.lower()


def windows_shortcuts():
    """desktop + Start-menu "BN Stream" shortcuts to this Kodi (portable when it runs portable), BN icon"""
    exe = os.path.join(xbmcvfs.translatePath('special://xbmc'), 'kodi.exe')
    if 'testkodi' in exe.lower():          # the build machine's test copy never touches the desktop
        return False
    if not os.path.exists(exe):
        return False
    ico_dir = xbmcvfs.translatePath('special://home/media')
    os.makedirs(ico_dir, exist_ok=True)
    ico = os.path.join(ico_dir, 'bn.ico')
    shutil.copyfile(os.path.join(MEDIA, 'bn.ico'), ico)
    portable = 'portable_data' in xbmcvfs.translatePath('special://home')
    places = [os.path.join(os.path.expanduser('~'), 'Desktop'),
              os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')]
    ps = []
    for folder in places:
        if not os.path.isdir(folder):
            continue
        lnk = os.path.join(folder, 'BN Stream.lnk')
        ps.append("$s=$w.CreateShortcut('%s');$s.TargetPath='%s';$s.Arguments='%s';$s.WorkingDirectory='%s';"
                  "$s.IconLocation='%s';$s.Description='BN Stream';$s.Save()"
                  % (lnk.replace("'", "''"), exe.replace("'", "''"), '-p' if portable else '',
                     os.path.dirname(exe).replace("'", "''"), ico.replace("'", "''")))
    if not ps:
        return False
    cmd = '$w=New-Object -ComObject WScript.Shell;' + ';'.join(ps)
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd], timeout=30,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return True


def android_offer():
    """one offer per install (setting brand_offer); yes -> backup, then open the download page"""
    if ADDON.getSetting('brand_offer') == 'done':
        return
    ADDON.setSetting('brand_offer', 'done')
    if not xbmcgui.Dialog().yesno(_s('offer_t'), _s('offer').replace('[CR]', '\n'), nolabel=_s('no'), yeslabel=_s('yes')):
        return
    try:
        from . import backup
        from .common import PROFILE
        backup.make_zip(os.path.join(PROFILE, 'before_bn_app.zip'))
    except Exception as e:
        log('backup before app switch: %s' % e, xbmc.LOGWARNING)
    xbmc.executebuiltin('StartAndroidActivity(,android.intent.action.VIEW,,%s)' % SITE)
    xbmcgui.Dialog().ok(_s('offer_t'), _s('how'))


def apply():
    """service: once per add-on version"""
    ver = ADDON.getAddonInfo('version')
    if ADDON.getSetting('brand_ver') == ver:
        return
    try:
        splash()
    except Exception as e:
        log('branding splash: %s' % e, xbmc.LOGWARNING)
    if not _is_our_app():
        try:
            if xbmc.getCondVisibility('System.Platform.Windows'):
                windows_shortcuts()
            elif xbmc.getCondVisibility('System.Platform.Android'):
                android_offer()
        except Exception as e:
            log('branding: %s' % e, xbmc.LOGWARNING)
    ADDON.setSetting('brand_ver', ver)
