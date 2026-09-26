# -*- coding: utf-8 -*-
"""YouTube plays through a small local HTTP server (setting kodion.http.port, default 50152).

Windows reserves port ranges for Hyper-V / WSL (netsh int ipv4 show excludedportrange protocol=tcp), often
49700-50800: then the port cannot be opened ("WinError 10013") and no YouTube video plays. Pick a usable port.
"""
import socket

import xbmcaddon

from .common import log

YT = 'plugin.video.youtube'
CANDIDATES = (51152, 51252, 52152, 53152, 54152, 55152, 56152)


def usable(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', int(port)))
        return True
    except OSError as e:
        # in use by YouTube itself is fine; blocked by Windows (10013 / EACCES) is not
        return getattr(e, 'winerror', None) == 10048 or e.errno in (98, 48)
    finally:
        s.close()


def check(fix=True):
    """(ok, detail). With fix=True a blocked port is replaced by a usable one."""
    try:
        addon = xbmcaddon.Addon(YT)
    except Exception:
        return None, 'not installed'
    port = addon.getSetting('kodion.http.port') or '50152'
    if usable(port):
        return True, 'port %s' % port
    if not fix:
        return False, 'port %s blocked by Windows' % port
    for p in CANDIDATES:
        if usable(p):
            addon.setSetting('kodion.http.port', str(p))
            log('YouTube port %s is blocked by Windows - moved to %d' % (port, p))
            return True, 'port %s blocked -> %d' % (port, p)
    return False, 'no usable port found'
