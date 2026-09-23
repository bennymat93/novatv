# -*- coding: utf-8 -*-
"""NovaTV Wizard: download, verify and install the NovaTV build."""
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

BUILD_INFO = 'https://bennymat93.github.io/novatv/build.json'
ADDON = xbmcaddon.Addon()
HOME = xbmcvfs.translatePath('special://home/')
TEMP = xbmcvfs.translatePath('special://temp/')
KEEP_ON_UPDATE = ['plugin.video.nova', 'plugin.video.pov', 'pvr.iptvsimple', 'service.subtitles.All_Subs',
                  'script.module.magneto', 'plugin.video.youtube']
LANG = (xbmc.getLanguage(xbmc.ISO_639_1) or 'en')
TXT = {
    'title': {'he': 'אשף NovaTV', 'ru': 'Мастер NovaTV', 'en': 'NovaTV Wizard'},
    'fresh': {'he': 'התקנה נקייה (מוחק הכל)', 'ru': 'Чистая установка (всё удалить)', 'en': 'Fresh install (wipe everything)'},
    'update': {'he': 'עדכון (שומר חשבונות, היסטוריה ומועדפים)', 'ru': 'Обновление (сохранить аккаунты, историю, избранное)',
               'en': 'Update (keep accounts, history and favourites)'},
    'dl': {'he': 'מוריד...', 'ru': 'Загрузка...', 'en': 'Downloading...'},
    'ex': {'he': 'מתקין...', 'ru': 'Установка...', 'en': 'Installing...'},
    'bad': {'he': 'הקובץ פגום – נסה שוב.', 'ru': 'Файл повреждён - попробуйте ещё раз.', 'en': 'Download is corrupt - please try again.'},
    'done': {'he': 'ההתקנה הושלמה. Kodi ייסגר כעת – פתח אותו שוב.', 'ru': 'Готово. Kodi закроется - откройте его снова.',
             'en': 'Installed. Kodi will now close - please open it again.'},
    'net': {'he': 'אין חיבור לשרת הבילד. בדוק אינטרנט.', 'ru': 'Нет связи с сервером сборки. Проверьте интернет.',
            'en': 'Cannot reach the build server. Check your internet connection.'},
}


def t(k):
    return TXT[k].get(LANG, TXT[k]['en'])


def main():
    d = xbmcgui.Dialog()
    try:
        info = json.loads(urllib.request.urlopen(BUILD_INFO, timeout=20).read().decode())
    except Exception as e:
        d.ok(t('title'), '%s\n%s' % (t('net'), e))
        return
    choice = d.select('%s  v%s' % (t('title'), info['version']), [t('update'), t('fresh')])
    if choice < 0:
        return
    target = os.path.join(TEMP, 'novatv_build.zip')
    pd = xbmcgui.DialogProgress()
    pd.create(t('title'), t('dl'))
    try:
        req = urllib.request.urlopen(info['url'], timeout=60)
        total = int(req.headers.get('Content-Length') or info.get('size') or 0)
        sha, got = hashlib.sha256(), 0
        with open(target, 'wb') as f:
            while True:
                chunk = req.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                got += len(chunk)
                if total:
                    pd.update(int(got * 100 / total), '%s %.1f / %.1f MB' % (t('dl'), got / 1e6, total / 1e6))
                if pd.iscanceled():
                    pd.close()
                    return
        if info.get('sha256') and sha.hexdigest() != info['sha256']:
            pd.close()
            d.ok(t('title'), t('bad'))
            return
        pd.update(0, t('ex'))
        keep_root = os.path.join(TEMP, 'nova_keep')
        shutil.rmtree(keep_root, ignore_errors=True)
        data_dir = os.path.join(HOME, 'userdata', 'addon_data')
        if choice == 0:
            for a in KEEP_ON_UPDATE:
                src = os.path.join(data_dir, a)
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(keep_root, a))
        me = ADDON.getAddonInfo('id')
        for sub in ('addons', 'userdata'):
            base = os.path.join(HOME, sub)
            if not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                if name in (me, 'packages', 'temp', 'Thumbnails') or name.startswith('kodi.log'):
                    continue
                p = os.path.join(base, name)
                try:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                except Exception as e:
                    xbmc.log('[NovaWizard] cannot remove %s: %s' % (p, e), xbmc.LOGWARNING)
        with zipfile.ZipFile(target) as z:
            names = z.namelist()
            for i, n in enumerate(names):
                try:
                    z.extract(n, HOME)
                except Exception as e:      # a locked file must not abort the whole install
                    xbmc.log('[NovaWizard] extract %s: %s' % (n, e), xbmc.LOGWARNING)
                if i % 200 == 0:
                    pd.update(int(i * 100 / len(names)), t('ex'))
        if os.path.isdir(keep_root):
            for a in os.listdir(keep_root):
                dst = os.path.join(data_dir, a)
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(os.path.join(keep_root, a), dst)
        pd.close()
        os.remove(target)
        d.ok(t('title'), t('done'))
        os._exit(1)   # hard exit so Kodi does not overwrite the new guisettings.xml on shutdown
    except Exception as e:
        pd.close()
        d.ok(t('title'), 'Error: %s' % e)


main()
