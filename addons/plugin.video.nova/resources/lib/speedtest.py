# -*- coding: utf-8 -*-
"""Help > Speed test: live internet check (latency, jitter, download, upload) against Cloudflare's speed test
endpoints (speed.cloudflare.com, no key), shown live in a progress dialog, then a verdict per use:
HD / Full HD / 4K streaming and live TV. The maths (mbps / verdict / jitter) is plain Python for unit tests."""
import time

DOWN = 'https://speed.cloudflare.com/__down?bytes=%d'
UP = 'https://speed.cloudflare.com/__up'
STR = {
    'title': ('בדיקת מהירות', 'Speed test'), 'ping': ('זמן תגובה', 'Latency'), 'jitter': ('ג׳יטר', 'Jitter'),
    'down': ('הורדה', 'Download'), 'up': ('העלאה', 'Upload'), 'ms': ('מ"ש', 'ms'), 'mbps': ('Mbps', 'Mbps'),
    'fail': ('אין חיבור לאינטרנט או שהבדיקה נכשלה', 'No internet connection or the test failed'),
    'ok': ('מתאים', 'good'), 'no': ('לא מספיק', 'not enough'), 'weak': ('גבולי', 'borderline'),
    'sd': ('צפייה ב-SD / רדיו', 'SD video / radio'), 'hd': ('צפייה ב-HD (720p)', 'HD video (720p)'),
    'fhd': ('צפייה ב-Full HD (1080p)', 'Full HD (1080p)'), 'uhd': ('צפייה ב-4K', '4K video'),
    'live': ('טלוויזיה חיה', 'Live TV'), 'measuring': ('בודק...', 'Measuring...'), 'result': ('תוצאה', 'Result'),
}
# Mbps a stream of that kind needs to play without stalls (with headroom for adaptive / debrid streams)
NEEDS = (('sd', 3), ('hd', 6), ('fhd', 12), ('uhd', 30), ('live', 8))


def mbps(nbytes, secs):
    return (nbytes * 8 / 1e6) / secs if secs > 0 else 0.0


def jitter(samples):
    """mean absolute difference between consecutive latency samples (RFC 3550 style)"""
    if len(samples) < 2:
        return 0.0
    return sum(abs(a - b) for a, b in zip(samples[1:], samples)) / (len(samples) - 1)


def verdict(down, ping_ms):
    """[(use, 'ok'|'weak'|'no')]; high latency makes live TV borderline"""
    out = []
    for key, need in NEEDS:
        v = 'ok' if down >= need * 1.25 else ('weak' if down >= need else 'no')
        if key == 'live' and v == 'ok' and ping_ms > 150:
            v = 'weak'
        out.append((key, v))
    return out


class Test(object):
    def __init__(self, on_update=None, cancelled=lambda: False, seconds=8):
        import requests
        self.s = requests.Session()
        self.s.headers['User-Agent'] = 'BNStream-speedtest/1.0'
        self.on_update, self.cancelled, self.seconds = on_update or (lambda *a: None), cancelled, seconds
        self.res = {'ping': None, 'jitter': None, 'down': None, 'up': None}

    def latency(self, n=8):
        samples = []
        for _ in range(n):
            t = time.time()
            self.s.get(DOWN % 0, timeout=5)
            samples.append((time.time() - t) * 1000)
            if self.cancelled():
                break
        samples = sorted(samples)[:max(1, len(samples) - 2)]      # drop the slowest (DNS / TLS warm-up)
        self.res['ping'], self.res['jitter'] = min(samples), jitter(samples)
        self.on_update('ping', self.res)

    def download(self):
        """repeated 25 MB bodies (the endpoint refuses more than 50 MB per request) for self.seconds, reporting the
        live rate every half second"""
        got, start, last = 0, time.time(), time.time()
        while time.time() - start < self.seconds and not self.cancelled():
            r = self.s.get(DOWN % 25000000, stream=True, timeout=10)
            r.raise_for_status()
            for chunk in r.iter_content(65536):
                got += len(chunk)
                now = time.time()
                if now - last >= 0.5:
                    self.res['down'] = mbps(got, now - start)
                    self.on_update('down', self.res)
                    last = now
                if now - start >= self.seconds or self.cancelled():
                    break
            r.close()
        self.res['down'] = mbps(got, time.time() - start)
        self.on_update('down', self.res)

    def upload(self):
        size, sent, start = 2000000, 0, time.time()
        blob = b'0' * size
        while time.time() - start < self.seconds / 2 and not self.cancelled():
            self.s.post(UP, data=blob, timeout=20)
            sent += size
            self.res['up'] = mbps(sent, time.time() - start)
            self.on_update('up', self.res)

    def run(self):
        self.latency()
        if not self.cancelled():
            self.download()
        if not self.cancelled():
            self.upload()
        return self.res


# ------------------------------------------------------------ Kodi
def _s(k, lang):
    return STR[k][0 if lang == 'he' else 1]


def lines(res, lang):
    f = lambda v, fmt: fmt % v if v is not None else '—'
    return ['%s: %s %s   ·   %s: %s %s' % (_s('ping', lang), f(res['ping'], '%.0f'), _s('ms', lang),
                                            _s('jitter', lang), f(res['jitter'], '%.0f'), _s('ms', lang)),
            '%s: [B]%s[/B] %s   ·   %s: %s %s' % (_s('down', lang), f(res['down'], '%.1f'), _s('mbps', lang),
                                                  _s('up', lang), f(res['up'], '%.1f'), _s('mbps', lang))]


def run_dialog():
    import xbmcgui
    from .common import ui_lang, log
    lang = 'he' if ui_lang() == 'he' else 'en'
    pd = xbmcgui.DialogProgress()
    pd.create(_s('title', lang), _s('measuring', lang))
    stage = {'ping': 10, 'down': 20, 'up': 75}
    t0 = time.time()

    def upd(step, res):
        pct = stage[step] + int(min(1.0, (time.time() - t0) / 20.0) * 20) if step != 'ping' else 15
        pd.update(min(99, pct), '\n'.join(lines(res, lang)))
    try:
        res = Test(upd, pd.iscanceled).run()
    except Exception as e:
        log('speed test: %s' % e)
        pd.close()
        return xbmcgui.Dialog().ok(_s('title', lang), _s('fail', lang))
    pd.close()
    col = {'ok': 'limegreen', 'weak': 'orange', 'no': 'red'}
    body = lines(res, lang) + [''] + ['[COLOR %s]●[/COLOR]  %s: %s' % (col[v], _s(k, lang), _s(v, lang))
                                     for k, v in verdict(res['down'] or 0, res['ping'] or 0)]
    xbmcgui.Dialog().textviewer('%s – %s' % (_s('title', lang), _s('result', lang)), '\n'.join(body))
