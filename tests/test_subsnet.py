"""subsnet.discover_server: saved address -> home network -> Tailscale address"""
import sys
import types

from resources.lib import subsnet


class FakeAddon:
    def __init__(self, **kv):
        self.kv = kv

    def getSetting(self, k):
        return self.kv.get(k, '')

    def setSetting(self, k, v):
        self.kv[k] = v


def _requests(alive):
    def get(url, timeout=0):
        if not any(url.startswith(a) for a in alive):
            raise OSError('down: ' + url)
    return types.SimpleNamespace(get=get)


def _run(monkeypatch, addon, alive, lan):
    monkeypatch.setattr(subsnet, 'ADDON', addon)
    monkeypatch.setitem(sys.modules, 'requests', _requests(alive))
    monkeypatch.setattr(subsnet, '_discover_loop', lambda s: lan)
    subsnet.discover_server()
    return addon.getSetting('sub_server')


def test_saved_address_alive_kept(monkeypatch):
    a = FakeAddon(sub_server='http://192.168.1.5:8765', sub_server_remote='http://100.1.1.1:8765')
    assert _run(monkeypatch, a, ['http://192.168.1.5'], lan=False) == 'http://192.168.1.5:8765'


def test_outside_home_uses_tailscale(monkeypatch):
    a = FakeAddon(sub_server='http://192.168.1.5:8765', sub_server_remote='http://100.1.1.1:8765')
    assert _run(monkeypatch, a, ['http://100.1.1.1'], lan=False) == 'http://100.1.1.1:8765'


def test_home_network_wins_over_tailscale(monkeypatch):
    a = FakeAddon(sub_server='http://dead:8765', sub_server_remote='http://100.1.1.1:8765')
    assert _run(monkeypatch, a, ['http://100.1.1.1'], lan=True) == 'http://dead:8765'   # LAN loop sets it itself


def test_nothing_reachable_keeps_setting(monkeypatch):
    a = FakeAddon(sub_server='http://dead:8765', sub_server_remote='http://100.1.1.1:8765')
    assert _run(monkeypatch, a, [], lan=False) == 'http://dead:8765'
