# -*- coding: utf-8 -*-
"""Render the BN brand set (icon, wordmark, splash, fanart, .ico) with Pillow.

Design: a deep-space rounded badge, a heavy geometric "BN" monogram filled with a
cyan -> violet -> magenta gradient, a play-arrow notch cut out of the B's lower
bowl, a thin orbit ring and a soft neon glow.
"""
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'brand')
FONT = r'C:\Windows\Fonts\seguibl.ttf'          # Segoe UI Black
S = 4                                             # supersampling factor

C1, C2, C3 = (0, 229, 255), (124, 77, 255), (255, 45, 170)   # cyan, violet, magenta
BG1, BG2 = (8, 10, 28), (26, 12, 58)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(w, h, stops, diagonal=True):
    g = Image.new('RGB', (w, h))
    px = g.load()
    for y in range(h):
        for x in range(w):
            t = ((x / w) * 0.65 + (y / h) * 0.35) if diagonal else y / h
            if t < 0.5:
                c = lerp(stops[0], stops[1], t / 0.5)
            else:
                c = lerp(stops[1], stops[2], (t - 0.5) / 0.5)
            px[x, y] = c
    return g


def fast_gradient(w, h, stops):
    small = gradient(64, 64, stops)
    return small.resize((w, h), Image.BICUBIC)


def monogram_mask(size):
    """White 'BN' on black, tight kerning, with a play-notch cut into the B."""
    m = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(m)
    font = ImageFont.truetype(FONT, int(size * 0.47))
    text = 'BN'
    kern = -int(size * 0.035)
    wb = d.textlength('B', font=font)
    wn = d.textlength('N', font=font)
    total = wb + wn + kern
    bbox = d.textbbox((0, 0), text, font=font)
    th = bbox[3] - bbox[1]
    x0 = (size - total) / 2
    y0 = (size - th) / 2 - bbox[1]
    d.text((x0, y0), 'B', font=font, fill=255)
    d.text((x0 + wb + kern, y0), 'N', font=font, fill=255)
    # turn the B's lower counter into a play arrow: fill the hole, then cut a triangle
    bb = d.textbbox((x0, y0), 'B', font=font)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    d.rectangle((bb[0] + bw * 0.30, bb[1] + bh * 0.58, bb[0] + bw * 0.70, bb[1] + bh * 0.84), fill=255)
    cx, cy, r = bb[0] + bw * 0.47, bb[1] + bh * 0.71, bh * 0.12
    d.polygon([(cx - r * 0.72, cy - r), (cx - r * 0.72, cy + r), (cx + r * 0.98, cy)], fill=0)
    return m


def rounded(size, radius):
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
    return m


def icon(px=1024, badge=True):
    n = px * S
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    if badge:
        bg = fast_gradient(n, n, (BG1, BG2, (40, 8, 60))).convert('RGBA')
        # soft radial light behind the letters
        light = Image.new('L', (n, n), 0)
        ImageDraw.Draw(light).ellipse((n * 0.12, n * 0.1, n * 0.88, n * 0.86), fill=150)
        light = light.filter(ImageFilter.GaussianBlur(n * 0.12))
        glow_col = Image.new('RGBA', (n, n), C2 + (255,))
        bg = Image.composite(glow_col, bg, light.point(lambda v: int(v * 0.45)))
        out.paste(bg, (0, 0), rounded(n, int(n * 0.22)))
        # orbit ring
        ring = Image.new('L', (n, n), 0)
        rd = ImageDraw.Draw(ring)
        rd.ellipse((n * 0.08, n * 0.08, n * 0.92, n * 0.92), outline=255, width=int(n * 0.012))
        ring = ImageChops.multiply(ring, rounded(n, int(n * 0.22)))
        ring_fill = fast_gradient(n, n, (C1, C2, C3)).convert('RGBA')
        out.paste(ring_fill, (0, 0), ring.point(lambda v: int(v * 0.55)))
    mask = monogram_mask(n)
    fill = fast_gradient(n, n, (C1, C2, C3)).convert('RGBA')
    glow = mask.filter(ImageFilter.GaussianBlur(n * 0.03)).point(lambda v: int(v * 0.9))
    out.paste(fill, (0, 0), glow)
    out.paste(fill, (0, 0), mask)
    # glossy highlight on the top half of the letters
    hl = Image.new('L', (n, n), 0)
    ImageDraw.Draw(hl).rectangle((0, 0, n, n * 0.44), fill=60)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(n * 0.04)), mask)
    out.paste(Image.new('RGBA', (n, n), (255, 255, 255, 255)), (0, 0), hl)
    return out.resize((px, px), Image.LANCZOS)


def wordmark(w=930, h=256):
    """Transparent badge + 'BN' lettering for the skin's logo slot (465x128 @2x)."""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ic = icon(h, badge=True)
    img.paste(ic, (0, 0), ic)
    n = h * S
    txt = Image.new('L', (w * S, n), 0)
    d = ImageDraw.Draw(txt)
    f1 = ImageFont.truetype(FONT, int(n * 0.52))
    f2 = ImageFont.truetype(r'C:\Windows\Fonts\segoeuil.ttf', int(n * 0.16))
    x = (h + h * 0.18) * S
    d.text((x, n * 0.08), 'BN', font=f1, fill=255)
    d.text((x + n * 0.02, n * 0.72), 'S T R E A M', font=f2, fill=200)
    fill = fast_gradient(w * S, n, (C1, C2, C3)).convert('RGBA')
    big = Image.new('RGBA', (w * S, n), (0, 0, 0, 0))
    big.paste(fill, (0, 0), txt)
    big = big.resize((w, h), Image.LANCZOS)
    img.alpha_composite(big)
    return img


def backdrop(w=1920, h=1080, with_logo=True):
    bg = fast_gradient(w, h, ((4, 5, 16), (18, 8, 40), (6, 4, 20))).convert('RGBA')
    glow = Image.new('L', (w, h), 0)
    ImageDraw.Draw(glow).ellipse((w * 0.25, h * 0.05, w * 0.75, h * 0.95), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(h * 0.18))
    bg = Image.composite(Image.new('RGBA', (w, h), C2 + (255,)), bg, glow.point(lambda v: int(v * 0.35)))
    if with_logo:
        ic = icon(int(h * 0.36))
        bg.alpha_composite(ic, ((w - ic.width) // 2, int(h * 0.26)))
        d = ImageDraw.Draw(bg)
        f = ImageFont.truetype(r'C:\Windows\Fonts\segoeuil.ttf', int(h * 0.035))
        t = 'B N   S T R E A M'
        tw = d.textlength(t, font=f)
        d.text(((w - tw) / 2, h * 0.68), t, font=f, fill=(200, 210, 255, 230))
    return bg.convert('RGB')


def main():
    os.makedirs(OUT, exist_ok=True)
    big = icon(1024)
    big.save(os.path.join(OUT, 'bn_icon_1024.png'))
    icon(512).save(os.path.join(OUT, 'icon.png'))
    icon(256).save(os.path.join(OUT, 'icon_256.png'))
    icon(941, badge=False).save(os.path.join(OUT, 'bn_mark_941.png'))
    wordmark().save(os.path.join(OUT, 'bn_wordmark.png'))
    backdrop().save(os.path.join(OUT, 'splash.jpg'), quality=92)
    backdrop(with_logo=False).save(os.path.join(OUT, 'fanart.jpg'), quality=90)
    big.save(os.path.join(OUT, 'bn.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('brand ->', OUT)


if __name__ == '__main__':
    main()
