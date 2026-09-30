# -*- coding: utf-8 -*-
"""Israeli channels with automatic failover (1.4.0 Phase 3).

Found by tools/stream_check.py (30/09): the free playlists carry the main Israeli channels only through restream
servers (iptvhd.ru / freeott / mcquack) - unlicensed copies, several paid (HOT, Sport 5), mostly 403. Those hosts
are dropped (RESTREAM_HOSTS, iptv.merge). The main channels play from licensed sources instead, several per
channel, tried in order:
  1. the broadcaster's own public stream (checked in 3 s),
  2. Idan+ (bundled, official broadcaster players) - main feed, then its backup feeds.
The playlist entry of such a channel is plugin://plugin.video.nova/?a=live&ch=<key>; live() resolves it.
"""
RESTREAM_HOSTS = ('iptvhd.ru', 'freeott.top', 'mcquack.net')

KAN = 'https://kancdn.medonecdn.net/livehls/oil/kancdn-live/live/%s/live.livx/playlist.m3u8'
IDAN = 'plugin://plugin.video.idanplus/?url=%s&mode=%s&module=%s&moredata=best'

# key: (names the playlists / guides use, [direct streams], [(Idan+ url, module, mode)])
CHANNELS = {
    'kan11': (['Kan 11', 'כאן 11'], [KAN % 'kan11'], [('ch_11', 'kan', 10), ('ch_11b', 'tv', 10)]),
    'keshet12': (['Keshet 12', 'קשת 12', 'Channel 12'], [],
                 [('ch_12', 'keshet', 10), ('ch_12b', 'keshet', 10), ('ch_12b2', 'keshet', 10), ('ch_12b3', 'keshet', 10)]),
    'reshet13': (['Channel 13 (Israel)', 'Reshet 13', 'רשת 13', 'Channel 13'], [],
                 [('ch_13', 'reshet', 4), ('ch_13b', 'reshet', 4), ('ch_13b2', 'reshet', 4)]),
    'now14': (['Now 14', 'עכשיו 14', 'Channel 14'], ['https://r.il.cdn-redge.media/livehls/oil/ch14/live/ch14/live.livx/playlist.m3u8'],
              [('ch_14', '14tv', 10), ('ch_14b', 'tv', 10), ('ch_14b2', 'tv', 10)]),
    'kanedu': (['Kan Educational', 'כאן חינוכית'], [], [('ch_23', 'kan', 10), ('ch_23b', 'tv', 10)]),
    'ch24': (['Channel 24 (Israel)', 'Channel 24', 'ערוץ 24'], [], [('ch_24', 'keshet', 10), ('ch_24b', 'keshet', 10)]),
    'makan33': (['Makan 33', 'מכאן 33'], [KAN % 'makan'], [('ch_33', 'kan', 10), ('ch_33b', 'tv', 10)]),
    'knesset': (['Knesset Channel', 'ערוץ הכנסת', 'כנסת 99'], [], [('ch_99', 'tv', 10)]),
    'ch9': (['Channel 9 (Israel)', 'Channel 9', 'ערוץ 9'], ['https://contact.gostreaming.tv/Con-11/index.m3u8'], [('ch_9', 'tv', 10)]),
    'hidabroot': (['Hidabroot', 'הידברות'], ['https://cdn.cybercdn.live/HidabrootIL/Live97/playlist.m3u8'], [('ch_97', 'hidabroot', 10)]),
    'i24he': (['i24NEWS Hebrew', 'i24 עברית'], ['https://i24newshebrew-cdn.encoders.immergo.tv/master.m3u8'], [('ch_i24news', 'tv', 10)]),
    'i24en': (['i24NEWS English'], ['https://i24newsenglish-cdn.encoders.immergo.tv/master.m3u8'], [('ch_i24newsen', 'tv', 10)]),
    'i24fr': (['i24NEWS French'], ['https://i24newsfrench-cdn.encoders.immergo.tv/master.m3u8'], [('ch_i24newsfr', 'tv', 10)]),
    'i24ar': (['i24NEWS Arabic'], ['https://i24newsarabic-cdn.encoders.immergo.tv/master.m3u8'], [('ch_i24newsar', 'tv', 10)]),
}


def is_restream(url):
    return any(h in (url or '') for h in RESTREAM_HOSTS)


def key_for(name):
    """playlist channel name -> CHANNELS key (same normalisation as the guide matching) or None"""
    from .epg import norm
    n = norm(name)
    for key, (names, _, _) in CHANNELS.items():
        if n in (norm(x) for x in names):
            return key
    return None


def candidates(key):
    names, direct, idan = CHANNELS[key]
    return list(direct) + [IDAN % (u, mode, module) for u, module, mode in idan]


# ------------------------------------------------------------ Kodi
def _alive(url, timeout=3):
    """a direct HLS stream answers with a playlist within the timeout"""
    import requests
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
        return r.status_code == 200 and '#EXTM3U' in r.text[:200]
    except Exception:
        return False


def live(handle, key):
    """resolve a channel to the first source that works"""
    import xbmc
    import xbmcgui
    import xbmcplugin
    from .common import log
    if key not in CHANNELS:
        return xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
    for url in candidates(key):
        if url.startswith('plugin://') or _alive(url):
            li = xbmcgui.ListItem(path=url)
            if not url.startswith('plugin://') and xbmc.getCondVisibility('System.HasAddon(inputstream.adaptive)'):
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setMimeType('application/vnd.apple.mpegurl')
                li.setContentLookup(False)
            log('live %s -> %s' % (key, url[:80]))
            return xbmcplugin.setResolvedUrl(handle, True, li)
    return xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
