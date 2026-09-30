# -*- coding: utf-8 -*-
"""TV guide for the free channels (1.4.0 Phase 3).

Source: epgshare01.online per-country XMLTV files (free, refreshed daily, 3+ days ahead, times with a UTC offset -
Kodi shows them in the device's time zone, Asia/Jerusalem in Israel incl. DST). The free iptv-org playlists carry
tvg-ids that no free guide uses, so channels are matched to guide channels by NAME: normalised (resolution,
HD/FHD, punctuation, the country suffix dropped) plus a table of Israeli Hebrew/English aliases.

The merged guide keeps only channels that are in the playlist; the playlist gets the guide's id as tvg-id.
Titles (and short descriptions) in other languages are translated to Hebrew once and cached (epg_tr.json) - the
setting epg_lang chooses he / en / original. match_* / norm / aliases are plain Python for unit tests.
"""
import gzip
import re

BASE = 'https://epgshare01.online/epgshare01/epg_ripper_%s.xml.gz'
# playlist country -> guide files (only those that exist on the server; checked 30/09/2026)
FILES = {'IL': ['IL1'], 'GB': ['UK1'], 'US': ['US2'], 'DE': ['DE1'], 'FR': ['FR1'], 'ES': ['ES1'], 'IT': ['IT1'],
         'NL': ['NL1'], 'TR': ['TR1'], 'AE': ['AE1'], 'SA': ['SA1'], 'CA': ['CA2'], 'AU': ['AU1'], 'IN': ['IN1'],
         'PL': ['PL1'], 'PT': ['PT1'], 'GR': ['GR1'], 'BR': ['BR1'], 'MX': ['MX1'], 'AR': ['AR1'], 'KZ': ['KZ1'],
         'RO': ['RO1'], 'SE': ['SE1'], 'NO': ['NO1'], 'DK': ['DK1'], 'FI': ['FI1'], 'CH': ['CH1'], 'AT': ['AT1'],
         'BE': ['BE2'], 'IE': ['IE1'], 'CZ': ['CZ1'], 'HU': ['HU1'], 'BG': ['BG1'], 'HR': ['HR1'], 'RS': ['RS1'],
         'EG': ['EG1'], 'JP': ['JP1'], 'KR': ['KR1'], 'PH': ['PH1'], 'ZA': ['ZA1']}
# Israeli channels: every spelling seen in playlists / guides -> one key
IL_ALIASES = {
    'kan11': ['kan 11', 'כאן 11', 'ערוץ 11 כאן', 'kan', 'kan 11 israel', 'ערוץ 11'],
    'keshet12': ['keshet 12', 'קשת 12', 'ערוץ 12', 'channel 12', 'keshet', 'קשת', 'n12'],
    'reshet13': ['reshet 13', 'רשת 13', 'ערוץ 13', 'channel 13', 'reshet', 'רשת', 'channel 13 israel'],
    'now14': ['channel 14', 'ערוץ 14', 'now 14', 'now14', 'ch 14'],
    'i24he': ['i24news hebrew', 'i24 עברית', 'עברית i24', 'i24news'],
    'i24en': ['i24news english'], 'i24fr': ['i24news french'], 'i24ar': ['i24news arabic'],
    'knesset': ['knesset', 'ערוץ הכנסת', 'knesset channel', 'channel 99'],
    'kanedu': ['kan educational', 'כאן חינוכית', 'kan chinuchit', 'kan 23', 'hinuchit'],
    'makan33': ['makan 33', 'מכאן', 'makan', 'מכאן 33'],
    'channel24': ['channel 24', 'ערוץ 24', 'music 24', 'מוזיקה 24', 'מוסיקה 24', 'ערוץ 24 בשידור חי'],
    'channel9': ['channel 9', 'ערוץ 9', '9 канал', 'канал 9'],
    'disney': ['disney channel', 'דיסני', 'disney'],
    'junior': ['junior', 'ג’וניור', "ג'וניור", 'גוניור'],
    'teennick': ['teennick', 'ערוץ teennick'],
    'yamtichoni': ['yam tichoni', 'ים תיכוני'],
    'vivaistanbul': ['viva istanbul', 'ויוה איסטנבול'],
    'vivapremium': ['viva premium', 'ויוה פרימיום'],
    'vivatelenovelas': ['viva telenovelas', 'ויוה טלנובלות'],
    'vacation': ['vacation channel', 'ערוץ הנופש'],
    'reality': ['reality channel', 'ערוץ הריאליטי'],
    'hidabroot': ['hidabroot', 'ערוץ הידברות', 'הידברות'],
    'one2': ['one 2', 'one2'],
    'goodlife': ['good life', 'good life+'],
    'homeplus': ['home +', 'home+', 'בית +', 'בית+'],
    'zoom': ['zoom', 'zoom toon'],
}


def norm(name):
    """'Keshet 12 (1080p) [Geo-blocked]' -> 'keshet 12'; Hebrew kept; the guide's dots become spaces"""
    n = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', name or '')
    n = re.sub(r'\.(il|uk|us|de|fr|es|it|nl|tr|ru|[a-z]{2})$', '', n.strip(), flags=re.I)
    n = n.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    n = re.sub(r'\b(hd|fhd|uhd|4k|sd|live|tv|שידור חי)\b', ' ', n, flags=re.I)
    return ' '.join(re.sub(r'[^\w֐-׿+! ]', ' ', n.lower()).split())


def alias_key(name):
    n = norm(name)
    for key, names in IL_ALIASES.items():
        if n in (norm(x) for x in names):
            return key
    return n


def channels_of(xml_text):
    """{guide id: [display names]} of an XMLTV text"""
    out = {}
    for m in re.finditer(r'<channel\s+id="([^"]+)"[^>]*>(.*?)</channel>', xml_text, re.S):
        names = re.findall(r'<display-name[^>]*>([^<]+)</display-name>', m.group(2))
        out[m.group(1)] = [m.group(1)] + names
    return out


def match(playlist_names, guide_channels):
    """{playlist name: guide id}: exact alias/normalised-name matches only (a wrong guide is worse than none)"""
    index = {}
    for gid, names in guide_channels.items():
        for n in names:
            index.setdefault(alias_key(n), gid)
    out = {}
    for name in playlist_names:
        gid = index.get(alias_key(name))
        if gid:
            out[name] = gid
    return out


def filter_guide(xml_text, keep_ids):
    """only the channels / programmes of keep_ids (the free guides list hundreds of channels)"""
    parts = []
    for m in re.finditer(r'<channel\s+id="([^"]+)".*?</channel>|<programme\b[^>]*\bchannel="([^"]+)".*?</programme>',
                         xml_text, re.S):
        if (m.group(1) or m.group(2)) in keep_ids:
            parts.append(m.group(0))
    return parts


HEB = re.compile(r'[֐-׿]')


def to_translate(parts):
    """unique programme titles / descriptions that are not Hebrew yet"""
    seen = []
    for p in parts:
        for tag in ('title', 'desc'):
            for t in re.findall(r'<%s[^>]*>([^<]{2,300})</%s>' % (tag, tag), p):
                if not HEB.search(t) and t not in seen:
                    seen.append(t)
    return seen


def apply_lang(parts, tr, mode):
    """mode 'he': Hebrew title (original kept in <sub-title> when there was none); 'en'/'orig': as the guide has it"""
    if mode != 'he' or not tr:
        return parts
    out = []
    for p in parts:
        if p.startswith('<programme'):
            p = re.sub(r'(<title[^>]*>)([^<]+)(</title>)', lambda m: m.group(1) + tr.get(m.group(2), m.group(2)) + m.group(3), p)
            p = re.sub(r'(<desc[^>]*>)([^<]+)(</desc>)', lambda m: m.group(1) + tr.get(m.group(2), m.group(2)) + m.group(3), p)
        out.append(p)
    return out


# ------------------------------------------------------------ Kodi / network
def build(playlist, errors, fetch, lang_mode='he', translate=None, cache=None):
    """playlist: [(name, country)] -> (parts for the merged guide, {name: guide id}).
    fetch(url) -> bytes; translate(lines) -> lines (Hebrew); cache: dict of earlier translations (updated)."""
    by_cc = {}
    for name, cc in playlist:
        by_cc.setdefault(cc, []).append(name)
    parts, ids = [], {}
    for cc, names in by_cc.items():
        for f in FILES.get(cc, []):
            try:
                raw = fetch(BASE % f)
                text = (gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw).decode('utf-8', 'ignore')
            except Exception as e:
                errors.append('EPG %s: %s' % (f, e))
                continue
            m = match([n for n in names if n not in ids], channels_of(text))
            ids.update(m)
            parts += filter_guide(text, set(m.values()))
    if translate and lang_mode == 'he':
        cache = cache if cache is not None else {}
        todo = [t for t in to_translate(parts) if t not in cache]
        for i in range(0, len(todo), 100):
            try:
                cache.update(dict(zip(todo[i:i + 100], translate(todo[i:i + 100]))))
            except Exception as e:
                errors.append('EPG translation: %s' % e)
                break
        parts = apply_lang(parts, cache, lang_mode)
    return parts, ids
