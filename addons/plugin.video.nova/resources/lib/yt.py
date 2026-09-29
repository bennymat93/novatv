# -*- coding: utf-8 -*-
"""YouTube lists without a personal API key.

The YouTube add-on (7.x) refuses search and channel pages until the user creates Google API
keys, but it still *plays* any video. NovaTV therefore reads the lists itself from YouTube's
public web endpoint (the one youtube.com uses) and hands playback to the YouTube add-on.
Stdlib + requests only; every failure returns an empty list.
"""

PLAY = 'plugin://plugin.video.youtube/play/?video_id=%s'
VIDEOS_TAB = 'EgZ2aWRlb3PyBgQKAjoA'
_CTX = {'client': {'clientName': 'WEB', 'clientVersion': '2.20250101.00.00', 'hl': 'en', 'gl': 'IL'}}


def _post(endpoint, body):
    import requests
    ctx = {'client': dict(_CTX['client'])}
    try:
        from .common import ui_lang
        ctx['client']['hl'] = {'he': 'iw', 'ru': 'ru'}.get(ui_lang(), 'en')
    except Exception:
        pass
    body = dict(body, context=ctx)
    r = requests.post('https://www.youtube.com/youtubei/v1/%s?prettyPrint=false' % endpoint, json=body,
                      headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=15)
    r.raise_for_status()
    return r.json()


def _walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            else:
                yield from _walk(v, key)
    elif isinstance(o, list):
        for i in o:
            yield from _walk(i, key)


def _text(t):
    if not t:
        return ''
    if 'simpleText' in t:
        return t['simpleText']
    if 'content' in t:
        return t['content']
    return ''.join(r.get('text', '') for r in t.get('runs', []))


def _items(data):
    out, seen = [], set()
    for v in _walk(data, 'videoRenderer'):
        vid = v.get('videoId')
        if not vid or vid in seen:
            continue
        seen.add(vid)
        thumbs = (v.get('thumbnail') or {}).get('thumbnails') or [{}]
        out.append({'id': vid, 'title': _text(v.get('title')), 'thumb': thumbs[-1].get('url', ''),
                    'channel': _text(v.get('ownerText')), 'duration': _text(v.get('lengthText')),
                    'plot': _text((v.get('detailedMetadataSnippets') or [{}])[0].get('snippetText'))})
    for v in _walk(data, 'lockupViewModel'):
        vid = v.get('contentId')
        if not vid or vid in seen or v.get('contentType') not in (None, 'LOCKUP_CONTENT_TYPE_VIDEO'):
            continue
        seen.add(vid)
        meta = (v.get('metadata') or {}).get('lockupMetadataViewModel') or {}
        src = next(_walk(v.get('contentImage') or {}, 'sources'), [{}])
        out.append({'id': vid, 'title': _text(meta.get('title')), 'thumb': (src[-1] if src else {}).get('url', ''),
                    'channel': '', 'duration': '', 'plot': ''})
    return [i for i in out if i['title']]


def _continuation(data):
    return next((c.get('token') for c in _walk(data, 'continuationCommand') if c.get('token')), '')


CACHE_MAX_AGE = 6 * 3600      # the last good answer is a fallback for a YouTube hiccup, never older than this


def norm_query(q):
    """cache key part: the whole query, case/space-normalised (different searches never share an entry)"""
    return ' '.join((q or '').lower().split())


def _cached(key, fetch):
    """one retry, then the last good answer of THIS key (at most CACHE_MAX_AGE old):
    a single YouTube hiccup must not show an empty list, and nothing stale is ever shown"""
    import time
    try:
        from .common import load, save
    except Exception:
        load = save = None
    for attempt in range(2):
        try:
            value = fetch()
            if value and value[0] if isinstance(value, tuple) else value:
                if save:
                    cache = load('yt_cache.json', {})
                    now = time.time()
                    cache = {k: v for k, v in cache.items()              # drop old / old-format entries
                             if isinstance(v, dict) and now - v.get('t', 0) < CACHE_MAX_AGE}
                    cache[key] = {'t': now, 'v': value}
                    save('yt_cache.json', cache)
                return value
        except Exception:
            pass
        time.sleep(1)
    hit = load('yt_cache.json', {}).get(key) if load else None
    if isinstance(hit, dict) and time.time() - hit.get('t', 0) < CACHE_MAX_AGE:
        return hit['v']
    return None


def search(q, limit=30):
    res = _cached('s:' + norm_query(q), lambda: _items(_post('search', {'query': q}))[:limit])
    return res or []


def channel(channel_id, token=''):
    """(videos, next_page_token)"""
    def fetch():
        data = _post('browse', {'continuation': token} if token else {'browseId': channel_id, 'params': VIDEOS_TAB})
        return _items(data), _continuation(data)
    res = _cached('c:%s:%s' % (channel_id, token[:40]), fetch)
    return tuple(res) if res else ([], '')
