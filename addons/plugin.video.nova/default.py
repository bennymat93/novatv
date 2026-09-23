# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.common import (ADDON, T, tmdb, art, load, save, now_str, MEDIA, ui_lang)
from resources.lib import accounts, iptv, radio

HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
POV = 'plugin://plugin.video.pov/?'


def url(**kw):
    return BASE + '?' + urlencode(kw)


def icon(name):
    import os
    for ext in ('.png', '.jpg'):
        p = os.path.join(MEDIA, name + ext)
        if os.path.exists(p):
            return p
    return 'DefaultFolder.png'


def folder(label, target, ic=None, plot='', fanart=None, context=None):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': ic or 'DefaultFolder.png', 'thumb': ic or 'DefaultFolder.png',
               'fanart': fanart or icon('fanart')})
    li.getVideoInfoTag().setPlot(plot)
    if context:
        li.addContextMenuItems(context)
    xbmcplugin.addDirectoryItem(HANDLE, target, li, True)


def end(content='', cache=True):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)


# ------------------------------------------------------------------ root
def root():
    folder(T('movies'), url(a='media_root', m='movie'), icon('movies'))
    folder(T('series'), url(a='media_root', m='tv'), icon('series'))
    folder(T('tv'), url(a='tv_root'), icon('tv'))
    folder(T('radio'), url(a='radio_root'), icon('radio'))
    folder(T('history'), url(a='history'), icon('history'))
    folder(T('favourites'), url(a='favs'), icon('favourites'))
    folder(T('accounts'), url(a='accounts'), icon('accounts'))
    end(cache=False)


GENRES = {  # tmdb genre ids (movie, tv)
    'movie': [28, 12, 16, 35, 80, 99, 18, 10751, 14, 36, 27, 10402, 9648, 10749, 878, 53, 10752, 37],
    'tv': [10759, 16, 35, 80, 99, 18, 10751, 10762, 9648, 10763, 10764, 10765, 10766, 10767, 10768, 37],
}
LANGS = [('he', 'hebrew'), ('en', 'english'), ('ru', 'russian')]


def media_root(m):
    folder(T('search'), url(a='search', m=m), icon('search'))
    folder(T('trending'), url(a='list', m=m, path='/trending/%s/week' % m), icon('trending'))
    folder(T('popular'), url(a='list', m=m, path='/%s/popular' % m), icon('popular'))
    folder(T('top_rated'), url(a='list', m=m, path='/%s/top_rated' % m), icon('top'))
    folder(T('genres'), url(a='genres', m=m), icon('genres'))
    folder(T('languages'), url(a='langs', m=m), icon('languages'))
    folder(T('years'), url(a='years', m=m), icon('years'))
    if m == 'tv':
        folder(T('kukhnya'), url(a='kukhnya'), icon('kitchen'))
    end(cache=False)


def genres(m):
    for g in tmdb('/genre/%s/list' % m)['genres']:
        folder(g['name'], url(a='list', m=m, path='/discover/%s' % m, with_genres=g['id'],
                              sort_by='popularity.desc'), icon('genres'))
    end()


def langs(m):
    for code, key in LANGS:
        folder(T(key), url(a='list', m=m, path='/discover/%s' % m, with_original_language=code,
                           sort_by='popularity.desc'), icon('lang_' + code))
    end()


def years(m):
    import datetime
    field = 'primary_release_year' if m == 'movie' else 'first_air_date_year'
    for y in range(datetime.date.today().year, 1949, -1):
        folder(str(y), url(a='list', m=m, path='/discover/%s' % m, sort_by='popularity.desc', **{field: y}),
               icon('years'))
    end()


def _fav_ctx(kind, item_id, label, extra=''):
    return [(T('add_fav'), 'RunPlugin(%s)' % url(a='fav_add', kind=kind, id=item_id, label=label, extra=extra))]


def media_item(m, it):
    title = it.get('title') or it.get('name') or ''
    year = (it.get('release_date') or it.get('first_air_date') or '')[:4]
    label = '%s (%s)' % (title, year) if year else title
    li = xbmcgui.ListItem(label)
    li.setArt(art(it))
    tag = li.getVideoInfoTag()
    tag.setTitle(title)
    tag.setOriginalTitle(it.get('original_title') or it.get('original_name') or '')
    tag.setPlot(it.get('overview') or '')
    tag.setRating(float(it.get('vote_average') or 0), int(it.get('vote_count') or 0), 'tmdb', True)
    if year:
        tag.setYear(int(year))
    tag.setUniqueIDs({'tmdb': str(it['id'])}, 'tmdb')
    ctx = _fav_ctx('movie' if m == 'movie' else 'series', it['id'], label)
    if m == 'movie':
        tag.setMediaType('movie')
        li.setProperty('IsPlayable', 'true')
        target = POV + urlencode({'mode': 'play_media', 'mediatype': 'movie', 'tmdb_id': it['id']})
        manual = POV + urlencode({'mode': 'play_media', 'mediatype': 'movie', 'tmdb_id': it['id'], 'autoplay': 'false'})
        ctx.append((T('choose_src'), 'PlayMedia(%s)' % manual))
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(HANDLE, target, li, False)
    else:
        tag.setMediaType('tvshow')
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(HANDLE, url(a='seasons', id=it['id']), li, True)


def list_(m, path, page='1', **filters):
    if path.startswith('/discover/'):
        filters.setdefault('vote_count.gte', 15)   # hide stubs / junk entries
    data = tmdb(path, page=page, **filters)
    for it in data.get('results', []):
        if it.get('media_type') in ('person',):
            continue
        media_item(it.get('media_type') or m, it)
    if int(page) < min(int(data.get('total_pages', 1)), 500):
        folder('[B]%s >>[/B]' % T('next_page'), url(a='list', m=m, path=path, page=int(page) + 1, **filters),
               icon('next'))
    end('movies' if m == 'movie' else 'tvshows')


def search(m):
    q = xbmcgui.Dialog().input(T('search'))
    if not q:
        return end()
    list_(m, '/search/%s' % m, query=q)


def seasons(tv_id):
    show = tmdb('/tv/%s' % tv_id)
    for s in show.get('seasons', []):
        if s.get('season_number') == 0 and not s.get('episode_count'):
            continue
        li = xbmcgui.ListItem(s.get('name') or '%s %s' % (T('season'), s['season_number']))
        a = art(s) or art(show)
        a.setdefault('fanart', art(show).get('fanart'))
        li.setArt(a)
        li.getVideoInfoTag().setPlot(s.get('overview') or show.get('overview') or '')
        xbmcplugin.addDirectoryItem(HANDLE, url(a='episodes', id=tv_id, s=s['season_number']), li, True)
    end('seasons')


def episodes(tv_id, s):
    show = tmdb('/tv/%s' % tv_id)
    season = tmdb('/tv/%s/season/%s' % (tv_id, s))
    history = {h.get('key'): h for h in load('history.json', [])}
    for e in season.get('episodes', []):
        key = 'tv:%s:%s:%s' % (tv_id, s, e['episode_number'])
        seen = history.get(key)
        label = '%dx%02d. %s' % (int(s), e['episode_number'], e.get('name') or '')
        if seen:
            label = '[COLOR limegreen]✓[/COLOR] %s  [COLOR grey](%s %s)[/COLOR]' % (label, T('watched_at'), seen['when'])
        li = xbmcgui.ListItem(label)
        a = art(e)
        a['fanart'] = art(show).get('fanart', '')
        a.setdefault('poster', art(show).get('poster', ''))
        li.setArt(a)
        tag = li.getVideoInfoTag()
        tag.setMediaType('episode')
        tag.setTitle(e.get('name') or '')
        tag.setTvShowTitle(show.get('name') or '')
        tag.setSeason(int(s))
        tag.setEpisode(e['episode_number'])
        tag.setPlot(e.get('overview') or '')
        tag.setFirstAired(e.get('air_date') or '')
        if e.get('runtime'):
            tag.setDuration(int(e['runtime']) * 60)
        tag.setUniqueIDs({'tmdb': str(tv_id)}, 'tmdb')
        li.setProperty('IsPlayable', 'true')
        params = {'mode': 'play_media', 'mediatype': 'episode', 'tmdb_id': tv_id, 'season': s,
                  'episode': e['episode_number']}
        manual = dict(params, autoplay='false')
        li.addContextMenuItems([(T('choose_src'), 'PlayMedia(%s)' % (POV + urlencode(manual)))])
        xbmcplugin.addDirectoryItem(HANDLE, POV + urlencode(params), li, False)
    end('episodes', cache=False)


def kukhnya():
    res = tmdb('/search/tv', query='Кухня', first_air_date_year=2012, language='ru-RU')
    hit = next((r for r in res.get('results', []) if r.get('original_language') == 'ru'), None)
    if not hit:
        xbmcgui.Dialog().notification('NovaTV', T('empty'))
        return end()
    seasons(hit['id'])


# ------------------------------------------------------------------ history / favourites
def history():
    items = load('history.json', [])
    if not items:
        folder(T('empty'), url(a='noop'))
    for h in items[:500]:
        li = xbmcgui.ListItem('[COLOR grey]%s[/COLOR]  %s' % (h['when'], h['label']))
        li.setArt({'thumb': h.get('thumb', ''), 'fanart': h.get('fanart', '')})
        li.getVideoInfoTag().setPlot('%s: %s\n%s' % (T('watched_at'), h['when'], h.get('plot', '')))
        playable = bool(h.get('play'))
        if playable:
            li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, h.get('play') or url(a='noop'), li, False)
    if items:
        folder('[COLOR red]%s[/COLOR]' % T('clear'), url(a='history_clear'))
    end(cache=False)


FAV_KINDS = [('movie', 'movies'), ('series', 'series'), ('channel', 'channels'), ('radio', 'radio')]


def favs(kind=None):
    data = load('favourites.json', [])
    if not kind:
        for k, label in FAV_KINDS:
            n = sum(1 for f in data if f['kind'] == k)
            folder('%s (%d)' % (T(label), n), url(a='favs', kind=k), icon(label))
        return end(cache=False)
    for f in [f for f in data if f['kind'] == kind]:
        rm = [(T('rem_fav'), 'RunPlugin(%s)' % url(a='fav_rm', kind=kind, id=f['id']))]
        if kind == 'movie':
            li = xbmcgui.ListItem(f['label'])
            li.setProperty('IsPlayable', 'true')
            li.addContextMenuItems(rm)
            xbmcplugin.addDirectoryItem(HANDLE, POV + urlencode({'mode': 'play_media', 'mediatype': 'movie',
                                                                'tmdb_id': f['id']}), li, False)
        elif kind == 'series':
            folder(f['label'], url(a='seasons', id=f['id']), context=rm)
        else:
            li = xbmcgui.ListItem(f['label'])
            li.setProperty('IsPlayable', 'true')
            li.addContextMenuItems(rm)
            xbmcplugin.addDirectoryItem(HANDLE, f.get('extra', ''), li, False)
    end(cache=False)


def fav_add(kind, id, label, extra=''):
    data = load('favourites.json', [])
    if not any(f['kind'] == kind and str(f['id']) == str(id) for f in data):
        data.insert(0, {'kind': kind, 'id': id, 'label': label, 'extra': extra, 'added': now_str()})
        save('favourites.json', data)
    xbmcgui.Dialog().notification('NovaTV', T('fav_added'), icon('favourites'), 2500)


def fav_rm(kind, id):
    data = [f for f in load('favourites.json', []) if not (f['kind'] == kind and str(f['id']) == str(id))]
    save('favourites.json', data)
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------------ router
def router(p):
    a = p.pop('a', None)
    if not a:
        return root()
    simple = {
        'media_root': lambda: media_root(p['m']),
        'genres': lambda: genres(p['m']),
        'langs': lambda: langs(p['m']),
        'years': lambda: years(p['m']),
        'search': lambda: search(p['m']),
        'seasons': lambda: seasons(p['id']),
        'episodes': lambda: episodes(p['id'], p['s']),
        'kukhnya': kukhnya,
        'history': history,
        'history_clear': lambda: (save('history.json', []), xbmc.executebuiltin('Container.Refresh')),
        'favs': lambda: favs(p.get('kind')),
        'fav_add': lambda: fav_add(**p),
        'fav_rm': lambda: fav_rm(**p),
        'accounts': lambda: accounts.screen(HANDLE, url),
        'acc': lambda: accounts.action(p['do']),
        'tv_root': lambda: iptv.menu(HANDLE, url, folder, end),
        'tv_do': lambda: iptv.action(p['do']),
        'radio_root': lambda: radio.menu(HANDLE, url, folder, end),
        'radio_list': lambda: radio.listing(HANDLE, url, end, **p),
        'noop': lambda: None,
    }
    if a == 'list':
        m, path = p.pop('m'), p.pop('path')
        return list_(m, path, **p)
    simple[a]()


if __name__ == '__main__':
    try:
        router(dict(parse_qsl(sys.argv[2][1:])))
    except Exception as e:
        import traceback
        xbmc.log('[NovaTV] ' + traceback.format_exc(), xbmc.LOGERROR)
        xbmcgui.Dialog().notification('NovaTV', '%s: %s' % (T('error'), e), xbmcgui.NOTIFICATION_ERROR)
        try:
            xbmcplugin.endOfDirectory(HANDLE, False)
        except Exception:
            pass
