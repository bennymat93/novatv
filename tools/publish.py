# -*- coding: utf-8 -*-
"""Build the GitHub Pages site for NovaTV.

  python tools/publish.py --gh-user USER --version 0.1.0

Produces site/ :
  index.html                      (Kodi file-manager source: https://USER.github.io/novatv/)
  repository.nova-1.0.0.zip       ("Install from zip file" entry point)
  repo/addons.xml(+.md5) + repo/<id>/<id>-<ver>.zip
  build.json + builds/NovaTV-<ver>.zip   (read by the NovaTV Wizard)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'site')
ADDONS = ['repository.nova', 'plugin.video.nova', 'plugin.program.novawizard', 'resource.uisounds.nova']


def zip_addon(src, dest):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(src):
            dirs[:] = [x for x in dirs if x != '__pycache__']
            for fn in files:
                if fn.endswith('.pyc'):
                    continue
                full = os.path.join(d, fn)
                z.write(full, os.path.join(os.path.basename(src), os.path.relpath(full, src)).replace(os.sep, '/'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gh-user', required=True)
    ap.add_argument('--version', default='0.1.0')
    a = ap.parse_args()
    user = a.gh_user.lower()

    # 1. stamp the GitHub user into repository + wizard sources
    for ad in ('repository.nova', 'plugin.program.novawizard'):
        for d, _, files in os.walk(os.path.join(ROOT, 'addons', ad)):
            for fn in files:
                if fn.endswith(('.xml', '.py')):
                    p = os.path.join(d, fn)
                    s = open(p, encoding='utf-8').read()
                    s2 = re.sub(r'__GHUSER__|[\w-]+(?=\.github\.io/novatv)', user, s)
                    if s2 != s:
                        open(p, 'w', encoding='utf-8').write(s2)

    # 2. build zip (includes the stamped add-ons)
    subprocess.check_call([sys.executable, os.path.join(ROOT, 'tools', 'make_build.py'), '--version', a.version])

    # 3. site
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(os.path.join(SITE, 'repo'))
    os.makedirs(os.path.join(SITE, 'builds'))
    xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for ad in ADDONS:
        src = os.path.join(ROOT, 'addons', ad)
        axml = open(os.path.join(src, 'addon.xml'), encoding='utf-8').read()
        ver = re.search(r'<addon[^>]*\bversion="([^"]+)"', axml).group(1)
        out_dir = os.path.join(SITE, 'repo', ad)
        os.makedirs(out_dir)
        zip_addon(src, os.path.join(out_dir, '%s-%s.zip' % (ad, ver)))
        for art in ('icon.png', 'fanart.jpg'):
            if os.path.exists(os.path.join(src, art)):
                shutil.copy(os.path.join(src, art), out_dir)
        xml.append(re.sub(r'<\?xml[^>]*\?>', '', axml).strip())
        if ad == 'repository.nova':
            shutil.copy(os.path.join(out_dir, '%s-%s.zip' % (ad, ver)), SITE)
            repo_zip = '%s-%s.zip' % (ad, ver)
    xml.append('</addons>')
    body = '\n'.join(xml) + '\n'
    open(os.path.join(SITE, 'repo', 'addons.xml'), 'w', encoding='utf-8').write(body)
    open(os.path.join(SITE, 'repo', 'addons.xml.md5'), 'w').write(hashlib.md5(body.encode('utf-8')).hexdigest())

    build = os.path.join(ROOT, 'dist', 'NovaTV-%s.zip' % a.version)
    shutil.copy(build, os.path.join(SITE, 'builds'))
    sha = hashlib.sha256(open(build, 'rb').read()).hexdigest()
    json.dump({'name': 'NovaTV', 'version': a.version, 'kodi': '21',
               'url': 'https://%s.github.io/novatv/builds/NovaTV-%s.zip' % (user, a.version),
               'size': os.path.getsize(build), 'sha256': sha},
              open(os.path.join(SITE, 'build.json'), 'w'), indent=1)
    open(os.path.join(SITE, '.nojekyll'), 'w').close()
    open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>NovaTV</title></head><body>\n'
        '<h1>NovaTV</h1>\n<p>Kodi: Settings &rarr; File manager &rarr; Add source &rarr; '
        '<code>https://%s.github.io/novatv/</code> &rarr; Add-ons &rarr; Install from zip file.</p>\n'
        '<a href="%s">%s</a><br>\n<a href="build.json">build.json</a>\n'
        '<h2>BN Stream app (Android)</h2>\n'
        '<a href="https://github.com/%s/novatv/releases/latest/download/BN-Stream-21.3-arm64-v8a.apk">BN Stream 64-bit (arm64)</a><br>\n'
        '<a href="https://github.com/%s/novatv/releases/latest/download/BN-Stream-21.3-armeabi-v7a.apk">BN Stream 32-bit (armv7)</a>\n'
        '</body></html>\n' % (user, repo_zip, repo_zip, user, user))
    print('site ready:', SITE)


if __name__ == '__main__':
    main()
