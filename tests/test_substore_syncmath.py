# -*- coding: utf-8 -*-
import os
import time

import pytest

from resources.lib import substore, syncmath, subfix
from resources.lib.subfix import Cue

SRT = '1\n00:00:01,000 --> 00:00:02,000\nשלום\n\n2\n00:00:03,000 --> 00:00:04,000\nמה נשמע\n'


def test_naming():
    assert os.path.basename(substore.path_for('/x', 'Reacher S04E01', 'he', 'ai')) == 'Reacher S04E01.he.ai.srt'
    assert os.path.basename(substore.path_for('/x', 'M', 'he', 'dl', 3)) == 'M.he.dl.v3.srt'
    with pytest.raises(ValueError):
        substore.path_for('/x', 'M', 'he', 'other')


def test_video_base():
    assert substore.video_base('Reacher', 4, 1) == 'Reacher S04E01'
    assert substore.video_base('Film') == 'Film'
    assert substore.video_base(path='http://h/a/My.Movie.2020.mkv?token=1') == 'My.Movie.2020'


def test_safe_base_unicode_and_long():
    b = substore.safe_base('ריצ׳ר: עונה/1 ' + 'א' * 300)
    assert '/' not in b and ':' not in b and len(b) <= substore.MAX_BASE and b.startswith('ריצ׳ר')


def test_save_versions_and_same_content(tmp_path):
    f = str(tmp_path)
    p1 = substore.save(f, 'Film', 'he', 'ai', text=SRT)
    p1b = substore.save(f, 'Film', 'he', 'ai', text=SRT)
    assert p1 == p1b                                            # same content -> same file, not a copy
    p2 = substore.save(f, 'Film', 'he', 'ai', text=SRT.replace('שלום', 'היי'))
    assert p2.endswith('.v2.srt')
    assert open(p1, 'rb').read().startswith(b'\xef\xbb\xbf')
    assert subfix.RLM in open(p1, encoding='utf-8-sig').read()  # Hebrew fixed on save


def test_save_empty_refused(tmp_path):
    with pytest.raises(ValueError):
        substore.save(str(tmp_path), 'Film', 'he', 'auto', text='')


def test_entries_preview_filter(tmp_path):
    f = str(tmp_path)
    substore.save(f, 'Film', 'he', 'ai', text=SRT)
    substore.save(f, 'Other', 'en', 'dl', text='1\n00:00:01,000 --> 00:00:02,000\nHi\n')
    open(os.path.join(f, 'random.txt'), 'w').write('x')
    e = substore.entries(f, 'Film')
    assert len(e) == 1 and e[0]['source'] == 'ai' and e[0]['lang'] == 'he'
    assert 'שלום' in e[0]['preview'] and 'מה נשמע' in e[0]['preview']
    assert len(substore.entries(f)) == 2


def test_cleanup_policies(tmp_path):
    f = str(tmp_path)
    paths = [substore.save(f, 'Film', 'he', 'ai', text=SRT.replace('שלום', 'x%d' % i)) for i in range(4)]
    for i, p in enumerate(paths):
        os.utime(p, (time.time() - (10 - i) * 86400,) * 2)
    gone = substore.cleanup(f, 'keep_last', keep_last=2)
    assert len(gone) == 2 and len(substore.entries(f)) == 2
    gone = substore.cleanup(f, 'older_than', older_days=7.5)
    assert len(gone) == 1
    assert substore.cleanup(f, 'keep_all') == []


def test_rename(tmp_path):
    p = substore.save(str(tmp_path), 'Film', 'he', 'dl', text=SRT)
    q = substore.rename(p, 'Film 2020')
    assert os.path.basename(q) == 'Film 2020.he.dl.srt' and not os.path.exists(p)


def test_missing_folder_is_empty():
    assert substore.entries('/no/such/folder') == []


# ---------------- sync math
def test_bookmark_delay():
    # subtitle appeared 1.5 s after the line was heard -> show it 1.5 s earlier
    assert syncmath.bookmark_delay(0.0, t_audio=100.0, t_sub=101.5) == -1.5
    assert syncmath.bookmark_delay(-0.5, t_audio=10.0, t_sub=9.0) == 0.5


def test_steps():
    assert syncmath.steps(0, 1.25, 0.1) == ('plus', 12) or syncmath.steps(0, 1.25, 0.1) == ('plus', 13)
    assert syncmath.steps(0.5, -0.5, 0.1) == ('minus', 10)
    assert syncmath.steps(0.3, 0.3, 0.1) == (None, 0)
    assert syncmath.steps(0, 0.1, syncmath.AUDIO_STEP) == ('plus', 4)


def test_parse_delay():
    assert syncmath.parse_delay('-1.250 s') == -1.25
    assert syncmath.parse_delay('0.000s') == 0.0
    assert syncmath.parse_delay('') == 0.0


def test_merge_dual_keeps_timings():
    a = [Cue(1000, 2000, 'שלום'), Cue(3000, 4000, 'עוד')]
    b = [Cue(1100, 2100, 'Hello')]
    m = syncmath.merge_dual(a, b)
    assert len(m) == 3
    assert [c for c in m if c.align == 8][0].start_ms == 1100
    assert '{\\an8}Hello' in subfix.to_srt(m)


def test_chunking_roundtrip_identical_timings():
    cues = [Cue(i * 1000, i * 1000 + 800, 'line %d' % i) for i in range(1, 101)]
    chunks = syncmath.chunk_cues(cues, size=30, context=3)
    assert sum(len(c) for c, _ in chunks) == 100
    assert chunks[1][1] == ['line 28', 'line 29', 'line 30']
    out = []
    for ch, _ in chunks:
        out += syncmath.apply_translation(ch, ['T' + c.text for c in ch])
    assert [(c.start_ms, c.end_ms) for c in out] == [(c.start_ms, c.end_ms) for c in cues]


def test_translation_count_mismatch_refused():
    with pytest.raises(ValueError):
        syncmath.apply_translation([Cue(0, 1, 'a')], [])
