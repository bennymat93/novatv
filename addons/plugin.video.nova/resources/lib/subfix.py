# -*- coding: utf-8 -*-
"""Robust subtitle handling (spec: docs/v1.1.0/research/SRT_HANDLING.md) - stdlib only, Python 3.8 (Kodi 21).

detect/decode encodings (BOM, UTF-8, cp1255, ISO-8859-8 incl. visual order, latin-1), tolerant SRT/WebVTT parsing,
repair (sort, empty, 0-length, overlaps, duplicates, negative times), tag normalisation, Hebrew RTL fixes (RLM,
punctuation, dialogue dashes), atomic UTF-8-with-BOM writing, fuzzy subtitle-to-video matching.
"""
import difflib
import os
import re
import unicodedata

RLM = '‏'
BIDI_CTRL = re.compile('[‪-‮⁦-⁩‎‏]')
HEB = re.compile('[א-ת]')
LETTER = re.compile(r'[^\W\d_]', re.U)
TS_RX = re.compile(r'^\s*(?:(\d+)\s*:\s*)?(\d{1,2})\s*:\s*(\d{1,2})\s*(?:[,.:]\s*(\d{1,3}))?\s*$')
TAG_RX = re.compile(r'<\s*(/?)\s*([a-zA-Z]+)([^>]*)>')
AN_RX = re.compile(r'^\s*\{\\an([1-9])\}')
OVERRIDE_RX = re.compile(r'\{\\[^}]*\}')
KEEP_TAGS = ('i', 'b', 'u', 'font')


class Cue(object):
    __slots__ = ('start_ms', 'end_ms', 'text', 'align')

    def __init__(self, start_ms, end_ms, text, align=None):
        self.start_ms, self.end_ms, self.text, self.align = int(start_ms), int(end_ms), text, align

    def __eq__(self, o):
        return (self.start_ms, self.end_ms, self.text, self.align) == (o.start_ms, o.end_ms, o.text, o.align)

    def __repr__(self):
        return 'Cue(%d, %d, %r, %r)' % (self.start_ms, self.end_ms, self.text, self.align)


# ------------------------------------------------------------------ encodings
def score_hebrew(text):
    """0..1: share of Hebrew letters among all letters, penalised by U+FFFD and C1 control characters"""
    letters = LETTER.findall(text)
    if not letters:
        return 0.0
    heb = sum(1 for c in letters if HEB.match(c))
    bad = text.count('�') + sum(1 for c in text if '\x80' <= c <= '\x9f')
    return max(0.0, heb / float(len(letters)) - 0.5 * bad / float(max(1, len(text))))


def is_visual_hebrew(text):
    """visual (reversed) Hebrew: final letters ךםןףץ mostly at the START of words"""
    words = re.findall('[א-ת]{2,}', text)
    finals = 'ךםןףץ'
    first = sum(1 for w in words if w[0] in finals)
    last = sum(1 for w in words if w[-1] in finals)
    return first + last >= 5 and first > 2 * last


def detect_encoding(data):
    """(codec, confidence) - BOM, strict UTF-8, then cp1255 / iso-8859-8 / latin-1 by score. Never raises."""
    if data.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig', 1.0
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return 'utf-16', 1.0
    try:
        data.decode('utf-8')
        return 'utf-8', 0.99
    except UnicodeDecodeError:
        pass
    high = [b for b in bytearray(data) if b >= 0x80]
    if not high:
        return 'utf-8', 0.9
    heb_bytes = sum(1 for b in high if 0xe0 <= b <= 0xfa)
    c1 = sum(1 for b in high if 0x80 <= b <= 0x9f)
    if heb_bytes / float(len(high)) > 0.5:
        # same letters in both; C1 bytes are quotes/dashes in cp1255 but control characters in ISO-8859-8,
        # so cp1255 (a superset for text) is the safe decoder either way - more sure when C1 bytes are present
        return 'cp1255', (0.95 if c1 else 0.85)
    return 'latin-1', 0.5


def decode_bytes(data):
    """decode with the detected codec; visual Hebrew is reversed per line; BOM stripped, newlines '\\n', NFC"""
    codec, _ = detect_encoding(data)
    text = data.decode(codec, errors='replace')
    text = text.replace('﻿', '').replace('\r\n', '\n').replace('\r', '\n')
    if is_visual_hebrew(text):
        text = '\n'.join(l[::-1] if HEB.search(l) and '-->' not in l else l for l in text.split('\n'))
    return unicodedata.normalize('NFC', text)


# ------------------------------------------------------------------ parsing
def parse_timestamp(s):
    """'[H:]MM:SS[,.:]fff' tolerant (spaces, 1-3 fraction digits scaled, hours unbounded) -> ms or None"""
    m = TS_RX.match(s or '')
    if not m:
        return None
    h, mi, se, fr = m.groups()
    ms = int(fr.ljust(3, '0')) if fr else 0
    return ((int(h or 0) * 60 + int(mi)) * 60 + int(se)) * 1000 + ms


def normalise_tags(text):
    """keep <i> <b> <u> <font color>, lowercase them; VTT <c.x> dropped; {\\anN} returned, other overrides dropped;
    unbalanced tags closed"""
    align = None
    m = AN_RX.match(text)
    if m:
        align = int(m.group(1))
        text = text[m.end():]
    text = OVERRIDE_RX.sub('', text)
    out, stack, pos = [], [], 0
    for t in TAG_RX.finditer(text):
        out.append(text[pos:t.start()])
        pos = t.end()
        close, name, rest = t.group(1), t.group(2).lower(), t.group(3)
        if name not in KEEP_TAGS:
            continue
        if close:
            if name in stack:
                while stack:
                    top = stack.pop()
                    out.append('</%s>' % top)
                    if top == name:
                        break
        else:
            if name == 'font':
                c = re.search(r'color\s*=\s*"?([#\w]+)"?', rest, re.I)
                if not c:
                    continue
                out.append('<font color="%s">' % c.group(1))
            else:
                out.append('<%s>' % name)
            stack.append(name)
    out.append(text[pos:])
    out.extend('</%s>' % n for n in reversed(stack))
    return ''.join(out).strip(), align


def _plain(text):
    return TAG_RX.sub('', text).strip()


def parse_subtitles(text):
    """SRT + WebVTT, tolerant: any line with '-->' starts a cue; index lines, WEBVTT/NOTE/STYLE and cue settings ignored"""
    cues = []
    lines = text.replace('\r', '').replace('﻿', '').split('\n')
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if '-->' not in line:
            i += 1
            continue
        a, _, b = line.partition('-->')
        b = b.strip().split(' ')[0] if b.strip() else ''
        start, end = parse_timestamp(a.strip()), parse_timestamp(b)
        i += 1
        body = []
        while i < n and lines[i].strip() and '-->' not in lines[i]:
            body.append(lines[i].rstrip())
            i += 1
        # a trailing numeric line right before the next timing line is the next index, not text
        if body and re.fullmatch(r'\d+', body[-1].strip()) and i < n and '-->' in lines[i]:
            body.pop()
        if start is None or end is None:
            continue
        txt, align = normalise_tags('\n'.join(body))
        cues.append(Cue(start, end, txt, align))
    return cues


def repair_cues(cues, min_ms=300, gap_ms=1):
    """clamp negatives, drop empty, fix 0-length, sort, merge duplicates, fix overlaps"""
    out = []
    for c in cues:
        c = Cue(max(0, c.start_ms), max(0, c.end_ms), c.text, c.align)
        if not _plain(c.text):
            continue
        if c.end_ms <= c.start_ms:
            c.end_ms = c.start_ms + min_ms
        out.append(c)
    out.sort(key=lambda c: (c.start_ms, c.end_ms))
    merged = []
    for c in out:
        if merged:
            p = merged[-1]
            if _plain(p.text) == _plain(c.text) and c.start_ms <= p.end_ms:
                p.end_ms = max(p.end_ms, c.end_ms)               # exact duplicate
                continue
            if c.start_ms < p.end_ms:
                overlap = p.end_ms - c.start_ms
                if overlap < 0.5 * (p.end_ms - p.start_ms):
                    p.end_ms = max(p.start_ms + 1, c.start_ms - gap_ms)
                else:
                    p.text = p.text + '\n' + c.text              # simultaneous speakers
                    p.end_ms = max(p.end_ms, c.end_ms)
                    continue
        merged.append(c)
    return merged


# ------------------------------------------------------------------ Hebrew
def fix_hebrew_line(line):
    """Hebrew line: strip old bidi controls, leading punctuation -> end, trailing ' -' -> front, RLM prefix (idempotent),
    RLM between a trailing Latin/number run and the final punctuation"""
    if not HEB.search(line):
        return line
    lead_tags = re.match(r'^((?:<[^>]+>)*)', line).group(1)
    body = BIDI_CTRL.sub('', line[len(lead_tags):])
    trail = re.search(r'((?:</[^>]+>)*)$', body).group(1)
    core = body[:len(body) - len(trail)] if trail else body
    m = re.match(r'^([.,?!:;]+)\s*(.*)$', core)
    if m and not re.search(r'[.,?!:;]$', m.group(2)):
        core = m.group(2) + m.group(1)
    m = re.match(r'^(.*\S)\s*-$', core)
    if m and not core.startswith('-'):
        core = '- ' + m.group(1)
    core = re.sub(r'([A-Za-z0-9])([.,?!:;]+)$', lambda x: x.group(1) + RLM + x.group(2), core)
    return lead_tags + RLM + core + trail


def fix_hebrew(cues):
    for c in cues:
        c.text = '\n'.join(fix_hebrew_line(l) for l in c.text.split('\n'))
    return cues


# ------------------------------------------------------------------ writing
def format_timestamp(ms):
    ms = max(0, int(ms))
    return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def to_srt(cues):
    out = []
    for n, c in enumerate(cues, 1):
        t = ('{\\an%d}' % c.align if c.align else '') + c.text
        out.append('%d\n%s --> %s\n%s\n' % (n, format_timestamp(c.start_ms), format_timestamp(c.end_ms), t))
    return '\n'.join(out)


def write_srt(cues, path):
    """UTF-8 with BOM, atomic (tmp + os.replace)"""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(to_srt(cues))
    os.replace(tmp, path)


def fix_file(src, dst=None, hebrew=True):
    with open(src, 'rb') as f:
        data = f.read()
    codec, conf = detect_encoding(data)
    text = decode_bytes(data)
    raw = parse_subtitles(text)
    cues = repair_cues(raw)
    if hebrew and sum(1 for c in cues if HEB.search(c.text)) >= max(1, len(cues) // 3):
        fix_hebrew(cues)
    write_srt(cues, dst or src)
    return {'encoding': codec, 'confidence': conf, 'cues_in': len(raw), 'cues_out': len(cues),
            'visual_reversed': is_visual_hebrew(data.decode(codec, errors='replace'))}


# ------------------------------------------------------------------ fuzzy matching
RELEASE_TAGS = re.compile(
    r'\b(2160p|1080p|720p|480p|4k|uhd|x26[45]|h\.?26[45]|hevc|avc|web[ .-]?dl|webrip|web|bluray|blu-ray|brrip|bdrip|'
    r'hdtv|dvdrip|hdr10?|hdr|dv|dovi|aac2?\.?0?|ac3|eac3|ddp?5\.1|dd5\.1|atmos|truehd|dts(-hd)?|proper|repack|'
    r'internal|remux|10bit|8bit|amzn|nf|dsnp|hmax|atvp|multi|subs?)\b', re.I)
LANG_SUFFIX = re.compile(r'[._ -](he|heb|hebrew|iw|en|eng|english|ru|rus)$', re.I)


def normalise_name(name):
    base = os.path.basename(name)
    base = re.sub(r'\.(srt|vtt|ass|ssa|sub|mkv|mp4|avi|m4v|ts|webm)$', '', base, flags=re.I)
    base = LANG_SUFFIX.sub('', base)
    base = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', base)
    base = re.sub(r'-[A-Za-z0-9]+$', '', base)                  # release group
    base = re.sub(r'[._\-]+', ' ', base.lower())
    base = RELEASE_TAGS.sub(' ', base)
    return re.sub(r'\s+', ' ', base).strip()


def parse_episode(name):
    m = re.search(r's(\d{1,2})[ ._-]?e(\d{1,3})', name, re.I) or re.search(r'\b(\d{1,2})x(\d{2,3})\b', name, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def match_score(video, sub):
    ev, es = parse_episode(video), parse_episode(sub)
    if (ev or es) and ev != es:
        return 0.0
    return difflib.SequenceMatcher(None, normalise_name(video), normalise_name(sub)).ratio()


def find_best_subtitle(video_path, candidates, threshold=0.6):
    vb = os.path.splitext(os.path.basename(video_path))[0].lower()
    for c in candidates:
        if os.path.basename(c).lower().startswith(vb + '.') or os.path.splitext(os.path.basename(c))[0].lower() == vb:
            return c
    best, best_s = None, 0.0
    for c in candidates:
        s = match_score(video_path, c) + (0.05 if re.search(r'[._ -](he|heb|hebrew)[._ -]', os.path.basename(c), re.I) else 0)
        if s > best_s:
            best, best_s = c, s
    return best if best_s >= threshold else None
