# -*- coding: utf-8 -*-
"""BN subtitles window (player button "כתוביות BN"): every subtitle track of the playing video in one list,
the AI track marked and switchable by hand, AI generation with its live progress, off/on, search and sync.

Plain Kodi dialogs only (Dialog.select with list items): the same look on every skin and remote-friendly.
"""
import json
import os

import xbmc
import xbmcgui

from .common import ui_lang

S = {
    'title': ('כתוביות', 'Subtitles', 'Субтитры'),
    'off': ('כבה כתוביות', 'Subtitles off', 'Выключить субтитры'),
    'on': ('הצג כתוביות', 'Show subtitles', 'Показать субтитры'),
    'now': ('מוצגת עכשיו', 'showing now', 'сейчас'),
    'ai_track': ('כתוביות AI', 'AI subtitles', 'ИИ-субтитры'),
    'ai_saved': ('הפעל את כתוביות ה-AI שנוצרו', 'Turn on the AI subtitles made for this video', 'Включить созданные ИИ-субтитры'),
    'ai_make': ('יצירת כתוביות AI בעברית', 'Make Hebrew AI subtitles', 'Создать ИИ-субтитры на иврите'),
    'ai_busy': ('כתוביות AI בהכנה: %s', 'AI subtitles in progress: %s', 'ИИ-субтитры готовятся: %s'),
    'search': ('חיפוש כתוביות (אתרים)', 'Search subtitles (sites)', 'Поиск субтитров (сайты)'),
    'delay': ('סנכרון כתוביות (הקדמה / איחור)', 'Subtitle sync (earlier / later)', 'Синхронизация субтитров'),
    'none': ('אין כתוביות בסרטון הזה', 'This video has no subtitles', 'В этом видео нет субтитров'),
    'embedded': ('בתוך הקובץ', 'in the file', 'в файле'),
    'external': ('קובץ', 'file', 'файл'),
    'noplay': ('אין סרטון מתנגן', 'Nothing is playing', 'Ничего не воспроизводится'),
}
LANG = {'heb': ('עברית', 'Hebrew', 'Иврит'), 'he': ('עברית', 'Hebrew', 'Иврит'), 'eng': ('אנגלית', 'English', 'Английский'),
        'en': ('אנגלית', 'English', 'Английский'), 'rus': ('רוסית', 'Russian', 'Русский'), 'ru': ('רוסית', 'Russian', 'Русский'),
        'ara': ('ערבית', 'Arabic', 'Арабский'), 'fre': ('צרפתית', 'French', 'Французский'), 'spa': ('ספרדית', 'Spanish', 'Испанский'),
        'ger': ('גרמנית', 'German', 'Немецкий')}


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def lang_name(code):
    row = LANG.get((code or '').lower())
    return row[{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]] if row else (code or '?')


def _rpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception:
        return {}


def tracks():
    """[{index, language, name, current}] + enabled flag, from the player itself"""
    pl = (_rpc('Player.GetActivePlayers').get('result') or [])
    pl = [p for p in pl if p.get('type') == 'video']
    if not pl:
        return None, False
    r = (_rpc('Player.GetProperties', playerid=pl[0]['playerid'],
              properties=['subtitles', 'currentsubtitle', 'subtitleenabled']).get('result') or {})
    cur = (r.get('currentsubtitle') or {}).get('index')
    out = [dict(t, current=(t.get('index') == cur)) for t in r.get('subtitles', [])]
    return out, bool(r.get('subtitleenabled'))


def label(t, enabled):
    name = t.get('name') or ''
    is_ai = 'BN AI' in name or name.startswith('ai_')
    what = s('ai_track') if is_ai else (s('external') if '(' in name else s('embedded'))
    text = '%s  ·  %s' % (lang_name(t.get('language')), name.split(' (')[0] or what)
    if is_ai:
        text = '[B][COLOR FFE8BE5A]AI[/COLOR][/B]  ' + text
    if t['current'] and enabled:
        text = '[COLOR limegreen]●[/COLOR] %s   [COLOR grey](%s)[/COLOR]' % (text, s('now'))
    return text


def show():
    player = xbmc.Player()
    if not player.isPlayingVideo():
        return xbmcgui.Dialog().notification('BN', s('noplay'), xbmcgui.NOTIFICATION_WARNING, 3000)
    home = xbmcgui.Window(10000)
    while True:
        ts, enabled = tracks()
        if ts is None:
            return
        rows, acts = [], []
        busy = home.getProperty('NovaTV.AISubs')
        if busy:
            rows.append('[COLOR FFE8BE5A]%s[/COLOR]' % (s('ai_busy') % busy))
            acts.append(('noop', None))
        for t in ts:
            rows.append(label(t, enabled))
            acts.append(('track', t['index']))
        if not ts:
            rows.append('[COLOR grey]%s[/COLOR]' % s('none'))
            acts.append(('noop', None))
        saved = home.getProperty('NovaTV.AISrt')
        if saved and os.path.exists(saved) and not any('BN AI' in (t.get('name') or '') for t in ts):
            rows.append('[B]%s[/B]' % s('ai_saved'))
            acts.append(('load', saved))
        if ts:
            rows.append(s('off') if enabled else s('on'))
            acts.append(('toggle', None))
        rows.append('[B][COLOR FFE8BE5A]%s[/COLOR][/B]' % s('ai_make'))
        acts.append(('ai', None))
        rows.append(s('search'))
        acts.append(('search', None))
        if ts:
            rows.append(s('delay'))
            acts.append(('delay', None))
        pre = next((i for i, a in enumerate(acts) if a[0] == 'track' and ts[[t['index'] for t in ts].index(a[1])]['current']), 0)
        i = xbmcgui.Dialog().select('BN – %s' % s('title'), rows, preselect=pre)
        if i < 0:
            return
        kind, val = acts[i]
        if kind == 'track':
            player.setSubtitleStream(int(val))
            player.showSubtitles(True)
            home.setProperty('NovaTV.SubsChosen', player.getPlayingFile())   # the service keeps this choice
        elif kind == 'load':
            player.setSubtitles(val)
            player.showSubtitles(True)
            home.setProperty('NovaTV.SubsChosen', player.getPlayingFile())
        elif kind == 'toggle':
            player.showSubtitles(not enabled)
            if not enabled:
                home.setProperty('NovaTV.SubsChosen', player.getPlayingFile())
        elif kind == 'ai':
            xbmc.executebuiltin('NotifyAll(plugin.video.nova,ai_now)')
            return
        elif kind == 'search':
            xbmc.executebuiltin('ActivateWindow(subtitlesearch)')
            return
        elif kind == 'delay':
            xbmc.executebuiltin('Action(SubtitleDelay)')
            return
        else:
            continue
        xbmc.sleep(400)            # show the list again with the new state: try another track right away
