# -*- coding: utf-8 -*-
"""Find the PC subtitle server: the saved address, else the home network (UDP 'NOVASUBS?' on port 8766),
else its Tailscale address (setting sub_server_remote) - works outside home on devices in the same tailnet."""
from .common import ADDON, log


def discover_server():
    """Find the PC subtitle server on the LAN (UDP broadcast) if the saved address is dead."""
    import socket
    import requests
    base = ADDON.getSetting('sub_server').rstrip('/')
    try:
        requests.get(base + '/health', timeout=2)
        return
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(2)
    try:
        if _discover_loop(s):
            return
    except OSError as e:
        log('subtitle server discovery: %s' % e)
    finally:
        s.close()
    remote = ADDON.getSetting('sub_server_remote').rstrip('/')
    if remote and remote != base:
        try:
            requests.get(remote + '/health', timeout=4)
            ADDON.setSetting('sub_server', remote)
            log('subtitle server reached outside home at %s' % remote)
        except Exception as e:
            log('subtitle server not reachable (home or %s): %s' % (remote, e))


def _discover_loop(s):
    for _ in range(3):
        s.sendto(b'NOVASUBS?', ('255.255.255.255', 8766))
        try:
            data, addr = s.recvfrom(64)
        except OSError:              # socket.timeout included: no server answered this round
            continue
        if data.startswith(b'NOVASUBS '):
            url = 'http://%s:%s' % (addr[0], data.split()[1].decode())
            ADDON.setSetting('sub_server', url)
            log('subtitle server discovered at %s' % url)
            return True
    return False
