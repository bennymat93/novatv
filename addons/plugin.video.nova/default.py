# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.common import (ADDON, T, tmdb, art, load, save, now_str, MEDIA, ui_lang)
from resources.lib import accounts, iptv, radio, backup, libraries, providers, status

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


BN_VIEW = 60          # BN Details view: backdrop + full info of the focused title (skin View_60_BN.xml)


def end(content='', cache=True):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)
    if content in ('movies', 'tvshows', 'seasons', 'episodes', 'videos'):
        xbmc.executebuiltin('Container.SetViewMode(%d)' % BN_VIEW)


def details(m, ids):
    """full TMDb details for a page of titles, fetched in parallel (cached 6 h by tmdb())"""
    import threading
    out = {}

    def one(i):
        try:
            if m == 'movie':
                out[i] = tmdb('/movie/%s' % i, append_to_response='credits,release_dates')
            else:
                out[i] = tmdb('/tv/%s' % i, append_to_response='credits,content_ratings')
        except Exception:
            pass
    th = [threading.Thread(target=one, args=(i,), daemon=True) for i in ids]
    [t.start() for t in th]
    [t.join(12) for t in th]
    return out


def apply_details(li, tag, m, d):
    """runtime, genres, tagline, cast, director, age rating, studio on the list item itself"""
    if not d:
        return
    tag.setGenres([g['name'] for g in d.get('genres', [])])
    if d.get('tagline'):
        tag.setTagLine(d['tagline'])
    rt = d.get('runtime') or (d.get('episode_run_time') or [0])[0]
    if rt:
        tag.setDuration(int(rt) * 60)
    cr = d.get('credits') or {}
    cast = []
    for c in (cr.get('cast') or [])[:8]:
        a = xbmc.Actor(c.get('name', ''), c.get('character', ''), c.get('order', 0),
                       ('https://image.tmdb.org/t/p/w185' + c['profile_path']) if c.get('profile_path') else '')
        cast.append(a)
    if cast:
        tag.setCast(cast)
    directors = [c['name'] for c in cr.get('crew', []) if c.get('job') == 'Director']
    if m != 'movie':
        directors = [c['name'] for c in d.get('created_by', [])]
    if directors:
        tag.setDirectors(directors[:2])
    studios = [c['name'] for c in (d.get('production_companies') or d.get('networks') or [])][:2]
    if studios:
        tag.setStudios(studios)
    mpaa = ''
    for r in (d.get('release_dates') or {}).get('results', []):
        if r.get('iso_3166_1') in ('IL', 'US'):
            mpaa = next((x.get('certification') for x in r.get('release_dates', []) if x.get('certification')), '') or mpaa
    for r in (d.get('content_ratings') or {}).get('results', []):
        if r.get('iso_3166_1') in ('IL', 'US') and r.get('rating'):
            mpaa = r['rating']
    if mpaa:
        tag.setMpaa(mpaa)
    if m != 'movie':
        li.setProperty('TotalSeasons', str(d.get('number_of_seasons') or ''))
        li.setProperty('TotalEpisodes', str(d.get('number_of_episodes') or ''))


# ------------------------------------------------------------------ root
def root():
    folder('[B]%s[/B]' % providers.s('hub_search'), url(a='hub_search'), icon('search'))
    folder(T('movies'), url(a='media_root', m='movie'), icon('movies'))
    folder(T('series'), url(a='media_root', m='tv'), icon('series'))
    folder(T('tv'), url(a='tv_root'), icon('tv'))
    folder(T('radio'), url(a='radio_root'), icon('radio'))
    folder(T('history'), url(a='history'), icon('history'))
    folder(T('favourites'), url(a='favs'), icon('favourites'))
    folder(providers.s('library'), url(a='libs'), icon('libraries'))
    folder(T('accounts'), url(a='accounts'), icon('accounts'))
    folder(T('backup_menu'), url(a='bk_menu'), icon('backup'))
    folder(status.s('title'), url(a='status'), icon('accounts'))
    end(cache=False)


def bk_menu():
    for label, act in ((T('backup'), 'bk_do'), (T('restore'), 'bk_restore')):
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': 'DefaultAddonProgram.png'})
        xbmcplugin.addDirectoryItem(HANDLE, url(a=act), li, False)
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


def media_item(m, it, d=None):
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
    tag.setPremiered(it.get('release_date') or it.get('first_air_date') or '')
    apply_details(li, tag, 'movie' if m == 'movie' else 'tv', d)
    ctx = _fav_ctx('movie' if m == 'movie' else 'series', it['id'], label)
    if m == 'movie':
        tag.setMediaType('movie')
        li.setProperty('IsPlayable', 'true')
        li.setProperty('IsPlayable', 'false')
        orig = it.get('original_title') or ''
        target = url(a='play', m='movie', id=it['id'], q=('%s %s' % (title, year)).strip(),
                     alt=('%s %s' % (orig, year)).strip() if orig and orig != title else '')
        manual = POV + urlencode({'mode': 'play_media', 'mediatype': 'movie', 'tmdb_id': it['id'], 'autoplay': 'false'})
        ctx.append((T('choose_src'), 'PlayMedia(%s)' % manual))
        ctx.append((providers.s('hub_search'), 'Container.Update(%s)' % url(a='hub_search', q=title)))
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
    rows = [it for it in data.get('results', []) if it.get('media_type') not in ('person',)]
    full = {}
    for kind in ('movie', 'tv'):
        ids = [it['id'] for it in rows if (it.get('media_type') or m) == kind]
        full.update({(kind, k): v for k, v in details(kind, ids).items()})
    for it in rows:
        kind = it.get('media_type') or m
        media_item(kind, it, full.get((kind, it['id'])))
    if int(page) < min(int(data.get('total_pages', 1)), 500):
        folder('[B]%s >>[/B]' % T('next_page'), url(a='list', m=m, path=path, page=int(page) + 1, **filters),
               icon('next'))
    end('movies' if m == 'movie' else 'tvshows')


def hub_search(q=''):
    if not q:
        q = xbmcgui.Dialog().input(providers.s('hub_search'))
    if not q:
        return end()
    xbmcplugin.setPluginCategory(HANDLE, q)
    providers.hub_results(HANDLE, q, media_item)
    end('videos', cache=False)


def play(m, id, q, alt='', s=None, e=None):
    if m == 'movie':
        pov = POV + urlencode({'mode': 'play_media', 'mediatype': 'movie', 'tmdb_id': id})
    else:
        pov = POV + urlencode({'mode': 'play_media', 'mediatype': 'episode', 'tmdb_id': id, 'season': s, 'episode': e})
    providers.play_with_fallback(pov, q, alt)


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
            label = '[COLOR limegreen]●[/COLOR] %s  [COLOR grey](%s %s)[/COLOR]' % (label, T('watched_at'), seen['when'])
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
        li.setProperty('IsPlayable', 'false')
        params = {'mode': 'play_media', 'mediatype': 'episode', 'tmdb_id': tv_id, 'season': s,
                  'episode': e['episode_number']}
        manual = dict(params, autoplay='false')
        li.addContextMenuItems([(T('choose_src'), 'PlayMedia(%s)' % (POV + urlencode(manual))),
                                (providers.s('hub_search'), 'Container.Update(%s)' % url(a='hub_search', q=show.get('name') or ''))])
        target = url(a='play', m='episode', id=tv_id, s=s, e=e['episode_number'],
                     q='%s %s' % (show.get('name') or '', e.get('name') or ''),
                     alt=show.get('original_name') if show.get('original_name') != show.get('name') else '')
        xbmcplugin.addDirectoryItem(HANDLE, target, li, False)
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
        target = h.get('play') or url(a='noop')
        if target.startswith('plugin://plugin.video.pov/'):       # entries saved before 0.1.8
            q = dict(parse_qsl(target.split('?', 1)[1]))
            target = url(a='play', m=q.get('mediatype', 'movie'), id=q.get('tmdb_id', ''), q=h['label'],
                         **({'s': q['season'], 'e': q['episode']} if q.get('season') else {}))
        li.setProperty('IsPlayable', 'false' if target.startswith(BASE) else 'true')
        xbmcplugin.addDirectoryItem(HANDLE, target, li, False)
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
            li.setProperty('IsPlayable', 'false')
            li.addContextMenuItems(rm)
            xbmcplugin.addDirectoryItem(HANDLE, url(a='play', m='movie', id=f['id'], q=f['label']), li, False)
        elif kind == 'series':
            folder(f['label'], url(a='seasons', id=f['id']), context=rm)
        elif kind == 'channel':
            li = xbmcgui.ListItem(f['label'])
            li.addContextMenuItems(rm)
            xbmcplugin.addDirectoryItem(HANDLE, url(a='tv_play', id=f['id']), li, False)
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
    refresh()


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
        'history_clear': lambda: (save('history.json', []), refresh()),
        'favs': lambda: favs(p.get('kind')),
        'fav_add': lambda: fav_add(**p),
        'fav_rm': lambda: fav_rm(**p),
        'accounts': lambda: accounts.screen(HANDLE, url),
        'acc': lambda: accounts.action(p['do']),
        'tv_root': lambda: iptv.menu(HANDLE, url, folder, end),
        'tv_do': lambda: iptv.action(p['do']),
        'tv_list': lambda: iptv.channel_list(HANDLE, p.get('group')),
        'tv_play': lambda: iptv.play_channel(p['id']),
        'radio_root': lambda: radio.menu(HANDLE, url, folder, end),
        'radio_list': lambda: radio.listing(HANDLE, url, end, **p),
        'noop': lambda: None,
        'libs': lambda: providers.library(HANDLE, url),
        'lib_cat': lambda: providers.library_cat(HANDLE, url, p['cat']),
        'lib_open': lambda: providers.open_provider(HANDLE, p['id'], p.get('q', '')),
        'sources': lambda: providers.sources_screen(HANDLE, url),
        'prov_toggle': lambda: (providers.toggle(p['id']), refresh()),
        'prov_install_all': lambda: (providers.install_all(), refresh()),
        'hub_search': lambda: hub_search(p.get('q', '')),
        'status': lambda: status.listing(HANDLE),
        'yt_channel': lambda: providers.yt_channel(HANDLE, url, p['id'], p.get('token', '')),
        'yt_search': lambda: providers.yt_search(HANDLE, p['q']),
        'ia_search': lambda: providers.ia_search(HANDLE, p['q']),
        'ia_item': lambda: providers.ia_item(HANDLE, p['id']),
        'ia_play': lambda: providers.ia_play(HANDLE, p['u'], p.get('t', ''), p.get('id', '')),
        'play': lambda: play(**p),
        'lib_install': lambda: libraries.install(p['id']),
        'bk_menu': bk_menu,
        'bk_do': backup.backup,
        'bk_restore': backup.restore,
        'bk_auto': lambda: backup.auto_backup(every_days=0),
    }
    if a == 'list':
        m, path = p.pop('m'), p.pop('path')
        return list_(m, path, **p)
    if a in ACTIONS:
        # actions are not folders: close the directory request first, refresh afterwards
        if HANDLE >= 0:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, updateListing=False, cacheToDisc=False)
        simple[a]()
        return
    simple[a]()


ACTIONS = {'fav_add', 'fav_rm', 'history_clear', 'acc', 'tv_do', 'tv_play', 'noop', 'lib_install', 'bk_do', 'bk_restore', 'bk_auto',
           'play', 'prov_toggle', 'prov_install_all'}


def refresh():
    # never refresh while Kodi is still building a listing (crashes Kodi 21)
    mon = xbmc.Monitor()
    for _ in range(40):
        if not xbmc.getCondVisibility('Container.IsUpdating'):
            break
        mon.waitForAbort(0.1)
    xbmc.executebuiltin('Container.Refresh')


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
