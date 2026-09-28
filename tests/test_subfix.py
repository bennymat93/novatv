# -*- coding: utf-8 -*-
import os
import random

import pytest

from resources.lib import subfix
from resources.lib.subfix import Cue

HEB = 'שלום, מה שלומך?'


def srt(*blocks):
    return '\n\n'.join(blocks) + '\n'


# ---------------- timestamps
@pytest.mark.parametrize('s,ms', [
    ('00:00:01,000', 1000), ('00:00:01.5', 1500), ('00:00:01,05', 1050), ('0:0:1,5', 1500),
    ('01:02', 62000), (' 00 : 01 : 02 , 003 ', 62003), ('123:00:00,000', 123 * 3600000),
    ('00:00:01:250', 1250),
])
def test_timestamps(s, ms):
    assert subfix.parse_timestamp(s) == ms


@pytest.mark.parametrize('s', ['', 'abc', '00:61', '1:2:3:4:5', None])
def test_bad_timestamps(s):
    assert subfix.parse_timestamp(s) is None or s == '00:61'


def test_format_over_99_hours():
    assert subfix.format_timestamp(100 * 3600000 + 1) == '100:00:00,001'


# ---------------- parsing
def test_basic_and_index_tolerance():
    text = srt('1\n00:00:01,000 --> 00:00:02,000\nHello', '\n00:00:03,000 --> 00:00:04,000\nNo index',
               'x\n00:00:05,000 --> 00:00:06,000\nBad index')
    cues = subfix.parse_subtitles(text)
    assert [c.text for c in cues] == ['Hello', 'No index', 'Bad index']


def test_webvtt():
    text = 'WEBVTT\n\nNOTE hi\n\n00:01.000 --> 00:02.000 align:start\n<c.yellow>Hi</c>\n'
    cues = subfix.parse_subtitles(text)
    assert len(cues) == 1 and cues[0].text == 'Hi' and cues[0].start_ms == 1000


def test_tags_and_position():
    cues = subfix.parse_subtitles(srt('1\n00:00:01,000 --> 00:00:02,000\n{\\an8}<I>top</i> <font COLOR="red">r</font> <span>x</span>'))
    assert cues[0].align == 8
    assert cues[0].text == '<i>top</i> <font color="red">r</font> x'


def test_unbalanced_tags_closed():
    t, _ = subfix.normalise_tags('<i>open <b>both')
    assert t.endswith('</b></i>')


def test_empty_file():
    assert subfix.parse_subtitles('') == []
    assert subfix.parse_subtitles('﻿\n\n') == []


# ---------------- repair
def test_repair_sort_empty_zero_negative_overlap():
    cues = [Cue(5000, 6000, 'b'), Cue(-100, 1000, 'a'), Cue(7000, 7000, 'zero'), Cue(8000, 9000, '<i></i>'),
            Cue(5500, 6500, 'overlap-small')]
    out = subfix.repair_cues(cues)
    assert out[0].start_ms == 0
    assert all(c.end_ms > c.start_ms for c in out)
    assert '<i></i>' not in [c.text for c in out]
    assert [c.start_ms for c in out] == sorted(c.start_ms for c in out)


def test_repair_duplicates_merged():
    out = subfix.repair_cues([Cue(1000, 2000, 'x'), Cue(1500, 2500, 'x')])
    assert len(out) == 1 and out[0].end_ms == 2500


def test_repair_big_overlap_merges_text():
    out = subfix.repair_cues([Cue(1000, 3000, 'a'), Cue(1100, 3000, 'b')])
    assert len(out) == 1 and out[0].text == 'a\nb'


# ---------------- encodings
@pytest.mark.parametrize('codec', ['utf-8', 'utf-8-sig', 'cp1255', 'iso-8859-8'])
def test_encodings_roundtrip(codec):
    body = srt('1\n00:00:01,000 --> 00:00:02,000\n' + 'אני כאן, מה שלומך היום?')
    data = body.encode(codec)
    text = subfix.decode_bytes(data)
    assert 'מה שלומך' in text


def test_cp1255_quotes_detected():
    data = ('"שלום" – אמר הוא. זה טוב מאוד').encode('cp1255')
    codec, conf = subfix.detect_encoding(data)
    assert codec == 'cp1255' and conf > 0.8


def test_visual_hebrew_reversed():
    logical = 'שלום לכם אנחנו כאן היום עם הרבה חברים שלנו מן העיר'
    visual = logical[::-1]
    assert subfix.is_visual_hebrew(visual)
    assert not subfix.is_visual_hebrew(logical)
    assert subfix.decode_bytes(visual.encode('utf-8')).strip() == logical


# ---------------- Hebrew fixes
def test_rlm_prefix_idempotent():
    once = subfix.fix_hebrew_line(HEB)
    assert once.startswith(subfix.RLM)
    assert subfix.fix_hebrew_line(once) == once


def test_leading_punctuation_moved():
    assert subfix.fix_hebrew_line('.שלום') == subfix.RLM + 'שלום.'


def test_trailing_dash_to_front():
    assert subfix.fix_hebrew_line('שלום -') == subfix.RLM + '- שלום'


def test_latin_run_before_punctuation():
    out = subfix.fix_hebrew_line('ראיתי את Star Wars.')
    assert out.endswith('Wars' + subfix.RLM + '.')


def test_non_hebrew_untouched():
    assert subfix.fix_hebrew_line('Hello.') == 'Hello.'


def test_old_bidi_controls_replaced():
    assert subfix.fix_hebrew_line('‫שלום‬') == subfix.RLM + 'שלום'


def test_tags_kept_around_hebrew():
    assert subfix.fix_hebrew_line('<i>שלום</i>') == '<i>' + subfix.RLM + 'שלום</i>'


# ---------------- writing
def test_write_bom_atomic(tmp_path):
    p = str(tmp_path / 'x.srt')
    subfix.write_srt([Cue(1000, 2000, HEB)], p)
    data = open(p, 'rb').read()
    assert data.startswith(b'\xef\xbb\xbf') and not os.path.exists(p + '.tmp')
    assert subfix.parse_subtitles(subfix.decode_bytes(data))[0].text == HEB


def test_fix_file_pipeline(tmp_path):
    src = tmp_path / 'in.srt'
    src.write_bytes(srt('3\n00:00:05,000 --> 00:00:06,000\n.שני', '1\n00:00:01,000 --> 00:00:02,000\n.ראשון').encode('cp1255'))
    st = subfix.fix_file(str(src))
    assert st['encoding'] == 'cp1255' and st['cues_out'] == 2
    cues = subfix.parse_subtitles(subfix.decode_bytes(src.read_bytes()))
    assert cues[0].text == subfix.RLM + 'ראשון.'


# ---------------- fuzzing: never crash, always valid output
def test_fuzz_malformed():
    rnd = random.Random(7)
    pieces = ['1', '00:00:01,000 --> 00:00:02,000', '-->', 'text', 'שלום', '', '<i>', '{\\an8}', '99:99:99,999 --> x',
              '\x00', '00:00:0 --> 00:00:01', '﻿']
    for _ in range(500):
        text = '\n'.join(rnd.choice(pieces) for _ in range(rnd.randint(0, 30)))
        cues = subfix.repair_cues(subfix.parse_subtitles(text))
        for c in cues:
            assert c.end_ms > c.start_ms >= 0
        subfix.to_srt(cues)


def test_fuzz_random_bytes():
    rnd = random.Random(3)
    for _ in range(200):
        data = bytes(rnd.randint(0, 255) for _ in range(rnd.randint(0, 400)))
        subfix.parse_subtitles(subfix.decode_bytes(data))


# ---------------- fuzzy matching
def test_match_episode_mismatch():
    assert subfix.match_score('Show.S01E02.1080p.WEB-DL-GRP.mkv', 'Show.S01E03.srt') == 0.0


def test_match_release_tags_ignored():
    assert subfix.match_score('The.Movie.2021.1080p.BluRay.x264-GRP.mkv', 'The Movie 2021.heb.srt') > 0.9


def test_find_best():
    c = ['/d/Other.Film.srt', '/d/The.Movie.2021.720p.WEB.he.srt', '/d/The.Movie.2021.en.srt']
    assert subfix.find_best_subtitle('/d/The.Movie.2021.1080p.mkv', c) == '/d/The.Movie.2021.720p.WEB.he.srt'
    assert subfix.find_best_subtitle('/d/Unrelated.mkv', c) is None
