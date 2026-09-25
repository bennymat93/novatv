# -*- coding: utf-8 -*-
"""Radio via the free, open radio-browser.info directory (no key, no quota)."""
import xbmcgui
import xbmcplugin

from .common import T, load, save, log

# radio-browser is run by volunteers on several mirrors; "all" is round-robin DNS and sometimes lands on a
# broken one (HTTP 502). Try each mirror, and fall back to the last good answer.
SERVERS = ['https://all.api.radio-browser.info', 'https://de1.api.radio-browser.info',
           'https://de2.api.radio-browser.info', 'https://fi1.api.radio-browser.info', 'https://nl1.api.radio-browser.info']
HEADERS = {'User-Agent': 'NovaTV/0.2'}


def _get(path, **params):
    import requests
    params.setdefault('hidebroken', 'true')
    params.setdefault('order', 'votes')
    params.setdefault('reverse', 'true')
    params.setdefault('limit', 300)
    key = 'radio_cache.json'
    cache = load(key, {})
    ck = path + '?' + '&'.join('%s=%s' % kv for kv in sorted(params.items()))
    for base in SERVERS:
        try:
            r = requests.get(base + '/json' + path, params=params, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            cache[ck] = data
            save(key, cache)
            return data
        except Exception as e:
            log('radio-browser %s: %s' % (base, e))
    return cache.get(ck, [])


def menu(handle, url, folder, end):
    folder(T('israel'), url(a='radio_list', by='country', v='IL'), 'DefaultMusicGenres.png')
    folder(T('russia'), url(a='radio_list', by='country', v='RU'), 'DefaultMusicGenres.png')
    folder(T('hebrew'), url(a='radio_list', by='language', v='hebrew'), 'DefaultMusicGenres.png')
    folder(T('russian'), url(a='radio_list', by='language', v='russian'), 'DefaultMusicGenres.png')
    folder(T('english'), url(a='radio_list', by='language', v='english'), 'DefaultMusicGenres.png')
    folder(T('top_world'), url(a='radio_list', by='top', v=''), 'DefaultMusicGenres.png')
    folder(T('search'), url(a='radio_list', by='search', v=''), 'DefaultAddonsSearch.png')
    end(cache=False)


def listing(handle, url, end, by, v):
    if by == 'country':
        data = _get('/stations/bycountrycodeexact/' + v)
    elif by == 'language':
        data = _get('/stations/bylanguageexact/' + v)
    elif by == 'search':
        q = xbmcgui.Dialog().input(T('search'))
        if not q:
            return end()
        data = _get('/stations/search', name=q)
    else:
        data = _get('/stations/topvote/100')
    seen = set()
    for s in data:
        name = (s.get('name') or '').strip()
        stream = s.get('url_resolved') or s.get('url')
        if not name or not stream or name.lower() in seen:
            continue
        seen.add(name.lower())
        li = xbmcgui.ListItem(name)
        li.setArt({'thumb': s.get('favicon') or 'DefaultAudio.png', 'icon': s.get('favicon') or 'DefaultAudio.png'})
        tag = li.getMusicInfoTag()
        tag.setTitle(name)
        tag.setGenres([g for g in (s.get('tags') or '').split(',') if g][:3])
        tag.setComment('%s · %s kbps' % (s.get('country') or '', s.get('bitrate') or '?'))
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems([(T('add_fav'), 'RunPlugin(%s)' % url(a='fav_add', kind='radio', id=s['stationuuid'],
                                                                     label=name, extra=stream))])
        xbmcplugin.addDirectoryItem(handle, stream, li, False)
    xbmcplugin.setContent(handle, 'songs')
    end()
