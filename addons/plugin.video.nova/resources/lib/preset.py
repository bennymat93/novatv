# -*- coding: utf-8 -*-
"""Password-locked pre-configured profile.

Admin: configure every account on one box -> "Create locked profile" -> choose password.
All account data (Real-Debrid, Trakt, IPTV, keys, subtitle server...) is packed with the
backup engine and encrypted (PBKDF2-SHA256 200k + HMAC-SHA256 stream + HMAC tag, stdlib only).
Users: "Unlock pre-configured profile" -> password -> everything is connected.
Without the password the user simply configures his own details as before.
Credentials are never stored in the repository in clear text.
"""
import hashlib
import hmac
import io
import os
import time
import zipfile

import xbmcgui
import xbmcvfs

from .common import PROFILE, ui_lang, load, save
from . import backup

MAGIC = b'NVP1'
LOCAL = os.path.join(PROFILE, 'preset.nvp')
SHIPPED = xbmcvfs.translatePath('special://home/addons/plugin.video.nova/resources/preset.nvp')
ITER = 200000

S = {
    'create': ('צור פרופיל מוגדר מראש (נעול בסיסמה)', 'Create locked pre-configured profile', 'Создать защищённый профиль'),
    'unlock': ('פתח פרופיל מוגדר מראש', 'Unlock pre-configured profile', 'Разблокировать готовый профиль'),
    'pw': ('סיסמה', 'Password', 'Пароль'),
    'pw2': ('הקלד שוב את הסיסמה', 'Repeat password', 'Повторите пароль'),
    'short': ('סיסמה חייבת להכיל לפחות 8 תווים', 'Password must be at least 8 characters', 'Минимум 8 символов'),
    'nomatch': ('הסיסמאות אינן תואמות', 'Passwords do not match', 'Пароли не совпадают'),
    'made': ('הפרופיל נוצר ונשמר', 'Profile created and saved', 'Профиль создан'),
    'export': ('לייצא עותק לתיקייה (USB / רשת)?', 'Export a copy to a folder (USB / network)?', 'Экспортировать копию в папку?'),
    'none': ('לא נמצא פרופיל. בחר קובץ .nvp', 'No profile found. Pick a .nvp file', 'Профиль не найден. Выберите файл .nvp'),
    'bad': ('סיסמה שגויה', 'Wrong password', 'Неверный пароль'),
    'locked': ('יותר מדי ניסיונות. נסה שוב בעוד %d דקות', 'Too many attempts. Try again in %d min', 'Слишком много попыток. Повторите через %d мин'),
    'done': ('כל החשבונות חוברו. Kodi ייסגר – פתח אותו מחדש.', 'All accounts connected. Kodi will close – open it again.',
             'Все аккаунты подключены. Kodi закроется – откройте снова.'),
}


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def _keys(pw, salt):
    k = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, ITER, 64)
    return k[:32], k[32:]


def _stream(key, nonce, data):
    base = hmac.new(key, nonce, hashlib.sha256)
    ks = bytearray()
    for i in range((len(data) + 31) // 32):
        h = base.copy()
        h.update(i.to_bytes(8, 'big'))
        ks += h.digest()
    n = len(data)
    return (int.from_bytes(data, 'big') ^ int.from_bytes(bytes(ks[:n]), 'big')).to_bytes(n, 'big')


def encrypt(pw, plain):
    salt, nonce = os.urandom(16), os.urandom(16)
    ek, mk = _keys(pw, salt)
    ct = _stream(ek, nonce, plain)
    return MAGIC + salt + nonce + hmac.new(mk, MAGIC + salt + nonce + ct, hashlib.sha256).digest() + ct


def decrypt(pw, blob):
    if blob[:4] != MAGIC:
        raise ValueError('not a NovaTV profile')
    salt, nonce, tag, ct = blob[4:20], blob[20:36], blob[36:68], blob[68:]
    ek, mk = _keys(pw, salt)
    if not hmac.compare_digest(tag, hmac.new(mk, blob[:36] + ct, hashlib.sha256).digest()):
        return None
    return _stream(ek, nonce, ct)


def create():
    d = xbmcgui.Dialog()
    pw = d.input(s('pw'), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if len(pw) < 8:
        return d.ok('NovaTV', s('short'))
    if d.input(s('pw2'), option=xbmcgui.ALPHANUM_HIDE_INPUT) != pw:
        return d.ok('NovaTV', s('nomatch'))
    tmp = os.path.join(xbmcvfs.translatePath('special://temp/'), 'nvp.zip')
    backup.make_zip(tmp)
    with open(tmp, 'rb') as f:
        blob = encrypt(pw, f.read())
    os.remove(tmp)
    with open(LOCAL, 'wb') as f:
        f.write(blob)
    if d.yesno('NovaTV', '%s\n%s' % (s('made'), s('export'))):
        dest = d.browse(3, 'NovaTV', 'files', '', False, False, '')
        if dest:
            xbmcvfs.copy(LOCAL, dest.rstrip('/\\') + '/preset.nvp')
    d.notification('NovaTV', s('made'))


def unlock():
    d = xbmcgui.Dialog()
    guard = load('preset_guard.json', {'fails': 0, 'until': 0})
    if time.time() < guard['until']:
        return d.ok('NovaTV', s('locked') % (1 + (guard['until'] - time.time()) // 60))
    path = next((p for p in (LOCAL, SHIPPED) if os.path.exists(p)), None)
    if not path:
        src = d.browse(1, s('none'), 'files', '.nvp', False, False, '')
        if not src:
            return
        path = os.path.join(xbmcvfs.translatePath('special://temp/'), 'preset.nvp')
        xbmcvfs.copy(src, path)
    pw = d.input(s('pw'), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if not pw:
        return
    with open(path, 'rb') as f:
        plain = decrypt(pw, f.read())
    if plain is None:
        guard['fails'] += 1
        if guard['fails'] >= 5:
            guard = {'fails': 0, 'until': time.time() + 600}
        save('preset_guard.json', guard)
        return d.ok('NovaTV', s('bad'))
    save('preset_guard.json', {'fails': 0, 'until': 0})
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        for m in z.namelist():
            if m == 'bn_backup.txt' or m.startswith('/') or '..' in m:
                continue
            z.extract(m, backup.USERDATA)
    d.ok('NovaTV', s('done'))
    os._exit(1)
