# -*- coding: utf-8 -*-
"""Local store for every subtitle the build creates (docs/v1.1.0 phase 4.1) - pure Python, testable without Kodi.

File name: <video base>.<lang>.<source>[.vN].srt   source: auto | ai | dl
UTF-8 with BOM, atomic write, never silently overwritten (same content -> same file, different content -> next version).
"""
import os
import re
import time

from . import subfix

SOURCES = ('auto', 'ai', 'dl')
MAX_BASE = 120
NAME_RX = re.compile(r'^(?P<base>.+)\.(?P<lang>[a-z]{2,3})\.(?P<src>auto|ai|dl)(?:\.v(?P<ver>\d+))?\.srt$', re.I)


def safe_base(name):
    """a file-system-safe base name (Windows + Android), Unicode kept, length capped"""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', name or 'video')
    name = re.sub(r'\s+', ' ', name).strip(' .') or 'video'
    return name[:MAX_BASE].rstrip(' .')


def video_base(title='', season=0, episode=0, path=''):
    """stable base for a video: 'Title S01E02' for episodes, 'Title' for films, else the file name of a local path"""
    if title:
        if int(season or 0) > 0 and int(episode or 0) > 0:
            return safe_base('%s S%02dE%02d' % (title, int(season), int(episode)))
        return safe_base(title)
    base = os.path.basename((path or '').split('?')[0].rstrip('/'))
    return safe_base(os.path.splitext(base)[0] or 'video')


def path_for(folder, base, lang, source, version=1):
    if source not in SOURCES:
        raise ValueError('source must be one of %s' % (SOURCES,))
    name = '%s.%s.%s%s.srt' % (safe_base(base), lang.lower(), source, '' if version <= 1 else '.v%d' % version)
    return os.path.join(folder, name)


def save(folder, base, lang, source, cues=None, text=None):
    """write cues (subfix.Cue list) or SRT text; returns the path. Same content already stored -> that path."""
    os.makedirs(folder, exist_ok=True)
    if cues is None:
        cues = subfix.repair_cues(subfix.parse_subtitles(text or ''))
    if not cues:
        raise ValueError('no subtitle cues to save')
    if lang in ('he', 'heb', 'iw'):
        subfix.fix_hebrew(cues)
    body = subfix.to_srt(cues)
    v = 1
    while True:
        p = path_for(folder, base, lang, source, v)
        if not os.path.exists(p):
            break
        with open(p, encoding='utf-8-sig', errors='replace') as f:
            if f.read() == body:
                return p
        v += 1
    subfix.write_srt(cues, p)
    return p


def entries(folder, base=None):
    """stored subtitles (optionally only for one video): dicts with path, base, lang, source, version, mtime, preview"""
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    want = safe_base(base).lower() if base else None
    for n in names:
        m = NAME_RX.match(n)
        if not m or (want and m.group('base').lower() != want):
            continue
        p = os.path.join(folder, n)
        out.append({'path': p, 'base': m.group('base'), 'lang': m.group('lang').lower(), 'source': m.group('src').lower(),
                    'version': int(m.group('ver') or 1), 'mtime': os.path.getmtime(p), 'preview': preview(p)})
    out.sort(key=lambda e: e['mtime'], reverse=True)
    return out


def preview(path, lines=3):
    """first lines of text (2-3) for the picker"""
    try:
        with open(path, 'rb') as f:
            cues = subfix.parse_subtitles(subfix.decode_bytes(f.read(200000)))
    except OSError:
        return ''
    txt = []
    for c in cues:
        t = re.sub(r'<[^>]+>|[‎‏‪-‮]', '', c.text).replace('\n', ' ').strip()
        if t:
            txt.append(t)
        if len(txt) >= lines:
            break
    return ' / '.join(txt)


def cleanup(folder, policy='keep_all', keep_last=5, older_days=90, now=None):
    """policy: keep_all | keep_last (N newest per video+lang+source) | older_than (delete older than X days).
    Returns the deleted paths."""
    now = now or time.time()
    gone = []
    items = entries(folder)
    if policy == 'older_than':
        for e in items:
            if now - e['mtime'] > older_days * 86400:
                os.remove(e['path'])
                gone.append(e['path'])
    elif policy == 'keep_last':
        groups = {}
        for e in items:                                        # newest first already
            groups.setdefault((e['base'].lower(), e['lang'], e['source']), []).append(e)
        for g in groups.values():
            for e in g[keep_last:]:
                os.remove(e['path'])
                gone.append(e['path'])
    return gone


def rename(path, new_base):
    m = NAME_RX.match(os.path.basename(path))
    if not m:
        raise ValueError('not a BN subtitle file')
    folder = os.path.dirname(path)
    v = 1
    while os.path.exists(path_for(folder, new_base, m.group('lang'), m.group('src').lower(), v)):
        v += 1
    dst = path_for(folder, new_base, m.group('lang'), m.group('src').lower(), v)
    os.replace(path, dst)
    return dst
