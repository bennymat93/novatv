# -*- coding: utf-8 -*-
"""Stability audit of every NovaTV provider, in a real Kodi (testkodi).

For each provider: installed? -> main menu lists items? -> search returns results (if it has
search)? -> one video actually plays (position advances)? The verdict goes to
addons/plugin.video.nova/resources/providers_status.json (read by providers.py and make_build.py)
and docs/audit/providers.csv.

  python tools/provider_audit.py --version X        (installs dist/NovaTV-X.zip into testkodi first)
"""
import argparse
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_suite as ts  # noqa: E402

ROOT = ts.ROOT
NOVA = os.path.join(ROOT, 'addons', 'plugin.video.nova')
SEARCH_LIMIT = 12          # the hub waits at most this long per source
QUERIES = {'idanplus': 'חדשות', 'youtube': 'Мосфильм', 'archive': 'Chaplin', 'imdbtrailers': 'Batman',
           'dailymotion': 'news', 'vimeo': 'nature', 'lbry': 'science', 'ted': 'climate'}


def providers():
    import ast
    tree = ast.parse(open(os.path.join(NOVA, 'resources', 'lib', 'providers.py'), encoding='utf-8').read())
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'PROVIDERS')
    return [{'id': p[0], 'addon': p[1], 'cat': p[3], 'search': p[4]} for p in ast.literal_eval(node.value)]


def close_dialogs():
    for _ in range(3):
        try:
            ts.rpc('Input.ExecuteAction', action='close', timeout=10)
        except Exception:
            pass
        time.sleep(0.5)


def listdir(path, timeout=60):
    try:
        r = ts.rpc('Files.GetDirectory', timeout=timeout, directory=path, media='video', properties=['title', 'file'])
    except Exception as e:
        return None, 'timeout/%s' % type(e).__name__
    if 'error' in r:
        return None, r['error'].get('message', 'error')
    return r['result'].get('files') or [], ''


def installed(aid):
    r = ts.rpc('Addons.GetAddonDetails', addonid=aid, properties=['enabled', 'version'])
    return r.get('result', {}).get('addon', {}).get('version') if 'result' in r and r['result']['addon']['enabled'] else None


def install(aid):
    ts.rpc('Addons.ExecuteAddon', addonid='plugin.video.nova', params='?a=lib_install&id=%s' % aid)
    for _ in range(90):
        time.sleep(2)
        if installed(aid):
            close_dialogs()
            return True
    close_dialogs()
    return False


SKIP = re.compile(r'(?i)(search|settings|history|login|log in|sign|account|user|profile|favou?rite|next page|clear|playlist|'
                  r'subscri|watch later|my |חיפוש|הגדרות|היסטוריה|כניסה|התחבר|משתמש|חשבון|מועדפים|הבא|הרשמ|'
                  r'поиск|настрой|вход|аккаунт|^[-=_ ]*$|-{3,})')


def find_playable(items, depth=2, want=3):
    """up to `want` real videos within `depth` folder levels"""
    out = []
    for it in items[:30]:
        lab = re.sub(r'\[/?[A-Z]+[^\]]*\]', '', it.get('label') or '')
        if SKIP.search(lab) or SKIP.search(it.get('file') or ''):
            continue
        if it.get('filetype') == 'file':
            out.append(it)
            if len(out) >= want:
                return out
    if depth:
        for it in items[:6]:
            lab = re.sub(r'\[/?[A-Z]+[^\]]*\]', '', it.get('label') or '')
            if it.get('filetype') == 'directory' and not SKIP.search(lab + (it.get('file') or '')):
                sub, _ = listdir(it['file'], 45)
                close_dialogs()
                if sub:
                    out += find_playable(sub, depth - 1, want - len(out))
                    if len(out) >= want:
                        break
    return out[:want]


def try_play(item):
    ts.rpc('Player.Stop', playerid=1)
    ts.rpc('Player.Open', item={'file': item['file']})
    pos = []
    for _ in range(20):
        time.sleep(2)
        w = ts.rpc('GUI.GetProperties', properties=['currentwindow']).get('result', {}).get('currentwindow', {})
        if w.get('id') == 12000:                 # "choose file / quality" list: pick the first, like a viewer
            ts.rpc('Input.Select')
            continue
        p = ts.rpc('Player.GetActivePlayers').get('result') or []
        if p:
            t = ts.rpc('Player.GetProperties', playerid=p[0]['playerid'], properties=['time']).get('result', {}).get('time', {})
            pos.append(t.get('hours', 0) * 3600 + t.get('minutes', 0) * 60 + t.get('seconds', 0))
            if len(pos) >= 3 and pos[-1] > pos[0]:
                ts.rpc('Player.Stop', playerid=p[0]['playerid'])
                time.sleep(2)
                return 'ok'
    for p in ts.rpc('Player.GetActivePlayers').get('result') or []:
        ts.rpc('Player.Stop', playerid=p['playerid'])
    close_dialogs()
    return 'no playback'


def audit(p):
    row = {'id': p['id'], 'addon': p['addon'], 'cat': p['cat'], 'version': '', 'menu': '', 'search': '', 'play': '', 'note': ''}
    v = installed(p['addon'])
    if not v:
        if not install(p['addon']):
            row['note'] = 'install failed'
            return row
        v = installed(p['addon'])
    row['version'] = v
    items, err = listdir('plugin://%s/' % p['addon'])
    close_dialogs()
    row['menu'] = len(items) if items is not None else 'fail: ' + err
    found = items or []
    if p['search']:
        from urllib.parse import quote, quote_plus
        q = QUERIES.get(p['id'], 'news')
        dm = ('https://api.dailymotion.com/videos?fields=description,duration,id,owner.username,taken_time,'
              'thumbnail_large_url,title,views_total&search={q}&sort=relevance&limit=25&family_filter=1&localization=en_EN&page=1')
        if p['search'] == 'internal:yt':
            url = 'plugin://plugin.video.nova/?a=yt_search&q=' + quote_plus(q)
        elif p['search'] == 'internal:ia':
            url = 'plugin://plugin.video.nova/?a=ia_search&q=' + quote_plus(q)
        else:
            url = p['search'].format(q=quote(q), dm=quote_plus(dm.format(q=quote_plus(q))))
        t0 = time.time()
        res, err = listdir(url)
        took = time.time() - t0
        close_dialogs()
        row['search'] = len(res) if res is not None else 'fail: ' + err
        if res is not None and took > SEARCH_LIMIT:
            row['search'] = 'slow: %.0fs' % took
        if res:
            found = res                     # search results are the safest place to find a video
    hits = find_playable(found, depth=3) if found else []
    row['play'] = 'nothing playable found'
    for hit in hits:
        row['play'] = try_play(hit)
        row['note'] = (hit.get('label') or '')[:60]
        if row['play'] == 'ok':
            break
    return row


def restart_kodi():
    ts.kill_kodi()
    ts.start_kodi()


def verdict(row):
    menu_ok = isinstance(row['menu'], int) and row['menu'] > 0
    search_ok = row['search'] == '' or (isinstance(row['search'], int) and row['search'] > 0)
    play_ok = row['play'] == 'ok'          # stable = a video really played
    return menu_ok and search_ok and play_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    ts.install(a.version)
    ts.start_kodi()
    rows, status = [], {}
    sp = os.path.join(NOVA, 'resources', 'providers_status.json')
    old = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
    for p in providers():
        if a.only and p['id'] not in a.only.split(','):
            continue
        t = time.time()
        try:
            row = audit(p)
        except Exception as e:
            row = {'id': p['id'], 'addon': p['addon'], 'cat': p['cat'], 'version': '', 'menu': 'fail', 'search': '',
                   'play': '', 'note': repr(e)[:80]}
            try:
                restart_kodi()
            except Exception:
                pass
        row['stable'] = verdict(row)
        if 'timeout' in '%s %s' % (row['menu'], row['search']) or row['play'] == 'no playback':
            restart_kodi()                   # a stuck dialog must not fail the next provider
        rows.append(row)
        status[p['id']] = {'addon': p['addon'], 'stable': row['stable'], 'checked': time.strftime('%Y-%m-%d'),
                           'menu': row['menu'], 'search': row['search'], 'play': row['play']}
        print('%-4s %-14s menu=%-6s search=%-6s play=%-22s %5.0fs  %s' % ('OK' if row['stable'] else 'BAD', p['id'], row['menu'],
              row['search'], row['play'], time.time() - t, row['note']), flush=True)
    old.update(status)
    json.dump(old, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(ROOT, 'docs', 'audit'), exist_ok=True)
    with open(os.path.join(ROOT, 'docs', 'audit', 'providers.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['id', 'addon', 'cat', 'version', 'menu', 'search', 'play', 'stable', 'note'])
        w.writeheader()
        w.writerows(rows)
    print('\n%d/%d stable' % (sum(r['stable'] for r in rows), len(rows)))
    ts.kill_kodi()


if __name__ == '__main__':
    main()
