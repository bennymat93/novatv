# -*- coding: utf-8 -*-
"""3D channel posters for the Israeli channels (BIG POSTER widget in TV & Radio).

For every channel of the free Israeli lists (iptv-org il + heb): download its logo, trim the margins, upscale
(Lanczos) and sharpen it, and place it on a 2:3 "3D card": dark glass panel with depth (drop shadow), a BN-gold
rim light, a top bevel highlight, the logo with its own soft shadow and a faded floor reflection, the channel
name underneath. Written to addons/plugin.video.nova/resources/media/channels/<slug>.jpg + index.json
(name -> file), so every device shows the same artwork with no work at run time.

    python tools/make_channel_art.py [--only "Kan 11,Keshet 12"]
Needs Pillow (build machine only).
"""
import argparse
import io
import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'media', 'channels')
LISTS = ['https://iptv-org.github.io/iptv/countries/il.m3u', 'https://iptv-org.github.io/iptv/languages/heb.m3u']
W, H = 600, 900                    # 2:3 poster
GOLD = (232, 190, 90)
FONTS = [r'C:\Windows\Fonts\segoeuib.ttf', r'C:\Windows\Fonts\arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def slug(name):
    """the channel's key: name without resolution / [Not 24/7] tags, lower case, only letters and digits"""
    name = re.sub(r'\s*\((?:\d{3,4}p|\d{3,4}i)\)|\s*\[[^\]]*\]', '', name or '')
    return re.sub(r'[^0-9a-z\u0590-\u05ff]+', '-', name.lower()).strip('-')


def clean_name(name):
    name = re.sub(r'\s*\((?:\d{3,4}p|\d{3,4}i)\)|\s*\[[^\]]*\]', '', name or '')
    return re.sub(r'\s*\(Israel\)', '', name).strip()


def channels():
    import requests
    seen = {}
    for url in LISTS:
        text = requests.get(url, timeout=30).text
        for line in text.splitlines():
            if line.startswith('#EXTINF'):
                name = line.rsplit(',', 1)[1].strip()
                m = re.search(r'tvg-logo="([^"]*)"', line)
                if m and m.group(1) and slug(name) not in seen:
                    seen[slug(name)] = (clean_name(name), m.group(1))
    return seen


def fetch_logo(url):
    import requests
    import time
    for wait in (0, 5, 15, 40):                 # Wikimedia answers 429 to bursts: wait and retry
        time.sleep(wait)
        r = requests.get(url, timeout=30, headers={'User-Agent': 'BNStreamArtwork/1.0 (build tool; github.com/bennymat93/novatv)'})
        if r.status_code != 429:
            break
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content))
    img.load()
    return img.convert('RGBA')


def trim(img):
    """cut transparent / flat-colour margins"""
    alpha = img.split()[-1]
    box = alpha.point(lambda a: 255 if a > 12 else 0).getbbox()
    if box and box != (0, 0) + img.size:
        return img.crop(box)
    bg = Image.new('RGBA', img.size, img.getpixel((0, 0)))
    box = ImageChops.difference(img, bg).convert('L').point(lambda v: 255 if v > 18 else 0).getbbox()
    return img.crop(box) if box else img


def enhance(img, max_w, max_h):
    """upscale to the target box (Lanczos, never down to blur) and sharpen"""
    img = trim(img)
    scale = min(max_w / img.width, max_h / img.height)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    # big upscales go in two steps: fewer ringing artefacts
    if scale > 3:
        mid = (img.width * 2, img.height * 2)
        img = img.resize(mid, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=2))
    img = img.resize(size, Image.LANCZOS)
    rgb, a = img.convert('RGB'), img.split()[-1]
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    out = rgb.convert('RGBA')
    out.putalpha(a)
    return out


def _dark(img):
    """mean brightness of the logo's visible pixels is low"""
    a = img.split()[-1].point(lambda v: 255 if v > 128 else 0)
    stat = ImageStat.Stat(img.convert('L'), a)
    return bool(stat.count[0]) and stat.mean[0] < 70


def _font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _rounded(size, radius):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return m


def visual(text):
    """Pillow draws characters left to right: Hebrew must be reordered for display (python-bidi)"""
    try:
        from bidi.algorithm import get_display
        return get_display(text)
    except ImportError:
        return text


def poster(logo, name):
    base = Image.new('RGB', (W, H), (8, 10, 16))
    # background: deep radial glow behind the card
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((-W * 0.3, H * 0.05, W * 1.3, H * 0.95), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    base = Image.composite(Image.new('RGB', (W, H), (34, 30, 22)), base, glow)

    cx, cy, cw, ch = 50, 90, W - 100, 560                 # the card
    # drop shadow: depth
    sh = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((cx + 10, cy + 26, cx + cw + 10, cy + ch + 34), 36, fill=200)
    base.paste((0, 0, 0), mask=sh.filter(ImageFilter.GaussianBlur(28)))
    # glass panel: vertical gradient
    card = Image.new('RGB', (cw, ch))
    grad = ImageDraw.Draw(card)
    for y in range(ch):
        t = y / ch
        grad.line((0, y, cw, y), fill=(int(46 - 26 * t), int(50 - 28 * t), int(62 - 34 * t)))
    mask = _rounded((cw, ch), 36)
    base.paste(card, (cx, cy), mask)
    # top bevel highlight + gold rim light
    over = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rounded_rectangle((cx, cy, cx + cw, cy + ch), 36, outline=GOLD + (190,), width=3)
    d.line((cx + 40, cy + 3, cx + cw - 40, cy + 3), fill=(255, 245, 220, 170), width=2)
    base = Image.alpha_composite(base.convert('RGBA'), over.filter(ImageFilter.GaussianBlur(0.6)))
    # glass sheen: a soft highlight fading down from the top edge (no hard band)
    sheen = Image.linear_gradient('L').resize((cw, int(ch * 0.5))).point(lambda v: int((255 - v) * 0.10))
    sheen_mask = Image.new('L', (cw, ch), 0)
    sheen_mask.paste(sheen, (0, 0))
    sheen_mask = ImageChops.multiply(sheen_mask, _rounded((cw, ch), 36))
    base.paste((255, 255, 255), (cx, cy), sheen_mask)

    # the logo: sharpened, its own soft shadow, centred
    lg = enhance(logo, cw - 90, ch - 170)
    lx, ly = cx + (cw - lg.width) // 2, cy + (ch - 80 - lg.height) // 2 + 10
    if _dark(lg):                     # a dark logo on the dark card: a soft light plate behind it
        pad = 34
        plate = Image.new('L', base.size, 0)
        ImageDraw.Draw(plate).rounded_rectangle((lx - pad, ly - pad, lx + lg.width + pad, ly + lg.height + pad), 28, fill=235)
        base.paste((240, 238, 232), mask=plate.filter(ImageFilter.GaussianBlur(6)))
    lsh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    lsh.paste((0, 0, 0, 170), (lx + 6, ly + 12), lg.split()[-1])
    base = Image.alpha_composite(base, lsh.filter(ImageFilter.GaussianBlur(10)))
    base.alpha_composite(lg, (lx, ly))
    # floor reflection: mirrored, fading
    refl = ImageOps.flip(lg).crop((0, 0, lg.width, min(lg.height, 90)))
    fade = Image.linear_gradient('L').resize(refl.size).point(lambda v: int((255 - v) * 0.28))
    r_alpha = ImageChops.multiply(refl.split()[-1], fade)
    refl.putalpha(r_alpha)
    ry = cy + ch - 70
    if ry + refl.height > cy + ch - 8:
        refl = refl.crop((0, 0, refl.width, max(1, cy + ch - 8 - ry)))
    base.alpha_composite(refl, (lx, ry))

    # channel name under the card
    d = ImageDraw.Draw(base)
    f = _font(46)
    name = visual(name)
    text = name if d.textlength(name, font=f) < W - 60 else name[:22] + '…'
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2 + 2, cy + ch + 72), text, font=f, fill=(0, 0, 0, 180))
    d.text(((W - tw) / 2, cy + ch + 70), text, font=f, fill=(245, 240, 230, 255))
    d.line((W / 2 - 60, cy + ch + 138, W / 2 + 60, cy + ch + 138), fill=GOLD + (220,), width=3)
    return base.convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'index.json')
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    only = {slug(x) for x in a.only.split(',') if x.strip()}
    done = failed = 0
    for key, (name, url) in sorted(channels().items()):
        if only and key not in only:
            continue
        try:
            img = poster(fetch_logo(url), name)
            fn = key + '.jpg'
            img.save(os.path.join(OUT, fn), 'JPEG', quality=90, optimize=True, progressive=True)
            index[key] = fn
            done += 1
        except Exception as e:
            print('  skip %s: %s' % (name, e), file=sys.stderr)
            failed += 1
    json.dump(index, open(idx_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('channel posters: %d made, %d skipped, %d in index' % (done, failed, len(index)))


if __name__ == '__main__':
    main()
