# -*- coding: utf-8 -*-
"""Curated learning sections: "ידע וטכנולוגיה" and "אילוף כלבים".

Content = curated YouTube channels (resources/topics/<section>.json, one easy-to-edit file per section), read with
yt.py (no API key), played by the bundled YouTube add-on. Only in-depth videos: at least `min_seconds` long,
Shorts never shown.
  knowledge: categories each with their own channels ('filter' channels must also match the category's title regex)
  dogs:      one channel list; a category = the videos of all channels whose title matches its regex;
             "top rated" = the most-watched long lessons of those (positive-reinforcement) channels
The selection logic (select / rank_top / age_days / search_local) is plain Python for unit tests.
"""
import json
import os
import re

SECTIONS = ('knowledge', 'dogs')
PAGES = {'knowledge': 2, 'dogs': 4}   # pages of ~30 newest videos per channel (dog channels: deeper back catalogue)


# ------------------------------------------------------------ pure logic
def age_days(age):
    """"3 weeks ago" -> 21 (unknown -> a large number: sorts last)"""
    m = re.match(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', age or '')
    if not m:
        return 10 ** 6
    n = int(m.group(1))
    return n * {'second': 0, 'minute': 0, 'hour': 0, 'day': 1, 'week': 7, 'month': 30, 'year': 365}[m.group(2)]


def select(videos, min_seconds, match=None):
    """long enough, not a Short, title matches (when a regex is given); duplicates removed"""
    rx = re.compile(match) if match else None
    out, seen = [], set()
    for v in videos:
        if v.get('short') or v['id'] in seen or int(v.get('secs') or 0) < min_seconds:
            continue
        if rx and not rx.search(v.get('title') or ''):
            continue
        seen.add(v['id'])
        out.append(v)
    return out


def newest_first(videos):
    return sorted(videos, key=lambda v: age_days(v.get('age')))


def rank_top(videos, min_seconds, limit=40):
    """"top rated" of a section: the most-watched long lessons (views), one list over all its channels"""
    return sorted(select(videos, min_seconds), key=lambda v: -int(v.get('views') or 0))[:limit]


def search_local(videos, q):
    """titles with every word of the query; when none has them all, the titles with most of the words"""
    words = [w for w in re.findall(r'\w+', (q or '').lower()) if len(w) > 1]
    if not words:
        return []
    scored = [(sum(w in (v.get('title') or '').lower() for w in words), v) for v in videos]
    full = [v for n, v in scored if n == len(words)]
    if full:
        return full
    best = max((n for n, _ in scored), default=0)
    return [v for n, v in scored if best and n == best]


# ------------------------------------------------------------ data
def _dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'topics')


def load(section):
    with open(os.path.join(_dir(), section + '.json'), encoding='utf-8') as f:
        return json.load(f)


def label(entry, lang):
    return entry.get({'he': 'he', 'en': 'en', 'ru': 'ru'}.get(lang, 'en')) or entry.get('en') or ''


def _channels_videos(channels, pages=2):
    """newest videos of every channel, in parallel (each cached 6 h by yt.py)"""
    from concurrent.futures import ThreadPoolExecutor
    from . import yt
    with ThreadPoolExecutor(6) as ex:
        lists = list(ex.map(lambda c: [dict(v, channel=v.get('channel') or c['name'], channel_id=c['id'])
                                       for v in yt.channel_videos(c['id'], pages)], channels))
    return [v for lst in lists for v in lst]


def category_videos(section, cat_id):
    cfg = load(section)
    cat = next(c for c in cfg['categories'] if c['id'] == cat_id)
    if section == 'dogs':
        return newest_first(select(_channels_videos(cfg['channels'], PAGES[section]), cfg['min_seconds'], cat.get('match')))
    out = []
    by_filter = {c['id']: c.get('filter', False) for c in cat['channels']}
    vids = _channels_videos(cat['channels'], PAGES[section])
    for v in select(vids, cfg['min_seconds']):
        if by_filter.get(v['channel_id']) and cat.get('match') and not re.search(cat['match'], v.get('title') or ''):
            continue
        out.append(v)
    return newest_first(out)


def all_channels(section):
    cfg = load(section)
    if section == 'dogs':
        return cfg['channels']
    seen, out = set(), []
    for cat in cfg['categories']:
        for c in cat['channels']:
            if c['id'] not in seen:
                seen.add(c['id'])
                out.append(c)
    return out


def top_videos(section):
    cfg = load(section)
    return rank_top(_channels_videos(all_channels(section), PAGES[section]), cfg['min_seconds'], (cfg.get('top') or {}).get('limit', 40))


def search(section, q):
    """only this section's channels: YouTube's search filtered to them + the channels' own recent videos"""
    from . import yt
    cfg = load(section)
    ids = {c['id'] for c in all_channels(section)}
    found = [v for v in yt.search_videos(q, pages=3) if v.get('channel_id') in ids]
    found += search_local(_channels_videos(all_channels(section), PAGES[section]), q)
    return select(found, cfg['min_seconds'])


# ------------------------------------------------------------ Kodi screens
def _list(handle, videos):
    import xbmcplugin
    from .providers import list_rows, yt_rows
    rows = yt_rows(videos)
    for r, v in zip(rows, videos):
        r['plot'] = ' · '.join(x for x in (v.get('channel'), v.get('duration'), v.get('age')) if x)
        r['art'] = {'thumb': v['thumb'], 'icon': v['thumb'], 'poster': v['thumb'], 'fanart': v['thumb']}
    list_rows(handle, rows)
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def root(handle, url, section, folder, end):
    """the section's own menu (also what the main-menu item opens)"""
    from .common import ui_lang, MEDIA, T
    cfg = load(section)
    lang = ui_lang()
    folder(T('search'), url(a='topic_search', s=section), os.path.join(MEDIA, 'search_%s.png' % section))
    if cfg.get('top'):
        folder(label(cfg['top'], lang), url(a='topic_top', s=section), os.path.join(MEDIA, 'cats', 'topic_top.png'))
    for c in cfg['categories']:
        folder(label(c, lang), url(a='topic_cat', s=section, c=c['id']), os.path.join(MEDIA, 'cats', 'topic_%s.png' % c['icon']))
    end(cache=False)


def categories(handle, url, section):
    """home widget: one tile per category"""
    import xbmcgui
    import xbmcplugin
    from .common import ui_lang, MEDIA
    lang = ui_lang()
    for c in load(section)['categories']:
        tile = os.path.join(MEDIA, 'cats', 'topic_%s.png' % c['icon'])
        li = xbmcgui.ListItem(label(c, lang))
        li.setArt({'icon': tile, 'thumb': tile})
        xbmcplugin.addDirectoryItem(handle, url(a='topic_cat', s=section, c=c['id']), li, True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def show_category(handle, section, cat_id):
    _list(handle, category_videos(section, cat_id))


def show_top(handle, section):
    _list(handle, top_videos(section))


def show_search(handle, section, q=''):
    import xbmcgui
    import xbmcplugin
    if not q:
        q = xbmcgui.Dialog().input(xbmc_label(section))
    if not q:
        return xbmcplugin.endOfDirectory(handle, succeeded=False)
    _list(handle, search(section, q))


def xbmc_label(section):
    from .common import ui_lang
    names = {'knowledge': ('חיפוש בידע וטכנולוגיה', 'Search knowledge & technology', 'Поиск: знания и технологии'),
             'dogs': ('חיפוש באילוף כלבים', 'Search dog training', 'Поиск: дрессировка собак')}
    return names[section][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]
