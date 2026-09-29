# -*- coding: utf-8 -*-
"""Season / episode parsing and exact matching for search results (pure: no Kodi imports).

parse(text) -> (season, episode), each an int or None. Understands:
  S2E5, S02E05, s2 e5, S02.E05, 2x05, Season 2 Episode 5, Season 2, Episode 5, Ep 5, Ep.05, E05,
  Hebrew: עונה 2 פרק 5, ע2 פ5, פרק 5, עונה 2
  Russian: 2 сезон 5 серия, Сезон 2 Серия 5, серия 5
Numbers are compared as integers (05 == 5); every number is a whole token, so episode 5 never matches 15/50/105
and season 2 never matches 12/20.

matches(want, title, description='') -> True only when the title (or, if the title has no season/episode at all,
the description) states exactly the wanted season AND/OR episode. A text without a parseable season/episode, or with
a conflicting one, does not match - never a guess.
"""
import re

_N = r'0*(\d{1,3})(?!\d)'              # a whole number (leading zeros allowed), not part of a longer number
_B = r'(?<![0-9A-Za-z֐-׿Ѐ-ӿ])'   # start of a token: no letter/digit (Latin/Hebrew/Cyrillic) before

# season+episode together, most specific first
_PAIR = [
    re.compile(_B + r's' + _N + r'[\s._-]*e(?:p(?:isode)?)?[\s._-]*' + _N, re.I),                    # S02E05, S2 E5, S02.E05, S2Ep5
    re.compile(_B + _N + r'x' + _N + r'(?![0-9A-Za-z])', re.I),                                       # 2x05
    re.compile(_B + r'season[\s._-]*' + _N + r'[\s,._-]*(?:episode|ep\.?)[\s._-]*' + _N, re.I),     # Season 2 Episode 5
    re.compile(_B + r'(?:עונה|ע)[\s\'"׳._-]*' + _N + r'[\s,._-]*(?:פרק|פ)[\s\'"׳._-]*' + _N),          # עונה 2 פרק 5 / ע2 פ5
    re.compile(_B + r'сезон[\s._-]*' + _N + r'[\s,._-]*(?:серия|эпизод)[\s._-]*' + _N, re.I),       # Сезон 2 Серия 5
    re.compile(_B + _N + r'[\s-]*(?:й|ой)?[\s-]*сезон[\s,._-]*' + _N + r'[\s-]*(?:я|ая)?[\s-]*(?:серия|эпизод)', re.I),  # 2 сезон 5 серия
]
_SEASON = [
    re.compile(_B + r's' + _N + r'(?![0-9A-Za-z])', re.I),                                            # S02
    re.compile(_B + r'season[\s._-]*' + _N, re.I),
    re.compile(_B + r'עונה[\s\'"׳._-]*' + _N),
    re.compile(_B + r'сезон[\s._-]*' + _N, re.I),
    re.compile(_B + _N + r'[\s-]*(?:й|ой)?[\s-]*сезон', re.I),
]
_EPISODE = [
    re.compile(_B + r'(?:episode|ep\.?|e)[\s._-]*' + _N, re.I),                                       # Episode 5, Ep 5, Ep.05, E05
    re.compile(_B + r'פרק[\s\'"׳._-]*' + _N),
    re.compile(_B + r'(?:серия|эпизод)[\s._-]*' + _N, re.I),
    re.compile(_B + _N + r'[\s-]*(?:я|ая)?[\s-]*(?:серия|эпизод)', re.I),
]


# "Серия 1 - 10", "E05-E08", "פרק 1-5": a compilation of several episodes, not one exact episode
# (a resolution such as "S02E05 - 720p" is not a range)
_RANGE = re.compile(r'\s*[-–—~]\s*(?:e|ep|episode|серия|פרק)?\s*\d{1,3}(?![\dpPkKiIрк])', re.I)


def _episode(t, m, group):
    return None if _RANGE.match(t, m.end(group)) else int(m.group(group))


def parse(text):
    """(season, episode) stated in text; each None when not stated (an episode range counts as not stated)"""
    t = text or ''
    for rx in _PAIR:
        m = rx.search(t)
        if m:
            return int(m.group(1)), _episode(t, m, 2)
    season = next((int(m.group(1)) for m in (rx.search(t) for rx in _SEASON) if m), None)
    m = next((m for m in (rx.search(t) for rx in _EPISODE) if m), None)
    return season, (_episode(t, m, 1) if m else None)


def wanted(query='', season=None, episode=None):
    """what a search asks for: explicit numbers win over numbers written in the query"""
    qs, qe = parse(query)
    s = int(season) if season not in (None, '') else qs
    e = int(episode) if episode not in (None, '') else qe
    return s, e


def matches(want, title, description=''):
    """exact match of the wanted (season, episode) - only the parts that were asked for"""
    ws, we = want
    if ws is None and we is None:
        return True                                 # nothing asked: not an episode search
    ts, te = parse(title)
    if ts is None and te is None:                   # title silent: the description may state it
        ts, te = parse(description)
    if we is not None and te != we:
        return False                                # missing or different episode
    if ws is not None and ts != ws:
        return False                                # missing or different season
    return True


def _words(text):
    return re.findall(r'[0-9a-z֐-׿а-яё]+', (text or '').lower())


def mentions(show, title, description=''):
    """every word of the show name appears as a whole word in the title (or the description when the title lacks it)"""
    need = [w for w in _words(show) if w not in ('the', 'a', 'an')] or _words(show)
    if not need:
        return True
    for text in (title, description):
        have = set(_words(text))
        if all(w in have for w in need):
            return True
    return False


def filter_items(want, items, title_key='label', desc_key='plot', show=''):
    """keep only the items that match exactly (all of them, in their order); with show, it must be that show"""
    if want == (None, None):
        return list(items)
    return [it for it in items if matches(want, it.get(title_key) or '', it.get(desc_key) or '')
            and (not show or mentions(show, it.get(title_key) or '', it.get(desc_key) or ''))]


def query_for(show, season=None, episode=None):
    """a search text that states the episode (sources rank by it); the results are filtered anyway"""
    # written the way titles in the show's language usually are (YouTube ranks by it)
    lang = 'ru' if re.search('[Ѐ-ӿ]', show or '') else 'he' if re.search('[֐-׿]', show or '') else 'en'
    fmt = {'ru': ('%d сезон %d серия', '%d сезон', '%d серия'), 'he': ('עונה %d פרק %d', 'עונה %d', 'פרק %d'),
           'en': ('S%02dE%02d', 'Season %d', 'Episode %d')}[lang]
    parts = [(show or '').strip()]
    if season not in (None, '') and episode not in (None, ''):
        parts.append(fmt[0] % (int(season), int(episode)))
    elif season not in (None, ''):
        parts.append(fmt[1] % int(season))
    elif episode not in (None, ''):
        parts.append(fmt[2] % int(episode))
    return ' '.join(p for p in parts if p)
