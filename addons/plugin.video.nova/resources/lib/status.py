# -*- coding: utf-8 -*-
"""System status: add-ons, services and how much content is available.

Shown once Kodi has fully started (service.py) and from the BN menu ("System status").
"""
import json
import threading

import xbmc
import xbmcgui
import xbmcplugin

from .common import T, ui_lang, load, save, log

S = {
    'title': ('מצב המערכת', 'System status', 'Состояние системы'),
    'ready': ('BN Stream מוכן לשימוש', 'BN Stream is ready', 'BN Stream готов'),
    'ready_ok': ('הכול פועל', 'everything works', 'всё работает'),
    'ready_bad': ('%d דורשים תשומת לב', '%d need attention', 'требуют внимания: %d'),
    'addons': ('תוספים', 'Add-ons', 'Дополнения'),
    'services': ('שירותים וחיבורים', 'Services & connections', 'Сервисы и подключения'),
    'content': ('תוכן זמין', 'Available content', 'Доступный контент'),
    'movies': ('סרטים בקטלוג (TMDb, בערך)', 'Movies in the catalogue (TMDb, approx.)', 'Фильмы в каталоге (TMDb, ок.)'),
    'tv': ('סדרות בקטלוג (TMDb, בערך)', 'TV shows in the catalogue (TMDb, approx.)', 'Сериалы в каталоге (TMDb, ок.)'),
    'live': ('ערוצי טלוויזיה חיים', 'Live TV channels', 'ТВ-каналы'),
    'radio': ('תחנות רדיו (ישראל, רוסיה, עברית)', 'Radio stations (Israel, Russia, Hebrew)', 'Радиостанции (Израиль, Россия, иврит)'),
    'sources': ('מקורות וידאו בספרייה', 'Video sources in the library', 'Видеоисточники'),
    'russian': ('ערוצי אולפנים רוסיים רשמיים', 'Official Russian studio channels', 'Официальные каналы киностудий'),
    'soviet': ('סרטים סובייטיים (ארכיון)', 'Soviet films (Internet Archive)', 'Советские фильмы (Архив)'),
    'favs': ('מועדפים', 'Favourites', 'Избранное'),
    'hist': ('נצפו', 'Watched', 'Просмотрено'),
    'internet': ('אינטרנט', 'Internet', 'Интернет'),
    'on': ('פעיל', 'active', 'активно'), 'off': ('כבוי', 'disabled', 'выключено'), 'missing': ('לא מותקן', 'not installed', 'не установлено'),
}
ADDONS = [('plugin.video.nova', 'NovaTV'), ('plugin.video.pov', 'POV'), ('plugin.video.idanplus', 'Idan+'),
          ('plugin.video.youtube', 'YouTube'), ('service.subtitles.All_Subs', 'All Subs'),
          ('pvr.iptvsimple', 'IPTV Simple (TV)'), ('inputstream.adaptive', 'InputStream Adaptive'),
          ('skin.fentastic', 'BN skin'), ('plugin.program.novawizard', 'NovaTV Wizard')]


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def _rpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception:
        return {}


def addon_rows():
    from .providers import PROVIDERS, name_of, status as prov_status
    rows = []
    stable = prov_status()
    ids = list(ADDONS) + [(p[1], name_of(p).split(' – ')[0]) for p in PROVIDERS
                          if stable.get(p[0], {}).get('stable', True) and p[1] not in dict(ADDONS)]
    for aid, name in ids:
        r = _rpc('Addons.GetAddonDetails', addonid=aid, properties=['enabled', 'version', 'broken'])
        a = (r.get('result') or {}).get('addon')
        if not a:
            rows.append((name, None, s('missing')))
        elif a.get('broken'):
            rows.append((name, False, 'broken: %s' % a['broken']))
        else:
            rows.append((name, bool(a.get('enabled')), '%s  %s' % (a.get('version', ''), s('on') if a.get('enabled') else s('off'))))
    return rows


def service_rows():
    from . import accounts
    rows = []
    try:
        import requests
        requests.get('https://www.google.com/generate_204', timeout=6)
        rows.append((s('internet'), True, 'OK'))
    except Exception as e:
        rows.append((s('internet'), False, str(e)[:60]))
    out = {}

    def one(k):
        out[k] = accounts.check(k)
    th = [threading.Thread(target=one, args=(k,), daemon=True) for k, _ in accounts.ROWS]
    [t.start() for t in th]
    [t.join(20) for t in th]
    for k, name in accounts.ROWS:
        ok, detail = out.get(k, (False, 'timeout'))
        rows.append((name, ok, detail or (T('ok') if ok else T('missing'))))
    return rows


def content_rows():
    from .common import tmdb
    from .providers import PROVIDERS, RUSSIAN, status as prov_status
    rows, got = [], {}

    def tm(key, path):
        # /discover caps total_results at 10,000 pages; the newest id is the size of the catalogue
        try:
            got[key] = int(tmdb(path).get('id') or 0)
        except Exception:
            got[key] = None

    def radio():
        from .radio import _get
        got['radio'] = sum(len(_get('/stations/' + p)) for p in
                           ('bycountrycodeexact/IL', 'bycountrycodeexact/RU', 'bylanguageexact/hebrew')) or None

    def soviet():
        try:
            import requests
            r = requests.get('https://archive.org/advancedsearch.php', timeout=15,
                             params={'q': '(советский фильм) AND mediatype:movies', 'rows': 0, 'output': 'json'}).json()
            got['soviet'] = int(r['response']['numFound'])
        except Exception:
            got['soviet'] = None
    jobs = [threading.Thread(target=tm, args=('movies', '/movie/latest'), daemon=True),
            threading.Thread(target=tm, args=('tv', '/tv/latest'), daemon=True),
            threading.Thread(target=radio, daemon=True), threading.Thread(target=soviet, daemon=True)]
    [j.start() for j in jobs]
    [j.join(25) for j in jobs]
    live = len((_rpc('PVR.GetChannels', channelgroupid='alltv').get('result') or {}).get('channels', []))
    st = prov_status()
    nsrc = len([p for p in PROVIDERS if st.get(p[0], {}).get('stable', True)])

    def fmt(v):
        return '{:,}'.format(v) if isinstance(v, int) else '?'
    rows.append((s('movies'), got.get('movies') is not None, fmt(got.get('movies'))))
    rows.append((s('tv'), got.get('tv') is not None, fmt(got.get('tv'))))
    rows.append((s('live'), live > 0, fmt(live)))
    rows.append((s('radio'), bool(got.get('radio')), fmt(got.get('radio'))))
    rows.append((s('sources'), nsrc > 0, fmt(nsrc)))
    rows.append((s('russian'), True, fmt(len(RUSSIAN))))
    rows.append((s('soviet'), got.get('soviet') is not None, fmt(got.get('soviet'))))
    rows.append((s('favs'), True, fmt(len(load('favourites.json', [])))))
    rows.append((s('hist'), True, fmt(len(load('history.json', [])))))
    return rows


def gather():
    data = {'addons': addon_rows(), 'services': service_rows(), 'content': content_rows()}
    save('status.json', data)
    return data


def problems(data):
    return [r for sec in ('addons', 'services') for r in data[sec] if r[1] is False]


def _mark(ok):
    return '[COLOR limegreen]●[/COLOR]' if ok else ('[COLOR grey]○[/COLOR]' if ok is None else '[COLOR red]●[/COLOR]')


def as_text(data):
    out = []
    for sec in ('content', 'services', 'addons'):
        out.append('[B][COLOR FFE8BE5A]%s[/COLOR][/B]' % s(sec))
        for name, ok, detail in data[sec]:
            out.append('%s  [B]%s[/B]   %s' % (_mark(ok), name, detail))
        out.append('')
    return '\n'.join(out)


def show_dialog(data=None):
    data = data or gather()
    xbmcgui.Dialog().textviewer('BN Stream – %s' % s('title'), as_text(data))


def announce():
    """called by the service once everything has started"""
    data = gather()
    bad = problems(data)
    msg = s('ready_ok') if not bad else s('ready_bad') % len(bad)
    xbmcgui.Dialog().notification(s('ready'), msg, xbmcgui.NOTIFICATION_INFO if not bad else xbmcgui.NOTIFICATION_WARNING, 8000)
    log('startup status: %d problems %s' % (len(bad), [b[0] for b in bad]))
    return data


def listing(handle):
    """the status as a list: readable with a TV remote"""
    data = gather()
    for sec in ('content', 'services', 'addons'):
        li = xbmcgui.ListItem('[B][COLOR FFE8BE5A]%s[/COLOR][/B]' % s(sec))
        xbmcplugin.addDirectoryItem(handle, 'plugin://plugin.video.nova/?a=noop', li, False)
        for name, ok, detail in data[sec]:
            li = xbmcgui.ListItem('%s  %s   [COLOR grey]%s[/COLOR]' % (_mark(ok), name, detail))
            li.getVideoInfoTag().setPlot(detail or '')
            xbmcplugin.addDirectoryItem(handle, 'plugin://plugin.video.nova/?a=noop', li, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
