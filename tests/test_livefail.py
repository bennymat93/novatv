# -*- coding: utf-8 -*-
"""Israeli channel failover table + restream filter"""
from resources.lib import livefail


def test_restream_hosts_dropped():
    assert livefail.is_restream('http://str2.iptvhd.ru:8080/5sport/index.m3u8|User-Agent=x')
    assert livefail.is_restream('http://stream.mcquack.net/294/index.m3u8')
    assert not livefail.is_restream('https://kancdn.medonecdn.net/livehls/oil/kancdn-live/live/kan11/live.livx/playlist.m3u8')


def test_names_map_to_keys():
    assert livefail.key_for('Kan 11 (1080p)') == 'kan11'
    assert livefail.key_for('Keshet 12 (1080p)') == 'keshet12'
    assert livefail.key_for('Channel 13 (Israel) (1080p)') == 'reshet13'
    assert livefail.key_for('Knesset Channel (576p)') == 'knesset'
    assert livefail.key_for('HOT Cinema 1 (1080p)') is None


def test_every_channel_has_several_sources_direct_first():
    for key in livefail.CHANNELS:
        c = livefail.candidates(key)
        assert c and c[-1].startswith('plugin://plugin.video.idanplus/')
        direct = livefail.CHANNELS[key][1]
        assert c[:len(direct)] == direct
    assert len(livefail.candidates('keshet12')) == 4
