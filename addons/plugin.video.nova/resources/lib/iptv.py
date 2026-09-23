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
HEB = re.compile('[֐-׿]')
CYR = re.compile('[Ѐ-ӿ]')


def sources():
    return load('iptv.json', {'m3u': [], 'epg': []})


def classify(name, group, attrs):
    text = '%s %s' % (name, group)
    low = text.lower()
    if HEB.search(text) or re.search(r'\b(il|israel|ישראל)\b', low) or attrs.get('tvg-country', '').upper() == 'IL':
        return 'Israel'
    for g, rx in KEYWORDS:
        if re.search(rx, low):
            return g
    if CYR.search(text) or attrs.get('tvg-country', '').upper() in ('RU', 'UA', 'BY', 'KZ'):
        return 'Russian'
    return 'Other'


ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def parse_m3u(text, source_name):
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF'):
            head, _, name = line.partition(',')
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
        if notify:
            xbmcgui.Dialog().notification('NovaTV', '...', xbmcgui.NOTIFICATION_INFO, 2000)
        return 0, []
    home.setProperty('NovaTV.iptv_busy', '1')
    try:
        return _merge(notify)
    finally:
        home.clearProperty('NovaTV.iptv_busy')


def _merge(notify):
    src = sources()
    channels, errors = [], []
    for s in src['m3u']:
        try:
            data = _fetch(s['url']).decode('utf-8', 'ignore')
            channels.extend(parse_m3u(data, s['name']))
        except Exception as e:
            errors.append('%s: %s' % (s['name'], e))
    # de-duplicate by normalised name: keep HD/first, remember alternates
    best = {}
    for c in channels:
        k = norm(c['name'])
        quality = 2 if re.search(r'4k|uhd|fhd', c['name'], re.I) else 1 if re.search(r'\bhd\b', c['name'], re.I) else 0
        c['q'] = quality
        c['group'] = classify(c['name'], c['attrs'].get('group-title', ''), c['attrs'])
        if k not in best or quality > best[k]['q']:
            best[k] = c
    used, lines = set(), ['#EXTM3U']
    ordered = sorted(best.values(), key=lambda c: ([b for b, _ in BLOCKS].index(c['group']), c['name'].lower()))
    nxt = {g: n for g, n in BLOCKS}
    for c in ordered:
        num = None
        for rx, n in FIXED:
            if re.search(rx, c['name'], re.I) and n not in used:
                num = n
                break
        if num is None:
            num = nxt[c['group']]
            while num in used or num in [n for _, n in FIXED]:
                num += 1
            nxt[c['group']] = num + 1
        used.add(num)
        a = c['attrs']
        attrs = ' '.join('%s="%s"' % (k, v) for k, v in a.items() if k not in ('tvg-chno', 'group-title'))
        lines.append('#EXTINF:-1 %s tvg-chno="%d" group-title="%s",%s' % (attrs, num, c['group'], c['name']))
        lines.extend(c['opts'])
        lines.append(c['url'])
    with open(MERGED_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    merge_epg(src['epg'], errors)
    configure_pvr()
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


def install_addon(addon_id, timeout=120):
    """Install from the official repo and confirm Kodi's yes/no prompt ourselves."""
    xbmc.executebuiltin('InstallAddon(%s)' % addon_id)
    mon = xbmc.Monitor()
    for _ in range(timeout * 2):
        if xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id):
            return True
        if xbmc.getCondVisibility('Window.IsTopMost(yesnodialog)'):
            xbmc.executebuiltin('SendClick(yesnodialog,11)')
        if mon.waitForAbort(0.5):
            break
    return False


def configure_pvr():
    """Write IPTV Simple instance settings first, then install (fresh) or restart (existing)."""
    was_installed = xbmc.getCondVisibility('System.HasAddon(%s)' % PVR)
    data_dir = xbmcvfs.translatePath('special://profile/addon_data/%s/' % PVR)
    os.makedirs(data_dir, exist_ok=True)
    settings = {
        'kodi_addon_instance_name': 'NovaTV', 'kodi_addon_instance_enabled': 'true',
        'm3uPathType': '0', 'm3uPath': MERGED_M3U, 'm3uCache': 'true', 'startNum': '1',
        'numberByOrder': 'false', 'epgPathType': '0', 'epgPath': MERGED_EPG, 'epgCache': 'true',
        'epgTimeShift': '0', 'logoPathType': '1', 'logoFromEpg': '1', 'catchupEnabled': 'true',
    }
    xml = ['<settings version="2">'] + ['    <setting id="%s">%s</setting>' % (k, v) for k, v in settings.items()] + ['</settings>']
    with open(os.path.join(data_dir, 'instance-settings-1.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml))
    # let Kodi number channels in our tvg-chno order
    _rpc('Settings.SetSettingValue', setting='pvrmanager.usebackendchannelnumbers', value=True)
    if not was_installed:
        install_addon(PVR)          # picks up the settings file on first start
        return
    # existing install: a single disable/enable cycle, waiting until the PVR manager settles
    mon = xbmc.Monitor()
    _rpc('Addons.SetAddonEnabled', addonid=PVR, enabled=False)
    mon.waitForAbort(4)
    _rpc('Addons.SetAddonEnabled', addonid=PVR, enabled=True)


def _rpc(method, **params):
    return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))


# ------------------------------------------------------------------ UI
def _action_item(handle, label, target, ic):
    import xbmcplugin
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': ic, 'thumb': ic})
    xbmcplugin.addDirectoryItem(handle, target, li, False)


def menu(handle, url, folder, end):
    _action_item(handle, T('channels'), url(a='tv_do', do='channels'), 'DefaultTVShows.png')
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
        rows = ['[+] M3U', '[+] EPG'] + ['M3U: %s' % s['name'] for s in src['m3u']] + ['EPG: %s' % u[:60] for u in src['epg']] + ['[✓] ' + T('ok')]
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
        elif i < 2 + len(src['m3u']):
            if d.yesno('NovaTV', T('clear') + '?'):
                src['m3u'].pop(i - 2)
        else:
            if d.yesno('NovaTV', T('clear') + '?'):
                src['epg'].pop(i - 2 - len(src['m3u']))
    save('iptv.json', src)
    if src['m3u']:
        merge()
