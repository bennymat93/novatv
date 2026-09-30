# -*- coding: utf-8 -*-
"""news + weather ticker: RSS parsing, weather line, combined feed"""
import xml.etree.ElementTree as ET

from resources.lib import ticker

FEED = ('<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>x</title>'
        '<item><title><![CDATA[ כותרת   ראשונה ]]></title></item><item><title>כותרת ראשונה</title></item>'
        '<item><title></title></item><item><title>שנייה &amp; עוד</title></item></channel></rss>')

WX = {'current': {'temperature_2m': 24.6, 'weather_code': 2},
      'daily': {'time': ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'],
                'temperature_2m_max': [30, 31.4, 29, 28], 'temperature_2m_min': [18, 19.2, 17, 16],
                'weather_code': [0, 0, 61, 3]}}


def test_items_clean_and_deduped():
    assert ticker.items(FEED) == ['כותרת ראשונה', 'שנייה & עוד']


def test_items_limit():
    assert len(ticker.items(FEED, limit=1)) == 1


def test_weather_line_hebrew():
    line = ticker.weather_line(WX, 'באר שבע', 'he')
    assert line.startswith('באר שבע 25° מעונן חלקית')
    assert 'חמישי 31°/19° בהיר' in line and 'שישי 29°/17° גשם קל' in line


def test_weather_line_english():
    assert 'Thu 31°/19° clear' in ticker.weather_line(WX, "Be'er Sheva", 'en')


def test_feed_weather_first_and_escaped():
    root = ET.fromstring(ticker.rss('מזג', ['a & b', '<c>']))
    assert [i.findtext('title') for i in root.iter('item')] == ['מזג', 'a & b', '<c>']


def test_failed_fetch_keeps_last_text(monkeypatch):
    t = ticker.Ticker()
    t.news, t.weather = ['old'], 'w'

    def boom(*a, **k):
        raise OSError('offline')
    monkeypatch.setattr(t, '_get', boom)
    t.refresh()
    assert t.news == ['old'] and t.weather == 'w'
