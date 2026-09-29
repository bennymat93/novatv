# -*- coding: utf-8 -*-
"""Country tiles for "Channels of the world" (TV & Radio): the country's flag (flagcdn.com, exact official artwork)
on the BN card, with a soft wave light for depth, a glass highlight and a shadow. Countries = those with at least
MIN channels in the free lists NovaTV merges (Israel has its own row).
    python tools/make_flag_art.py
-> addons/plugin.video.nova/resources/media/flags/<cc>.png + countries.json {cc: [he, en, ru]}
"""
import io
import json
import math
import os
import re
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_category_art import card, S          # the same card as the category tiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'media', 'flags')
MIN = 3
ALIAS = {'UK': 'GB'}


def free_lists():
    src = open(os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'lib', 'iptv.py'), encoding='utf-8').read()
    return re.findall(r"\('iptv-org [^']+', '(https://[^']+\.m3u)'\)", src)


def countries():
    import requests
    n = Counter()
    for url in free_lists():
        for line in requests.get(url, timeout=60).text.splitlines():
            if line.startswith('#EXTINF'):
                m = re.search(r'tvg-country="([^"]+)"', line) or re.search(r'tvg-id="[^"]*\.([a-z]{2})(?:@[^"]*)?"', line)
                if m:
                    cc = ALIAS.get(m.group(1).upper(), m.group(1).upper())
                    n[cc] += 1
    return {cc: k for cc, k in n.items() if k >= MIN and cc != 'IL' and len(cc) == 2}


def flag_tile(flag):
    img = card()
    fw = 330
    fh = int(fw * flag.height / flag.width)
    if fh > 250:
        fh, fw = 250, int(250 * flag.width / flag.height)
    f = flag.convert('RGB').resize((fw, fh), Image.LANCZOS)
    # wave light: bands of light and shade across the cloth -> depth, the design itself unchanged
    shade = Image.new('L', (fw, fh))
    sd = ImageDraw.Draw(shade)
    for x in range(fw):
        v = 128 + int(34 * math.sin(x / fw * math.pi * 2.2 + 0.6))
        sd.line((x, 0, x, fh), fill=v)
    light = Image.new('RGB', (fw, fh), (255, 255, 255))
    dark = Image.new('RGB', (fw, fh), (0, 0, 0))
    lit = Image.composite(light, f, shade.point(lambda v: max(0, v - 128) * 2))          # highlights
    f = Image.composite(dark, lit, shade.point(lambda v: max(0, 128 - v) * 2))           # shadows
    # rounded corners
    mask = Image.new('L', (fw, fh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fw - 1, fh - 1), 18, fill=255)
    x, y = (S - 8 - fw) // 2, (S - 8 - fh) // 2
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x + 8, y + 16, x + fw + 8, y + fh + 16), 18, fill=(0, 0, 0, 190))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(12)))
    img.paste(f, (x, y), mask)
    gloss = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gm = Image.linear_gradient('L').resize((fw, fh // 2)).point(lambda v: int((255 - v) * 0.22))
    gl = Image.new('L', (fw, fh), 0)
    gl.paste(gm, (0, 0))
    gl = Image.composite(gl, Image.new('L', (fw, fh), 0), mask)
    gloss.paste((255, 255, 255, 255), (x, y), gl)
    img = Image.alpha_composite(img, gloss)
    ImageDraw.Draw(img).rounded_rectangle((x, y, x + fw, y + fh), 18, outline=(255, 255, 255, 60), width=2)
    return img


def main():
    import requests
    os.makedirs(OUT, exist_ok=True)
    names = {l: requests.get('https://flagcdn.com/%s/codes.json' % l, timeout=30).json() for l in ('he', 'en', 'ru')}
    found = countries()
    table = {}
    for cc in sorted(found, key=lambda c: -found[c]):
        low = cc.lower()
        if low not in names['en']:
            continue
        r = requests.get('https://flagcdn.com/w640/%s.png' % low, timeout=30)
        if r.status_code != 200:
            print('  no flag: %s' % cc, file=sys.stderr)
            continue
        flag_tile(Image.open(io.BytesIO(r.content))).save(os.path.join(OUT, '%s.png' % low), optimize=True)
        table[cc] = [names['he'][low], names['en'][low], names['ru'][low]]
    json.dump(table, open(os.path.join(OUT, 'countries.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('flags: %d countries' % len(table))


if __name__ == '__main__':
    main()
