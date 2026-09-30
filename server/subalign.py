# -*- coding: utf-8 -*-
"""Automatic subtitle-to-audio alignment (like ffsubsync / alass, standard library + numpy).

1. speech activity of the video's audio (Silero VAD bundled with faster-whisper) -> a 0/1 signal at 10 Hz
2. the subtitle's own on-screen intervals -> the same kind of signal
3. for each frame-rate ratio a subtitle may have been timed for (23.976 / 24 / 25 fps mixes), find by FFT
   cross-correlation the shift that makes the two signals agree best
4. best (scale, offset) wins if it beats "no change" clearly; the SRT is rewritten t' = t * scale + offset
Measured quality: the agreement (fraction of subtitle time that falls on speech) before and after.
"""
import re

import numpy as np

HZ = 20                          # signal resolution: 50 ms
MAX_SHIFT = 60.0                 # seconds either way
RATIOS = (1.0, 25 / 23.976, 23.976 / 25, 24 / 23.976, 23.976 / 24, 25 / 24, 24 / 25)
TS = re.compile(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)')


def parse_srt(text):
    """[(start, end, text_block)] in seconds; keeps every cue's text as it is"""
    cues = []
    for block in re.split(r'\r?\n\s*\r?\n', text.strip()):
        m = TS.search(block)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        body = block[m.end():].strip('\r\n')
        cues.append((a, b, body))
    return cues


def _ts(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_srt(cues):
    return '\n'.join('%d\n%s --> %s\n%s\n' % (i, _ts(a), _ts(b), body) for i, (a, b, body) in enumerate(cues, 1))


def signal(intervals, length):
    """[(start, end)] seconds -> 0/1 array of `length` samples at HZ"""
    s = np.zeros(length, dtype=np.float32)
    for a, b in intervals:
        i, j = max(0, int(a * HZ)), min(length, int(b * HZ) + 1)
        if j > i:
            s[i:j] = 1.0
    return s


def _xcorr(a, b):
    """correlation of a against b shifted by k samples, for every k (FFT)"""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    fa, fb = np.fft.rfft(a, n), np.fft.rfft(b, n)
    return np.fft.irfft(fa * np.conj(fb), n)


def agreement(speech, cues, scale=1.0, offset=0.0):
    """fraction of subtitle on-screen time that lands on speech"""
    sub = signal([(a * scale + offset, b * scale + offset) for a, b, _ in cues], len(speech))
    total = sub.sum()
    return float((sub * speech).sum() / total) if total else 0.0


def best_fit(speech_intervals, cues, duration):
    """-> (scale, offset seconds, before, after, prominence): the timing change that best matches the speech.
    prominence = how far the best score stands above "no change", in standard deviations of all scores tried."""
    length = int(duration * HZ) + 1
    speech = signal(speech_intervals, length)
    sp = speech - speech.mean()                 # centred: rewards speech-on-speech and silence-on-silence alike
    best, zero, spread = (1.0, 0.0, -1e9), None, []
    maxk = int(MAX_SHIFT * HZ)
    for r in RATIOS:
        sub = signal([(a * r, b * r) for a, b, _ in cues], length)
        if not sub.any():
            continue
        c = _xcorr(sp, sub - sub.mean())
        n = len(c)
        vals = np.concatenate([c[:maxk + 1], c[n - maxk:]])
        spread.append(vals)
        if r == 1.0:
            zero = c[0]
        k = int(np.argmax(vals))
        shift = k if k <= maxk else k - len(vals)
        if vals[k] > best[2]:
            best = (r, shift / HZ, vals[k])
    r, off, score = best
    allv = np.concatenate(spread)
    prom = float((score - zero) / (allv.std() or 1.0)) if zero is not None else 0.0
    return r, off, agreement(speech, cues), agreement(speech, cues, r, off), prom


def refine(speech_intervals, cues, scale, offset, window=1.0):
    """fine offset: the median distance from each (coarsely placed) line start to the nearest speech onset -
    the 100 ms grid and dense dialogue leave the correlation peak a few hundred ms wide"""
    onsets = np.array(sorted(a for a, _ in speech_intervals))
    if not len(onsets):
        return offset
    d = []
    for a, _, _ in cues:
        t = a * scale + offset
        i = np.searchsorted(onsets, t)
        near = [onsets[j] - t for j in (i - 1, i) if 0 <= j < len(onsets)]
        m = min(near, key=abs) if near else None
        if m is not None and abs(m) <= window:
            d.append(m)
    return offset + float(np.median(d)) if len(d) >= 8 else offset


def apply(cues, scale, offset):
    return [(a * scale + offset, b * scale + offset, body) for a, b, body in cues]


def align_srt(srt_text, speech_intervals, duration, min_prominence=1.0):
    """-> (new srt text or None when no change is warranted, info dict)"""
    cues = parse_srt(srt_text)
    if len(cues) < 10:
        return None, {'reason': 'too few cues'}
    scale, offset, before, after, prom = best_fit(speech_intervals, cues, duration)
    info = {'scale': round(scale, 5), 'offset': round(offset, 2), 'before': round(before, 3), 'after': round(after, 3),
            'prominence': round(prom, 2)}
    if (abs(offset) < 0.1 and scale == 1.0) or prom < min_prominence:
        info['reason'] = 'already in sync'
        return None, info
    return write_srt(apply(cues, scale, offset)), info
