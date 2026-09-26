# -*- coding: utf-8 -*-
"""NovaTV hub: every video add-on is a *provider* behind NovaTV.

Kodi only talks to NovaTV. NovaTV runs one query against all enabled providers at the
same time (TMDb/POV, Idan+, YouTube, Internet Archive, Dailymotion, Vimeo, TED, live
channels, radio ...) and shows one merged list. When POV finds no source for a title,
play_with_fallback() searches the other providers for the same title.

Only add-ons from the official Kodi repository (plus Idan+/POV that ship with the build).
Which providers are stable is decided by tools/provider_audit.py -> resources/providers_status.json.
"""
import json
import os
import re
import threading
import time
from urllib.parse import quote, quote_plus, urlencode

import xbmc
import xbmcgui

from .common import monitor
import xbmcplugin

from .common import T, ui_lang, load, save, log, ADDON_PATH

# ------------------------------------------------------------------ registry
# id, add-on, (he, en, ru), category, search template ({q} = url-quoted query) or None = browse only
DM_API = ('https://api.dailymotion.com/videos?fields=description,duration,id,owner.username,taken_time,'
          'thumbnail_large_url,title,views_total&search={q}&sort=relevance&limit=25&family_filter=1&localization=en_EN&page=1')
PROVIDERS = [
    # --- core (ship with the build)
    ('pov', 'plugin.video.pov', ('POV – סרטים וסדרות (Real-Debrid)', 'POV – movies & series (Real-Debrid)', 'POV – фильмы и сериалы (Real-Debrid)'), 'movies', None),
    ('idanplus', 'plugin.video.idanplus', ('עידן+ – כאן, קשת, רשת, 14, 9', 'Idan+ – Israeli broadcasters', 'Idan+ – израильские каналы'), 'israel',
     'plugin://plugin.video.idanplus/?mode=4&url={q}'),
    ('youtube', 'plugin.video.youtube', ('YouTube', 'YouTube', 'YouTube'), 'video',
     'internal:yt'),        # NovaTV reads YouTube itself: the add-on needs personal API keys for lists
    # --- movies & series (free, legal)
    ('archive', 'plugin.video.archive.org', ('Internet Archive – סרטים קלאסיים וסובייטיים', 'Internet Archive – classic & Soviet films', 'Internet Archive – классика и советское кино'), 'movies',
     'internal:ia'),        # NovaTV uses archive.org's API: the add-on's page scraper no longer plays
    ('pluto', 'plugin.video.plutotv', ('Pluto TV – ערוצים וסרטים', 'Pluto TV – free channels & movies', 'Pluto TV – каналы и фильмы'), 'movies', None),
    ('popcornflix', 'plugin.video.popcornflix', ('Popcornflix – סרטים', 'Popcornflix – movies', 'Popcornflix – фильмы'), 'movies', None),
    ('shoutfactory', 'plugin.video.shoutfactorytv', ('Shout! Factory TV', 'Shout! Factory TV', 'Shout! Factory TV'), 'movies', None),
    ('contv', 'plugin.video.contv', ('ConTV – מדע בדיוני ופנטזיה', 'ConTV – sci-fi & fantasy', 'ConTV – фантастика'), 'movies', None),
    ('imdbtrailers', 'plugin.video.imdb.trailers', ('טריילרים (IMDb)', 'IMDb Trailers', 'Трейлеры IMDb'), 'movies',
     'plugin://plugin.video.imdb.trailers/?action=search_word&keyword={q}'),
    # --- video platforms
    ('dailymotion', 'plugin.video.dailymotion_com', ('Dailymotion', 'Dailymotion', 'Dailymotion'), 'video',
     'plugin://plugin.video.dailymotion_com/?mode=listVideos&url={dm}'),
    ('vimeo', 'plugin.video.vimeo', ('Vimeo', 'Vimeo', 'Vimeo'), 'video', 'plugin://plugin.video.vimeo/search/?query={q}'),
    ('twitch', 'plugin.video.twitch', ('Twitch – שידורים חיים', 'Twitch – live streams', 'Twitch – стримы'), 'video', None),
    ('lbry', 'plugin.video.lbry', ('Odysee / LBRY', 'Odysee / LBRY', 'Odysee / LBRY'), 'video', 'plugin://plugin.video.lbry/search/{q}/1'),
    ('peertube', 'plugin.video.pt', ('PeerTube', 'PeerTube', 'PeerTube'), 'video', None),
    # --- documentaries & learning
    ('ted', 'plugin.video.ted.talks', ('TED – הרצאות', 'TED Talks', 'TED – лекции'), 'docs',
     'plugin://plugin.video.ted.talks/?mode=searchMore&search_term={q}&page=0'),
    ('docheaven', 'plugin.video.documentaryheaven', ('Documentary Heaven – תעודה', 'Documentary Heaven', 'Documentary Heaven – документальные'), 'docs', None),
    ('filmsforaction', 'plugin.video.filmsforaction', ('Films For Action – תעודה', 'Films For Action', 'Films For Action'), 'docs', None),
    ('nasa', 'plugin.video.nasa', ('NASA', 'NASA', 'NASA'), 'docs', None),
    ('esa', 'plugin.video.esa', ('ESA – סוכנות החלל האירופית', 'ESA – European Space Agency', 'ESA – Европейское космическое агентство'), 'docs', None),
    ('eso', 'plugin.video.eso', ('ESO – אסטרונומיה', 'ESO – astronomy', 'ESO – астрономия'), 'docs', None),
    ('arte', 'plugin.video.arteplussept', ('ARTE – תרבות ותעודה', 'ARTE – culture & documentaries', 'ARTE – культура'), 'docs', None),
    ('ccc', 'plugin.video.media-ccc-de', ('media.ccc.de – הרצאות טכנולוגיה', 'media.ccc.de – tech talks', 'media.ccc.de – доклады'), 'docs', None),
    ('fosdem', 'plugin.video.fosdem', ('FOSDEM – קוד פתוח', 'FOSDEM – open source talks', 'FOSDEM'), 'docs', None),
    # --- news
    ('nhk', 'plugin.video.nhklive', ('NHK World – חדשות', 'NHK World – news', 'NHK World – новости'), 'news', None),
    ('cbcnews', 'plugin.video.cbcnews', ('CBC News', 'CBC News', 'CBC News'), 'news', None),
    ('wsj', 'plugin.video.wsj', ('Wall Street Journal', 'Wall Street Journal', 'Wall Street Journal'), 'news', None),
    ('foxnews', 'plugin.video.fox.news', ('Fox News', 'Fox News', 'Fox News'), 'news', None),
    ('npr', 'plugin.video.npr', ('NPR – מוזיקה', 'NPR Music', 'NPR – музыка'), 'music', None),
    # --- kids
    ('pbskids', 'plugin.video.pbskids', ('PBS Kids – ילדים', 'PBS Kids', 'PBS Kids – детям'), 'kids', None),
    ('tvokids', 'plugin.video.tvokids', ('TVO Kids – ילדים', 'TVO Kids', 'TVO Kids – детям'), 'kids', None),
    # --- sport
    ('redbull', 'plugin.video.redbull.tv', ('Red Bull TV – ספורט אתגרי', 'Red Bull TV – extreme sports', 'Red Bull TV – экстрим'), 'sport', None),
    ('f1', 'plugin.video.formula1', ('Formula 1 – סרטונים', 'Formula 1 videos', 'Формула 1'), 'sport', None),
    ('motorsport', 'plugin.video.motorsporthub', ('Motorsport Hub', 'Motorsport Hub', 'Motorsport Hub'), 'sport', None),
    ('eventvods', 'plugin.video.eventvods', ('Eventvods – ספורט אלקטרוני', 'Eventvods – esports', 'Eventvods – киберспорт'), 'sport', None),
    # --- free US live channels (may be geo-restricted outside the US)
    ('buzzr', 'plugin.video.buzzr', ('BUZZR – שעשועונים', 'BUZZR – game shows', 'BUZZR'), 'live', None),
    ('comet', 'plugin.video.comettv', ('Comet TV – מדע בדיוני', 'Comet TV – sci-fi', 'Comet TV'), 'live', None),
    ('dabl', 'plugin.video.dabl', ('Dabl', 'Dabl', 'Dabl'), 'live', None),
    ('courttv', 'plugin.video.courttv', ('Court TV', 'Court TV', 'Court TV'), 'live', None),
    ('metv', 'plugin.video.metv', ('MeTV – קלאסיקות', 'MeTV – classics', 'MeTV'), 'live', None),
]
CATS = [('israel', ('ישראל', 'Israel', 'Израиль')), ('russian', ('ברוסית', 'Russian', 'На русском')),
        ('movies', ('סרטים וסדרות', 'Movies & series', 'Фильмы и сериалы')), ('video', ('פלטפורמות וידאו', 'Video platforms', 'Видеоплатформы')),
        ('docs', ('תעודה ולימוד', 'Documentaries & learning', 'Документальное и обучение')), ('news', ('חדשות', 'News', 'Новости')),
        ('kids', ('ילדים', 'Kids', 'Детям')), ('sport', ('ספורט', 'Sport', 'Спорт')), ('music', ('מוזיקה', 'Music', 'Музыка')),
        ('live', ('ערוצים חיים (ארה"ב)', 'Free live channels (US)', 'Прямые каналы (США)'))]

# official Russian studio channels on YouTube (free, published by the rights holders)
RUSSIAN = [
    ('UCEK3tT7DcfWGWJpNEDBdWog', ('מוספילם – סרטים סובייטיים ורוסיים', 'Mosfilm – Soviet & Russian films', 'Мосфильм – советское и российское кино')),
    ('UCC2mTjSz2Hohl3zDBTCqF1Q', ('מוספילם לילדים', 'Mosfilm for kids', 'Мосфильм – для детей')),
    ('UCHS2LM1n3f5cyL-ebgkqyLw', ('סויוזמולטפילם – סרטים מצוירים', 'Soyuzmultfilm – animation', 'Союзмультфильм')),
    ('UC8p4E9GyMy-3OdLFx0GswTQ', ('סויוזמולטפילם לפעוטות', 'Soyuzmultfilm for toddlers', 'Союзмультфильм для мам и малышей')),
    ('UC5A-Wp9ujcr5g9sYagAafEA', ('סמשריקי', 'Smeshariki', 'Смешарики')),
    ('UCfU8IgesHohe5D8XkcY99Jw', ('בלרוספילם', 'Belarusfilm', 'Беларусьфильм')),
    ('UC4tlrTXCBw6NPZ9nCA3_s9w', ('קינופויסק – טריילרים וסקירות', 'Kinopoisk – trailers & reviews', 'Кинопоиск')),
]

STATUS_FILE = os.path.join(ADDON_PATH, 'resources', 'providers_status.json')
S = {
    'hub_search': ('חיפוש בכל המקורות', 'Search all sources', 'Поиск по всем источникам'),
    'sources': ('מקורות ותוספים', 'Sources & add-ons', 'Источники и дополнения'),
    'searching': ('מחפש בכל המקורות...', 'Searching all sources...', 'Поиск по всем источникам...'),
    'more': ('עוד תוצאות מ-%s', 'More from %s', 'Ещё из %s'),
    'none': ('לא נמצא באף מקור', 'Not found in any source', 'Ничего не найдено'),
    'pov_none': ('לא נמצאו מקורות ב-POV – מחפש בשאר המקורות', 'POV found no sources – searching all other sources',
                 'POV ничего не нашёл – ищу в остальных источниках'),
    'pick': ('נמצא במקורות נוספים', 'Found in other sources', 'Найдено в других источниках'),
    'on': ('פעיל', 'on', 'вкл'), 'off': ('כבוי', 'off', 'выкл'), 'not_inst': ('לא מותקן', 'not installed', 'не установлено'),
    'unstable': ('לא יציב כרגע', 'currently unstable', 'сейчас нестабильно'),
    'searchable': ('כלול בחיפוש', 'in search', 'в поиске'),
    'toggle': ('הפעל / כבה', 'Enable / disable', 'Вкл / выкл'), 'open': ('פתח', 'Open', 'Открыть'),
    'settings': ('הגדרות התוסף', 'Add-on settings', 'Настройки дополнения'),
    'install': ('התקן', 'Install', 'Установить'), 'install_all': ('התקן את כל המקורות היציבים', 'Install all stable sources', 'Установить все стабильные'),
    'live': ('ערוצים חיים', 'Live channels', 'Прямые каналы'), 'radio': ('רדיו', 'Radio', 'Радио'),
    'movies_series': ('סרטים וסדרות', 'Movies & series', 'Фильмы и сериалы'),
    'library': ('הספרייה המרכזית', 'Central library', 'Центральная библиотека'),
}


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def name_of(p):
    return p[2][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


CORE = {'pov', 'idanplus', 'youtube', 'archive'}      # ship with the build; never hidden by the audit


def status():
    try:
        with open(STATUS_FILE, encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        st = {}
    for pid in CORE:
        st.setdefault(pid, {})['stable'] = True
    return st


def installed(addon_id):
    # installed AND enabled: calling a disabled add-on fails ("Unknown addon id")
    return xbmc.getCondVisibility('System.HasAddon(%s) + System.AddonIsEnabled(%s)' % (addon_id, addon_id))


def enabled_map():
    return load('providers.json', {})


def is_on(pid):
    """user switch; default on for providers the audit marked stable"""
    m = enabled_map()
    if pid in m:
        return bool(m[pid])
    st = status().get(pid)
    return st is None or st.get('stable', True)


def search_targets():
    return [p for p in PROVIDERS if p[4] and is_on(p[0]) and installed(p[1])]


def build_url(p, q):
    if p[4] == 'internal:yt':
        return 'plugin://plugin.video.nova/?' + urlencode({'a': 'yt_search', 'q': q})
    if p[4] == 'internal:ia':
        return 'plugin://plugin.video.nova/?' + urlencode({'a': 'ia_search', 'q': q})
    return p[4].format(q=quote(q), dm=quote_plus(DM_API.format(q=quote_plus(q))))


def ia_rows(items):
    return [{'label': ('%s (%s)' % (i['title'], i['year'])) if i['year'] else i['title'],
             'file': 'plugin://plugin.video.nova/?' + urlencode({'a': 'ia_item', 'id': i['id']}), 'filetype': 'directory',
             'thumbnail': i['thumb'], 'art': {'thumb': i['thumb'], 'poster': i['thumb']}, 'plot': i['plot']} for i in items]


def yt_rows(videos):
    from .yt import PLAY
    return [{'label': v['title'], 'file': PLAY % v['id'], 'filetype': 'file', 'thumbnail': v['thumb'],
             'art': {'thumb': v['thumb'], 'icon': v['thumb']},
             'plot': ' · '.join(x for x in (v.get('channel'), v.get('duration'), v.get('plot')) if x)} for v in videos]


# ------------------------------------------------------------------ JSON-RPC directory reads
def _rpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception as e:
        return {'error': str(e)}


PROPS = ['title', 'thumbnail', 'art', 'plot', 'year', 'file']


def read_dir(path):
    r = _rpc('Files.GetDirectory', directory=path, media='video', properties=PROPS)
    return (r.get('result') or {}).get('files') or []


def _useful(items):
    """drop navigation / history / settings rows that search pages add around the results"""
    out = []
    for it in items:
        lab = re.sub(r'\[/?[A-Z]+[^\]]*\]', '', it.get('label') or '').strip()
        f = it.get('file') or ''
        if not lab or lab in ('..',) or re.search(r'(?i)(next page|nächste|history|היסטוריה|הגדרות|settings|new search|חיפוש חדש)', lab):
            continue
        if re.search(r'(?i)(search_history|/settings|action=clear|mode=History)', f):
            continue
        it['label'] = lab
        out.append(it)
    return out


# ------------------------------------------------------------------ hub search
def run_search(q, providers=None, per_timeout=12):
    """query every provider in parallel. returns [(provider, items)] in registry order"""
    providers = search_targets() if providers is None else providers
    results = {}
    gate = threading.Semaphore(5)          # each search starts a Python interpreter: spare small TV boxes

    def work(p):
        t = time.time()
        try:
            with gate:
                if p[4] == 'internal:yt':
                    from . import yt
                    results[p[0]] = yt_rows(yt.search(q))
                elif p[4] == 'internal:ia':
                    from . import ia
                    results[p[0]] = ia_rows(ia.search(q))
                else:
                    results[p[0]] = _useful(read_dir(build_url(p, q)))
        except Exception as e:
            log('hub search %s: %s' % (p[0], e), xbmc.LOGWARNING)
            results[p[0]] = []
        log('hub search %s: %d items in %.1fs' % (p[0], len(results[p[0]]), time.time() - t))

    threads = [threading.Thread(target=work, args=(p,), daemon=True) for p in providers]
    for th in threads:
        th.start()
    deadline = time.time() + per_timeout
    for th in threads:
        th.join(max(0.1, deadline - time.time()))
    return [(p, results.get(p[0]) or []) for p in providers if results.get(p[0])]


def _live_matches(q):
    r = _rpc('PVR.GetChannels', channelgroupid='alltv', properties=['channelnumber', 'icon'])
    ql = q.lower()
    return [c for c in (r.get('result') or {}).get('channels', []) if ql in c['label'].lower()][:30]


def _radio_matches(q):
    from .radio import _get
    return _get('/stations/search', name=q, limit=20, order='clickcount')

def _header(handle, text, target='plugin://plugin.video.nova/?a=noop', folder=False):
    li = xbmcgui.ListItem('[COLOR gold][B]%s[/B][/COLOR]' % text)
    li.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(handle, target, li, folder)


def _add_foreign(handle, p, it):
    name = '%s  [COLOR grey]· %s[/COLOR]' % (it['label'], name_of(p).split(' – ')[0])
    li = xbmcgui.ListItem(name)
    a = it.get('art') or {}
    if it.get('thumbnail') and 'thumb' not in a:
        a['thumb'] = it['thumbnail']
    li.setArt(a)
    tag = li.getVideoInfoTag()
    tag.setTitle(it['label'])
    tag.setPlot(it.get('plot') or '')
    is_dir = it.get('filetype') == 'directory'
    if not is_dir:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(handle, it['file'], li, is_dir)


def hub_results(handle, q, media_item, per_provider=8):
    """one merged list: movies & series (TMDb -> POV), every add-on, live channels, radio"""
    from .common import tmdb
    tm = {}

    def tmdb_work():
        try:
            tm['r'] = tmdb('/search/multi', query=q).get('results', [])
        except Exception:
            tm['r'] = []
    th = threading.Thread(target=tmdb_work, daemon=True)
    th.start()
    found = run_search(q)
    th.join(20)
    total = 0
    titles = [r for r in tm.get('r', []) if r.get('media_type') in ('movie', 'tv')]
    if titles:
        _header(handle, '%s (%d)' % (s('movies_series'), len(titles)))
        for r in titles[:20]:
            media_item(r['media_type'], r)
        total += len(titles)
    for p, items in found:
        _header(handle, '%s (%d)' % (name_of(p), len(items)))
        for it in items[:per_provider]:
            _add_foreign(handle, p, it)
        if len(items) > per_provider:
            _header(handle, '   ' + s('more') % name_of(p).split(' – ')[0], build_url(p, q), True)
        total += len(items)
    live = _live_matches(q)
    if live:
        _header(handle, '%s (%d)' % (s('live'), len(live)))
        for c in live:
            li = xbmcgui.ListItem('%s  %s' % (c.get('channelnumber') or '', c['label']))
            li.setArt({'icon': c.get('icon') or 'DefaultTVShows.png', 'thumb': c.get('icon') or 'DefaultTVShows.png'})
            xbmcplugin.addDirectoryItem(handle, 'plugin://plugin.video.nova/?a=tv_play&id=%d' % c['channelid'], li, False)
        total += len(live)
    radios = _radio_matches(q)
    if radios:
        _header(handle, '%s (%d)' % (s('radio'), len(radios)))
        for st in radios:
            stream = st.get('url_resolved') or st.get('url')
            if not stream:
                continue
            li = xbmcgui.ListItem(st.get('name', '').strip())
            li.setArt({'thumb': st.get('favicon') or 'DefaultAudio.png', 'icon': st.get('favicon') or 'DefaultAudio.png'})
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle, stream, li, False)
        total += len(radios)
    if not total:
        xbmcgui.Dialog().notification('NovaTV', s('none'), xbmcgui.NOTIFICATION_INFO, 4000)
    return total


# ------------------------------------------------------------------ POV first, then everything else
NORES = 'nova.pov_noresults'
_HOOK_OLD = '\tdef _no_results(self):\n\t\thide_busy_dialog()\n'
_HOOK_NEW = _HOOK_OLD + "\t\tset_property('nova.pov_noresults', '1')\n"


def ensure_pov_hook():
    """POV updates itself from its repository and loses our one-line 'no results' signal:
    put it back (idempotent). Returns True when the hook is in place."""
    import xbmcvfs
    p = xbmcvfs.translatePath('special://home/addons/plugin.video.pov/resources/lib/modules/sources.py')
    try:
        with open(p, encoding='utf-8') as f:
            src = f.read()
        if _HOOK_NEW in src:
            return True
        if _HOOK_OLD not in src:
            log('POV changed - no-results hook not applied (idle detection still works)', xbmc.LOGWARNING)
            return False
        with open(p, 'w', encoding='utf-8') as f:
            f.write(src.replace(_HOOK_OLD, _HOOK_NEW, 1))
        log('POV no-results hook applied')
        return True
    except Exception as e:
        log('POV hook: %s' % e, xbmc.LOGWARNING)
        return False


def play_with_fallback(pov_url, query, alt_query='', timeout=240):
    """POV plays it if it can. When POV reports "no results" (patched by make_build) the other
    providers are searched for the same title and the user picks from the merged list."""
    ensure_pov_hook()
    home = xbmcgui.Window(10000)
    home.clearProperty(NORES)
    player, mon = xbmc.Player(), monitor()
    xbmc.executebuiltin('PlayMedia(%s)' % pov_url)
    start, idle = time.time(), 0
    while time.time() - start < timeout and not mon.abortRequested():
        if player.isPlayingVideo():
            return True
        if home.getProperty(NORES):
            home.clearProperty(NORES)
            break
        # backstop if the hook is missing: POV finished (no dialog, nothing busy, nothing playing) for 6 s
        busy = xbmc.getCondVisibility('System.HasActiveModalDialog | Window.IsActive(busydialog) | '
                                      'Window.IsActive(busydialognocancel) | Player.HasMedia')
        idle = 0 if busy else idle + 1
        if time.time() - start > 8 and idle >= 12:
            break
        if mon.waitForAbort(0.5):
            return False
    else:
        return False
    xbmcgui.Dialog().notification('NovaTV', s('pov_none'), xbmcgui.NOTIFICATION_INFO, 4000)
    return fallback_pick(query, alt_query)


def fallback_pick(query, alt_query=''):
    pd = xbmcgui.DialogProgressBG()
    pd.create('NovaTV', s('searching'))
    found = run_search(query)
    if alt_query and alt_query.lower() != query.lower():
        seen = {p[0] for p, _ in found}
        found += [(p, i) for p, i in run_search(alt_query) if p[0] not in seen]
    pd.close()
    rows, labels = [], []
    for p, items in found:
        for it in items[:10]:
            rows.append(it)
            labels.append('%s  [COLOR grey]· %s[/COLOR]' % (it['label'], name_of(p).split(' – ')[0]))
    if not rows:
        xbmcgui.Dialog().ok('NovaTV', s('none'))
        return False
    i = xbmcgui.Dialog().select(s('pick'), labels)
    if i < 0:
        return False
    it = rows[i]
    if it.get('filetype') == 'directory':
        xbmc.executebuiltin('ActivateWindow(Videos,%s,return)' % it['file'])
    else:
        xbmc.executebuiltin('PlayMedia(%s)' % it['file'])
    return True


# ------------------------------------------------------------------ central library / sources screen
def library(handle, url):
    """all providers by category, plus the Russian studio channels"""
    col = {'he': 0, 'en': 1, 'ru': 2}[ui_lang()]
    st = status()
    for cat, names in CATS:
        if cat == 'russian':
            n = len(RUSSIAN) + 1
        else:
            n = len([p for p in PROVIDERS if p[3] == cat and st.get(p[0], {}).get('stable', True)])
        if n:
            li = xbmcgui.ListItem('%s  [COLOR grey](%d)[/COLOR]' % (names[col], n))
            li.setArt({'icon': 'DefaultAddonVideo.png', 'thumb': 'DefaultAddonVideo.png'})
            xbmcplugin.addDirectoryItem(handle, url(a='lib_cat', cat=cat), li, True)
    li = xbmcgui.ListItem('[COLOR gold]%s[/COLOR]' % s('sources'))
    li.setArt({'icon': 'DefaultAddonProgram.png'})
    xbmcplugin.addDirectoryItem(handle, url(a='sources'), li, True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def library_cat(handle, url, cat):
    col = {'he': 0, 'en': 1, 'ru': 2}[ui_lang()]
    if cat == 'russian':
        for cid, names in RUSSIAN:
            li = xbmcgui.ListItem(names[col])
            li.setArt({'icon': 'special://home/addons/plugin.video.youtube/icon.png', 'thumb': 'special://home/addons/plugin.video.youtube/icon.png'})
            xbmcplugin.addDirectoryItem(handle, url(a='yt_channel', id=cid), li, True)
        li = xbmcgui.ListItem(('ארכיון האינטרנט – סרטים סובייטיים', 'Internet Archive – Soviet films', 'Internet Archive – советские фильмы')[col])
        li.setArt({'icon': 'DefaultAddonVideo.png'})
        xbmcplugin.addDirectoryItem(handle, url(a='ia_search', q='советский фильм'), li, True)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    st = status()
    for p in PROVIDERS:
        if p[3] != cat or not st.get(p[0], {}).get('stable', True):
            continue
        ok = installed(p[1])
        label = name_of(p) if ok else '%s  [COLOR grey](%s)[/COLOR]' % (name_of(p), T('lib_install'))
        li = xbmcgui.ListItem(label)
        ic = 'special://home/addons/%s/icon.png' % p[1] if ok else 'DefaultAddonVideo.png'
        li.setArt({'icon': ic, 'thumb': ic})
        li.addContextMenuItems([(s('settings'), 'Addon.OpenSettings(%s)' % p[1])] if ok else [])
        xbmcplugin.addDirectoryItem(handle, url(a='lib_open', id=p[0]), li, True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def open_provider(handle, pid, q=''):
    """a provider's own menu (or a query), shown *inside* NovaTV; installs on first use"""
    p = next(x for x in PROVIDERS if x[0] == pid)
    if not installed(p[1]):
        from .iptv import install_addon
        xbmcgui.Dialog().notification('NovaTV', '%s: %s' % (T('lib_install'), name_of(p)), xbmcgui.NOTIFICATION_INFO, 3000)
        if not install_addon(p[1]):
            xbmcgui.Dialog().ok('NovaTV', '%s\n%s' % (T('bk_fail'), p[1]))
            return xbmcplugin.endOfDirectory(handle, False)
    path = build_url(p, q) if q and p[4] else 'plugin://%s/' % p[1]
    items = read_dir(path)
    for it in items:
        lab = it.get('label') or ''
        li = xbmcgui.ListItem(lab)
        a = it.get('art') or {}
        if it.get('thumbnail') and 'thumb' not in a:
            a['thumb'] = it['thumbnail']
        li.setArt(a)
        li.getVideoInfoTag().setPlot(it.get('plot') or '')
        is_dir = it.get('filetype') == 'directory'
        if not is_dir:
            li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(handle, it['file'], li, is_dir)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def list_rows(handle, rows):
    for it in rows:
        li = xbmcgui.ListItem(it['label'])
        li.setArt(it.get('art') or {})
        tag = li.getVideoInfoTag()
        tag.setTitle(it['label'])
        tag.setPlot(it.get('plot') or '')
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(handle, it['file'], li, False)


def yt_channel(handle, url, cid, token=''):
    from . import yt
    videos, nxt = yt.channel(cid, token)
    list_rows(handle, yt_rows(videos))
    if nxt:
        li = xbmcgui.ListItem('[B]%s >>[/B]' % T('next_page'))
        xbmcplugin.addDirectoryItem(handle, url(a='yt_channel', id=cid, token=nxt), li, True)
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    xbmc.executebuiltin('Container.SetViewMode(60)')      # BN Details view


def ia_search(handle, q):
    from . import ia
    for it in ia_rows(ia.search(q)):
        li = xbmcgui.ListItem(it['label'])
        li.setArt(it['art'])
        li.getVideoInfoTag().setPlot(it['plot'])
        xbmcplugin.addDirectoryItem(handle, it['file'], li, True)
    xbmcplugin.setContent(handle, 'movies')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    xbmc.executebuiltin('Container.SetViewMode(60)')      # BN Details view


def ia_item(handle, identifier):
    from . import ia
    thumb = 'https://archive.org/services/img/%s' % identifier
    for f in ia.files(identifier):
        li = xbmcgui.ListItem(f['title'])
        li.setArt({'thumb': thumb, 'poster': thumb, 'fanart': thumb})
        tag = li.getVideoInfoTag()
        meta = f.get('meta') or {}
        tag.setTitle(f['title'])
        tag.setMediaType('movie')
        tag.setPlot(meta.get('plot', ''))
        if meta.get('year', '').isdigit():
            tag.setYear(int(meta['year']))
        if meta.get('genre'):
            tag.setGenres([g.strip() for g in re.split(r'[;,]', meta['genre']) if g.strip()][:3])
        tag.setTagLine(meta.get('title', '') if meta.get('title') != f['title'] else '')
        li.setProperty('IsPlayable', 'true')
        target = 'plugin://plugin.video.nova/?' + urlencode({'a': 'ia_play', 'u': f['url'], 't': f['title'], 'id': identifier})
        xbmcplugin.addDirectoryItem(handle, target, li, False)
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    xbmc.executebuiltin('Container.SetViewMode(60)')      # BN Details view


def ia_play(handle, u, t, identifier=''):
    """resolve an Archive film with its details, so the player knows it is a movie (subtitles, history)"""
    li = xbmcgui.ListItem(t, path=u)
    thumb = 'https://archive.org/services/img/%s' % identifier if identifier else ''
    li.setArt({'thumb': thumb, 'poster': thumb})
    tag = li.getVideoInfoTag()
    tag.setTitle(t)
    tag.setMediaType('movie')
    xbmcplugin.setResolvedUrl(handle, True, li)


def yt_search(handle, q):
    from . import yt
    list_rows(handle, yt_rows(yt.search(q)))
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    xbmc.executebuiltin('Container.SetViewMode(60)')      # BN Details view


def sources_screen(handle, url):
    st = status()
    li = xbmcgui.ListItem('[COLOR gold]%s[/COLOR]' % s('install_all'))
    li.setArt({'icon': 'DefaultAddonService.png'})
    xbmcplugin.addDirectoryItem(handle, url(a='prov_install_all'), li, False)
    for p in PROVIDERS:
        ok = installed(p[1])
        stable = st.get(p[0], {}).get('stable', True)
        flags = [s('on') if is_on(p[0]) else s('off')]
        if not ok:
            flags.append(s('not_inst'))
        if not stable:
            flags.append(s('unstable'))
        if p[4]:
            flags.append(s('searchable'))
        colour = 'limegreen' if is_on(p[0]) and ok else 'grey'
        li = xbmcgui.ListItem('[COLOR %s]●[/COLOR] %s  [COLOR grey](%s)[/COLOR]' % (colour, name_of(p), ', '.join(flags)))
        li.setArt({'icon': 'special://home/addons/%s/icon.png' % p[1] if ok else 'DefaultAddonVideo.png'})
        ctx = [(s('toggle'), 'RunPlugin(%s)' % url(a='prov_toggle', id=p[0]))]
        if ok:
            ctx.append((s('settings'), 'Addon.OpenSettings(%s)' % p[1]))
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(handle, url(a='prov_toggle', id=p[0]), li, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def toggle(pid):
    m = enabled_map()
    m[pid] = not is_on(pid)
    save('providers.json', m)


def install_all():
    from .iptv import install_addon
    st = status()
    todo = [p for p in PROVIDERS if not installed(p[1]) and st.get(p[0], {}).get('stable', True)]
    pd = xbmcgui.DialogProgress()
    pd.create('NovaTV', s('install_all'))
    for i, p in enumerate(todo):
        if pd.iscanceled():
            break
        pd.update(int(i * 100 / max(1, len(todo))), name_of(p))
        install_addon(p[1], timeout=90)
    pd.close()
