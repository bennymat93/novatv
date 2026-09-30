# -*- coding: utf-8 -*-
"""Help (last main-menu item): user guide, troubleshooting table, search over both, About.

Content lives in resources/help/guide.json and trouble.json (he + en). The language toggle (Hebrew <-> English)
is the setting help_lang ('' = follow the interface). search() / text helpers are plain Python for unit tests.
"""
import json
import os
import re

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'help')
STR = {
    'guide': ('מדריך למשתמש', 'User guide'), 'trouble': ('פתרון בעיות', 'Troubleshooting'),
    'search': ('חיפוש בעזרה', 'Search help'), 'about': ('אודות', 'About'), 'speed': ('בדיקת מהירות', 'Speed test'),
    'toggle': ('English', 'עברית'), 'problem': ('בעיה', 'Problem'), 'causes': ('סיבות אפשריות', 'Possible causes'),
    'fix': ('פתרון מוצע', 'Suggested fix'), 'none': ('לא נמצאו תוצאות', 'No results'),
    'build': ('Build', 'Build'), 'version': ('גרסה', 'Version'), 'built': ('תאריך בנייה', 'Build date'),
    'kodi': ('גרסת Kodi', 'Kodi version'), 'platform': ('פלטפורמה', 'Platform'), 'profile': ('סוג מכשיר', 'Device type'),
    'addons': ('תוספים מותקנים', 'Installed add-ons'), 'credits': ('קרדיטים', 'Credits'),
    'license': ('רישיון', 'License'), 'support': ('תמיכה', 'Support'),
}


def load(name):
    with open(os.path.join(HERE, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def plain(text):
    return re.sub(r'\[/?[A-Z]+[^\]]*\]', ' ', (text or '').replace('[CR]', '\n'))


def search(q, lang):
    """sections and table rows containing every word of the query (either language's text, shown in lang)"""
    words = [w for w in re.findall(r'\w+', (q or '').lower()) if len(w) > 1]
    if not words:
        return []
    out = []
    for sec in load('guide')['sections']:
        hay = ' '.join(plain(sec[l]['title'] + ' ' + sec[l]['body']) for l in ('he', 'en')).lower()
        if all(w in hay for w in words):
            out.append(('guide', sec['id'], sec[lang]['title']))
    for i, row in enumerate(load('trouble')['rows']):
        hay = ' '.join(' '.join(row[l]) for l in ('he', 'en')).lower()
        if all(w in hay for w in words):
            out.append(('trouble', str(i), row[lang][0]))
    return out


def trouble_text(rows, lang):
    k = STR
    i = 0 if lang == 'he' else 1
    out = []
    for r in rows:
        p, c, f = r[lang]
        out.append('[B][COLOR FFE8BE5A]%s[/COLOR][/B]\n[B]%s:[/B] %s\n[B]%s:[/B] %s\n' % (p, k['causes'][i], c, k['fix'][i], f))
    return '\n'.join(out)


# ------------------------------------------------------------ Kodi
def _lang():
    from .common import ADDON, ui_lang
    v = ADDON.getSetting('help_lang')
    return v if v in ('he', 'en') else ('he' if ui_lang() == 'he' else 'en')


def s(k):
    return STR[k][0 if _lang() == 'he' else 1]


def root(handle, url, folder, end):
    from .common import MEDIA
    lang = _lang()
    tile = lambda n: os.path.join(MEDIA, 'cats', 'topic_%s.png' % n)
    folder(s('guide'), url(a='help_guide'), tile('guide'))
    folder(s('trouble'), url(a='help_trouble'), tile('trouble'))
    folder(s('search'), url(a='help_search'), os.path.join(MEDIA, 'search_help.png'))
    folder(s('speed'), url(a='speedtest'), tile('speed'))
    folder(s('about'), url(a='help_about'), tile('about'))
    folder('[COLOR grey]%s ⇄ %s[/COLOR]' % ('עברית' if lang == 'he' else 'English', s('toggle')), url(a='help_lang'),
           'DefaultAddonLanguage.png')
    end(cache=False)


def cats(handle, url):
    """home row: the Help tiles"""
    import xbmcgui
    import xbmcplugin
    from .common import MEDIA
    for key, a, icon in (('guide', 'help_guide', 'guide'), ('trouble', 'help_trouble', 'trouble'),
                         ('speed', 'speedtest', 'speed'), ('about', 'help_about', 'about')):
        tile = os.path.join(MEDIA, 'cats', 'topic_%s.png' % icon)
        li = xbmcgui.ListItem(s(key))
        li.setArt({'icon': tile, 'thumb': tile})
        xbmcplugin.addDirectoryItem(handle, url(a=a), li, a != 'speedtest')     # the test is an action, not a folder
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def guide(handle, url, folder, end):
    lang = _lang()
    for sec in load('guide')['sections']:
        folder(sec[lang]['title'], url(a='help_show', kind='guide', id=sec['id']), 'DefaultAddonHelper.png',
               plot=plain(sec[lang]['body']))
    end(cache=False)


def trouble(handle, url, folder, end):
    lang = _lang()
    folder('[B]%s[/B]' % s('trouble'), url(a='help_show', kind='trouble', id='*'), 'DefaultIconInfo.png')
    for i, r in enumerate(load('trouble')['rows']):
        folder(r[lang][0], url(a='help_show', kind='trouble', id=str(i)), 'DefaultIconWarning.png',
               plot='%s: %s\n%s: %s' % (s('causes'), r[lang][1], s('fix'), r[lang][2]))
    end(cache=False)


def show(kind, rid):
    import xbmcgui
    lang = _lang()
    if kind == 'guide':
        sec = next(x for x in load('guide')['sections'] if x['id'] == rid)
        xbmcgui.Dialog().textviewer(sec[lang]['title'], sec[lang]['body'].replace('[CR]', '\n\n'))
    else:
        rows = load('trouble')['rows']
        rows = rows if rid == '*' else [rows[int(rid)]]
        xbmcgui.Dialog().textviewer(s('trouble'), trouble_text(rows, lang))


def do_search(handle, url, folder, end, q=''):
    import xbmcgui
    if not q:
        q = xbmcgui.Dialog().input(s('search'))
    if not q:
        return end()
    found = search(q, _lang())
    for kind, rid, title in found:
        folder(title, url(a='help_show', kind=kind, id=rid),
               'DefaultAddonHelper.png' if kind == 'guide' else 'DefaultIconWarning.png')
    if not found:
        folder('[COLOR grey]%s[/COLOR]' % s('none'), url(a='noop'), 'DefaultIconInfo.png')
    end(cache=False)


def toggle():
    import xbmc
    from .common import ADDON
    ADDON.setSetting('help_lang', 'en' if _lang() == 'he' else 'he')
    xbmc.executebuiltin('Container.Refresh')


def about_text():
    import platform
    import xbmc
    from .common import ADDON
    lang = _lang()
    i = 0 if lang == 'he' else 1
    built = ''
    try:
        import xbmcvfs
        built = open(xbmcvfs.translatePath('special://userdata/novatv_build.txt'), encoding='utf-8').read().strip()
    except Exception:
        pass
    from . import profiles
    r = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddons',
                                                  'params': {'properties': ['name', 'version', 'enabled']}})))
    adds = (r.get('result') or {}).get('addons', [])
    lines = ['[B][COLOR FFE8BE5A]BN Stream[/COLOR][/B]',
             '%s: %s' % (STR['version'][i], ADDON.getAddonInfo('version')),
             '%s: %s' % (STR['built'][i], built or '-'),
             '%s: %s' % (STR['kodi'][i], xbmc.getInfoLabel('System.BuildVersion')),
             '%s: %s (%s)' % (STR['platform'][i], platform.system() or xbmc.getInfoLabel('System.OSVersionInfo'),
                              xbmc.getInfoLabel('System.OSVersionInfo')),
             '%s: %s' % (STR['profile'][i], profiles.label(profiles.current(), lang)),
             '', '[B]%s[/B]' % STR['addons'][i]]
    lines += ['%s  %s%s' % (a.get('name') or a['addonid'], a.get('version', ''), '' if a.get('enabled') else '  (off)')
              for a in sorted(adds, key=lambda a: (a.get('name') or '').lower())]
    lines += ['', '[B]%s[/B]' % STR['credits'][i],
              'Kodi (XBMC Foundation), FENtastic skin, POV, iptv-org, radio-browser.info, TMDb, Open-Meteo, faster-whisper',
              '[B]%s[/B]: GPL-2.0 (Kodi and bundled add-ons keep their own licenses)' % STR['license'][i],
              '[B]%s[/B]: https://github.com/bennymat93/novatv/issues' % STR['support'][i]]
    return '\n'.join(lines)


def about():
    import xbmcgui
    xbmcgui.Dialog().textviewer(s('about'), about_text())
