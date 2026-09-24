# -*- coding: utf-8 -*-
"""Re-brand the official Kodi 21.3 Android APK as "BN Stream".

 * package org.xbmc.kodi -> org.bn.stream (installs next to normal Kodi)
 * provider authorities renamed in the manifest AND in the smali code
 * app name, launcher icons, Android-TV banner, splash, in-app icons -> BN Gold
 * signed with a local BN key (work/apk/bn.keystore, created once)

  python tools/make_apk.py            -> dist/BN-Stream-21.3-arm64-v8a.apk + armeabi-v7a.apk
"""
import glob
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work', 'apk')
BRAND = os.path.join(ROOT, 'brand')
JAVA = glob.glob(os.path.join(W, 'jdk', '*', 'bin', 'java.exe'))[0]
KEYTOOL = JAVA.replace('java.exe', 'keytool.exe')
OLD, NEW = 'org.xbmc.kodi', 'org.bn.stream'
NAME = 'BN Stream'
DENS = {'ldpi': 36, 'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}


def run(*a):
    subprocess.check_call(list(a), cwd=W, stdout=subprocess.DEVNULL)


def banner(w, h):
    """Android TV home-row banner: gold icon + 'BN Stream' on black."""
    from PIL import ImageDraw, ImageFont
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from brand_gold import backdrop
    img = backdrop(w * 4, h * 4, logo=False).convert('RGBA')
    ic = Image.open(os.path.join(BRAND, 'bn_icon_1024.png')).resize((int(h * 4 * .8),) * 2, Image.LANCZOS)
    img.alpha_composite(ic, (int(h * .4), int(h * .4)))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(r'C:\Windows\Fonts\bahnschrift.ttf', int(h * 4 * .26))
    f.set_variation_by_name('Bold')
    d.text((int(h * 4 * 1.0), int(h * 4 * .3)), 'BN', font=f, fill=(232, 190, 90))
    f2 = ImageFont.truetype(r'C:\Windows\Fonts\segoeuil.ttf', int(h * 4 * .13))
    d.text((int(h * 4 * 1.02), int(h * 4 * .6)), 'STREAM', font=f2, fill=(232, 200, 130))
    return img.resize((w, h), Image.LANCZOS).convert('RGB')


def rebrand(dec):
    # --- manifest: package, authorities, label
    mf = os.path.join(dec, 'AndroidManifest.xml')
    s = open(mf, encoding='utf-8').read()
    s = s.replace('package="%s"' % OLD, 'package="%s"' % NEW)
    for suffix in ('file', 'media', 'ytdl'):
        s = s.replace('android:authorities="%s.%s"' % (OLD, suffix), 'android:authorities="%s.%s"' % (NEW, suffix))
    # activity/receiver class names stay org.xbmc.kodi.* (the code lives there)
    open(mf, 'w', encoding='utf-8').write(s)
    yml = os.path.join(dec, 'apktool.yml')
    y = open(yml, encoding='utf-8').read()
    y = re.sub(r'renameManifestPackage: .*', 'renameManifestPackage: null', y)
    open(yml, 'w', encoding='utf-8').write(y)
    # --- smali: authority strings used by FileProvider / ContentProvider code
    n = 0
    for p in glob.glob(os.path.join(dec, 'smali*', '**', '*.smali'), recursive=True):
        t = open(p, encoding='utf-8').read()
        t2 = re.sub(r'"%s\.(file|media|ytdl)"' % re.escape(OLD), lambda m: '"%s.%s"' % (NEW, m.group(1)), t)
        t2 = t2.replace('"content://%s.' % OLD, '"content://%s.' % NEW)                  # search provider URI
        t2 = t2.replace('"ComponentInfo{%s/' % OLD, '"ComponentInfo{%s/' % NEW)          # own component id
        if p.endswith('XBMCBroadcastReceiver.smali'):                                   # launch-on-boot: launch *us*
            t2 = t2.replace('const-string v0, "%s"' % OLD, 'const-string v0, "%s"' % NEW)
        if t2 != t:
            open(p, 'w', encoding='utf-8').write(t2)
            n += 1
    print('   smali files patched:', n)
    # --- name
    for sp in glob.glob(os.path.join(dec, 'res', 'values*', 'strings.xml')):
        t = open(sp, encoding='utf-8').read()
        t = re.sub(r'(<string name="app_name">)[^<]*(</string>)', r'\g<1>%s\g<2>' % NAME, t)
        open(sp, 'w', encoding='utf-8').write(t)
    # --- images
    icon = Image.open(os.path.join(BRAND, 'bn_icon_1024.png'))
    for dn, px in DENS.items():
        p = os.path.join(dec, 'res', 'drawable-%s' % dn, 'ic_launcher.png')
        if os.path.exists(p):
            icon.resize((px, px), Image.LANCZOS).save(p)
    ban = banner(320, 180)
    for p in [os.path.join(dec, 'res', 'drawable-xhdpi', 'banner.png'), os.path.join(dec, 'assets', 'media', 'banner.png')]:
        ban.save(p)
    Image.open(os.path.join(BRAND, 'splash.jpg')).convert('RGB').save(os.path.join(dec, 'assets', 'media', 'applaunch_screen.png'))
    for p in glob.glob(os.path.join(dec, 'assets', 'media', 'icon*x*.png')):
        sz = Image.open(p).size
        icon.resize(sz, Image.LANCZOS).save(p)
    # Kodi's own splash inside the app
    for p in glob.glob(os.path.join(dec, 'assets', 'media', 'splash*')):
        Image.open(os.path.join(BRAND, 'splash.jpg')).convert('RGB').save(p) if p.endswith('.jpg') else None


def keystore():
    ks = os.path.join(W, 'bn.keystore')
    if not os.path.exists(ks):
        run(KEYTOOL, '-genkeypair', '-keystore', ks, '-alias', 'bn', '-keyalg', 'RSA', '-keysize', '2048',
            '-validity', '10000', '-storepass', 'bnstream', '-keypass', 'bnstream', '-dname', 'CN=BN Stream')
    return ks


def build(src, arch):
    dec = os.path.join(W, 'dec_' + arch)
    shutil.rmtree(dec, ignore_errors=True)
    print('decode', src)
    run(JAVA, '-jar', 'apktool.jar', 'd', '-f', src, '-o', dec)
    rebrand(dec)
    out = os.path.join(W, 'bn_%s_unsigned.apk' % arch)
    print('build', arch)
    run(JAVA, '-jar', 'apktool.jar', 'b', dec, '-o', out)
    ks = keystore()
    run(JAVA, '-jar', 'signer.jar', '-a', out, '--ks', ks, '--ksAlias', 'bn', '--ksPass', 'bnstream',
        '--ksKeyPass', 'bnstream', '-o', os.path.join(W, 'signed_' + arch))
    signed = glob.glob(os.path.join(W, 'signed_' + arch, '*.apk'))[0]
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    final = os.path.join(ROOT, 'dist', 'BN-Stream-21.3-%s.apk' % arch)
    shutil.copy(signed, final)
    print('->', final, '%.1f MB' % (os.path.getsize(final) / 1e6))


if __name__ == '__main__':
    build('kodi64.apk', 'arm64-v8a')
    build('kodi32.apk', 'armeabi-v7a')
