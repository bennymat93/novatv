# -*- coding: utf-8 -*-
"""Guards for the third-party subtitle services All_Subs and All Subs Plus.

Found by the 0.2.2 deep tests:
  * All_Subs' automatic search keeps running after the video changed or Kodi was asked to quit, then places the
    subtitle it found into whatever plays now (a subtitle of the previous video / another title) and holds Kodi's
    exit. Guards: remember the video of the search (Player.OnPlay), place a subtitle only while that same video
    plays, leave the wait loops as soon as Kodi quits.
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


def apply(addon_dir):
    """All_Subs: 1 when autosub.py was changed, 0 when the guards were already there; raises if it changed shape"""
    return _patch(os.path.join(addon_dir, 'autosub.py'), MARK, EDITS)


def apply_plus(addon_dir):
    """All Subs Plus: its main loop ends when Kodi quits"""
    return _patch(os.path.join(addon_dir, 'autosub.py'), PLUS_MARK, [(PLUS_OLD, PLUS_NEW)])
