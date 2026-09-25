# -*- coding: utf-8 -*-
"""Find the PC subtitle server on the home network (answers UDP 'NOVASUBS?' on port 8766)."""
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
        _discover_loop(s)
    except OSError as e:
        log('subtitle server discovery: %s' % e)
    finally:
        s.close()


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
            return
