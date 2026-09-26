# -*- coding: utf-8 -*-
"""Unified IPTV: merge any number of M3U + EPG sources into one numbered
channel list and feed it to PVR IPTV Simple Client."""
import gzip
import json
import os
import re
import time

import xbmc
import xbmcgui

from .common import monitor
import xbmcvfs

from .common import T, load, save, PROFILE, log

MERGED_M3U = os.path.join(PROFILE, 'nova_channels.m3u')
MERGED_EPG = os.path.join(PROFILE, 'nova_epg.xml.gz')
PVR = 'pvr.iptvsimple'

# Israeli channels keep their familiar numbers (like Yes/HOT/Partner)
FIXED = [(r'\bkan\s*11\b|כאן\s*11', 11), (r'\bkeshet\s*12\b|\bchannel\s*12\b|קשת\s*12|ערוץ\s*12', 12),
         (r'\breshet\s*13\b|\bchannel\s*13\b|רשת\s*13|ערוץ\s*13', 13), (r'\bchannel\s*14\b|ערוץ\s*14', 14),
         (r'\bi24', 15), (r'\bkan\s*educ|חינוכית', 23), (r'\bmakan\b|מכאן', 33), (r'\bknesset|כנסת', 99),
         (r'\bchannel\s*9\b|\b9\s*канал|ערוץ\s*9', 9)]
# group -> first number of its block
BLOCKS = [('Israel', 1), ('News', 100), ('Movies', 200), ('Series', 300), ('Kids', 400), ('Sport', 500),
          ('Documentary', 600), ('Music', 700), ('Russian', 800), ('Other', 1000)]
KEYWORDS = [
    ('Kids', r'kid|cartoon|junior|disney|nick|мульт|детск|ילד|הופ|לוגי'),
    ('Sport', r'sport|спорт|ספורט|eurosport|espn|football|футбол|матч'),
    ('News', r'news|новост|חדשות|cnn|bbc world|euronews|sky news|россия 24|i24'),
    ('Movies', r'movie|cinema|film|кино|фильм|סרט|hbo|cinemax'),
    ('Series', r'series|сериал|סדרות|drama'),
    ('Documentary', r'docu|discovery|nat.?geo|history|animal|природ|תעוד|viasat'),
    ('Music', r'music|музык|מוזיק|mtv|vh1'),
]
GROUP_KEYS = {'grp_' + b.lower() for b, _ in BLOCKS}
HEB = re.compile('[֐-׿]')
CYR = re.compile('[Ѐ-ӿ]')


# free, publicly available channels (iptv-org community index) - each can be switched off
FREE = [
    ('iptv-org IL', 'https://iptv-org.github.io/iptv/countries/il.m3u'),
    ('iptv-org Hebrew', 'https://iptv-org.github.io/iptv/languages/heb.m3u'),
    ('iptv-org Russian', 'https://iptv-org.github.io/iptv/languages/rus.m3u'),
    ('iptv-org Movies', 'https://iptv-org.github.io/iptv/categories/movies.m3u'),
    ('iptv-org Kids', 'https://iptv-org.github.io/iptv/categories/kids.m3u'),
    ('iptv-org Documentary', 'https://iptv-org.github.io/iptv/categories/documentary.m3u'),
    ('iptv-org News', 'https://iptv-org.github.io/iptv/categories/news.m3u'),
    ('iptv-org Music', 'https://iptv-org.github.io/iptv/categories/music.m3u'),
    ('iptv-org English', 'https://iptv-org.github.io/iptv/languages/eng.m3u'),
]
# large lists start switched off (user can enable them in IPTV sources)
FREE_OFF = {'iptv-org English', 'iptv-org News', 'iptv-org Music'}
DEAD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dead_streams.json')


def dead_streams():
    try:
        with open(DEAD_FILE, encoding='utf-8') as f:
            return set(json.load(f))
    except Exception:
        return set()


def sources():
    src = load('iptv.json', {'m3u': [], 'epg': []})
    src.setdefault('m3u', [])        # a hand-edited / partial file must not break the TV section
    src.setdefault('epg', [])
    src.setdefault('free', {})
    for name, _ in FREE:
        src['free'].setdefault(name, name not in FREE_OFF)
    return src


def all_m3u(src):
    return list(src['m3u']) + [{'name': n, 'url': u} for n, u in FREE if src['free'].get(n, True)]


def country(attrs):
    c = attrs.get('tvg-country', '').upper()
    if not c:
        m = re.search(r'\.([a-z]{2})(?:@|$)', attrs.get('tvg-id', ''))
        c = m.group(1).upper() if m else ''
    return c


def classify(name, group, attrs, src=''):
    text = '%s %s' % (name, group)
    low = text.lower()
    cc = country(attrs)
    if HEB.search(text) or re.search(r'\b(il|israel|ישראל)\b', low) or cc == 'IL' or src in ('iptv-org IL', 'iptv-org Hebrew'):
        return 'Israel'
    if CYR.search(text) or cc in ('RU', 'UA', 'BY', 'KZ') or src == 'iptv-org Russian':
        return 'Russian'
    for g, rx in KEYWORDS:
        if re.search(rx, low):
            return g
    return 'Other'


ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text, source_name):
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF'):
            # attributes may contain commas (user-agent) -> name is after the comma following the last quoted value
            m = re.match(r'(#EXTINF[^"]*(?:"[^"]*"[^"]*?)*?),([^"]*)$', line)
            head, name = (m.group(1), m.group(2)) if m else line.partition(',')[::2]
            cur = {'attrs': dict(ATTR.findall(head)), 'name': name.strip(), 'opts': []}
        elif line.startswith('#EXTVLCOPT') or line.startswith('#KODIPROP'):
            if cur is not None:
                cur['opts'].append(line)
        elif line and not line.startswith('#') and cur:
            cur['url'] = line
            cur['src'] = source_name
            out.append(cur)
            cur = None
    return out


BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'


def with_headers(c):
    """Many free streams reject Kodi's default user-agent (HTTP 403). Kodi accepts
    'url|Header=value&...' - add the playlist's own headers, else a browser UA."""
    u = c['url']
    if '|' in u or not u.startswith('http'):
        return u
    from urllib.parse import quote
    h = {}
    for o in c.get('opts', []):
        k, _, v = o.split(':', 1)[-1].partition('=')
        h[k.strip().lower()] = v.strip()
    a = c.get('attrs', {})
    ua = h.get('http-user-agent') or a.get('http-user-agent') or BROWSER_UA
    ref = h.get('http-referrer') or a.get('http-referrer')
    hdr = 'User-Agent=' + quote(ua)
    if ref:
        hdr += '&Referer=' + quote(ref)
    return u + '|' + hdr


def norm(name):
    n = re.sub(r'\b(hd|fhd|uhd|4k|sd|hevc|h265|\+1)\b', '', name.lower())
    return re.sub(r'[\W_]+', '', n)


def _fetch(u):
    import requests
    if u.startswith(('http://', 'https://')):
        r = requests.get(u, timeout=60, headers={'User-Agent': 'Kodi'})
        r.raise_for_status()
        return r.content
    with xbmcvfs.File(u, 'rb') as f:
        return bytes(f.readBytes())


def merge(notify=True):
    home = xbmcgui.Window(10000)
    if home.getProperty('NovaTV.iptv_busy') == '1':
        # another refresh is running (e.g. the automatic one at start): wait for it, then apply the
        # newest sources - dropping the request would leave the viewer with the old channel list
        if notify:
            xbmcgui.Dialog().notification('NovaTV', '...', xbmcgui.NOTIFICATION_INFO, 2000)
        mon = monitor()
        for _ in range(600):
            if home.getProperty('NovaTV.iptv_busy') != '1' or mon.waitForAbort(0.5):
                break
    home.setProperty('NovaTV.iptv_busy', '1')
    try:
        return _merge(notify)
    finally:
        home.clearProperty('NovaTV.iptv_busy')


def _merge(notify):
    src = sources()
    channels, errors = [], []
    for s in all_m3u(src):
        try:
            data = _fetch(s['url']).decode('utf-8', 'ignore')
            channels.extend(parse_m3u(data, s['name']))
        except Exception as e:
            errors.append('%s: %s' % (s['name'], e))
    dead = dead_streams()
    if dead:
        channels = [c for c in channels if c.get('url') not in dead]
    # de-duplicate by normalised name: keep HD/first, remember alternates
    best = {}
    for c in channels:
        k = norm(c['name'])
        quality = 2 if re.search(r'4k|uhd|fhd', c['name'], re.I) else 1 if re.search(r'\bhd\b', c['name'], re.I) else 0
        c['q'] = quality
        c['group'] = classify(c['name'], c['attrs'].get('group-title', ''), c['attrs'], c.get('src', ''))
        if k not in best or quality > best[k]['q']:
            best[k] = c
    used, lines = set(), ['#EXTM3U']
    ordered = sorted(best.values(), key=lambda c: ([b for b, _ in BLOCKS].index(c['group']), c['name'].lower()))
    nxt = {g: n for g, n in BLOCKS}
    fixed_nums = {n for _, n in FIXED}
    for c in ordered:
        num = None
        for rx, n in FIXED:
            if re.search(rx, c['name'], re.I) and n not in used:
                num = n
                break
        if num is None:
            g = c['group']
            starts = [n for _, n in BLOCKS]
            end = next((n for n in starts if n > dict(BLOCKS)[g]), 5000)
            num = nxt[g]
            while num in used or num in fixed_nums:
                num += 1
            if num >= end:          # block full -> overflow range, keeps other blocks' numbers stable
                g = '_overflow'
                num = nxt.setdefault(g, 5000)
                while num in used:
                    num += 1
            nxt[g] = num + 1
        used.add(num)
        a = c['attrs']
        attrs = ' '.join('%s="%s"' % (k, v) for k, v in a.items() if k not in ('tvg-chno', 'group-title'))
        lines.append('#EXTINF:-1 %s tvg-chno="%d" group-title="%s",%s' % (attrs, num, c['group'], c['name']))
        lines.extend(c['opts'])
        lines.append(with_headers(c))
    with open(MERGED_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    merge_epg(src['epg'], errors)
    if not configure_pvr(force=notify):
        errors.append('PVR IPTV Simple Client could not be installed - check internet, then Accounts > IPTV again')
    save('iptv_status.json', {'when': time.time(), 'channels': len(best), 'errors': errors})
    if notify:
        msg = '%d %s' % (len(best), T('channels'))
        if errors:
            xbmcgui.Dialog().ok('NovaTV', msg + '\n' + '\n'.join(errors))
        else:
            xbmcgui.Dialog().notification('NovaTV', msg, xbmcgui.NOTIFICATION_INFO, 4000)
    return len(best), errors


def merge_epg(urls, errors):
    """Stream-merge several XMLTV files into one gzip without loading a DOM."""
    tmp = MERGED_EPG + '.tmp'
    seen_channels = set()
    with gzip.open(tmp, 'wt', encoding='utf-8') as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="NovaTV">\n')
        for u in urls:
            try:
                raw = _fetch(u)
                if raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                text = raw.decode('utf-8', 'ignore')
                body = text[text.find('<tv'):]
                body = body[body.find('>') + 1:body.rfind('</tv>')]
                for m in re.finditer(r'<channel\s+id="([^"]+)".*?</channel>|<programme\b.*?</programme>', body, re.S):
                    if m.group(1):
                        if m.group(1) in seen_channels:
                            continue
                        seen_channels.add(m.group(1))
                    out.write(m.group(0) + '\n')
            except Exception as e:
                errors.append('EPG %s: %s' % (u[:40], e))
        out.write('</tv>\n')
    os.replace(tmp, MERGED_EPG)


def repo_knows(addon_id):
    """is the add-on in Kodi's repository index (installable)?"""
    r = _jsonrpc('Addons.GetAddons', installed=False, properties=['name'])
    return any(a.get('addonid') == addon_id for a in (r.get('result') or {}).get('addons', []))


def install_addon(addon_id, timeout=120):
    """Install from the official repo and confirm Kodi's yes/no prompt ourselves."""
    mon = monitor()
    for attempt in range(3):                    # dependency downloads sometimes fail - retry
        if not xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id) and not repo_knows(addon_id):
            # Kodi's download of the repository index timed out ("wrong digest"): it knows no add-on to install
            # until its next refresh (up to a day) - refresh now and wait for the index
            log('install %s: not in the repository index - refreshing repositories' % addon_id, xbmc.LOGWARNING)
            xbmc.executebuiltin('UpdateAddonRepos')
            for _ in range(90):
                if repo_knows(addon_id) or mon.waitForAbort(1):
                    break
        xbmc.executebuiltin('InstallAddon(%s)' % addon_id)
        for _ in range(timeout * 2 // 3):
            if xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id):
                return True
            if xbmc.getCondVisibility('Window.IsTopMost(yesnodialog)'):
                xbmc.executebuiltin('SendClick(yesnodialog,11)')
            if xbmc.getCondVisibility('Window.IsTopMost(okdialog)'):   # "download failed" box
                xbmc.executebuiltin('Dialog.Close(okdialog)')
                log('install %s: attempt %d failed, retrying' % (addon_id, attempt + 1), xbmc.LOGWARNING)
                break
            if mon.waitForAbort(0.5):
                return False
        mon.waitForAbort(3)
    return xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id)


def configure_pvr(force=False):
    """Write IPTV Simple instance settings first, then install (fresh) or restart (existing).

    IPTV Simple re-reads the merged files by itself every hour (m3uRefreshMode), so a running client is only
    restarted when its settings changed or the viewer asked (force). Disabling/enabling the client on every
    refresh crashed Kodi 21 now and then (PVR client destroyed while channels were being read)."""
    was_installed = xbmc.getCondVisibility('System.HasAddon(%s)' % PVR)
    data_dir = xbmcvfs.translatePath('special://profile/addon_data/%s/' % PVR)
    os.makedirs(data_dir, exist_ok=True)
    settings = {
        'kodi_addon_instance_name': 'NovaTV', 'kodi_addon_instance_enabled': 'true',
        'm3uPathType': '0', 'm3uPath': MERGED_M3U, 'm3uCache': 'true', 'startNum': '1',
        'numberByOrder': 'false', 'epgPathType': '0', 'epgPath': MERGED_EPG, 'epgCache': 'true',
        'epgTimeShift': '0', 'logoPathType': '1', 'logoFromEpg': '1', 'catchupEnabled': 'true',
        'm3uRefreshMode': '1', 'm3uRefreshIntervalMins': '60',
    }
    xml = ['<settings version="2">'] + ['    <setting id="%s">%s</setting>' % (k, v) for k, v in settings.items()] + ['</settings>']
    body = '\n'.join(xml)
    sp = os.path.join(data_dir, 'instance-settings-1.xml')
    try:
        with open(sp, encoding='utf-8') as f:
            same = f.read() == body
    except Exception:
        same = False
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(body)
    # let Kodi number channels in our tvg-chno order
    _rpc('Settings.SetSettingValue', setting='pvrmanager.usebackendchannelnumbers', value=True)
    if not was_installed:
        return install_addon(PVR)   # picks up the settings file on first start
    if same and not force and _addon_enabled():
        return True                 # the client refreshes the files itself - no restart
    # existing install: restart the client, but never overlap restarts (that aborts a big channel load)
    mon = monitor()
    for attempt in range(4):
        _rpc('Addons.SetAddonEnabled', addonid=PVR, enabled=False)
        for _ in range(20):                     # wait until the add-on is off and the PVR manager stopped
            if mon.waitForAbort(1) or (not _addon_enabled() and not _pvr_available()):
                break
        mon.waitForAbort(2)
        for _ in range(5):                      # Kodi sometimes drops an enable right after a disable
            _rpc('Addons.SetAddonEnabled', addonid=PVR, enabled=True)
            if mon.waitForAbort(2) or _addon_enabled():
                break
        for _ in range(45):                     # 5000+ channels take a while on slow boxes
            if mon.waitForAbort(1) or _pvr_available():
                return True
        log('PVR did not come up (attempt %d) - restarting IPTV client' % (attempt + 1))
    return False


def _jsonrpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception:
        return {}


def _addon_enabled():
    return bool(_jsonrpc('Addons.GetAddonDetails', addonid=PVR, properties=['enabled']).get('result', {}).get('addon', {}).get('enabled'))


def _pvr_available():
    if not _jsonrpc('PVR.GetProperties', properties=['available']).get('result', {}).get('available'):
        return False
    return bool(_jsonrpc('PVR.GetChannelGroups', channeltype='tv').get('result', {}).get('channelgroups'))


def _rpc(method, **params):
    return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))


# ------------------------------------------------------------------ UI
def _action_item(handle, label, target, ic):
    import xbmcplugin
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': ic, 'thumb': ic})
    xbmcplugin.addDirectoryItem(handle, target, li, False)


def menu(handle, url, folder, end):
    folder(T('channels'), url(a='tv_list'), 'DefaultTVShows.png')
    all_id = _rpc('PVR.GetChannelGroupDetails', channelgroupid='alltv').get('result', {}).get('channelgroupdetails', {}).get('channelgroupid')
    for g in _rpc('PVR.GetChannelGroups', channeltype='tv').get('result', {}).get('channelgroups', []):
        if g['channelgroupid'] != all_id:
            folder('   ' + T('grp_' + g['label'].lower()) if ('grp_' + g['label'].lower()) in GROUP_KEYS else '   ' + g['label'],
                   url(a='tv_list', group=g['channelgroupid']), 'DefaultTVShows.png')
    _action_item(handle, T('guide'), url(a='tv_do', do='guide'), 'DefaultPVRGuide.png')
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.idanplus)'):
        folder(T('israeli_tv'), 'plugin://plugin.video.idanplus/', 'DefaultTVShows.png')
    folder(T('iptv_src'), url(a='accounts'), 'DefaultAddonService.png')
    end(cache=False)


def action(do):
    if do == 'channels':
        xbmc.executebuiltin('ActivateWindow(TVChannels)')
    elif do == 'guide':
        xbmc.executebuiltin('ActivateWindow(TVGuide)')
    elif do == 'refresh':
        merge()


def edit_sources():
    src = sources()
    d = xbmcgui.Dialog()
    while True:
        free = ['%s %s' % ('[x]' if src['free'].get(n, True) else '[  ]', n) for n, _ in FREE]
        own = ['M3U: %s' % x['name'] for x in src['m3u']]
        epg = ['EPG: %s' % u[:60] for u in src['epg']]
        rows = ['[+] M3U', '[+] EPG'] + free + own + epg + ['[x] ' + T('ok')]
        i = d.select(T('iptv_src'), rows)
        if i < 0 or i == len(rows) - 1:
            break
        if i == 0:
            u = d.input('M3U URL')
            if u:
                name = d.input('Name', 'IPTV %d' % (len(src['m3u']) + 1))
                src['m3u'].append({'name': name or u, 'url': u.strip()})
        elif i == 1:
            u = d.input('EPG URL (xml / xml.gz)')
            if u:
                src['epg'].append(u.strip())
        elif i < 2 + len(free):
            n = FREE[i - 2][0]
            src['free'][n] = not src['free'].get(n, True)
        elif i < 2 + len(free) + len(own):
            if d.yesno('BN', T('clear') + '?'):
                src['m3u'].pop(i - 2 - len(free))
        elif d.yesno('BN', T('clear') + '?'):
            src['epg'].pop(i - 2 - len(free) - len(own))
    save('iptv.json', src)
    if all_m3u(src):
        merge()


def channel_list(handle, group=None):
    """Yes/HOT-style list: number, logo, what is on now (with progress) and next."""
    import xbmcplugin
    props = ['channelnumber', 'icon', 'broadcastnow', 'broadcastnext', 'hidden']
    r = _rpc('PVR.GetChannels', channelgroupid=int(group) if group else 'alltv', properties=props)
    for c in sorted(r.get('result', {}).get('channels', []), key=lambda c: c.get('channelnumber') or 0):
        if c.get('hidden'):
            continue
        now, nxt = c.get('broadcastnow') or {}, c.get('broadcastnext') or {}
        label = '[B]%s[/B]  %s' % (c.get('channelnumber'), c['label'])
        if now.get('title'):
            label += '   [COLOR grey]%s[/COLOR]' % now['title']
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': c.get('icon') or 'DefaultTVShows.png', 'thumb': c.get('icon') or 'DefaultTVShows.png'})
        plot = ''
        if now.get('title'):
            plot = '[B]%s %s[/B]  (%d%%)\n%s' % (now.get('starttime', '')[11:16], now['title'],
                                                int(now.get('progresspercentage') or 0), now.get('plot') or '')
        if nxt.get('title'):
            plot += '\n\n[COLOR grey]%s %s[/COLOR]' % (nxt.get('starttime', '')[11:16], nxt['title'])
        tag = li.getVideoInfoTag()
        tag.setPlot(plot)
        tag.setTitle(c['label'])
        li.setProperty('IsPlayable', 'false')
        target = 'plugin://plugin.video.nova/?a=tv_play&id=%d' % c['channelid']
        li.addContextMenuItems([(T('add_fav'), 'RunPlugin(plugin://plugin.video.nova/?a=fav_add&kind=channel&id=%d&label=%s&extra=%s)'
                                 % (c['channelid'], c['label'], 'pvr_channel_%d' % c['channelid']))])
        xbmcplugin.addDirectoryItem(handle, target, li, False)
    xbmcplugin.setContent(handle, 'videos')
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def play_channel(cid):
    _rpc('Player.Open', item={'channelid': int(cid)})
