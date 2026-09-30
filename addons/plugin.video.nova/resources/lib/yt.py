# -*- coding: utf-8 -*-
"""YouTube lists without a personal API key.

The YouTube add-on (7.x) refuses search and channel pages until the user creates Google API
keys, but it still *plays* any video. NovaTV therefore reads the lists itself from YouTube's
public web endpoint (the one youtube.com uses) and hands playback to the YouTube add-on.
Stdlib + requests only; every failure returns an empty list.
"""
import json
import re

PLAY = 'plugin://plugin.video.youtube/play/?video_id=%s'
VIDEOS_TAB = 'EgZ2aWRlb3PyBgQKAjoA'
_CTX = {'client': {'clientName': 'WEB', 'clientVersion': '2.20250101.00.00', 'hl': 'en', 'gl': 'IL'}}


def _post(endpoint, body, hl=None):
    """hl: force the answer's language ('en' = numbers and dates in one known format)"""
    import requests
    ctx = {'client': dict(_CTX['client'])}
    try:
        from .common import ui_lang
        ctx['client']['hl'] = hl or {'he': 'iw', 'ru': 'ru'}.get(ui_lang(), 'en')
    except Exception:
        ctx['client']['hl'] = hl or 'en'
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


_DUR = re.compile(r'"text":\s*"(\d{1,2}:\d{2}(?::\d{2})?)"')
_VIEWS = re.compile(r'"content":\s*"([\d.,]+[KMB]?) (?:views|צפיות)"')
_AGO = re.compile(r'"content":\s*"(\d+ \w+ ago|לפני [^"]+)"')


def seconds(duration):
    """"1:02:03" / "21:33" -> seconds (0 when unknown)"""
    s = 0
    for part in (duration or '').split(':'):
        if not part.isdigit():
            return 0
        s = s * 60 + int(part)
    return s


def _views(text):
    m = re.match(r'([\d.,]+)\s*([KMB]?)', (text or '').replace(',', ''))
    if not m:
        return 0
    return int(float(m.group(1)) * {'': 1, 'K': 1e3, 'M': 1e6, 'B': 1e9}[m.group(2)])


def _items(data):
    """videos of a youtubei answer: id, title, thumb, channel (+ channel_id), duration ("21:33"), secs, views, age.
    Shorts (reel / shortsLockupViewModel / /shorts/ links) are never returned."""
    out, seen = [], set()
    for v in _walk(data, 'videoRenderer'):
        vid = v.get('videoId')
        if not vid or vid in seen:
            continue
        seen.add(vid)
        thumbs = (v.get('thumbnail') or {}).get('thumbnails') or [{}]
        owner = next(_walk(v.get('ownerText') or {}, 'browseId'), '')
        url = next(_walk(v.get('navigationEndpoint') or {}, 'url'), '')
        dur = _text(v.get('lengthText'))
        out.append({'id': vid, 'title': _text(v.get('title')), 'thumb': thumbs[-1].get('url', ''),
                    'channel': _text(v.get('ownerText')), 'channel_id': owner, 'duration': dur, 'secs': seconds(dur),
                    'views': _views(_text(v.get('viewCountText'))), 'age': _text(v.get('publishedTimeText')),
                    'short': '/shorts/' in url,
                    'plot': _text((v.get('detailedMetadataSnippets') or [{}])[0].get('snippetText'))})
    for v in _walk(data, 'lockupViewModel'):
        vid = v.get('contentId')
        if not vid or vid in seen or v.get('contentType') not in (None, 'LOCKUP_CONTENT_TYPE_VIDEO'):
            continue
        seen.add(vid)
        meta = (v.get('metadata') or {}).get('lockupMetadataViewModel') or {}
        src = next(_walk(v.get('contentImage') or {}, 'sources'), [{}])
        blob = json.dumps(v, ensure_ascii=False)            # YouTube's new format: duration / views / age are badges
        dur = (_DUR.findall(blob) or [''])[0]
        views = (_VIEWS.findall(blob) or [''])[0]
        age = (_AGO.findall(blob) or [''])[0]
        out.append({'id': vid, 'title': _text(meta.get('title')), 'thumb': (src[-1] if src else {}).get('url', ''),
                    'channel': '', 'channel_id': '', 'duration': dur, 'secs': seconds(dur), 'views': _views(views),
                    'age': age, 'short': '/shorts/' in blob, 'plot': ''})
    for v in _walk(data, 'playlistVideoRenderer'):          # course playlists (MIT OCW, NPTEL ...)
        vid = v.get('videoId')
        if not vid or vid in seen:
            continue
        seen.add(vid)
        thumbs = (v.get('thumbnail') or {}).get('thumbnails') or [{}]
        secs = int(v.get('lengthSeconds') or 0)
        out.append({'id': vid, 'title': _text(v.get('title')), 'thumb': thumbs[-1].get('url', ''),
                    'channel': _text(v.get('shortBylineText')), 'channel_id': next(_walk(v.get('shortBylineText') or {}, 'browseId'), ''),
                    'duration': _text(v.get('lengthText')), 'secs': secs, 'views': 0, 'age': '', 'short': False, 'plot': ''})
    return [i for i in out if i['title'] and not i['short']]


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


def channel_videos(channel_id, pages=2):
    """the newest videos of a channel over `pages` pages (~30 each), English metadata; cached like the lists"""
    def fetch():
        out, token = [], ''
        for _ in range(pages):
            data = _post('browse', {'continuation': token} if token else {'browseId': channel_id, 'params': VIDEOS_TAB}, hl='en')
            out += _items(data)
            token = _continuation(data)
            if not token:
                break
        return out
    return _cached('cv:%s:%d' % (channel_id, pages), fetch) or []


def playlist_videos(playlist_id):
    """every video of a playlist (course lectures in order)"""
    def fetch():
        out, token = [], ''
        for _ in range(10):
            data = _post('browse', {'continuation': token} if token else {'browseId': 'VL' + playlist_id}, hl='en')
            out += _items(data)
            token = _continuation(data)
            if not token:
                break
        return out
    return _cached('pl:%s' % playlist_id, fetch) or []


def search_videos(q, pages=1):
    """search (English metadata, videos only) - callers filter by channel / duration"""
    def fetch():
        out, token = [], ''
        for _ in range(pages):
            data = _post('search', {'continuation': token} if token else {'query': q, 'params': 'EgIQAQ=='}, hl='en')
            out += _items(data)
            token = _continuation(data)
            if not token:
                break
        return out
    return _cached('sv:%s:%d' % (norm_query(q), pages), fetch) or []
