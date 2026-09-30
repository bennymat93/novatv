# -*- coding: utf-8 -*-
"""Bottom news + weather ticker.

Kodi's own RSS control shows it (skin: control type="rss", RssFeeds.xml set 1). That control swaps in new text only
when a scroll lap ends and keeps the last good text when a fetch fails, which is exactly "refresh between cycles,
never mid-scroll". Kodi reads RSS over http only, so the service serves one combined feed at
http://127.0.0.1:PORT/ticker.rss: Israeli news flashes (ynet, fallback Walla) + current weather and a 3-day forecast
(Open-Meteo, no key; city from the add-on setting, default Be'er Sheva). Sources are fetched every REFRESH seconds;
a failed fetch keeps the previous items, so the ticker never goes empty or shows an error.
The text building (items / weather_line / rss) is plain Python for unit tests.
"""
import threading
import time
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

PORT = 51153
REFRESH = 600
NEWS = ['https://www.ynet.co.il/Integration/StoryRss1854.xml',       # ynet flashes
        'https://rss.walla.co.il/feed/22']                             # Walla breaking news (fallback)
MAX_NEWS = 12
SEP = '   •   '

# WMO weather codes -> (he, en)
WMO = {0: ('בהיר', 'clear'), 1: ('בהיר ברובו', 'mainly clear'), 2: ('מעונן חלקית', 'partly cloudy'),
       3: ('מעונן', 'overcast'), 45: ('ערפל', 'fog'), 48: ('ערפל', 'fog'), 51: ('טפטוף', 'drizzle'),
       53: ('טפטוף', 'drizzle'), 55: ('טפטוף', 'drizzle'), 61: ('גשם קל', 'light rain'), 63: ('גשם', 'rain'),
       65: ('גשם חזק', 'heavy rain'), 71: ('שלג', 'snow'), 80: ('ממטרים', 'showers'), 81: ('ממטרים', 'showers'),
       82: ('ממטרים חזקים', 'heavy showers'), 95: ('סופת רעמים', 'thunderstorm'), 96: ('סופת רעמים', 'thunderstorm'),
       99: ('סופת רעמים', 'thunderstorm')}
DAYS = {'he': ('שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון'),
        'en': ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')}


# ------------------------------------------------------------ pure
def items(xml_text, limit=MAX_NEWS):
    """RSS text -> headline titles (newest first as the feed lists them), duplicates and empties removed"""
    out = []
    for it in ET.fromstring(xml_text.encode('utf-8') if isinstance(xml_text, str) else xml_text).iter('item'):
        t = ' '.join((it.findtext('title') or '').split())
        if t and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def weather_line(data, city, lang='he'):
    """Open-Meteo forecast JSON -> 'באר שבע 25° מעונן חלקית · חמישי 31°/19° · ...'"""
    import datetime
    k = 0 if lang == 'he' else 1
    cur = data['current']
    parts = ['%s %d° %s' % (city, round(cur['temperature_2m']), WMO.get(cur['weather_code'], ('', ''))[k])]
    d = data['daily']
    for i, day in enumerate(d['time'][1:4], 1):
        wd = DAYS['he' if lang == 'he' else 'en'][datetime.date.fromisoformat(day).weekday()]
        parts.append('%s %d°/%d° %s' % (wd, round(d['temperature_2m_max'][i]), round(d['temperature_2m_min'][i]),
                                        WMO.get(d['weather_code'][i], ('', ''))[k]))
    return ' · '.join(p.strip() for p in parts)


def rss(weather, news):
    """one feed; weather first, then the headlines"""
    entries = ([weather] if weather else []) + list(news)
    body = ''.join('<item><title>%s</title></item>' % escape(e) for e in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>BN</title>%s</channel></rss>'
            % body).encode('utf-8')


# ------------------------------------------------------------ service
class Ticker(object):
    def __init__(self, city='באר שבע', lang='he'):
        self.city, self.lang = city, lang
        self.news, self.weather = [], ''
        self._geo = None
        self.server = None

    def _get(self, url, **kw):
        import requests
        return requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, **kw)

    def _coords(self):
        if self._geo is None or self._geo[0] != self.city:
            r = self._get('https://geocoding-api.open-meteo.com/v1/search',
                          params={'name': self.city, 'count': 1, 'language': self.lang}).json()
            g = (r.get('results') or [None])[0]
            if not g:
                raise ValueError('city not found: %s' % self.city)
            self._geo = (self.city, g['latitude'], g['longitude'])
        return self._geo[1], self._geo[2]

    def refresh(self):
        """one fetch round; any failure keeps the previous text"""
        for u in NEWS:
            try:
                got = items(self._get(u).content)
                if got:
                    self.news = got
                    break
            except Exception:
                continue
        try:
            lat, lon = self._coords()
            data = self._get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat, 'longitude': lon, 'current': 'temperature_2m,weather_code',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min', 'timezone': 'Asia/Jerusalem',
                'forecast_days': 4}).json()
            self.weather = weather_line(data, self.city, self.lang)
        except Exception:
            pass

    def feed(self):
        return rss(self.weather, self.news)

    def serve(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        me = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                body = me.feed()
                self.send_response(200)
                self.send_header('Content-Type', 'application/rss+xml; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', PORT), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


def run(monitor, enabled, city, lang):
    """service loop: serve while the ticker is on, refresh every REFRESH s; returns when Kodi quits"""
    t = None
    while not monitor.abortRequested():
        if enabled():
            if t is None:
                t = Ticker(city(), lang())
                try:
                    t.serve()
                except OSError:
                    t = None              # port busy (a second service copy): try again next round
            if t is not None:
                t.city, t.lang = city(), lang()
                first = not t.news and not t.weather
                t.refresh()
                if first and (t.news or t.weather):
                    # Kodi asked for the feed before the service was up and waits a whole interval: reload now
                    import xbmc
                    xbmc.executebuiltin('RefreshRSS')
        elif t is not None:
            t.stop()
            t = None
        if monitor.waitForAbort(REFRESH if t is not None else 30):
            break
    if t is not None:
        t.stop()
