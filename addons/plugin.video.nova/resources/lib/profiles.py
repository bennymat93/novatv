# -*- coding: utf-8 -*-
"""Device profiles + first-run wizard (docs/DEVICE_PROFILES.md has the table and the reasoning).

The viewer picks the device type once (first start after installation, or later in BN > Settings > Device type);
the profile is applied at once through Kodi's own settings (JSON-RPC Settings.SetSettingValue) and the skin's
touch mode. Cache values scale with the device memory (System.Memory(total)). plan() is pure Python for tests.
"""
import json

ORDER = ('tv', 'pc', 'touch', 'car', 'phone', 'tablet')
LABELS = {
    'tv': ('טלוויזיה / סטרימר עם שלט (Android TV)', 'TV / streaming box with remote (Android TV)'),
    'pc': ('מחשב סטנדרטי או נייד', 'Desktop / laptop computer'),
    'touch': ('מכשיר עם מסך מגע', 'Touch-screen device'),
    'car': ('מסך מולטימדיה ברכב', 'Car multimedia screen'),
    'phone': ('סמארטפון', 'Smartphone'),
    'tablet': ('טאבלט', 'Tablet'),
}
# skinzoom: % added to the skin (bigger targets / text); touch: skin touch mode (on-screen Back, drag scrolling);
# mouse: pointer input; saver: screensaver minutes (0 = never); dim: dim on pause; refresh: switch the display
# refresh rate to the video's (smooth motion on TVs, off where switching blanks the screen or is impossible);
# buffer: seconds of video to read ahead (readfactor) - more on flaky mobile links
PROFILES = {
    'tv':     {'skinzoom': 0,  'touch': False, 'mouse': False, 'saver': 10, 'dim': True,  'refresh': True,  'readfactor': 400},
    'pc':     {'skinzoom': 0,  'touch': False, 'mouse': True,  'saver': 10, 'dim': True,  'refresh': False, 'readfactor': 400},
    'touch':  {'skinzoom': 6,  'touch': True,  'mouse': True,  'saver': 15, 'dim': True,  'refresh': False, 'readfactor': 400},
    'car':    {'skinzoom': 12, 'touch': True,  'mouse': True,  'saver': 0,  'dim': False, 'refresh': False, 'readfactor': 1000},
    'phone':  {'skinzoom': 10, 'touch': True,  'mouse': True,  'saver': 5,  'dim': True,  'refresh': False, 'readfactor': 1000},
    'tablet': {'skinzoom': 6,  'touch': True,  'mouse': True,  'saver': 10, 'dim': True,  'refresh': False, 'readfactor': 500},
}


MEMSIZES = (16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)


def cache_mb(total_ram_mb, profile):
    """video cache in MB (Kodi uses ~3x this in RAM): a fifth of the memory, 64..512 MB; cars and phones
    lean on the cache harder (tunnels, cell hand-overs)"""
    part = 4 if profile in ('car', 'phone') else 5
    want = max(64, min(512, (total_ram_mb or 2048) // part // 3))
    return max(v for v in MEMSIZES if v <= want)     # Kodi accepts only its own list of sizes


def plan(profile, total_ram_mb, platform):
    """-> {kodi setting id: value} + skin touch flag for this device"""
    p = PROFILES[profile]
    s = {
        'lookandfeel.skinzoom': p['skinzoom'],
        'input.enablemouse': p['mouse'],
        'screensaver.mode': '' if p['saver'] == 0 else 'screensaver.xbmc.builtin.dim',
        'screensaver.usedimonpause': p['dim'],
        'screensaver.disableforaudio': True,
        'filecache.buffermode': 4,                  # buffer every network file system (streams included)
        'filecache.memorysize': cache_mb(total_ram_mb, profile),
        'filecache.readfactor': p['readfactor'],
        'videoplayer.adjustrefreshrate': 2 if p['refresh'] else 0,   # 2 = on start/stop, 0 = off
    }
    if p['saver']:
        s['screensaver.time'] = p['saver']
    if platform == 'windows':
        s['videoplayer.usedxva2'] = True            # hardware decoding
    elif platform == 'android':
        s['videoplayer.usemediacodec'] = True
        s['videoplayer.usemediacodecsurface'] = True
    return s, p['touch']


# ------------------------------------------------------------ Kodi
def _rpc(method, **params):
    import xbmc
    return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))


def label(profile, lang='he'):
    return LABELS.get(profile, ('—', '—'))[0 if lang == 'he' else 1]


def current():
    from .common import ADDON
    return ADDON.getSetting('device_profile')


def platform():
    import xbmc
    for k, cond in (('windows', 'Windows'), ('android', 'Android'), ('osx', 'OSX'), ('ios', 'IOS'), ('tvos', 'TVOS'),
                    ('linux', 'Linux')):
        if xbmc.getCondVisibility('System.Platform.' + cond):
            return k
    return 'other'


def ram_mb():
    import re
    import xbmc
    m = re.search(r'(\d+)', xbmc.getInfoLabel('System.Memory(total)').replace(',', ''))
    return int(m.group(1)) if m else 2048


def apply(profile):
    import xbmc
    from .common import ADDON, log
    settings, touch = plan(profile, ram_mb(), platform())
    bad = []
    for k, v in settings.items():
        r = _rpc('Settings.SetSettingValue', setting=k, value=v)
        if 'error' in r:
            bad.append(k)
    xbmc.executebuiltin('Skin.%s(touchmode)' % ('SetBool' if touch else 'Reset'))
    ADDON.setSetting('device_profile', profile)
    log('device profile %s applied (%d settings%s)' % (profile, len(settings), ', not accepted: %s' % bad if bad else ''))
    return bad


def suggest():
    """a sensible first choice: Android TV boxes have no touch screen, Windows is a PC, other Android is a phone"""
    import xbmc
    p = platform()
    if p == 'android':
        return 'tv' if xbmc.getCondVisibility('System.Platform.Android.TV') or not xbmc.getCondVisibility('System.HasTouch') else 'phone'
    return 'pc' if p in ('windows', 'osx', 'linux') else 'tv'


def wizard(force=False):
    """first start (no profile yet) or from Settings: choose, apply at once"""
    import xbmcgui
    from .common import ui_lang
    if current() and not force:
        return
    lang = 'he' if ui_lang() == 'he' else 'en'
    title = 'BN Stream – ' + ('איזה מכשיר זה?' if lang == 'he' else 'Which device is this?')
    first = suggest()
    options = sorted(ORDER, key=lambda k: k != first)
    i = xbmcgui.Dialog().select(title, [label(k, lang) for k in options], preselect=0)
    if i < 0:
        if not current():
            apply(first)            # closed without choosing: the suggestion, changeable in Settings
        return
    apply(options[i])
    xbmcgui.Dialog().notification('BN Stream', label(options[i], lang), xbmcgui.NOTIFICATION_INFO, 3000)
