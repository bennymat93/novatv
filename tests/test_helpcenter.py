# -*- coding: utf-8 -*-
"""Help center content + search, speed test maths"""
import pytest

from resources.lib import helpcenter, speedtest


def test_every_section_has_both_languages():
    for sec in helpcenter.load('guide')['sections']:
        for l in ('he', 'en'):
            assert sec[l]['title'] and len(sec[l]['body']) > 80
    for row in helpcenter.load('trouble')['rows']:
        assert len(row['he']) == 3 and len(row['en']) == 3


@pytest.mark.parametrize('topic', ['buffering', 'EPG', 'subtitles', 'sound', 'update', 'touch', 'scaling'])
def test_required_troubleshooting_topics(topic):
    words = {'buffering': 'Buffering', 'EPG': 'EPG', 'subtitles': 'sync', 'sound': 'No sound', 'update': 'Update failed',
             'touch': 'Touch', 'scaling': 'cut off'}
    assert any(words[topic].lower() in ' '.join(r['en']).lower() for r in helpcenter.load('trouble')['rows'])


def test_search_both_languages():
    assert any(k == 'trouble' for k, _, _ in helpcenter.search('כתוביות סנכרון', 'he'))
    assert any(k == 'guide' for k, _, _ in helpcenter.search('remote keyboard', 'en'))
    assert helpcenter.search('zzqq', 'he') == []


def test_speed_maths():
    assert speedtest.mbps(12500000, 1) == 100
    assert speedtest.jitter([10, 20, 10]) == 10
    v = dict(speedtest.verdict(10, 40))
    assert v['hd'] == 'ok' and v['fhd'] == 'no' and v['live'] == 'ok'
    assert dict(speedtest.verdict(50, 300))['live'] == 'weak'
