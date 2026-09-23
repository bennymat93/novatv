# -*- coding: utf-8 -*-
"""One screen for every login / key, with a live test and a clear fix hint."""
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from .common import ADDON, T, load, ui_lang

HINTS = {
    'rd': ('היכנס ל-real-debrid.com/device והזן את הקוד שיופיע. ודא שהמנוי בתוקף.',
           'Open real-debrid.com/device and enter the code shown. Make sure the subscription is active.',
           'Откройте real-debrid.com/device и введите показанный код. Проверьте, что подписка активна.'),
    'trakt': ('היכנס ל-trakt.tv/activate והזן את הקוד.', 'Open trakt.tv/activate and enter the code.',
              'Откройте trakt.tv/activate и введите код.'),
    'tmdb': ('אופציונלי. מפתח חינמי ב-themoviedb.org/settings/api', 'Optional. Free key at themoviedb.org/settings/api',
             'Необязательно. Бесплатный ключ: themoviedb.org/settings/api'),
    'gemini': ('אופציונלי. מפתח חינמי ב-aistudio.google.com. בלעדיו התרגום ימשיך בשרת המקומי.',
               'Optional. Free key at aistudio.google.com. Without it translation continues via the local server.',
               'Необязательно. Бесплатный ключ: aistudio.google.com. Без него перевод идёт через локальный сервер.'),
    'server': ('הפעל את NovaTV Subtitle Server במחשב וודא ששני המכשירים באותה רשת. כתובת: http://IP-של-המחשב:8765',
               'Start the NovaTV Subtitle Server on the PC and make sure both devices are on the same network. Address: http://PC-IP:8765',
               'Запустите NovaTV Subtitle Server на ПК; оба устройства должны быть в одной сети. Адрес: http://IP-ПК:8765'),
    'iptv': ('הוסף קישור M3U וקישור EPG מספק ה-IPTV. אם מופיעים רק ערוצי Demo – המנוי אינו פעיל.',
             'Add the M3U and EPG links from your IPTV provider. If only "Demo" channels appear, the subscription is not active.',
             'Добавьте ссылки M3U и EPG от провайдера. Если видны только каналы «Demo» - подписка не активна.'),
}


def hint(k):
    return HINTS[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def _pov(setting):
    try:
        return xbmcaddon.Addon('plugin.video.pov').getSetting(setting)
    except Exception:
        return ''


def check(k):
    """Returns (ok: bool|None, detail). None = not configured."""
    import requests
    try:
        if k == 'rd':
            tok = _pov('rd.token')
            if not tok:
                return None, ''
            r = requests.get('https://api.real-debrid.com/rest/1.0/user', headers={'Authorization': 'Bearer ' + tok}, timeout=10)
            if r.status_code != 200:
                return False, 'HTTP %d' % r.status_code
            u = r.json()
            days = max(0, int((time.mktime(time.strptime(u['expiration'][:10], '%Y-%m-%d')) - time.time()) / 86400)) if u.get('expiration') else 0
            if u.get('type') != 'premium':
                return False, 'account is not premium'
            return True, '%s · premium %d days' % (u.get('username'), days)
        if k == 'trakt':
            return (True, _pov('trakt_user')) if _pov('trakt.token') else (None, '')
        if k == 'tmdb':
            key = ADDON.getSetting('tmdb_key')
            if not key:
                return (True, 'using built-in token') if _pov('tmdb_read_token') else (None, '')
            r = requests.get('https://api.themoviedb.org/3/configuration', params={'api_key': key}, timeout=10)
            return (r.status_code == 200, 'OK' if r.status_code == 200 else 'invalid key (HTTP %d)' % r.status_code)
        if k == 'gemini':
            key = ADDON.getSetting('gemini_key')
            if not key:
                return None, ''
            r = requests.get('https://generativelanguage.googleapis.com/v1beta/models', params={'key': key}, timeout=10)
            return (r.status_code == 200, 'OK' if r.status_code == 200 else 'HTTP %d' % r.status_code)
        if k == 'server':
            base = ADDON.getSetting('sub_server').rstrip('/')
            r = requests.get(base + '/health', timeout=4)
            j = r.json()
            return True, '%s · %s' % (j.get('device'), j.get('model'))
        if k == 'iptv':
            st = load('iptv_status.json', {})
            if not load('iptv.json', {}).get('m3u'):
                return None, ''
            if st.get('errors'):
                return False, '; '.join(st['errors'])[:120]
            return (st.get('channels', 0) > 0, '%s %s' % (st.get('channels', 0), T('channels')))
    except Exception as e:
        return False, str(e)[:120]
    return None, ''


ROWS = [('rd', 'Real-Debrid'), ('trakt', 'Trakt'), ('iptv', 'IPTV (M3U + EPG)'), ('server', 'AI Subtitle Server'),
        ('gemini', 'Gemini AI'), ('tmdb', 'TMDb')]


def screen(handle, url):
    for k, name in ROWS:
        ok, detail = check(k)
        if ok:
            status = '[COLOR limegreen]● %s[/COLOR]' % T('ok')
        elif ok is None:
            status = '[COLOR grey]○ %s[/COLOR]' % T('missing')
        else:
            status = '[COLOR red]✖ %s[/COLOR]' % T('error')
        li = xbmcgui.ListItem('%s   %s' % (name, status))
        plot = detail or ''
        if not ok:
            plot = (detail + '\n\n' if detail else '') + hint(k)
        li.getVideoInfoTag().setPlot(plot)
        li.setLabel2(detail)
        li.setArt({'icon': 'DefaultAddonService.png'})
        xbmcplugin.addDirectoryItem(handle, url(a='acc', do=k), li, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def action(k):
    d = xbmcgui.Dialog()
    if k in ('rd', 'trakt'):
        xbmc.executebuiltin('RunPlugin(plugin://plugin.video.pov/?mode=myservices)', True)
    elif k == 'iptv':
        from . import iptv
        iptv.edit_sources()
    elif k in ('gemini', 'tmdb'):
        sid = k + '_key'
        v = d.input(k.upper() + ' key', ADDON.getSetting(sid))
        ADDON.setSetting(sid, v.strip())
    elif k == 'server':
        v = d.input('http://PC-IP:8765', ADDON.getSetting('sub_server'))
        if v:
            ADDON.setSetting('sub_server', v.strip())
    ok, detail = check(k)
    if ok:
        d.notification('NovaTV', '%s ✓ %s' % (T('ok'), detail), xbmcgui.NOTIFICATION_INFO, 4000)
    elif ok is False:
        d.ok('NovaTV – ' + T('error'), '%s\n\n%s' % (detail, hint(k)))
    xbmc.executebuiltin('Container.Refresh')
