# -*- coding: utf-8 -*-
"""Shared helpers: i18n (he/en/ru), JSON storage, TMDb client."""
import json
import os
import time

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon('plugin.video.nova')
ADDON_ID = 'plugin.video.nova'
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
MEDIA = os.path.join(ADDON_PATH, 'resources', 'media')
os.makedirs(PROFILE, exist_ok=True)

# ---------------------------------------------------------------- i18n
STRINGS = {
    'movies':      ('סרטים', 'Movies', 'Фильмы'),
    'series':      ('סדרות', 'Series', 'Сериалы'),
    'tv':          ('ערוצי טלוויזיה', 'TV Channels', 'ТВ-каналы'),
    'radio':       ('רדיו', 'Radio', 'Радио'),
    'history':     ('היסטוריית צפייה', 'Watch History', 'История просмотров'),
    'favourites':  ('מועדפים', 'Favourites', 'Избранное'),
    'accounts':    ('חשבונות וחיבורים', 'Accounts & Connections', 'Аккаунты и подключения'),
    'settings':    ('הגדרות', 'Settings', 'Настройки'),
    'search':      ('חיפוש', 'Search', 'Поиск'),
    'trending':    ('חם השבוע', 'Trending This Week', 'Популярное за неделю'),
    'popular':     ('פופולרי', 'Popular', 'Популярное'),
    'top_rated':   ('המדורגים ביותר', 'Top Rated', 'Лучшие по рейтингу'),
    'genres':      ('לפי ז\'אנר', 'By Genre', 'По жанрам'),
    'languages':   ('לפי שפה', 'By Language', 'По языку'),
    'years':       ('לפי שנה', 'By Year', 'По году'),
    'hebrew':      ('עברית', 'Hebrew', 'Иврит'),
    'english':     ('אנגלית', 'English', 'Английский'),
    'russian':     ('רוסית', 'Russian', 'Русский'),
    'next_page':   ('עמוד הבא', 'Next page', 'Следующая страница'),
    'season':      ('עונה', 'Season', 'Сезон'),
    'choose_src':  ('בחר מקור ידנית', 'Choose source manually', 'Выбрать источник вручную'),
    'add_fav':     ('הוסף למועדפים', 'Add to favourites', 'Добавить в избранное'),
    'rem_fav':     ('הסר ממועדפים', 'Remove from favourites', 'Удалить из избранного'),
    'fav_added':   ('נוסף למועדפים', 'Added to favourites', 'Добавлено в избранное'),
    'channels':    ('ערוצים', 'Channels', 'Каналы'),
    'guide':       ('מדריך שידורים', 'TV Guide', 'Телепрограмма'),
    'iptv_src':    ('מקורות IPTV', 'IPTV sources', 'Источники IPTV'),
    'israel':      ('ישראל', 'Israel', 'Израиль'),
    'russia':      ('רוסיה', 'Russia', 'Россия'),
    'top_world':   ('הפופולריות בעולם', 'Top worldwide', 'Популярные в мире'),
    'watched_at':  ('נצפה', 'Watched', 'Просмотрено'),
    'clear':       ('נקה', 'Clear', 'Очистить'),
    'ok':          ('מחובר', 'Connected', 'Подключено'),
    'missing':     ('לא מוגדר', 'Not set', 'Не задано'),
    'error':       ('שגיאה', 'Error', 'Ошибка'),
    'israeli_tv':  ('ערוצים ישראליים (עידן+)', 'Israeli channels (Idan+)', 'Израильские каналы (Idan+)'),
    'empty':       ('אין פריטים', 'Nothing here yet', 'Пока пусто'),
    'ai_start':    ('לא נמצאו כתוביות בעברית – מתחיל תרגום AI', 'No Hebrew subtitles found - starting AI subtitles', 'Субтитры на иврите не найдены - запуск ИИ'),
    'ai_ready':    ('כתוביות AI נטענו', 'AI subtitles loaded', 'ИИ-субтитры загружены'),
    'ai_progress': ('כתוביות AI', 'AI subtitles', 'ИИ-субтитры'),
    'ai_noserver': ('שרת כתוביות AI לא זמין', 'AI subtitle server unreachable', 'Сервер ИИ-субтитров недоступен'),
    'movies_he':   ('סרטים', 'Movies', 'Фильмы'),
    'grp_israel':  ('ישראלי', 'Israeli', 'Израиль'),
    'grp_news':    ('חדשות', 'News', 'Новости'),
    'grp_movies':  ('סרטים', 'Movies', 'Кино'),
    'grp_series':  ('סדרות', 'Series', 'Сериалы'),
    'grp_kids':    ('ילדים', 'Kids', 'Детские'),
    'grp_sport':   ('ספורט', 'Sport', 'Спорт'),
    'grp_documentary': ('תעודה וטבע', 'Documentary', 'Познавательные'),
    'grp_music':   ('מוזיקה', 'Music', 'Музыка'),
    'grp_russian': ('רוסית', 'Russian', 'Русские'),
    'grp_other':   ('אחר', 'Other', 'Другие'),
    'libraries':   ('ספריות חינמיות', 'Free Libraries', 'Бесплатные библиотеки'),
    'lib_install': ('יותקן בלחיצה', 'installs on click', 'установится по нажатию'),
    'backup_menu': ('גיבוי ושחזור', 'Backup & Restore', 'Резервная копия'),
    'backup':      ('גיבוי עכשיו', 'Back up now', 'Создать копию'),
    'restore':     ('שחזור מגיבוי', 'Restore from backup', 'Восстановить'),
    'bk_where':    ('בחר תיקייה לגיבוי (USB / רשת / מקומי)', 'Choose backup folder (USB / network / local)', 'Папка для копии (USB / сеть / локально)'),
    'bk_done':     ('הגיבוי נשמר', 'Backup saved', 'Копия сохранена'),
    'bk_files':    ('קבצים', 'files', 'файлов'),
    'bk_fail':     ('הפעולה נכשלה', 'Operation failed', 'Ошибка операции'),
    'bk_pick':     ('בחר קובץ גיבוי...', 'Choose a backup file...', 'Выбрать файл...'),
    'bk_auto':     ('גיבוי אוטומטי', 'Automatic backup', 'Автокопия'),
    'bk_invalid':  ('זה לא קובץ גיבוי של BN', 'This is not a BN backup file', 'Это не копия BN'),
    'bk_confirm':  ('לשחזר? ההגדרות הנוכחיות יוחלפו.', 'Restore? Current settings will be replaced.', 'Восстановить? Текущие настройки будут заменены.'),
    'bk_restored': ('השחזור הושלם. Kodi ייסגר – פתח אותו שוב.', 'Restored. Kodi will close - open it again.', 'Готово. Kodi закроется - откройте снова.'),
    'free_src':    ('ערוצים חינמיים מובנים', 'Built-in free channels', 'Встроенные бесплатные каналы'),
    'kukhnya':     ('קוכניה (המטבח)', 'Kukhnya (Kitchen)', 'Кухня'),
}
_LANG_INDEX = {'he': 0, 'en': 1, 'ru': 2}


def ui_lang():
    code = xbmc.getLanguage(xbmc.ISO_639_1) or 'en'
    return code if code in _LANG_INDEX else 'en'


def T(key):
    row = STRINGS.get(key)
    return row[_LANG_INDEX[ui_lang()]] if row else key


def tmdb_lang():
    choice = ADDON.getSetting('content_lang')
    table = {'1': 'he-IL', '2': 'en-US', '3': 'ru-RU'}
    if choice in table:
        return table[choice]
    return {'he': 'he-IL', 'ru': 'ru-RU'}.get(ui_lang(), 'en-US')


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[NovaTV] %s' % msg, level)


# ---------------------------------------------------------------- storage
def _path(name):
    return os.path.join(PROFILE, name)


def load(name, default):
    try:
        with open(_path(name), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save(name, data):
    tmp = _path(name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(name))


# ---------------------------------------------------------------- TMDb
TMDB = 'https://api.themoviedb.org/3'
IMG = 'https://image.tmdb.org/t/p/'


def _tmdb_auth():
    key = ADDON.getSetting('tmdb_key').strip()
    if key:
        return {'api_key': key}, {}
    # fall back to the read token that ships with POV
    try:
        token = xbmcaddon.Addon('plugin.video.pov').getSetting('tmdb_read_token')
    except Exception:
        token = ''
    if not token:       # first seconds after install POV is not registered yet: read its shipped default
        try:
            import re
            px = xbmcvfs.translatePath('special://home/addons/plugin.video.pov/resources/settings.xml')
            with open(px, encoding='utf-8') as f:
                m = re.search(r'id="tmdb_read_token"[^>]*default="([^"]+)"', f.read())
            token = m.group(1) if m else ''
        except Exception:
            token = ''
    return {}, ({'Authorization': 'Bearer ' + token} if token else {})


_CACHE_TTL = 6 * 3600


def tmdb(path, **params):
    import hashlib
    import requests
    params.setdefault('language', tmdb_lang())
    q, headers = _tmdb_auth()
    params.update(q)
    ck = hashlib.md5((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    cdir = _path('cache')
    os.makedirs(cdir, exist_ok=True)
    cfile = os.path.join(cdir, ck + '.json')
    if os.path.exists(cfile) and time.time() - os.path.getmtime(cfile) < _CACHE_TTL:
        with open(cfile, encoding='utf-8') as f:
            return json.load(f)
    r = requests.get(TMDB + path, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    with open(cfile, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return data


def art(item):
    a = {}
    if item.get('poster_path'):
        a['poster'] = a['thumb'] = IMG + 'w500' + item['poster_path']
    if item.get('backdrop_path'):
        a['fanart'] = IMG + 'w1280' + item['backdrop_path']
    if item.get('still_path'):
        a['thumb'] = IMG + 'w500' + item['still_path']
    return a


def now_str(ts=None):
    return time.strftime('%d/%m/%Y %H:%M', time.localtime(ts or time.time()))
