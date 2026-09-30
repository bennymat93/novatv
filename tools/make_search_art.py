# -*- coding: utf-8 -*-
"""Search tiles for the home widgets (Movies / Series): a 16:9 picture shaped like a search field.
    python tools/make_search_art.py    -> addons/plugin.video.nova/resources/media/search_movie.png, search_tv.png"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'media')
GOLD = (232, 190, 90)
W, H = 960, 540
FONT = r'C:\Windows\Fonts\segoeui.ttf'
FONT_B = r'C:\Windows\Fonts\segoeuib.ttf'


def rtl(text):
    """Pillow without libraqm draws Hebrew left-to-right: reverse the visual order"""
    return text[::-1]


def tile(title, hint, path):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))       # transparent: only the field and the title show
    # the search field: rounded, glassy, gold rim, drop shadow
    x0, y0, x1, y1 = 70, 200, W - 70, 340
    sh = Image.new('L', (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle((x0 + 6, y0 + 16, x1 + 6, y1 + 22), 70, fill=210)
    img.paste((0, 0, 0, 200), mask=sh.filter(ImageFilter.GaussianBlur(22)))
    field = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(field)
    fd.rounded_rectangle((x0, y0, x1, y1), 70, fill=(34, 38, 50, 255), outline=GOLD + (230,), width=4)
    img = Image.alpha_composite(img, field)
    sheen = Image.new('RGBA', (W, H), (0, 0, 0, 0))            # glass highlight, blended over the field
    ImageDraw.Draw(sheen).rounded_rectangle((x0 + 10, y0 + 8, x1 - 10, y0 + 58), 50, fill=(255, 255, 255, 22))
    img = Image.alpha_composite(img, sheen.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(img)
    # magnifier on the right (RTL field)
    cx, cy, r = x1 - 90, (y0 + y1) // 2 - 6, 30
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GOLD, width=9)
    d.line((cx - r * 0.7, cy + r * 0.7, cx - r * 1.55, cy + r * 1.55), fill=GOLD, width=11)
    # hint text + caret
    f = ImageFont.truetype(FONT, 58)
    t = rtl(hint)
    tw = d.textlength(t, font=f)
    tx = cx - r - 40 - tw
    d.text((tx, cy - 38), t, font=f, fill=(170, 172, 182))
    d.line((tx - 18, cy - 34, tx - 18, cy + 38), fill=(245, 240, 230), width=5)
    # title above
    fb = ImageFont.truetype(FONT_B, 72)
    t = rtl(title)
    d.text(((W - d.textlength(t, font=fb)) / 2, 70), t, font=fb, fill=(245, 240, 230))
    d.line((W / 2 - 70, 160, W / 2 + 70, 160), fill=GOLD, width=4)
    img.save(path, 'PNG', optimize=True)


if __name__ == '__main__':
    tile('חיפוש סרטים', 'שם הסרט...', os.path.join(OUT, 'search_movie.png'))
    tile('חיפוש סדרות', 'שם הסדרה...', os.path.join(OUT, 'search_tv.png'))
    tile('חיפוש בכל המקורות', 'מה לחפש?...', os.path.join(OUT, 'search_all.png'))
    tile('חיפוש בידע וטכנולוגיה', 'נושא, הרצאה, קורס...', os.path.join(OUT, 'search_knowledge.png'))
    tile('חיפוש באילוף כלבים', 'נושא אילוף...', os.path.join(OUT, 'search_dogs.png'))
    tile('חיפוש בעזרה', 'בעיה, הגדרה, כפתור...', os.path.join(OUT, 'search_help.png'))
    print('search tiles written')
