# -*- coding: utf-8 -*-
"""One command per release - everything ships together and stays in sync.

  python tools/release.py --version 0.1.8 --notes "what changed"

 1. version -> addon.xml (plugin.video.nova)
 2. build zip + site (publish.py, also regenerates the user guide)
 3. full test suite on testkodi                          (stops on failure)
 4. Android APKs with the build embedded (make_apk.py)
 5. Windows installer (make_windows.py) + silent install + test suite on the installed copy
 6. git commit + push main, push site to gh-pages, GitHub release with APKs, setup and zip
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
VENV = os.path.join(ROOT, '.venv11', 'Scripts', 'python.exe')     # Pillow for the APK artwork
GH_USER = 'bennymat93'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'


def run(*a, cwd=ROOT):
    print('>', ' '.join(a[1:3]) if a[0] in (PY, VENV) else ' '.join(a[:3]), flush=True)
    subprocess.check_call(list(a), cwd=cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--notes', required=True, help='one line: what changed (commit + release notes)')
    ap.add_argument('--skip-installed-test', action='store_true')
    a = ap.parse_args()
    v = a.version
    ax = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'addon.xml')
    s = open(ax, encoding='utf-8').read()
    open(ax, 'w', encoding='utf-8').write(re.sub(r'(name="NovaTV" version=")[^"]+', r'\g<1>' + v, s, count=1))

    run(PY, 'tools/publish.py', '--gh-user', GH_USER, '--version', v)
    run(PY, 'tools/test_suite.py', '--version', v)
    run(PY, 'tools/make_guide.py')                     # now includes this run's test results
    shutil.copy(os.path.join(ROOT, 'docs', 'guide.html'), os.path.join(ROOT, 'site', 'guide.html'))
    run(VENV if os.path.exists(VENV) else PY, 'tools/make_apk.py', '--version', v)
    run(PY, 'tools/make_windows.py', '--version', v)
    if not a.skip_installed_test:
        inst = os.path.join(ROOT, 'work', 'wintest')
        subprocess.call(['taskkill', '/IM', 'kodi.exe', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run(os.path.join(ROOT, 'dist', 'BN-Stream-Setup-%s.exe' % v), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/DIR=' + inst, '/TASKS=')
        run(PY, 'tools/test_suite.py', '--version', v, '--installed', inst)

    msg = 'v%s: %s%s' % (v, a.notes, TRAILER)
    run('git', 'add', '-A')
    run('git', 'commit', '-q', '-m', msg)
    run('git', 'push', '-q', 'origin', 'main')
    ghp = os.path.join(ROOT, 'work', 'ghp')
    for n in os.listdir(ghp):
        if n != '.git':
            p = os.path.join(ghp, n)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    shutil.copytree(os.path.join(ROOT, 'site'), ghp, dirs_exist_ok=True)
    run('git', 'add', '-A', cwd=ghp)
    run('git', 'commit', '-q', '-m', 'Site v%s%s' % (v, TRAILER), cwd=ghp)
    run('git', 'push', '-q', 'origin', 'gh-pages', cwd=ghp)
    d = os.path.join(ROOT, 'dist')
    assets = [os.path.join(d, n) for n in ('BN-Stream-21.3-arm64-v8a.apk', 'BN-Stream-21.3-armeabi-v7a.apk',
                                           'BN-Stream-Setup-%s.exe' % v, 'NovaTV-%s.zip' % v)]
    run('gh', 'release', 'create', 'v' + v, *assets, '--title', 'BN Stream %s' % v, '--notes',
        '%s\n\n* Android: BN Stream APK (build pre-installed, ready on first start)\n'
        '* Windows: BN-Stream-Setup-%s.exe (Kodi + build, ready after install)\n'
        '* Guide: https://%s.github.io/novatv/guide.html' % (a.notes, v, GH_USER))
    print('released', v)


if __name__ == '__main__':
    main()
