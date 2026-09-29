# -*- coding: utf-8 -*-
"""episode search end to end without Kodi: query -> sources -> exact filter; stale state; slow sources; cache keys"""
import threading
import time

from resources.lib import providers, yt, epmatch

YT = ('youtube', 'plugin.video.youtube', ('', '', ''), '', 'internal:yt')

# what YouTube really does: popular Season 1 videos first, whatever was asked
CATALOG = ['Show S01E01', 'Show S01E05', 'Show Season 1 Episode 2', 'Show S02E15', 'Show S12E05',
           'Show - best scenes', 'Show S02E05 full episode', 'Show 2x05 (HD)', 'Show S02E06']


def fake_search(q, limit=30):
    return [{'id': str(i), 'title': t, 'thumb': '', 'channel': '', 'duration': '', 'plot': ''}
            for i, t in enumerate(CATALOG)]


def _labels(found):
    return [it['label'] for _, items in found for it in items]


def test_search_s1_then_s2e5_only_s2e5(monkeypatch):
    monkeypatch.setattr(yt, 'search', fake_search)
    first = providers.exact(providers.run_search(epmatch.query_for('Show', 1, 1), [YT]), (1, 1))
    assert _labels(first) == ['Show S01E01']
    second = providers.exact(providers.run_search(epmatch.query_for('Show', 2, 5), [YT]), (2, 5))
    assert _labels(second) == ['Show S02E05 full episode', 'Show 2x05 (HD)']      # nothing from the S1 search


def test_no_exact_match_is_empty_not_fallback(monkeypatch):
    monkeypatch.setattr(yt, 'search', fake_search)
    assert providers.exact(providers.run_search('Show S07E07', [YT]), (7, 7)) == []


def test_free_text_search_not_filtered(monkeypatch):
    monkeypatch.setattr(yt, 'search', fake_search)
    assert len(_labels(providers.exact(providers.run_search('Show', [YT]), (None, None)))) == len(CATALOG)


def test_slow_old_source_answer_is_ignored(monkeypatch):
    """a source that answers after the deadline never changes (or leaks into) the answer already given"""
    slow = ('slow', 'plugin.video.youtube', ('', '', ''), '', 'internal:yt')
    calls = []

    def search(q, limit=30):
        calls.append(q)
        if q == 'old':
            time.sleep(1.5)                 # the older search is slow ...
            return [{'id': 'x', 'title': 'OLD S01E01', 'thumb': '', 'channel': '', 'duration': '', 'plot': ''}]
        return [{'id': 'y', 'title': 'NEW S02E05', 'thumb': '', 'channel': '', 'duration': '', 'plot': ''}]
    monkeypatch.setattr(yt, 'search', search)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault('old', providers.run_search('old', [slow], per_timeout=0.3)))
    t.start()
    time.sleep(0.05)
    new = providers.run_search('new', [slow], per_timeout=2)     # ... the newer one starts meanwhile
    t.join()
    time.sleep(1.5)                                              # let the old thread finish writing
    assert _labels(new) == ['NEW S02E05']
    assert out['old'] == []                                     # the late answer was dropped, not merged anywhere
    assert _labels(new) == ['NEW S02E05']                       # unchanged after the late answer arrived


def test_cache_keys_never_shared_and_expire(monkeypatch):
    store = {}
    from resources.lib import common
    monkeypatch.setattr(common, 'load', lambda name, default: dict(store.get(name, default)), raising=False)
    monkeypatch.setattr(common, 'save', lambda name, v: store.__setitem__(name, v), raising=False)
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    answers = {'show s01e01': ['S1'], 'show s02e05': ['S2E5']}
    for q in ('Show S01E01', 'Show  S02E05'):
        assert yt._cached('s:' + yt.norm_query(q), lambda q=q: answers[yt.norm_query(q)]) == answers[yt.norm_query(q)]
    assert set(store['yt_cache.json']) == {'s:show s01e01', 's:show s02e05'}
    # YouTube down: each query gets only its own last answer ...
    def down():
        raise OSError('down')
    assert yt._cached('s:show s02e05', down) == ['S2E5']
    assert yt._cached('s:show s03e01', down) is None             # ... never another query's
    # ... and never an expired one
    store['yt_cache.json']['s:show s02e05']['t'] -= yt.CACHE_MAX_AGE + 1
    assert yt._cached('s:show s02e05', down) is None


def test_filter_cost_is_negligible():
    items = [{'label': t} for t in CATALOG] * 100               # 900 results
    t = time.perf_counter()
    epmatch.filter_items((2, 5), items)
    assert time.perf_counter() - t < 0.2
