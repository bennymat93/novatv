# -*- coding: utf-8 -*-
"""free TV guide: name matching (Hebrew/English aliases), filtering, translation cache"""
from resources.lib import epg

GUIDE = ('<tv><channel id="כאן.11.il"><display-name>כאן 11</display-name></channel>'
         '<channel id="ערוץ.12.שידור.חי.il"><display-name>ערוץ 12</display-name></channel>'
         '<channel id="Discovery.HD.il"><display-name>Discovery HD</display-name></channel>'
         '<programme start="20260930060000 +0000" stop="20260930070000 +0000" channel="כאן.11.il"><title>חדשות</title></programme>'
         '<programme start="20260930060000 +0000" stop="20260930070000 +0000" channel="Discovery.HD.il"><title>Gold Rush</title>'
         '<desc>Miners dig.</desc></programme>'
         '<programme start="20260930060000 +0000" stop="20260930070000 +0000" channel="other.il"><title>x</title></programme></tv>')


def test_norm():
    assert epg.norm('Keshet 12 (1080p) [Geo-blocked]') == 'keshet 12'
    assert epg.norm('ערוץ.12.שידור.חי.il') == 'ערוץ 12'


def test_match_aliases_and_names():
    m = epg.match(['Kan 11 (1080p)', 'Keshet 12 (1080p)', 'Discovery (720p)', 'Unknown TV'], epg.channels_of(GUIDE))
    assert m == {'Kan 11 (1080p)': 'כאן.11.il', 'Keshet 12 (1080p)': 'ערוץ.12.שידור.חי.il', 'Discovery (720p)': 'Discovery.HD.il'}


def test_filter_keeps_only_matched():
    parts = epg.filter_guide(GUIDE, {'כאן.11.il'})
    assert len(parts) == 2 and all('other.il' not in p for p in parts)


def test_translation_only_non_hebrew_and_applied():
    parts = epg.filter_guide(GUIDE, {'כאן.11.il', 'Discovery.HD.il'})
    assert epg.to_translate(parts) == ['Gold Rush', 'Miners dig.']
    out = epg.apply_lang(parts, {'Gold Rush': 'בהלה לזהב', 'Miners dig.': 'כורים חופרים.'}, 'he')
    assert any('<title>בהלה לזהב</title>' in p for p in out)
    assert epg.apply_lang(parts, {'Gold Rush': 'x'}, 'orig') == parts


def test_build_uses_cache_and_reports_errors():
    calls = []

    def fetch(u):
        if 'IL1' in u:
            return GUIDE.encode('utf-8')
        raise OSError('down')

    def tr(lines):
        calls.append(lines)
        return ['HE:' + l for l in lines]
    errors, cache = [], {'Miners dig.': 'כורים'}
    parts, ids = epg.build([('Kan 11', 'IL'), ('Discovery', 'IL'), ('BBC One', 'GB')], errors, fetch, 'he', tr, cache)
    assert ids == {'Kan 11': 'כאן.11.il', 'Discovery': 'Discovery.HD.il'}
    assert calls == [['Gold Rush']] and cache['Gold Rush'] == 'HE:Gold Rush'
    assert errors and 'UK1' in errors[0]
