# -*- coding: utf-8 -*-
"""Pure calculations for the player panels (testable without Kodi).

Kodi: subtitle delay > 0 shows subtitles LATER; Action(SubtitleDelayPlus/Minus) moves it by 0.1 s;
audio delay Action(AudioDelayPlus/Minus) by 0.025 s. There is no JSON-RPC setter, so a target value is reached by
repeating actions (steps()).
"""
from . import subfix

SUB_STEP = 0.1
AUDIO_STEP = 0.025


def bookmark_delay(current, t_audio, t_sub):
    """VLC 'sync by bookmarking': the viewer marks the moment he HEARS a line (t_audio) and the moment the matching
    subtitle APPEARS (t_sub). The subtitle must move by (t_audio - t_sub): earlier if it came late."""
    return round(float(current) + (float(t_audio) - float(t_sub)), 3)


def steps(current, target, step):
    """(action_direction, count) to go from current to target in fixed steps: ('plus'|'minus'|None, n)"""
    n = int(round((float(target) - float(current)) / step))
    if n == 0:
        return None, 0
    return ('plus' if n > 0 else 'minus'), abs(n)


def parse_delay(label):
    """'-1.250 s' / '0.000s' / '' (Kodi info labels) -> float seconds"""
    import re
    m = re.search(r'-?\d+(?:[.,]\d+)?', label or '')
    return float(m.group(0).replace(',', '.')) if m else 0.0


def merge_dual(primary, secondary):
    """one subtitle file with two languages: primary cues as they are (bottom), secondary cues on top ({\\an8}).
    Timings of both are kept exactly."""
    out = [subfix.Cue(c.start_ms, c.end_ms, c.text, c.align) for c in primary]
    out += [subfix.Cue(c.start_ms, c.end_ms, c.text, 8) for c in secondary]
    out.sort(key=lambda c: (c.start_ms, c.align or 0))
    return out


def chunk_cues(cues, size=40, context=4):
    """AI translation batches: [(chunk_cues, previous_context_texts)] - every cue appears in exactly one chunk,
    timings untouched (the translation only replaces text)"""
    out = []
    for i in range(0, len(cues), size):
        prev = [c.text for c in cues[max(0, i - context):i]]
        out.append((cues[i:i + size], prev))
    return out


def apply_translation(cues, texts):
    """same cues, new text, identical timings; refuses a result with a different line count"""
    if len(texts) != len(cues):
        raise ValueError('translation has %d lines for %d cues' % (len(texts), len(cues)))
    return [subfix.Cue(c.start_ms, c.end_ms, t, c.align) for c, t in zip(cues, texts)]
