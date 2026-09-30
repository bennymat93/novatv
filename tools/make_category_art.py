# -*- coding: utf-8 -*-
"""Category tiles for the home widgets ("by category" / "by year" / "by language"): a square card with a symbol,
the name is written under it by the skin. Written to addons/plugin.video.nova/resources/media/cats/:
  genre_<tmdb genre id>.png   a line icon (Segoe Fluent Icons) in gold
  year_<yyyy>.png             the year in gold
  lang_<code>.png             the language in its own script
    python tools/make_category_art.py
"""
import datetime
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'resources', 'media', 'cats')
S = 460
GOLD = (232, 190, 90)
F = r'C:\Windows\Fonts'

# TMDb genre ids -> Segoe Fluent Icons glyph (Windows 11 system icon font: thin, modern line icons)
ICONS = os.path.join(F, 'SegoeIcons.ttf')
GENRES = {28: 0xE945, 12: 0xE774, 16: 0xE790, 35: 0xE76E, 80: 0xE928, 99: 0xE722, 18: 0xE716, 10751: 0xE80F,
          14: 0xF4A5, 36: 0xE825, 27: 0xECAD, 10402: 0xE8D6, 9648: 0xE9CE, 10749: 0xEB51, 878: 0xE99A, 10770: 0xE7F4,
          53: 0xE95E, 10752: 0xEA18, 37: 0xE706, 10759: 0xE945, 10762: 0xE7FC, 10763: 0xE8A1, 10764: 0xE714,
          10765: 0xE99A, 10766: 0xEB51, 10767: 0xE720, 10768: 0xE825}
# learning sections (resources/topics/*.json 'icon') -> glyph
TOPICS = {'power': 0xEC4A, 'control': 0xE9E9, 'tech': 0xE950, 'top': 0xE734, 'puppy': 0xE7BE, 'obedience': 0xEB95,
          'leash': 0xE805, 'recall': 0xE81C, 'behavior': 0xE9D9, 'tricks': 0xEA86, 'sport': 0xE7C1,
          # help center tiles
          'guide': 0xE736, 'trouble': 0xE90F, 'hsearch': 0xE721, 'about': 0xE946, 'profile': 0xE7F4, 'update': 0xE895, 'speed': 0xE701}
# language code -> (text in its own script, font)
LANGS = {'he': ('עב', 'segoeuisl.ttf', True), 'en': ('EN', 'segoeuisl.ttf', False), 'ru': ('РУ', 'segoeuisl.ttf', False),
         'fr': ('FR', 'segoeuisl.ttf', False), 'es': ('ES', 'segoeuisl.ttf', False), 'de': ('DE', 'segoeuisl.ttf', False),
         'it': ('IT', 'segoeuisl.ttf', False), 'tr': ('TR', 'segoeuisl.ttf', False), 'ko': ('한국', 'malgun.ttf', False),
         'ja': ('日本', 'YuGothM.ttc', False), 'hi': ('हिं', 'Nirmala.ttc', False)}


def card():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sh = Image.new('L', (S, S), 0)
    ImageDraw.Draw(sh).rounded_rectangle((24, 30, S - 20, S - 12), 44, fill=150)
    img.paste((0, 0, 0, 255), mask=sh.filter(ImageFilter.GaussianBlur(16)))
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((18, 18, S - 26, S - 26), 40, fill=255)
    grad = Image.new('RGBA', (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        gd.line((0, y, S, y), fill=(int(30 - 12 * t), int(32 - 13 * t), int(40 - 16 * t), 255))
    face = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    face.paste(grad, (0, 0), m)
    img = Image.alpha_composite(img, face)
    ImageDraw.Draw(img).rounded_rectangle((18, 18, S - 26, S - 26), 40, outline=GOLD + (120,), width=2)
    glow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S * 0.18, S * 0.12, S * 0.78, S * 0.72), fill=GOLD + (26,))
    return Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(60)))


def centred_text(img, text, font, fill, embedded=False, dy=0):
    d = ImageDraw.Draw(img)
    box = d.textbbox((0, 0), text, font=font, embedded_color=embedded)
    x = (S - 8 - (box[2] - box[0])) / 2 - box[0]
    y = (S - 8 - (box[3] - box[1])) / 2 - box[1] + dy
    if not embedded:                                     # 3D: dark offset copy under the gold
        d.text((x + 5, y + 8), text, font=font, fill=(0, 0, 0, 170))
    d.text((x, y), text, font=font, fill=fill, embedded_color=embedded)


def gold_text(img, text, font):
    """gold gradient text with a soft 3D shadow"""
    mask = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(mask)
    box = d.textbbox((0, 0), text, font=font)
    x = (S - 8 - (box[2] - box[0])) / 2 - box[0]
    y = (S - 8 - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=255)
    shadow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 190), (6, 10), mask)
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(5)))
    grad = Image.new('RGBA', (S, S))
    gd = ImageDraw.Draw(grad)
    for yy in range(S):
        t = yy / S
        gd.line((0, yy, S, yy), fill=(int(255 - 40 * t), int(226 - 70 * t), int(150 - 100 * t), 255))
    img.paste(grad, (0, 0), mask)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    icons = ImageFont.truetype(ICONS, 200)
    for gid, cp in GENRES.items():
        gold_text(card(), chr(cp), icons).save(os.path.join(OUT, 'genre_%d.png' % gid), optimize=True)
    for name, cp in TOPICS.items():
        gold_text(card(), chr(cp), icons).save(os.path.join(OUT, 'topic_%s.png' % name), optimize=True)
    fy = ImageFont.truetype(os.path.join(F, 'segoeuisl.ttf'), 150)
    for y in range(datetime.date.today().year + 1, 1949, -1):
        gold_text(card(), str(y), fy).save(os.path.join(OUT, 'year_%d.png' % y), optimize=True)
    for code, (text, font, rtl) in LANGS.items():
        size = 190
        f = ImageFont.truetype(os.path.join(F, font), size)
        while size > 60 and ImageDraw.Draw(card()).textlength(text, font=f) > S * 0.55:   # fit inside the card
            size -= 6
            f = ImageFont.truetype(os.path.join(F, font), size)
        gold_text(card(), text[::-1] if rtl else text, f).save(os.path.join(OUT, 'lang_%s.png' % code), optimize=True)
    print('category tiles: %d files' % len(os.listdir(OUT)))


if __name__ == '__main__':
    main()
