# -*- coding: utf-8 -*-
"""Player controls shared by the service (zero-state) and the player panels. Verified on Kodi 21 (2026-09-27):
InfoLabels Player.SubtitleDelay / Player.AudioDelay ('0.300 s'), Player.PlaySpeed ('1.00'); actions SubtitleDelayPlus/Minus
move 0.1 s, AudioDelayPlus/Minus 0.025 s; JSON-RPC Player.GetViewMode / Player.SetViewMode {viewmode} (no playerid).
"""
import json

import xbmc

from . import syncmath


def rpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception:
        return {}


def action(name, times=1):
    for _ in range(int(times)):
        xbmc.executebuiltin('Action(%s)' % name)
        xbmc.sleep(15)


def sub_delay():
    return syncmath.parse_delay(xbmc.getInfoLabel('Player.SubtitleDelay'))


def audio_delay():
    return syncmath.parse_delay(xbmc.getInfoLabel('Player.AudioDelay'))


def set_sub_delay(target):
    d, n = syncmath.steps(sub_delay(), target, syncmath.SUB_STEP)
    if d:
        action('SubtitleDelayPlus' if d == 'plus' else 'SubtitleDelayMinus', n)
    return sub_delay()


def set_audio_delay(target):
    d, n = syncmath.steps(audio_delay(), target, syncmath.AUDIO_STEP)
    if d:
        action('AudioDelayPlus' if d == 'plus' else 'AudioDelayMinus', n)
    return audio_delay()


def speed():
    try:
        return float(xbmc.getInfoLabel('Player.PlaySpeed') or 1)
    except ValueError:
        return 1.0


def set_speed(target):
    """tempo in 0.1 steps (needs Player.TempoEnabled)"""
    for _ in range(40):
        s = speed()
        if abs(s - target) < 0.05 or not xbmc.getCondVisibility('Player.TempoEnabled'):
            break
        xbmc.executebuiltin('PlayerControl(%s)' % ('TempoUp' if s < target else 'TempoDown'))
        xbmc.sleep(60)
    return speed()


def view_mode():
    return (rpc('Player.GetViewMode').get('result') or {})


def reset_view():
    vm = view_mode()
    if vm and (vm.get('viewmode') != 'normal' or abs(float(vm.get('zoom', 1)) - 1) > 0.01):
        rpc('Player.SetViewMode', viewmode='normal')


def state():
    """what the player currently carries (for the session log line and the tests)"""
    vm = view_mode()
    return {'file': xbmc.getInfoLabel('Player.FilenameAndPath')[:120],
            'subtitles_on': bool(xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled')),
            'subtitle': xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage'),
            'sub_delay': sub_delay(), 'audio_delay': audio_delay(), 'speed': speed(),
            'viewmode': vm.get('viewmode'), 'zoom': vm.get('zoom'), 'time': xbmc.getInfoLabel('Player.Time')}
