# -*- coding: utf-8 -*-
"""Draw the BN player icon set: one style (white, same stroke, same optical size), 128x128 PNG with transparency.

  .venv11/Scripts/python tools/make_osd_icons.py  ->  addons/plugin.video.nova/resources/skin/icons/*.png
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'skin', 'icons')
S = 512                       # drawn at 4x, downsampled -> smooth edges
W = 30                        # stroke width at 4x
C = (255, 255, 255, 255)


def canvas():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def save(im, name):
    im.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, name + '.png'))


def tri(d, pts):
    d.polygon(pts, fill=C)


def prev_(d):
    d.rectangle((120, 136, 160, 376), fill=C)
    tri(d, [(392, 136), (392, 376), (176, 256)])


def next_(d):
    tri(d, [(120, 136), (120, 376), (336, 256)])
    d.rectangle((352, 136, 392, 376), fill=C)


def rew(d):
    tri(d, [(256, 146), (256, 366), (86, 256)])
    tri(d, [(426, 146), (426, 366), (256, 256)])


def fwd(d):
    tri(d, [(86, 146), (86, 366), (256, 256)])
    tri(d, [(256, 146), (256, 366), (426, 256)])


def play(d):
    tri(d, [(166, 116), (166, 396), (406, 256)])


def pause(d):
    d.rounded_rectangle((146, 126, 226, 386), 18, fill=C)
    d.rounded_rectangle((286, 126, 366, 386), 18, fill=C)


def stop(d):
    d.rounded_rectangle((146, 146, 366, 366), 28, fill=C)


def bubble(d):
    d.rounded_rectangle((76, 106, 436, 346), 44, outline=C, width=W)
    d.polygon([(170, 330), (170, 420), (250, 340)], fill=C)


def subs(d):
    bubble(d)
    d.rounded_rectangle((140, 190, 300, 212), 10, fill=C)
    d.rounded_rectangle((320, 190, 372, 212), 10, fill=C)
    d.rounded_rectangle((140, 250, 220, 272), 10, fill=C)
    d.rounded_rectangle((240, 250, 372, 272), 10, fill=C)


def ai(d):
    bubble(d)
    f = ImageFont.truetype('arialbd.ttf', 150)
    d.text((256, 228), 'AI', font=f, fill=C, anchor='mm')


def sync(d):
    # clock + two-way arrow: move subtitles earlier / later
    d.ellipse((96, 96, 416, 416), outline=C, width=W)
    d.line((256, 256, 256, 160), fill=C, width=W)
    d.line((256, 256, 330, 300), fill=C, width=W)
    d.ellipse((238, 238, 274, 274), fill=C)


def audio(d):
    d.polygon([(96, 206), (166, 206), (256, 126), (256, 386), (166, 306), (96, 306)], fill=C)
    for r in (70, 130):
        d.arc((256 - r, 256 - r, 256 + r, 256 + r), -45, 45, fill=C, width=W)


def picture(d):
    d.rounded_rectangle((76, 116, 436, 346), 26, outline=C, width=W)
    d.line((196, 406, 316, 406), fill=C, width=W)
    d.line((256, 346, 256, 406), fill=C, width=W)
    d.polygon([(130, 310), (220, 210), (280, 270), (330, 220), (390, 310)], fill=C)


def bookmark(d):
    d.polygon([(156, 96), (356, 96), (356, 416), (256, 336), (156, 416)], outline=C, width=W)


def info(d):
    d.ellipse((96, 96, 416, 416), outline=C, width=W)
    d.ellipse((236, 150, 276, 190), fill=C)
    d.rounded_rectangle((238, 222, 274, 360), 14, fill=C)


def playlist(d):
    for y in (150, 236, 322):
        d.rounded_rectangle((200, y - 14, 420, y + 14), 12, fill=C)
    tri(d, [(92, 120), (92, 210), (166, 165)])
    d.rounded_rectangle((92, 222, 166, 250), 12, fill=C)
    d.rounded_rectangle((92, 308, 166, 336), 12, fill=C)


def gear(d):
    cx = cy = 256
    for k in range(8):                                   # teeth
        a = k * math.pi / 4
        x, y = cx + 150 * math.cos(a), cy + 150 * math.sin(a)
        d.rounded_rectangle((x - 34, y - 34, x + 34, y + 34), 10, fill=C)
    d.ellipse((cx - 140, cy - 140, cx + 140, cy + 140), fill=C)
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(0, 0, 0, 0))


def focus(d):
    d.ellipse((0, 0, S - 1, S - 1), fill=C)


ICONS = {'previous': prev_, 'rewind': rew, 'play': play, 'pause': pause, 'stop': stop, 'forward': fwd,
         'next': next_, 'subtitles': subs, 'ai': ai, 'sync': sync, 'audio': audio, 'picture': picture,
         'bookmark': bookmark, 'info': info, 'playlist': playlist, 'settings': gear, 'focus': focus}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in ICONS.items():
        im, d = canvas()
        fn(d)
        save(im, name)
        if name == 'focus':
            continue
        # focused look, pre-drawn: gold circle with the icon in dark (a plain button needs one image per state)
        base = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(base).ellipse((0, 0, S - 1, S - 1), fill=(232, 190, 90, 255))
        icon = im.resize((int(S * 0.6), int(S * 0.6)), Image.LANCZOS)
        dark = Image.new('RGBA', icon.size, (16, 19, 24, 255))
        dark.putalpha(icon.split()[3])
        base.alpha_composite(dark, (int(S * 0.2), int(S * 0.2)))
        base.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, name + '_fo.png'))
        # normal look: the icon at the same optical size inside the same 128 box
        norm = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        norm.alpha_composite(icon, (int(S * 0.2), int(S * 0.2)))
        norm.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, name + '_nf.png'))
    # preview sheet for review
    sheet = Image.new('RGB', (len(ICONS) * 140, 150), (20, 22, 30))
    for i, name in enumerate(ICONS):
        ic = Image.open(os.path.join(OUT, name + '.png'))
        sheet.paste(ic, (i * 140 + 6, 11), ic)
    sheet.save(os.path.join(ROOT, 'work', 'bn_icons_preview.png'))
    print('icons:', len(ICONS), OUT)


if __name__ == '__main__':
    main()
