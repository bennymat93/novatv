# -*- coding: utf-8 -*-
"""learning sections: YouTube parsing (new lockup format, Shorts), duration threshold, top ranking, search, config"""
import json
import os
import re

import pytest

from resources.lib import yt, topics


def lockup(vid, title, dur, views='1.2M views', age='3 weeks ago', short=False):
    return {'lockupViewModel': {
        'contentId': vid, 'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO',
        'contentImage': {'thumbnailViewModel': {'image': {'sources': [{'url': 'http://t/%s.jpg' % vid}]},
                         'overlays': [{'thumbnailBadgeViewModel': {'text': dur}}] if dur else []}},
        'metadata': {'lockupMetadataViewModel': {'title': {'content': title}, 'metadata': {'contentMetadataViewModel': {
            'metadataRows': [{'metadataParts': [{'text': {'content': views}}, {'text': {'content': age}}]}]}}}},
        'rendererContext': {'commandContext': {'onTap': {'innertubeCommand': {'commandMetadata': {'webCommandMetadata': {
            'url': ('/shorts/%s' if short else '/watch?v=%s') % vid}}}}}}}}


def test_new_youtube_format_duration_views_age():
    items = yt._items({'contents': [lockup('a', 'Transformer basics', '21:33', '1.3M views', '2 weeks ago')]})
    assert items[0]['duration'] == '21:33' and items[0]['secs'] == 1293
    assert items[0]['views'] == 1300000 and items[0]['age'] == '2 weeks ago'


def test_shorts_never_returned():
    data = {'contents': [lockup('a', 'Long lecture', '45:00'), lockup('s', 'Quick tip', '0:45', short=True)]}
    assert [i['id'] for i in yt._items(data)] == ['a']


@pytest.mark.parametrize('text, secs', [('1:02:03', 3723), ('21:33', 1293), ('0:59', 59), ('', 0), ('LIVE', 0)])
def test_seconds(text, secs):
    assert yt.seconds(text) == secs


def test_threshold_and_shorts_filter():
    vids = [{'id': '1', 'title': 'x', 'secs': 599}, {'id': '2', 'title': 'x', 'secs': 600},
            {'id': '3', 'title': 'x', 'secs': 3000, 'short': True}, {'id': '2', 'title': 'x', 'secs': 600}]
    assert [v['id'] for v in topics.select(vids, 600)] == ['2']          # 599 s out, Short out, duplicate out


def test_category_regex():
    vids = [{'id': '1', 'title': 'How a substation works', 'secs': 900},
            {'id': '2', 'title': 'My vacation vlog', 'secs': 900}]
    assert [v['id'] for v in topics.select(vids, 600, '(?i)substation|transformer')] == ['1']


def test_top_is_by_views_long_only():
    vids = [{'id': 'a', 'title': 't', 'secs': 900, 'views': 10}, {'id': 'b', 'title': 't', 'secs': 900, 'views': 500},
            {'id': 'c', 'title': 't', 'secs': 60, 'views': 9999}]
    assert [v['id'] for v in topics.rank_top(vids, 480)] == ['b', 'a']


def test_age_sort():
    vids = [{'id': 'old', 'age': '2 years ago'}, {'id': 'new', 'age': '3 days ago'}, {'id': 'x', 'age': ''}]
    assert [v['id'] for v in topics.newest_first(vids)] == ['new', 'old', 'x']


def test_local_search_all_words_then_best():
    vids = [{'id': '1', 'title': 'PID Control explained'}, {'id': '2', 'title': 'PID tuning in practice'},
            {'id': '3', 'title': 'Transformers'}]
    assert [v['id'] for v in topics.search_local(vids, 'pid tuning')] == ['2']
    assert [v['id'] for v in topics.search_local(vids, 'pid loops')] == ['1', '2']      # none has both: best matches


@pytest.mark.parametrize('section', topics.SECTIONS)
def test_config_files_valid(section):
    cfg = topics.load(section)
    assert cfg['min_seconds'] >= 480
    for c in cfg['categories']:
        assert c['he'] and c['en'] and c['ru'] and c['icon']
        if c.get('match'):
            re.compile(c['match'])
        media = os.path.join(os.path.dirname(topics.__file__), '..', 'media', 'cats', 'topic_%s.png' % c['icon'])
        assert os.path.exists(media), 'tile missing: %s' % c['icon']
    chans = topics.all_channels(section)
    assert chans and all(re.match(r'^UC[\w-]{22}$', c['id']) for c in chans)
