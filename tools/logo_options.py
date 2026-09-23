# -*- coding: utf-8 -*-
"""Render 4 alternative BN logo concepts + a comparison sheet (brand/options/)."""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import make_logo as base

OUT = os.path.join(base.OUT, 'options')
BLACK = r'C:\Windows\Fonts\seguibl.ttf'
BAHN = r'C:\Windows\Fonts\bahnschrift.ttf'
LIGHT = r'C:\Windows\Fonts\segoeuil.ttf'
S = 4


def text_mask(n, text, font_path, scale, kern=-0.03, dy=0.0, variation=None):
    m = Image.new('L', (n, n), 0)
    d = ImageDraw.Draw(m)
    f = ImageFont.truetype(font_path, int(n * scale))
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + kern * n * (len(text) - 1)
    bb = d.textbbox((0, 0), text, font=f)
    x = (n - total) / 2
    y = (n - (bb[3] - bb[1])) / 2 - bb[1] + dy * n
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=255)
        x += w + kern * n
    return m


def paint(out, mask, colors):
    n = out.width
    out.paste(base.fast_gradient(n, n, colors).convert('RGBA'), (0, 0), mask)


def rounded(n, r):
    return base.rounded(n, int(n * r))


# ---------------------------------------------------------------- A: Neon Play (current)
def opt_a(px):
    return base.icon(px)


# ---------------------------------------------------------------- B: Gold Premium
def opt_b(px):
    n = px * S
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    bg = base.fast_gradient(n, n, ((12, 12, 14), (26, 24, 22), (8, 8, 10))).convert('RGBA')
    out.paste(bg, (0, 0), rounded(n, 0.22))
    frame = Image.new('L', (n, n), 0)
    ImageDraw.Draw(frame).rounded_rectangle((n * .07, n * .07, n * .93, n * .93), int(n * .16), outline=255, width=int(n * .014))
    gold = ((255, 226, 140), (212, 160, 55), (255, 236, 170))
    paint(out, frame, gold)
    m = text_mask(n, 'BN', BAHN, 0.50, kern=-0.02, variation='Bold')
    shadow = m.filter(ImageFilter.GaussianBlur(n * .02))
    out.paste(Image.new('RGBA', (n, n), (0, 0, 0, 200)), (int(n * .01), int(n * .015)), shadow)
    paint(out, m, gold)
    line = Image.new('L', (n, n), 0)
    ImageDraw.Draw(line).rectangle((n * .30, n * .74, n * .70, n * .752), fill=255)
    paint(out, line, gold)
    return out.resize((px, px), Image.LANCZOS)


# ---------------------------------------------------------------- C: Red Cinema (Netflix-like energy)
def opt_c(px):
    n = px * S
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    bg = base.fast_gradient(n, n, ((20, 0, 4), (8, 0, 2), (0, 0, 0))).convert('RGBA')
    out.paste(bg, (0, 0), rounded(n, 0.22))
    m = text_mask(n, 'BN', BLACK, 0.58, kern=-0.06)
    # italic shear for motion
    m = m.transform((n, n), Image.AFFINE, (1, 0.18, -n * 0.09, 0, 1, 0), Image.BICUBIC)
    glow = m.filter(ImageFilter.GaussianBlur(n * .05))
    out.paste(Image.new('RGBA', (n, n), (255, 20, 40, 255)), (0, 0), glow.point(lambda v: int(v * .7)))
    paint(out, m, ((255, 70, 70), (229, 9, 20), (150, 0, 10)))
    # speed stripes
    st = Image.new('L', (n, n), 0)
    d = ImageDraw.Draw(st)
    for i, y in enumerate((0.73, 0.78, 0.83)):
        d.rounded_rectangle((n * (.18 + i * .05), n * y, n * (.82 - i * .08), n * (y + .018)), int(n * .01), fill=255)
    paint(out, st, ((255, 90, 90), (229, 9, 20), (120, 0, 10)))
    return out.resize((px, px), Image.LANCZOS)


# ---------------------------------------------------------------- D: Minimal Glass / Israeli blue
def opt_d(px):
    n = px * S
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    bg = base.fast_gradient(n, n, ((0, 56, 184), (0, 110, 230), (80, 190, 255))).convert('RGBA')
    out.paste(bg, (0, 0), rounded(n, 0.5 * 0.999))       # circle
    gl = Image.new('L', (n, n), 0)
    ImageDraw.Draw(gl).ellipse((-n * .2, -n * .75, n * 1.2, n * .5), fill=55)
    gl = ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(n * .02)), rounded(n, 0.4999))
    out.paste(Image.new('RGBA', (n, n), (255, 255, 255, 255)), (0, 0), gl)
    m = text_mask(n, 'BN', BAHN, 0.46, kern=-0.005, variation='SemiBold')
    sh = m.filter(ImageFilter.GaussianBlur(n * .025))
    out.paste(Image.new('RGBA', (n, n), (0, 20, 80, 150)), (0, int(n * .012)), sh)
    out.paste(Image.new('RGBA', (n, n), (255, 255, 255, 255)), (0, 0), m)
    return out.resize((px, px), Image.LANCZOS)


OPTIONS = [('A', 'Neon Play', opt_a), ('B', 'Gold Premium', opt_b),
           ('C', 'Red Cinema', opt_c), ('D', 'Blue Glass', opt_d)]


def sheet():
    os.makedirs(OUT, exist_ok=True)
    tile, pad = 420, 60
    w, h = pad + (tile + pad) * 4, 700
    sh = Image.new('RGB', (w, h), (14, 15, 22))
    d = ImageDraw.Draw(sh)
    ft = ImageFont.truetype(BLACK, 54)
    fs = ImageFont.truetype(LIGHT, 34)
    d.text((pad, 30), 'BN — choose a logo', font=ft, fill=(240, 240, 250))
    for i, (key, name, fn) in enumerate(OPTIONS):
        img = fn(512)
        img.save(os.path.join(OUT, 'option_%s.png' % key))
        x = pad + i * (tile + pad)
        sh.paste(img.resize((tile, tile), Image.LANCZOS), (x, 130), img.resize((tile, tile), Image.LANCZOS))
        small = img.resize((72, 72), Image.LANCZOS)                   # how it looks as a tiny app icon
        sh.paste(small, (x, 580), small)
        d.text((x + 90, 575), '%s  %s' % (key, name), font=ft if False else fs, fill=(230, 230, 240))
        d.text((x + 90, 615), 'icon size preview', font=ImageFont.truetype(LIGHT, 22), fill=(140, 140, 160))
    p = os.path.join(OUT, 'BN_logo_options.png')
    sh.save(p)
    print(p)


if __name__ == '__main__':
    sheet()
