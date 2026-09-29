# -*- coding: utf-8 -*-
"""Google Drive screens and actions (NovaTV menu "Google Drive", Accounts row, service jobs)."""
import os
import time

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from .common import ADDON, PROFILE, load, save, log, ui_lang, now_str, monitor
from . import gdrive

S = {
    'title': ('Google Drive', 'Google Drive', 'Google Drive'),
    'connect': ('התחבר לחשבון Google', 'Sign in to Google', 'Войти в аккаунт Google'),
    'connected': ('מחובר: %s', 'Signed in: %s', 'Вход выполнен: %s'),
    'disconnect': ('התנתק מ-Google Drive', 'Sign out of Google Drive', 'Выйти из Google Drive'),
    'login_head': ('התחברות ל-Google Drive', 'Sign in to Google Drive', 'Вход в Google Drive'),
    'login_body': ('בטלפון או במחשב היכנס אל:[CR][B]%s[/B][CR]והזן את הקוד:[CR][B][COLOR gold]%s[/COLOR][/B]',
                   'On your phone or computer open:[CR][B]%s[/B][CR]and enter the code:[CR][B][COLOR gold]%s[/COLOR][/B]',
                   'На телефоне или компьютере откройте:[CR][B]%s[/B][CR]и введите код:[CR][B][COLOR gold]%s[/COLOR][/B]'),
    'login_ok': ('מחובר ל-Google Drive', 'Signed in to Google Drive', 'Вход в Google Drive выполнен'),
    'login_fail': ('ההתחברות נכשלה', 'Sign-in failed', 'Вход не выполнен'),
    'no_client': ('Google Drive לא הוגדר בבילד הזה (חסר OAuth client)', 'Google Drive is not set up in this build (no OAuth client)',
                  'Google Drive не настроен в этой сборке (нет OAuth client)'),
    'backup_now': ('גיבוי עכשיו ל-Drive', 'Back up to Drive now', 'Резервная копия в Drive сейчас'),
    'restore': ('שחזור מגיבוי ב-Drive', 'Restore a backup from Drive', 'Восстановить из Drive'),
    'sync_now': ('סנכרון בין המכשירים (מועדפים, היסטוריה, IPTV)', 'Sync between devices (favourites, history, IPTV)',
                 'Синхронизация устройств (избранное, история, IPTV)'),
    'subs_up': ('העלאת הכתוביות שנוצרו ל-Drive', 'Upload created subtitles to Drive', 'Загрузить созданные субтитры в Drive'),
    'browse': ('תיקיית BN Stream ב-Drive', 'BN Stream folder on Drive', 'Папка BN Stream в Drive'),
    'auto': ('גיבוי שבועי אוטומטי ל-Drive: %s', 'Weekly automatic backup to Drive: %s', 'Еженедельная копия в Drive: %s'),
    'on': ('פעיל', 'on', 'вкл'), 'off': ('כבוי', 'off', 'выкл'),
    'working': ('עובד מול Google Drive...', 'Working with Google Drive...', 'Работа с Google Drive...'),
    'backup_done': ('הגיבוי הועלה ל-Drive (%d קבצים)', 'Backup uploaded to Drive (%d files)', 'Копия загружена в Drive (%d файлов)'),
    'no_backups': ('אין גיבויים ב-Drive', 'No backups on Drive', 'В Drive нет копий'),
    'synced': ('סונכרן: %d מועדפים, %d בהיסטוריה', 'Synced: %d favourites, %d history items', 'Синхронизировано: %d избранных, %d в истории'),
    'subs_done': ('הועלו %d כתוביות', '%d subtitles uploaded', 'Загружено субтитров: %d'),
    'empty': ('התיקייה ריקה', 'The folder is empty', 'Папка пуста'),
    'error': ('שגיאה ב-Google Drive: %s', 'Google Drive error: %s', 'Ошибка Google Drive: %s'),
    'space': ('נפח: %s מתוך %s', 'Storage: %s of %s', 'Место: %s из %s'),
    'sign_first': ('התחבר קודם ל-Google Drive', 'Sign in to Google Drive first', 'Сначала войдите в Google Drive'),
}
SYNC_MERGED = ('favourites.json', 'history.json', 'favourites_removed.json')
SYNC_LATEST = ('iptv.json', 'providers.json')           # whole-file settings: the newer copy wins
VIDEO_EXT = ('.mp4', '.mkv', '.avi', '.mov', '.ts', '.m4v', '.webm', '.mp3', '.flac', '.m4a')


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def client():
    """(client id, secret): the settings (manual override), else resources/gdrive_client.json shipped with the build
    (kept out of git: .gitignore; make_build / publish copy it from the working tree)"""
    cid, secret = ADDON.getSetting('gd_client_id').strip(), ADDON.getSetting('gd_client_secret').strip()
    if cid:
        return cid, secret
    try:
        import json
        with open(os.path.join(ADDON.getAddonInfo('path'), 'resources', 'gdrive_client.json'), encoding='utf-8') as f:
            c = json.load(f)
        c = c.get('installed') or c.get('web') or c          # also the file as downloaded from Google Cloud
        return c.get('client_id', ''), c.get('client_secret', '')
    except (OSError, ValueError):
        return '', ''


def drive():
    cid, secret = client()
    return gdrive.Drive(cid, secret, os.path.join(PROFILE, 'gdrive_token.json'))


def configured():
    return bool(client()[0])


def _note(msg, kind=xbmcgui.NOTIFICATION_INFO, ms=4000):
    xbmcgui.Dialog().notification('Google Drive', msg, kind, ms)


def _human(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return ('%.1f %s' % (n, unit)) if unit != 'B' else '%d B' % n
        n /= 1024.0


def _guard(fn):
    """every action: a clear message instead of a traceback; signs in first when needed"""
    def run(*a, **kw):
        if not configured():
            return xbmcgui.Dialog().ok('Google Drive', s('no_client'))
        try:
            return fn(*a, **kw)
        except gdrive.NotSignedIn:
            if login():
                return fn(*a, **kw)
        except gdrive.DriveError as e:
            log('google drive: %s' % e, xbmc.LOGWARNING)
            xbmcgui.Dialog().ok('Google Drive', s('error') % e)
        except Exception as e:                      # network down etc.
            log('google drive: %r' % e, xbmc.LOGWARNING)
            xbmcgui.Dialog().ok('Google Drive', s('error') % e)
    return run


# ------------------------------------------------------------ sign in / out
def login():
    if not configured():
        xbmcgui.Dialog().ok('Google Drive', s('no_client'))
        return False
    d = drive()
    try:
        info = d.start_login()
    except Exception as e:
        xbmcgui.Dialog().ok('Google Drive', '%s\n%s' % (s('login_fail'), e))
        return False
    pd = xbmcgui.DialogProgress()
    pd.create(s('login_head'), s('login_body') % (info['verification_url'], info['user_code']))
    mon = monitor()
    total = int(info.get('expires_in', 900))
    start, interval = time.time(), int(info.get('interval', 5))
    ok = False
    try:
        while time.time() - start < total and not pd.iscanceled():
            pd.update(int(100 * (time.time() - start) / total))
            if mon.waitForAbort(interval):
                break
            try:
                if d.poll_login(info['device_code']):
                    ok = True
                    break
            except gdrive.DriveError as e:
                xbmcgui.Dialog().ok('Google Drive', '%s\n%s' % (s('login_fail'), e))
                break
    finally:
        pd.close()
    if ok:
        _note(s('login_ok'))
        xbmc.executebuiltin('Container.Refresh')
    return ok


def logout():
    drive().logout()
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------ menu
def menu(handle, url):
    def row(label, target, folder=False, icon='DefaultAddonService.png', plot=''):
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': icon, 'thumb': icon})
        if plot:
            li.getVideoInfoTag().setPlot(plot)
        xbmcplugin.addDirectoryItem(handle, target, li, folder)
    if not configured():
        row('[COLOR grey]%s[/COLOR]' % s('no_client'), url(a='noop'))
        return xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    d = drive()
    if not d.signed_in():
        row('[COLOR gold]%s[/COLOR]' % s('connect'), url(a='gd', do='login'), icon='DefaultUser.png')
        return xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    plot = ''
    try:
        used, limit = d.usage()
        plot = s('space') % (_human(used), _human(limit) if limit else '∞')
    except Exception:
        pass
    row('[COLOR limegreen]%s[/COLOR]' % (s('connected') % (d.account() or 'Google')), url(a='noop'), plot=plot,
        icon='DefaultUser.png')
    row(s('backup_now'), url(a='gd', do='backup'))
    row(s('restore'), url(a='gd', do='restore'))
    row(s('sync_now'), url(a='gd', do='sync'))
    row(s('subs_up'), url(a='gd', do='subs'))
    row(s('browse'), url(a='gd_browse'), folder=True, icon='DefaultFolder.png')
    auto = ADDON.getSetting('gd_auto') != 'false'
    row(s('auto') % s('on' if auto else 'off'), url(a='gd', do='auto_toggle'))
    row('[COLOR grey]%s[/COLOR]' % s('disconnect'), url(a='gd', do='logout'))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def action(do):
    {'login': login, 'logout': logout, 'backup': backup_now, 'restore': restore, 'sync': sync_now,
     'subs': upload_subtitles, 'auto_toggle': _toggle_auto}[do]()


def _toggle_auto():
    ADDON.setSetting('gd_auto', 'false' if ADDON.getSetting('gd_auto') != 'false' else 'true')
    xbmc.executebuiltin('Container.Refresh')


# ------------------------------------------------------------ backups
def _backup(d, keep):
    from . import backup
    name = 'BN-backup-%s.zip' % time.strftime('%Y%m%d-%H%M')
    tmp = os.path.join(xbmcvfs.translatePath('special://temp/'), name)
    n = backup.make_zip(tmp)
    try:
        folder = d.folder('Backups')
        d.upload(tmp, folder, name, 'application/zip')
        for old in gdrive.prune(d.list(folder), keep):
            d.delete(old['id'])
    finally:
        os.remove(tmp)
    return n


@_guard
def backup_now():
    pd = xbmcgui.DialogProgressBG()
    pd.create('Google Drive', s('working'))
    try:
        n = _backup(drive(), int(ADDON.getSetting('gd_keep') or 5))
    finally:
        pd.close()
    _note(s('backup_done') % n)


@_guard
def restore():
    from . import backup
    d = drive()
    files = [f for f in d.list(d.folder('Backups')) if f['name'].endswith('.zip')]
    if not files:
        return xbmcgui.Dialog().ok('Google Drive', s('no_backups'))
    labels = ['%s   [COLOR grey]%s · %s[/COLOR]' % (f['name'], f.get('modifiedTime', '')[:16].replace('T', ' '),
                                                    _human(int(f.get('size', 0)))) for f in files]
    i = xbmcgui.Dialog().select(s('restore'), labels)
    if i < 0:
        return
    local = os.path.join(xbmcvfs.translatePath('special://temp/'), 'bn_restore.zip')
    pd = xbmcgui.DialogProgressBG()
    pd.create('Google Drive', s('working'))
    try:
        d.download(files[i]['id'], local)
    finally:
        pd.close()
    backup.restore_zip(local)


def auto(every_days=7):
    """service: weekly Drive backup + sync, silently (never a dialog)"""
    if not configured() or ADDON.getSetting('gd_auto') == 'false':
        return
    d = drive()
    if not d.signed_in():
        return
    try:
        sync(d)
        last = float(load('gdrive_state.json', {}).get('last_backup', 0))
        if time.time() - last >= every_days * 86400:
            _backup(d, int(ADDON.getSetting('gd_keep') or 5))
            save('gdrive_state.json', dict(load('gdrive_state.json', {}), last_backup=time.time()))
            log('google drive: weekly backup uploaded')
    except Exception as e:
        log('google drive auto: %s' % e, xbmc.LOGWARNING)


# ------------------------------------------------------------ sync between devices
def _remote_json(d, folder, name):
    import json
    found = d.list(folder, name=name)
    if not found:
        return None, None
    tmp = os.path.join(xbmcvfs.translatePath('special://temp/'), 'gd_' + name)
    d.download(found[0]['id'], tmp)
    try:
        with open(tmp, encoding='utf-8') as f:
            return json.load(f), found[0].get('modifiedTime', '')
    finally:
        os.remove(tmp)


def _push(d, folder, name, data):
    import json
    tmp = os.path.join(xbmcvfs.translatePath('special://temp/'), 'gd_' + name)
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    try:
        d.upload(tmp, folder, name, 'application/json', replace=True)
    finally:
        os.remove(tmp)


def sync(d):
    folder = d.folder('Sync')
    fav_r, _ = _remote_json(d, folder, 'favourites.json')
    his_r, _ = _remote_json(d, folder, 'history.json')
    rem_r, _ = _remote_json(d, folder, 'favourites_removed.json')
    removed = gdrive.merge_removed(load('favourites_removed.json', []), rem_r or [])
    favs = gdrive.merge_favourites(load('favourites.json', []), fav_r or [], removed)
    hist = gdrive.merge_history(load('history.json', []), his_r or [])
    for name, data in (('favourites.json', favs), ('history.json', hist), ('favourites_removed.json', removed)):
        save(name, data)
        _push(d, folder, name, data)
    state = load('gdrive_state.json', {})
    for name in SYNC_LATEST:                     # whole settings files: a change on one device is copied to the others
        path = os.path.join(PROFILE, name)
        local_changed = os.path.exists(path) and os.path.getmtime(path) > state.get('mtime_' + name, 0)
        remote, rtime = _remote_json(d, folder, name)
        remote_changed = remote is not None and rtime != state.get('rtime_' + name)
        if remote_changed and not local_changed:
            save(name, remote)                   # another device changed it
        elif local_changed:
            _push(d, folder, name, load(name, {}))
            rtime = (d.list(folder, name=name) or [{}])[0].get('modifiedTime', '')
        if os.path.exists(path):
            state['mtime_' + name] = os.path.getmtime(path)
        state['rtime_' + name] = rtime
    save('gdrive_state.json', state)
    return len(favs), len(hist)


@_guard
def sync_now():
    pd = xbmcgui.DialogProgressBG()
    pd.create('Google Drive', s('working'))
    try:
        n_f, n_h = sync(drive())
    finally:
        pd.close()
    _note(s('synced') % (n_f, n_h))


# ------------------------------------------------------------ subtitles
@_guard
def upload_subtitles():
    from . import player_menus
    d = drive()
    local_dir = player_menus.subs_folder()
    folder = d.folder('Subtitles')
    have = {f['name'] for f in d.list(folder)}
    n = 0
    pd = xbmcgui.DialogProgressBG()
    pd.create('Google Drive', s('working'))
    try:
        names = sorted(f for f in os.listdir(local_dir) if f.lower().endswith(('.srt', '.ass', '.ssa', '.vtt')))
        for i, name in enumerate(names):
            if name not in have:
                d.upload(os.path.join(local_dir, name), folder, name, 'application/x-subrip')
                n += 1
            pd.update(int(100 * (i + 1) / max(1, len(names))))
    finally:
        pd.close()
    _note(s('subs_done') % n)


# ------------------------------------------------------------ browse the BN Stream folder
def browse(handle, url, fid=''):
    if not configured() or not drive().signed_in():
        li = xbmcgui.ListItem('[COLOR gold]%s[/COLOR]' % (s('connect') if configured() else s('no_client')))
        xbmcplugin.addDirectoryItem(handle, url(a='gd', do='login') if configured() else url(a='noop'), li, False)
        return xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    d = drive()
    try:
        items = d.list(fid or d.folder())
    except Exception as e:
        log('google drive browse: %s' % e, xbmc.LOGWARNING)
        items = []
    if not items:
        xbmcplugin.addDirectoryItem(handle, url(a='noop'), xbmcgui.ListItem('[COLOR grey]%s[/COLOR]' % s('empty')), False)
    for f in sorted(items, key=lambda f: (f['mimeType'] != gdrive.FOLDER, f['name'].lower())):
        li = xbmcgui.ListItem(f['name'])
        if f['mimeType'] == gdrive.FOLDER:
            li.setArt({'icon': 'DefaultFolder.png'})
            xbmcplugin.addDirectoryItem(handle, url(a='gd_browse', id=f['id']), li, True)
        elif f['name'].lower().endswith(VIDEO_EXT):
            li.setArt({'icon': 'DefaultVideo.png'})
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle, url(a='gd_play', id=f['id'], name=f['name']), li, False)
        else:
            li.setArt({'icon': 'DefaultFile.png'})
            li.getVideoInfoTag().setPlot('%s · %s' % (_human(int(f.get('size', 0))), f.get('modifiedTime', '')[:16].replace('T', ' ')))
            target = url(a='gd', do='restore') if f['name'].endswith('.zip') else url(a='noop')
            xbmcplugin.addDirectoryItem(handle, target, li, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def play(handle, fid, name):
    """stream straight from Drive: Kodi sends the access token as a request header"""
    from urllib.parse import quote
    d = drive()
    token = d._access()
    li = xbmcgui.ListItem(name, path='%s/files/%s?alt=media|Authorization=%s' % (gdrive.API, fid, quote('Bearer ' + token)))
    xbmcplugin.setResolvedUrl(handle, True, li)


def remember_removed(kind, id):
    """a removed favourite stays removed on every device after the next sync"""
    data = [r for r in load('favourites_removed.json', []) if not (r.get('kind') == kind and str(r.get('id')) == str(id))]
    data.insert(0, {'kind': kind, 'id': id, 'removed': now_str()})
    save('favourites_removed.json', data[:1000])
