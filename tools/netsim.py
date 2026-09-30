# -*- coding: utf-8 -*-
"""Weak-network simulator for playback tests (no admin rights, no drivers): an HTTP/HTTPS forward proxy that
shapes every connection through it.

  --mbps     total bandwidth (token bucket shared by all connections)
  --latency  added delay per request / per read in ms, --jitter +- ms
  --drop     probability per second that a connection is cut (a lossy link seen from the player: stalls + reconnects)

Kodi uses it through its own proxy settings (network.usehttpproxy / httpproxyserver / httpproxyport), which
tools/test_suite.py t_weak_network sets and clears. HTTPS goes through CONNECT tunnels (shaped the same way).

    python tools/netsim.py --port 8899 --mbps 3 --latency 80 --jitter 40 --drop 0.01
"""
import argparse
import random
import select
import socket
import socketserver
import threading
import time


class Bucket(object):
    def __init__(self, mbps):
        self.rate = mbps * 1e6 / 8          # bytes per second
        self.tokens, self.last = self.rate / 4, time.time()
        self.lock = threading.Lock()

    def take(self, n):
        while True:
            with self.lock:
                now = time.time()
                self.tokens = min(self.rate / 2, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                need = (n - self.tokens) / self.rate
            time.sleep(min(0.2, need))


class Shaper(object):
    def __init__(self, mbps, latency, jitter, drop):
        self.bucket = Bucket(mbps)
        self.latency, self.jitter, self.drop = latency / 1000.0, jitter / 1000.0, drop
        self.bytes = 0

    def delay(self):
        time.sleep(max(0.0, self.latency + random.uniform(-self.jitter, self.jitter)))

    def pipe(self, a, b):
        """copy both ways until either side closes; downstream (b -> a) is shaped"""
        last_drop = time.time()
        socks = [a, b]
        while True:
            r, _, _ = select.select(socks, [], [], 1.0)
            now = time.time()
            if self.drop and now - last_drop >= 1.0:
                last_drop = now
                if random.random() < self.drop:
                    return                     # the link "dropped": the player must reconnect
            for s in r:
                data = s.recv(16384)
                if not data:
                    return
                if s is b:
                    self.bucket.take(len(data))
                    self.bytes += len(data)
                    if random.random() < 0.02:
                        self.delay()           # occasional latency spikes on the way down
                    a.sendall(data)
                else:
                    b.sendall(data)


def make_handler(shaper):
    class H(socketserver.BaseRequestHandler):
        def handle(self):
            c = self.request
            head = b''
            while b'\r\n\r\n' not in head:
                chunk = c.recv(4096)
                if not chunk:
                    return
                head += chunk
            line = head.split(b'\r\n', 1)[0].decode('latin-1')
            method, target, _ = line.split(' ', 2)
            shaper.delay()
            try:
                if method == 'CONNECT':
                    host, port = target.rsplit(':', 1)
                    up = socket.create_connection((host, int(port)), timeout=15)
                    c.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    rest = head.split(b'\r\n\r\n', 1)[1]
                    if rest:
                        up.sendall(rest)
                else:
                    # absolute-form http://host:port/path -> origin-form to the host
                    rest = target.split('://', 1)[1]
                    hostport, _, path = rest.partition('/')
                    host, _, port = hostport.partition(':')
                    up = socket.create_connection((host, int(port or 80)), timeout=15)
                    first, others = head.split(b'\r\n', 1)
                    up.sendall(('%s /%s HTTP/1.1\r\n' % (method, path)).encode('latin-1') + others)
                shaper.pipe(c, up)
            except Exception:
                pass
            finally:
                try:
                    up.close()
                except Exception:
                    pass
    return H


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start(port, mbps, latency=0, jitter=0, drop=0.0):
    """run in a background thread; returns (server, shaper) - server.shutdown() to stop"""
    shaper = Shaper(mbps, latency, jitter, drop)
    srv = Server(('127.0.0.1', port), make_handler(shaper))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, shaper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8899)
    ap.add_argument('--mbps', type=float, default=3)
    ap.add_argument('--latency', type=float, default=80)
    ap.add_argument('--jitter', type=float, default=40)
    ap.add_argument('--drop', type=float, default=0.0)
    a = ap.parse_args()
    srv, sh = start(a.port, a.mbps, a.latency, a.jitter, a.drop)
    print('netsim on 127.0.0.1:%d  %.1f Mbps  %d+-%d ms  drop %.3f/s' % (a.port, a.mbps, a.latency, a.jitter, a.drop))
    try:
        while True:
            time.sleep(5)
            print('%.1f MB through' % (sh.bytes / 1e6), flush=True)
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == '__main__':
    main()
