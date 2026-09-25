# -*- coding: utf-8 -*-
"""Keeps the NovaTV subtitle server running on the PC.

  pythonw supervisor.py            run (no console window) - used by autostart
  python  supervisor.py install    autostart at Windows sign-in (absolute paths) + start now
  python  supervisor.py uninstall  remove autostart and stop
  python  supervisor.py status     is it running?

Restarts the server whenever it exits or stops answering /health (crash, GPU driver reset,
network change after sleep), and writes everything to server/logs/server.log (rotated).
"""
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, 'logs')
LOG = os.path.join(LOGS, 'server.log')
PORT = 8765
LOCK = os.path.join(LOGS, 'supervisor.pid')
TASK = 'NovaTV Subtitle Server'
STARTUP = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')


def python(windowless=False):
    exe = sys.executable
    d = os.path.dirname(exe)
    name = 'pythonw.exe' if windowless else 'python.exe'
    return os.path.join(d, name) if os.path.exists(os.path.join(d, name)) else exe


def note(msg):
    os.makedirs(LOGS, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('%s [supervisor] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))


def rotate():
    if os.path.exists(LOG) and os.path.getsize(LOG) > 5 * 1024 * 1024:
        old = LOG + '.1'
        if os.path.exists(old):
            os.remove(old)
        os.replace(LOG, old)


def healthy(timeout=5):
    try:
        return urllib.request.urlopen('http://127.0.0.1:%d/health' % PORT, timeout=timeout).status == 200
    except Exception:
        return False


def pid_alive(pid):
    out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'], capture_output=True, text=True,
                         creationflags=0x08000000).stdout
    return str(pid) in out


def already_running():
    try:
        pid = int(open(LOCK).read().strip())
        return pid != os.getpid() and pid_alive(pid)
    except Exception:
        return False


def run():
    os.makedirs(LOGS, exist_ok=True)
    if already_running():
        return
    open(LOCK, 'w').write(str(os.getpid()))
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    backoff, fails = 5, 0
    while True:
        rotate()
        if healthy(2):                      # someone started a server by hand: just watch it
            time.sleep(30)
            continue
        note('starting server')
        started = time.time()
        with open(LOG, 'a', encoding='utf-8') as out:
            p = subprocess.Popen([python(), os.path.join(HERE, 'nova_subs.py'), 'serve', '--port', str(PORT)],
                                 cwd=HERE, env=env, stdout=out, stderr=subprocess.STDOUT, creationflags=0x08000000)
        misses = 0
        while p.poll() is None:
            time.sleep(15)
            if time.time() - started < 120:  # model warm-up
                continue
            misses = 0 if healthy(10) else misses + 1
            if misses >= 4:                    # alive but deaf for a minute: restart it
                note('server not answering - restarting')
                p.kill()
                break
        code = p.poll()
        note('server exited (code %s) after %.0f s' % (code, time.time() - started))
        fails = fails + 1 if time.time() - started < 60 else 0
        time.sleep(min(300, backoff * (2 ** min(fails, 6))))


def install():
    """autostart via a Startup-folder shortcut to pythonw (no admin rights, no console window)"""
    lnk = os.path.join(STARTUP, TASK + '.lnk')
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{exe}';"
          "$s.Arguments='\"{script}\"';$s.WorkingDirectory='{wd}';$s.WindowStyle=7;"
          "$s.Description='Keeps the NovaTV AI subtitle server running';$s.Save()").format(
        lnk=lnk, exe=python(True), script=os.path.abspath(__file__), wd=HERE)
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
    print('autostart:', lnk, '->', python(True), os.path.abspath(__file__))
    if not already_running():
        subprocess.Popen([python(True), os.path.abspath(__file__)], cwd=HERE, creationflags=0x00000008 | 0x08000000)
    for _ in range(60):
        if healthy(3):
            print('server is running: http://127.0.0.1:%d/health' % PORT)
            return
        time.sleep(3)
    print('server did not answer yet - see', LOG)


def uninstall():
    lnk = os.path.join(STARTUP, TASK + '.lnk')
    if os.path.exists(lnk):
        os.remove(lnk)
    stop()
    print('autostart removed')


def stop():
    for pidfile in (LOCK,):
        try:
            subprocess.run(['taskkill', '/PID', open(pidfile).read().strip(), '/T', '/F'], capture_output=True)
        except Exception:
            pass


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if cmd == 'install':
        install()
    elif cmd == 'uninstall':
        uninstall()
    elif cmd == 'status':
        print('running' if healthy() else 'NOT running', '| log:', LOG)
    else:
        run()
