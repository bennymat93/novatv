# -*- coding: utf-8 -*-
"""pytest setup: the add-on is importable as `resources.lib.*`; minimal Kodi module stubs for code that imports them."""
import os
import sys
import types

ADDON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addons', 'plugin.video.nova')
sys.path.insert(0, ADDON)


def _stub(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules.setdefault(name, m)
    return m


class _Monitor(object):
    def abortRequested(self):
        return False

    def waitForAbort(self, t=0):
        return False


class _Player(object):
    def __init__(self, *a, **k):
        pass


_stub('xbmc', LOGINFO=1, LOGWARNING=2, LOGERROR=3, log=lambda *a, **k: None, Monitor=_Monitor, Player=_Player,
      getInfoLabel=lambda l: '', getCondVisibility=lambda c: False, executebuiltin=lambda *a, **k: None,
      executeJSONRPC=lambda q: '{}', getLanguage=lambda *a: 'he', ISO_639_1=0, sleep=lambda ms: None)
_stub('xbmcgui', Window=lambda *a: types.SimpleNamespace(getProperty=lambda k: '', setProperty=lambda k, v: None,
                                                          clearProperty=lambda k: None),
      Dialog=lambda: None, ListItem=object, NOTIFICATION_INFO='info', NOTIFICATION_WARNING='w', NOTIFICATION_ERROR='e')
_stub('xbmcaddon', Addon=lambda *a: types.SimpleNamespace(getSetting=lambda k: '', setSetting=lambda k, v: None,
                                                          getSettingBool=lambda k: False,
                                                          getAddonInfo=lambda k: os.path.join(ADDON, '_profile')))
_stub('xbmcvfs', translatePath=lambda p: p)
_stub('xbmcplugin')
