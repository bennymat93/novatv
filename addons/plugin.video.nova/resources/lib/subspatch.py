# -*- coding: utf-8 -*-
"""Guards for the third-party subtitle services All_Subs and All Subs Plus.

Found by the 0.2.2 deep tests:
  * All_Subs' automatic search keeps running after the video changed or Kodi was asked to quit, then places the
    subtitle it found into whatever plays now (a subtitle of the previous video / another title) and holds Kodi's
    exit. Guards: remember the video of the search (Player.OnPlay), place a subtitle only while that same video
    plays, leave the wait loops as soon as Kodi quits.
  * 1.1.0 (v5): after many quick video starts its queued automatic searches still ran with nothing playing and
    while Kodi quit (Subscene retries held the exit for ~2 min): no search once Kodi quits or no video plays.
  * All Subs Plus' main loop read "Kodi quits" once at start and never ended, so Kodi had to kill it on exit.

Pure Python (no Kodi modules): used by tools/make_build.py and by the NovaTV service at start-up, because the
services update themselves from their repository and lose the change (idempotent, like the POV hook).
"""
import os

MARK = '# BN guard v4'

HELPERS = '''
%s: subtitles only for the video they were searched for, and nothing once Kodi quits
_bn_file = ''
_BN_PLAYER = xbmc.Player()   # ONE Player: Players created in loops and freed while Kodi notified them crashed Kodi


def _bn_playing_file():
    for _ in range(100):
        if monit.abortRequested():
            return ''
        try:
            if _BN_PLAYER.isPlayingVideo():
                return _BN_PLAYER.getPlayingFile()
        except Exception:
            pass
        xbmc.sleep(100)
    return ''


def _bn_same_video():
    try:
        return (not monit.abortRequested()) and _BN_PLAYER.isPlayingVideo() and \\
            (not _bn_file or _BN_PLAYER.getPlayingFile() == _bn_file)
    except Exception:
        return False
''' % MARK

PLACE_SUB = ('def place_sub(video_data,f_result,last_sub_name_in_cache,last_sub_language_in_cache,all_subs,'
             'last_sub_in_cache_is_empty):\n')

EDITS = [
    # every xbmc.Player() of the service -> one shared Player (created with the helpers below)
    ('xbmc.Player()', '_BN_PLAYER'),
    # helpers right after the module's own monitor
    ("ab_req=monit.abortRequested()\n", "ab_req=monit.abortRequested()\n" + HELPERS),
    # both wait loops end when Kodi quits
    ("    while counter<70:\n", "    while counter<70 and not monit.abortRequested():\n"),
    # the video this search is for
    ("        if method=='Player.OnPlay':\n",
     "        if method=='Player.OnPlay':\n            global _bn_file\n            _bn_file = _bn_playing_file()\n"),
    # nothing to download once the video changed or Kodi quits
    (PLACE_SUB, PLACE_SUB + "    if not _bn_same_video():\n        return None, None\n"),
    # its 5 s message pauses end when Kodi quits (xbmc.sleep ignored it: Kodi had to kill the service on exit)
    ('xbmc.sleep(5000)', 'monit.waitForAbort(5)'),
    # never place a subtitle into another video (or while quitting)
    ("            xbmc.sleep(200)\n            _BN_PLAYER.setSubtitles(sub_file)        \n",
     "            xbmc.sleep(200)\n            if not _bn_same_video():\n"
     "                log.warning('BN guard: video changed or Kodi quits - subtitle not placed')\n"
     "                return None, None\n"
     "            _BN_PLAYER.setSubtitles(sub_file)        \n"),
]

PLUS_MARK = '# BN guard plus v1'
PLUS_OLD = "        xbmc.sleep(sleep_time)\n        '''\n        if counter_2_hr"
PLUS_NEW = ("        if monitor.waitForAbort(sleep_time / 1000.0):  %s\n            break\n        '''\n        if counter_2_hr"
            % PLUS_MARK)


def _patch(path, mark, edits):
    with open(path, encoding='utf-8', newline='') as f:
        s = f.read()
    if mark in s:
        return 0
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for old, new in edits:
        if old not in s:
            raise RuntimeError('%s changed: %r' % (os.path.basename(os.path.dirname(path)), old[:50]))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)
    return 1


MARK5 = '# BN guard v5'
SEARCH = 'def temporary_pop_and_get_subtitles(video_data):\n'
EDITS5 = [(SEARCH, SEARCH + "    if monit.abortRequested() or not _BN_PLAYER.isPlayingVideo():  %s\n"
                            "        return []   # nothing plays any more / Kodi quits: no search\n" % MARK5)]


# v5: the search engine and the message overlay created a new xbmc.Player() every 10-100 ms in worker threads (the
# 0.2.2 crash pattern: Kodi crashed at CloseFile) and never noticed Kodi quitting (exit held ~2 min).
# One Monitor per process (module level, never freed); "is something playing" read as an InfoLabel (no object).
PLAYING = "xbmc.getCondVisibility('Player.HasMedia')"
GENERAL5 = [
    ('import xbmc,xbmcaddon,xbmcvfs,xbmcgui\n',
     'import xbmc,xbmcaddon,xbmcvfs,xbmcgui\n_BN_MON = xbmc.Monitor()   %s: one Monitor per process\n' % MARK5),
    ('            cond=xbmc.Monitor().abortRequested()\n', '            cond=_BN_MON.abortRequested()\n'),
    ('while (not cond) and (xbmc.Player().isPlaying()):', 'while (not _BN_MON.abortRequested()) and %s:' % PLAYING),
    ('xbmc.Player().isPlaying()', PLAYING),
]
ENGINE5 = [
    ('import xbmc,xbmcgui,time,xbmcplugin\n',
     'import xbmc,xbmcgui,time,xbmcplugin\n\n\ndef _bn_quit():   %s\n'
     '    from resources.modules import general\n    return general._BN_MON.abortRequested()\n\n\n' % MARK5),
    ('xbmc.Player().isPlaying()', PLAYING),
    # Kodi quits: stop the source threads like the search time-out does
    ('        if  elapsed_time>ExcludeTime: \n', '        if  elapsed_time>ExcludeTime or _bn_quit(): \n'),
]


# v6: the one-off xbmc.Player() calls of every video start (get_video_data, the sources, the subtitle window) ran in
# worker threads too; each created+freed Player registers for Kodi's player callbacks -> the same crash when freed
# while Kodi delivered one (dump 1.1.0: python3.8.dll+0xdfec1 in a Python thread at CloseFile). One Player per process.
MARK6 = '# BN guard v6'
SHARED = 'from resources.modules.general import _BN_PLAYER   %s\n' % MARK6
# a backlog of queued Player.OnPlay notifications (quick zapping) was replayed one by one, even after Kodi quit
BN_FILE = "            _bn_file = _bn_playing_file()\n"
AUTOSUB6 = [(BN_FILE, BN_FILE + "            if not _bn_file:   %s: nothing plays any more / Kodi quits\n"
                                "                return\n" % MARK6)]
# v7: while Kodi quits the video still counts as playing, so the backlog passed v6: a queued notification for the video
# handled less than 60 s ago is a duplicate (a real replay of the same file after a minute still searches)
MARK7 = '# BN guard v7'
V6_RET = "                return\n"
AUTOSUB7 = [("_bn_file = ''\n", "_bn_file = ''\n_bn_done = ('', 0.0)   %s: the last video handled + when\n" % MARK7),
            ("            if not _bn_file:   %s: nothing plays any more / Kodi quits\n" % MARK6 + V6_RET,
             "            if not _bn_file:   %s: nothing plays any more / Kodi quits\n" % MARK6 + V6_RET +
             "            global _bn_done\n"
             "            if _bn_done[0] == _bn_file and time.time() - _bn_done[1] < 60:\n"
             "                return\n"
             "            _bn_done = (_bn_file, time.time())\n")]
GENERAL6 = [('_BN_MON = xbmc.Monitor()', '_BN_PLAYER = xbmc.Player()   %s: one Player per process\n_BN_MON = xbmc.Monitor()' % MARK6),
            ('xbmc.Player()', '_BN_PLAYER')]



def apply(addon_dir):
    """All_Subs: 1 when a file was changed, 0 when the guards were already there; raises if it changed shape"""
    path = os.path.join(addon_dir, 'autosub.py')
    mods = os.path.join(addon_dir, 'resources', 'modules')
    n = _patch(path, MARK, EDITS) | _patch(path, MARK5, EDITS5) | _patch(path, MARK6, AUTOSUB6) | _patch(path, MARK7, AUTOSUB7) | \
        _patch(os.path.join(mods, 'general.py'), MARK5, GENERAL5) | _patch(os.path.join(mods, 'engine.py'), MARK5, ENGINE5)
    # general.py first: _BN_PLAYER must exist there before the others import it (replace-all runs after the anchor edit,
    # so general's own new line keeps its xbmc.Player())
    g = os.path.join(mods, 'general.py')
    n |= _patch(g, MARK6, GENERAL6[:1])
    with open(g, encoding='utf-8', newline='') as f:
        s = f.read()
    head, sep, rest = s.partition('_BN_MON = xbmc.Monitor()')
    if 'xbmc.Player()' in rest:
        with open(g, 'w', encoding='utf-8', newline='') as f:
            f.write(head + sep + rest.replace('xbmc.Player()', '_BN_PLAYER'))
        n = 1
    for rel in (('resources', 'modules', 'engine.py'), ('resources', 'modules', 'sub_window.py'),
                ('resources', 'sources', 'bsplayer.py')):
        p = os.path.join(addon_dir, *rel)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8', newline='') as f:
            s = f.read()
        if MARK6 in s:
            continue
        crlf = '\r\n' in s
        lines = s.replace('\r\n', '\n').split('\n')
        at = next(i for i, l in enumerate(lines) if l.startswith(('import ', 'from ')) and '__future__' not in l)
        lines.insert(at + 1, SHARED.rstrip('\n'))
        s = '\n'.join(lines[:at + 2]) + '\n' + '\n'.join(lines[at + 2:]).replace('xbmc.Player()', '_BN_PLAYER')
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(s.replace('\n', '\r\n') if crlf else s)
        n = 1
    return n


def apply_plus(addon_dir):
    """All Subs Plus: its main loop ends when Kodi quits"""
    return _patch(os.path.join(addon_dir, 'autosub.py'), PLUS_MARK, [(PLUS_OLD, PLUS_NEW)])
