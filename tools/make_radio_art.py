# -*- coding: utf-8 -*-
"""Radio station posters in the same 3D style as the Israeli TV channels (tools/make_channel_art.py poster()).

Stations: Israel + Hebrew-language stations from radio-browser (what the "רדיו ישראל" row and the radio menu show).
A station without a usable logo gets a clean text logo (its initials in BN gold) on the same card, so every tile in
the row looks the same. Output: addons/plugin.video.nova/resources/media/radio/<slug>.jpg + index.json
(slug of the name -> file); radio.py uses it and falls back to the favicon for stations not in the index.

    python tools/make_radio_art.py [--only "Galgalatz,Kan Bet"]
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_channel_art as art                                   # noqa: E402

ROOT = art.ROOT
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'media', 'radio')
API = 'https://de1.api.radio-browser.info/json/stations/'
PATHS = ['bycountrycodeexact/IL', 'bylanguageexact/hebrew']


def stations():
    import requests
    out = {}
    for p in PATHS:
        data = requests.get(API + p, params={'hidebroken': 'true', 'order': 'votes', 'reverse': 'true', 'limit': 300},
                            headers={'User-Agent': 'BNStreamArtwork/1.0'}, timeout=30).json()
        for s in data:
            name = ' '.join((s.get('name') or '').split())
            key = art.slug(name)
            if key and key not in out:
                out[key] = (name, s.get('favicon') or '')
    return out


def text_logo(name):
    """a clean logo for stations without one: the FM frequency when the name has it ("101.5 FM"), else the short
    name (first word or two), in BN gold; Hebrew in visual order"""
    import re
    m = re.search(r'(\d{2,3}(?:[.,]\d)?)\s*(?:fm|FM|Fm|אף אם)?', name)
    lines = ([m.group(1).replace(',', '.'), 'FM'] if m and 87 <= float(m.group(1).replace(',', '.')) <= 108
             else [' '.join(re.sub(r'[^\w\s֐-׿]', ' ', name).split()[:2])[:14] or name[:10]])
    img = Image.new('RGBA', (600, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sizes = [210, 120] if len(lines) == 2 else [150 if len(lines[0]) <= 7 else 100]
    y = 300 - sum(s * 1.15 for s in sizes) / 2
    for txt, size in zip(lines, sizes):
        f = art._font(size)
        txt = art.visual(txt)
        while d.textlength(txt, font=f) > 560 and size > 50:
            size -= 10
            f = art._font(size)
        d.text(((600 - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=art.GOLD + (255,))
        y += size * 1.15
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    only = {art.slug(x) for x in a.only.split(',') if x.strip()}
    done = plain = 0
    for key, (name, logo_url) in sorted(stations().items()):
        if only and key not in only:
            continue
        logo = None
        if logo_url:
            try:
                logo = art.fetch_logo(logo_url)
                if min(logo.size) < 32:                      # a tiny favicon upscales to mush: text logo instead
                    logo = None
            except Exception:
                logo = None
        if logo is None:
            logo, plain = text_logo(name), plain + 1
        try:
            img = art.poster(logo, name)
        except Exception as e:
            print('skip %s: %s' % (name, e))
            continue
        fn = key + '.jpg'
        img.save(os.path.join(OUT, fn), 'JPEG', quality=82, optimize=True, progressive=True)
        index[key] = fn
        done += 1
    json.dump(index, open(idx_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)
    print('radio posters: %d (%d with a text logo)' % (done, plain))


if __name__ == '__main__':
    main()
