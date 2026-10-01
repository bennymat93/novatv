# -*- coding: utf-8 -*-
"""Binary add-ons for THIS device (1.4.3).

Root cause of "YouTube does not play on iPhone / iPad": the build zip (wizard / link install) carries the Windows
builds of inputstream.adaptive and pvr.iptvsimple (<platform>windows-x86_64</platform>). Kodi on iOS / tvOS / macOS /
Linux does not load them; the service only installed an add-on when its folder was missing - it was not, so nothing
happened, and plugin.video.youtube (MPEG-DASH through inputstream.adaptive) could not play.

ensure(): a binary add-on whose <platform> does not fit this device is removed and installed again from the official
Kodi repository (Android, macOS, Windows builds) - or, on iOS / tvOS / Linux where Kodi ships these add-ons
built in, simply removed so Kodi's own copy is used again (the Windows copy in the user folder overrode it). If inputstream.adaptive is still not
available, nothing can replace it: YouTube's plain streams no longer play (tested 01/10/2026).
platform_fits() is plain Python for tests.
"""
import os
import re
import shutil

BINARY = ('inputstream.adaptive', 'pvr.iptvsimple')


def platform_fits(tags, plat, arch=''):
    """tags: the add-on's <platform> value ('windows-x86_64', 'android-aarch64 android-armv7', 'all', ...);
    plat: windows / android / ios / tvos / osx / linux"""
    tags = (tags or 'all').lower().split()
    for t in tags:
        if t == 'all' or t == plat:
            return True
        if t.startswith(plat + '-') and (not arch or arch in t or plat in ('ios', 'tvos')):
            return True
        if plat == 'windows' and t.startswith('windowsstore'):
            return True
    return False


def current_platform():
    import platform as _p
    import xbmc
    for name, cond in (('windows', 'Windows'), ('android', 'Android'), ('tvos', 'TVOS'), ('ios', 'IOS'),
                       ('osx', 'OSX'), ('linux', 'Linux')):
        if xbmc.getCondVisibility('System.Platform.' + cond):
            m = (_p.machine() or '').lower()
            arch = 'aarch64' if m in ('arm64', 'aarch64') else 'armv7' if m.startswith('arm') else 'x86_64' if '64' in m else ''
            return name, arch
    return 'other', ''


def _platform_tag(addon_dir):
    try:
        text = open(os.path.join(addon_dir, 'addon.xml'), encoding='utf-8', errors='ignore').read()
    except OSError:
        return None
    m = re.search(r'<platform>([^<]*)</platform>', text)
    return m.group(1).strip() if m else 'all'


def _rpc(method, **params):
    import json
    import xbmc
    return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))


def ensure(log):
    import xbmc
    import xbmcvfs
    from .iptv import install_addon
    plat, arch = current_platform()
    home = xbmcvfs.translatePath('special://home/addons')
    for aid in BINARY:
        d = os.path.join(home, aid)
        tag = _platform_tag(d)
        wrong = tag is not None and not platform_fits(tag, plat, arch)
        if wrong:
            log('%s: build for "%s" on this %s device - replacing it from the Kodi repository' % (aid, tag, plat))
            shutil.rmtree(d, ignore_errors=True)
            xbmc.executebuiltin('UpdateLocalAddons')
            xbmc.sleep(3000)
        builtin = os.path.isdir(os.path.join(xbmcvfs.translatePath('special://xbmc/addons'), aid))
        if builtin:
            # iOS / tvOS (and Linux distro packages) ship it inside Kodi itself - the repository has no build for
            # them; the Windows copy in the user folder had overridden it. Make sure the built-in one is on.
            _rpc('Addons.SetAddonEnabled', addonid=aid, enabled=True)
        elif wrong or not xbmc.getCondVisibility('System.HasAddon(%s)' % aid):
            log('installing %s for %s: %s' % (aid, plat, install_addon(aid)))
    youtube_mode(log)


def youtube_mode(log):
    """YouTube (2026) plays only through inputstream.adaptive - tested: its plain streams fail ("Error creating
    demuxer"), so there is no fallback; make sure YouTube uses it, and say so in the log when it is missing"""
    import xbmc
    import xbmcaddon
    if not xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
        return
    if not xbmc.getCondVisibility('System.AddonIsEnabled(inputstream.adaptive)'):
        log('YouTube cannot play: inputstream.adaptive is not available on this device', xbmc.LOGWARNING)
        return
    yt = xbmcaddon.Addon('plugin.video.youtube')
    if yt.getSetting('kodion.video.quality.isa') != 'true' or yt.getSetting('kodion.mpd.videos') != 'true':
        yt.setSetting('kodion.video.quality.isa', 'true')
        yt.setSetting('kodion.mpd.videos', 'true')
        log('YouTube: MPEG-DASH via inputstream.adaptive restored')
