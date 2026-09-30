# -*- coding: utf-8 -*-
"""device profiles: every profile complete, cache scales with memory, platform decoding, touch flags"""
import pytest

from resources.lib import profiles


@pytest.mark.parametrize('p', profiles.ORDER)
def test_profile_plan_complete(p):
    s, touch = profiles.plan(p, 4096, 'android')
    for k in ('lookandfeel.skinzoom', 'filecache.memorysize', 'filecache.readfactor', 'screensaver.mode',
              'videoplayer.usemediacodec', 'videoplayer.adjustrefreshrate'):
        assert k in s
    assert touch == (p in ('touch', 'car', 'phone', 'tablet'))
    assert profiles.label(p, 'he') and profiles.label(p, 'en')


def test_cache_scales_with_memory():
    assert profiles.cache_mb(1024, "tv") == 64
    assert profiles.cache_mb(16384, 'pc') == 512
    assert profiles.cache_mb(3072, 'car') > profiles.cache_mb(3072, 'tv')


def test_car_never_sleeps_and_tv_switches_refresh():
    car, _ = profiles.plan('car', 2048, 'android')
    tv, _ = profiles.plan('tv', 2048, 'android')
    assert car['screensaver.mode'] == '' and 'screensaver.time' not in car
    assert tv['videoplayer.adjustrefreshrate'] == 2 and car['videoplayer.adjustrefreshrate'] == 0


def test_windows_uses_dxva():
    s, _ = profiles.plan('pc', 8192, 'windows')
    assert s['videoplayer.usedxva2'] is True and 'videoplayer.usemediacodec' not in s
