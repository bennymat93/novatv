# -*- coding: utf-8 -*-
"""automatic subtitle alignment: recovers a known offset and a 25/23.976 frame-rate drift"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
np = pytest.importorskip('numpy')
import subalign  # noqa: E402


def speech(seed=1, duration=1500):
    rnd, t, out = random.Random(seed), 5.0, []
    while t < duration - 10:
        d = rnd.uniform(0.8, 4.5)
        out.append((t, t + d))
        t += d + rnd.uniform(0.3, 6)
    return out


def srt_from(intervals, scale=1.0, offset=0.0):
    cues = [(a * scale + offset, b * scale + offset, 'line %d' % i) for i, (a, b) in enumerate(intervals)]
    return subalign.write_srt(cues)


@pytest.mark.parametrize('offset', [2.4, -1.7, 0.6, 12.0])
def test_recovers_offset(offset):
    sp = speech()
    new, info = subalign.align_srt(srt_from(sp, 1.0, offset), sp, 1500)
    assert new and abs(info['offset'] + offset) <= 0.15 and info['scale'] == 1.0
    assert info['after'] > 0.95 > info['before']


def test_recovers_framerate_drift():
    sp = speech(2)
    # a subtitle timed for 25 fps shown on a 23.976 fps video: every time is 23.976/25 of the right one
    new, info = subalign.align_srt(srt_from(sp, 23.976 / 25, 0.0), sp, 1500)
    assert new and abs(info['scale'] - 25 / 23.976) < 1e-4 and info['after'] > 0.9


def test_in_sync_is_left_alone():
    sp = speech(3)
    new, info = subalign.align_srt(srt_from(sp), sp, 1500)
    assert new is None


def test_srt_roundtrip_keeps_text():
    text = '1\n00:00:01,000 --> 00:00:02,500\nשלום\nעולם\n\n2\n00:01:00,250 --> 00:01:02,000\n<i>x</i>\n'
    cues = subalign.parse_srt(text)
    assert cues[0] == (1.0, 2.5, 'שלום\nעולם') and cues[1][2] == '<i>x</i>'
    assert subalign.parse_srt(subalign.write_srt(cues)) == cues
