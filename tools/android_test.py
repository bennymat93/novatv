# -*- coding: utf-8 -*-
"""Android smoke test on the emulator (AVD "bn", Android 14 x86_64, arm64 via ndk_translation).

  python tools/android_test.py --version 0.2.2 [--apk dist/BN-Stream-21.3-arm64-v8a.apk] [--keep]

Fresh install of the APK -> first start unpacks the build -> Kodi reaches the home screen with the BN skin,
NovaTV <version> and its service run, the All_Subs guards and the AI button are in place, no crash (logcat)
and no Python traceback from BN add-ons. Screenshot in work/android/smoke.png.
"""
import argparse
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK = os.path.join(ROOT, 'work', 'android', 'sdk')
ADB = os.path.join(SDK, 'platform-tools', 'adb.exe')
EMU = os.path.join(SDK, 'emulator', 'emulator.exe')
PKG = 'org.bn.stream'
HOME = '/sdcard/Android/data/%s/files/.kodi' % PKG
RESULTS = []


def adb(*a, timeout=120, check=False):
    r = subprocess.run([ADB] + list(a), capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout)
    if check and r.returncode:
        raise RuntimeError('adb %s: %s' % (' '.join(a), r.stderr.strip()[:200]))
    return r.stdout


def sh(cmd, timeout=60):
    return adb('shell', cmd, timeout=timeout)


def result(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print('%-4s %-40s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def boot():
    if 'emulator-' in adb('devices'):
        return False
    env = dict(os.environ, ANDROID_SDK_ROOT=SDK, ANDROID_AVD_HOME=os.path.join(ROOT, 'work', 'android', 'avd'))
    subprocess.Popen([EMU, '-avd', 'bn', '-no-window', '-no-audio', '-no-snapshot-save', '-no-boot-anim', '-gpu', 'swiftshader_indirect'],
                     env=env, stdout=open(os.path.join(ROOT, 'work', 'android', 'emu.log'), 'w'), stderr=subprocess.STDOUT)
    adb('wait-for-device', timeout=300)
    for _ in range(200):
        if sh('getprop sys.boot_completed').strip() == '1':
            time.sleep(10)
            return True
        time.sleep(3)
    raise RuntimeError('emulator did not boot')


def kodi_log():
    return sh('cat %s/temp/kodi.log' % HOME, timeout=60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--apk', default=os.path.join(ROOT, 'dist', 'BN-Stream-21.3-arm64-v8a.apk'))
    ap.add_argument('--keep', action='store_true', help='leave the emulator running')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    started = boot()
    try:
        adb('uninstall', PKG, timeout=120)
        # a fresh install: leftovers of an earlier install belong to another app uid and cannot be overwritten
        adb('root', timeout=60)
        time.sleep(3)
        sh('rm -rf /sdcard/Android/data/%s /data/media/0/Android/data/%s' % (PKG, PKG))
        out = adb('install', '-r', '-g', a.apk, timeout=600)
        result('APK installs', 'Success' in out, os.path.basename(a.apk))
        # what the viewer does on the first start: allow Kodi's access to files (its own prompt + system dialog)
        sh('appops set --uid %s MANAGE_EXTERNAL_STORAGE allow' % PKG)
        adb('logcat', '-c')
        act = sh('cmd package resolve-activity --brief %s | tail -1' % PKG).strip()
        sh('am start -n %s' % act)
        log, t0 = '', time.time()
        while time.time() - t0 < 600:                # first start unpacks ~50 MB and installs the TV add-on
            time.sleep(10)
            log = kodi_log()
            if re.search(r'startup status: \d+ problems', log) or 'FATAL EXCEPTION' in adb('logcat', '-d', '-b', 'crash'):
                break
        crash = adb('logcat', '-d', '-b', 'crash')
        open(os.path.join(ROOT, 'work', 'android', 'crash.log'), 'w', encoding='utf-8').write(crash)
        open(os.path.join(ROOT, 'work', 'android', 'logcat.log'), 'w', encoding='utf-8').write(adb('logcat', '-d', timeout=120))
        result('No crash (logcat)', PKG not in crash and 'Fatal signal' not in crash, crash.strip()[:200])
        result('Kodi running', bool(sh('pidof %s' % PKG).strip()))
        m = re.search(r'plugin\.video\.nova v([\d.]+) installed', log)
        result('Build unpacked, NovaTV version', bool(m) and m.group(1) == a.version, m.group(1) if m else 'not found')
        result('BN skin loaded', 'skin.fentastic' in log)
        st = re.search(r'startup status: (\d+) problems (.*)', log)
        result('"BN Stream ready" status announced', bool(st), st.group(0)[:120] if st else 'no announcement in %ds' % (time.time() - t0))
        osd = sh('grep -c ai_subs_now %s/addons/skin.fentastic/xml/DialogSubtitles.xml' % HOME).strip()
        result('AI subtitle button in the skin', osd not in ('', '0'), osd)
        guard = sh('grep -c "BN guard v" %s/addons/service.subtitles.All_Subs/autosub.py' % HOME).strip()
        result('All_Subs guards', guard not in ('', '0'), guard)
        ours = [l for l in log.splitlines() if ('NovaTV' in l or 'plugin.video.nova' in l) and ('Traceback' in l or ' error ' in l.lower())
                and 'GetDirectory' not in l]
        result('No errors from BN add-ons', not ours, ours[0][:160] if ours else '')
        adb('exec-out', 'screencap', '-p', timeout=60)
        with open(os.path.join(ROOT, 'work', 'android', 'smoke.png'), 'wb') as f:
            f.write(subprocess.run([ADB, 'exec-out', 'screencap', '-p'], capture_output=True, timeout=60).stdout)
        open(os.path.join(ROOT, 'work', 'android', 'smoke_kodi.log'), 'w', encoding='utf-8').write(log)
    finally:
        if started and not a.keep:
            adb('emu', 'kill')
    passed = sum(1 for r in RESULTS if r[1])
    print('\n%d/%d passed' % (passed, len(RESULTS)))
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == '__main__':
    main()
