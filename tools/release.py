# -*- coding: utf-8 -*-
"""One command per release - everything ships together and stays in sync.

  python tools/release.py --version 0.1.8 --notes "what changed"

 1. version -> addon.xml (plugin.video.nova)
 2. build zip + site (publish.py, also regenerates the user guide)
 3. full test suite on testkodi                          (stops on failure)
 4. Android APKs with the build embedded (make_apk.py) + emulator smoke test (android_test.py)
 5. Windows installer (make_windows.py) + silent install + test suite on the installed copy
 6. git commit + push main, push site to gh-pages, GitHub release with APKs, setup and zip
"""
import argparse
import json
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


STATE = os.path.join(ROOT, 'work', 'release_state.json')


def state(v):
    try:
        st = json.load(open(STATE, encoding='utf-8'))
        return st if st.get('version') == v else {'version': v, 'done': []}
    except Exception:
        return {'version': v, 'done': []}


def step(v, name, fn):
    """run a release step once: a stopped release rerun with the same version continues where it stopped"""
    st = state(v)
    if name in st['done']:
        print('= %s (done earlier)' % name, flush=True)
        return
    fn()
    st['done'].append(name)
    json.dump(st, open(STATE, 'w', encoding='utf-8'))


def both(*cmds):
    """run commands in parallel; stop the release if any fails"""
    procs = [(c, subprocess.Popen(c, cwd=ROOT)) for c in cmds]
    bad = [' '.join(c[1:3]) for c, p in procs if p.wait() != 0]
    if bad:
        raise SystemExit('failed: %s' % ', '.join(bad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--notes', required=True, help='one line: what changed (commit + release notes)')
    ap.add_argument('--skip-installed-test', action='store_true')
    ap.add_argument('--skip-android-test', action='store_true')
    a = ap.parse_args()
    v = a.version
    ax = os.path.join(ROOT, 'addons', 'plugin.video.nova', 'addon.xml')
    s = open(ax, encoding='utf-8').read()
    open(ax, 'w', encoding='utf-8').write(re.sub(r'(name="NovaTV" version=")[^"]+', r'\g<1>' + v, s, count=1))

    # the build is always remade (a fix after a stop must be in it); every other step runs once per version:
    # a stopped release rerun with the same version continues where it stopped, the tests from the failed check
    run(PY, 'tools/publish.py', '--gh-user', GH_USER, '--version', v)
    step(v, 'tests', lambda: run(PY, 'tools/test_suite.py', '--version', v, '--stop-on-fail', '--resume'))
    run(PY, 'tools/make_guide.py')                     # now includes this run's test results
    shutil.copy(os.path.join(ROOT, 'docs', 'guide.html'), os.path.join(ROOT, 'site', 'guide.html'))
    # APKs and the Windows installer build at the same time; then the emulator test runs next to the installed-copy test
    step(v, 'packages', lambda: both([VENV if os.path.exists(VENV) else PY, 'tools/make_apk.py', '--version', v],
                                     [PY, 'tools/make_windows.py', '--version', v]))
    if not a.skip_android_test:
        step(v, 'android', lambda: run(PY, 'tools/android_test.py', '--version', v))
    if not a.skip_installed_test:
        def installed():
            inst = os.path.join(ROOT, 'work', 'wintest')
            subprocess.call(['taskkill', '/IM', 'kodi.exe', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            run(os.path.join(ROOT, 'dist', 'BN-Stream-Setup-%s.exe' % v), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                '/DIR=' + inst, '/TASKS=')
            run(PY, 'tools/test_suite.py', '--version', v, '--installed', inst, '--stop-on-fail', '--resume')
        step(v, 'installed', installed)

    msg = 'v%s: %s%s' % (v, a.notes, TRAILER)
    run('git', 'add', '-A')
    run('git', 'commit', '-q', '-m', msg)
    run(PY, 'tools/make_guide.py')                     # version history now contains this release
    shutil.copy(os.path.join(ROOT, 'docs', 'guide.html'), os.path.join(ROOT, 'site', 'guide.html'))
    run('git', 'add', 'docs')
    run('git', 'commit', '-q', '-m', 'Guide: regenerate for v%s%s' % (v, TRAILER))
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
