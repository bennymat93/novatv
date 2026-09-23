# -*- coding: utf-8 -*-
"""Final BN brand = option B 'Gold Premium'. Renders every asset the build uses."""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import make_logo as base
from logo_options import opt_b, text_mask, paint, BAHN, S

GOLD = ((255, 226, 140), (212, 160, 55), (255, 236, 170))
LIGHT = r'C:\Windows\Fonts\segoeuil.ttf'


def mark(px):
    """Gold letters only (transparent) - replaces Kodi's K logo."""
    n = px * S
    out = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    m = text_mask(n, 'BN', BAHN, 0.55, kern=-0.02, variation='Bold')
    out.paste(Image.new('RGBA', (n, n), (0, 0, 0, 170)), (int(n * .01), int(n * .015)), m.filter(ImageFilter.GaussianBlur(n * .02)))
    paint(out, m, GOLD)
    return out.resize((px, px), Image.LANCZOS)


def wordmark(w=930, h=256):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ic = opt_b(h)
    img.alpha_composite(ic)
    W, H = w * S, h * S
    t = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(t)
    f1 = ImageFont.truetype(BAHN, int(H * 0.50)); f1.set_variation_by_name('Bold')
    f2 = ImageFont.truetype(LIGHT, int(H * 0.15))
    x = (h * 1.16) * S
    d.text((x, H * 0.06), 'BN', font=f1, fill=255)
    d.text((x + H * 0.02, H * 0.72), 'S T R E A M', font=f2, fill=255)
    big = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    big.paste(base.fast_gradient(W, H, GOLD).convert('RGBA'), (0, 0), t)
    img.alpha_composite(big.resize((w, h), Image.LANCZOS))
    return img


def backdrop(w=1920, h=1080, logo=True):
    bg = base.fast_gradient(w, h, ((6, 6, 8), (22, 19, 14), (4, 4, 6))).convert('RGBA')
    g = Image.new('L', (w, h), 0)
    ImageDraw.Draw(g).ellipse((w * .28, h * .1, w * .72, h * .9), fill=110)
    g = g.filter(ImageFilter.GaussianBlur(h * .2))
    bg = Image.composite(Image.new('RGBA', (w, h), (120, 90, 30, 255)), bg, g.point(lambda v: int(v * .35)))
    if logo:
        ic = opt_b(int(h * .36))
        bg.alpha_composite(ic, ((w - ic.width) // 2, int(h * .25)))
        d = ImageDraw.Draw(bg)
        f = ImageFont.truetype(LIGHT, int(h * .035))
        s = 'B N   S T R E A M'
        d.text(((w - d.textlength(s, font=f)) / 2, h * .67), s, font=f, fill=(230, 200, 130, 255))
    return bg.convert('RGB')


if __name__ == '__main__':
    o = base.OUT
    big = opt_b(1024)
    big.save(os.path.join(o, 'bn_icon_1024.png'))
    opt_b(512).save(os.path.join(o, 'icon.png'))
    opt_b(256).save(os.path.join(o, 'icon_256.png'))
    mark(941).save(os.path.join(o, 'bn_mark_941.png'))
    wordmark().save(os.path.join(o, 'bn_wordmark.png'))
    backdrop().save(os.path.join(o, 'splash.jpg'), quality=92)
    backdrop(logo=False).save(os.path.join(o, 'fanart.jpg'), quality=90)
    big.save(os.path.join(o, 'bn.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('gold brand ->', o)
