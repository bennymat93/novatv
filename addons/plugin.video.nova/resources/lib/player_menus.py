# -*- coding: utf-8 -*-
"""BN player panels (v1.1.0 phase 3/4), remote-first: plain Kodi list dialogs, D-pad + OK + Back only.

sync()      subtitle/audio delay: native slider, fine/coarse steps (remembered), VLC bookmark sync, reset
settings()  the gear menu of the spec (next episode, audio, subtitles, advanced subtitles, video, audio stream,
            subtitle toggle, speed) + aspect/zoom, A-B loop, jump to time / +-N s, screenshot
audio()     audio tracks, audio delay, volume boost (Kodi's audio settings)
subtitles() the subtitles menu of the spec + our three generation actions + the unified picker
appearance() subtitle size / colour / outline / background / opacity / position / encoding, applied live
"""
import io
import json
import os
import re
import time
import zipfile

import xbmc
import xbmcgui

from . import playerctl, substore, subfix, syncmath
from .common import ADDON, PROFILE, T, log

WIN = xbmcgui.Window(10000)
GOLD = 'FFE8BE5A'


def _sel(title, rows, pre=0):
    return xbmcgui.Dialog().select(title, rows, preselect=max(0, pre))


def _note(msg, ms=3000, kind=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification('BN', msg, kind, ms)


def _player():
    p = xbmc.Player()
    return p if p.isPlayingVideo() else None


def _fmt(d):
    return ('+' if d > 0 else '') + '%.3fs' % d


# ------------------------------------------------------------------ sync
STEPS = (0.05, 0.1, 0.25, 0.5, 1.0, 5.0)


def sync():
    """subtitle + audio delay panel; stays open so the viewer can press repeatedly"""
    while _player():
        step = float(ADDON.getSetting('sync_step') or 0.5)
        sd, ad = playerctl.sub_delay(), playerctl.audio_delay()
        a, s = WIN.getProperty('NovaTV.SyncMarkAudio'), WIN.getProperty('NovaTV.SyncMarkSub')
        rows = [
            ('slider', 'סרגל היסט כתוביות (עדין)'),
            ('earlier', 'כתוביות מוקדם יותר  −%ss' % step),
            ('later', 'כתוביות מאוחר יותר  +%ss' % step),
            ('step', 'גודל צעד: %ss' % step),
            ('mark_a', 'סנכרון בסימון 1/2: שמעתי את השורה עכשיו' + ('  ✓' if a else '')),
            ('mark_s', 'סנכרון בסימון 2/2: הכתובית הופיעה עכשיו' + ('  ✓' if s else '')),
            ('reset_s', 'איפוס כתוביות ל-0'),
            ('a_earlier', 'שמע מוקדם יותר  −0.025s'),
            ('a_later', 'שמע מאוחר יותר  +0.025s'),
            ('reset_a', 'איפוס שמע ל-0'),
        ]
        i = _sel('סנכרון · כתוביות %s · שמע %s' % (_fmt(sd), _fmt(ad)), [r[1] for r in rows], 1)
        if i < 0:
            return
        k = rows[i][0]
        if k == 'slider':
            xbmc.executebuiltin('Action(SubtitleDelay)')
            return
        if k == 'earlier':
            playerctl.set_sub_delay(sd - step)
        elif k == 'later':
            playerctl.set_sub_delay(sd + step)
        elif k == 'step':
            j = _sel('גודל צעד', ['%ss' % x for x in STEPS], STEPS.index(step) if step in STEPS else 3)
            if j >= 0:
                ADDON.setSetting('sync_step', str(STEPS[j]))          # remembered
        elif k in ('mark_a', 'mark_s'):
            p = _player()
            t = p.getTime() if p else 0
            WIN.setProperty('NovaTV.SyncMarkAudio' if k == 'mark_a' else 'NovaTV.SyncMarkSub', '%.3f' % t)
            a, s = WIN.getProperty('NovaTV.SyncMarkAudio'), WIN.getProperty('NovaTV.SyncMarkSub')
            if a and s:
                target = syncmath.bookmark_delay(sd, float(a), float(s))
                playerctl.set_sub_delay(target)
                WIN.clearProperty('NovaTV.SyncMarkAudio')
                WIN.clearProperty('NovaTV.SyncMarkSub')
                _note('הכתוביות סונכרנו: %s' % _fmt(playerctl.sub_delay()))
        elif k == 'reset_s':
            playerctl.set_sub_delay(0.0)
        elif k == 'a_earlier':
            playerctl.set_audio_delay(ad - syncmath.AUDIO_STEP)
        elif k == 'a_later':
            playerctl.set_audio_delay(ad + syncmath.AUDIO_STEP)
        elif k == 'reset_a':
            playerctl.set_audio_delay(0.0)


# ------------------------------------------------------------------ settings (gear)
def _jump_to_time():
    t = xbmcgui.Dialog().numeric(2, 'קפיצה לזמן (שש:דד)')
    if t and _player():
        h, m = (t.split(':') + ['0'])[:2]
        xbmc.Player().seekTime(int(h) * 3600 + int(m) * 60)


def settings():
    while _player():
        auto_next = playerctl.rpc('Settings.GetSettingValue', setting='videoplayer.autoplaynextitem').get('result', {}).get('value')
        rows = [
            ('next', 'הגדרות הפרק הבא: ניגון אוטומטי %s' % ('פעיל' if auto_next else 'כבוי')),
            ('audio', 'הגדרות אודיו'),
            ('subs', 'הגדרות כתוביות'),
            ('subs_adv', 'הגדרות כתוביות – מתקדם'),
            ('video', 'הגדרות וידאו'),
            ('astream', 'החלף זרם שמע   [%s]' % (xbmc.getInfoLabel('VideoPlayer.AudioLanguage') or '-')),
            ('stoggle', 'Toggle subtitle   [%s]' % (xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage') or '-')),
            ('speed', 'מהירות ניגון   [%s]' % xbmc.getInfoLabel('Player.PlaySpeed')),
            ('view', 'יחס תצוגה / זום'),
            ('ab', 'לולאה A-B   [%s]' % (WIN.getProperty('NovaTV.ABLoop') or 'כבוי')),
            ('jump', 'קפיצה לזמן'),
            ('shot', 'צילום מסך'),
        ]
        i = _sel('הגדרות', [r[1] for r in rows])
        if i < 0:
            return
        k = rows[i][0]
        if k == 'next':
            playerctl.rpc('Settings.SetSettingValue', setting='videoplayer.autoplaynextitem',
                          value=[] if auto_next else [0, 1, 2, 3, 4])
        elif k in ('audio', 'subs', 'video'):
            xbmc.executebuiltin('ActivateWindow(%s)' % {'audio': 'osdaudiosettings', 'subs': 'osdsubtitlesettings',
                                                        'video': 'osdvideosettings'}[k])
            return
        elif k == 'subs_adv':
            appearance()
        elif k == 'astream':
            xbmc.executebuiltin('AudioNextLanguage')
        elif k == 'stoggle':
            xbmc.executebuiltin('ShowSubtitles')
        elif k == 'speed':
            speeds = [0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0]
            if not xbmc.getCondVisibility('Player.TempoEnabled'):
                _note('שינוי מהירות לא זמין בקובץ הזה')
                continue
            j = _sel('מהירות ניגון', ['%.2fx' % x for x in speeds], speeds.index(1.0))
            if j >= 0:
                playerctl.set_speed(speeds[j])
        elif k == 'view':
            modes = [('normal', 'רגיל'), ('zoom', 'זום'), ('stretch4x3', 'מתיחה 4:3'), ('widezoom', 'זום רחב'),
                     ('stretch16x9', 'מתיחה 16:9'), ('original', 'גודל מקורי')]
            j = _sel('יחס תצוגה / זום', [m[1] for m in modes])
            if j >= 0:
                playerctl.rpc('Player.SetViewMode', viewmode=modes[j][0])
        elif k == 'ab':
            p = _player()
            cur = WIN.getProperty('NovaTV.ABLoop')
            if cur and ',' in cur:
                WIN.clearProperty('NovaTV.ABLoop')
            elif cur:
                a = float(cur)
                b = p.getTime() if p else a
                if b > a + 1:
                    WIN.setProperty('NovaTV.ABLoop', '%.2f,%.2f' % (a, b))
                    _note('לולאה A-B פעילה')
            elif p:
                WIN.setProperty('NovaTV.ABLoop', '%.2f' % p.getTime())
                _note('נקודה A נקבעה – בחר שוב לקביעת B')
        elif k == 'jump':
            _jump_to_time()
            return
        elif k == 'shot':
            xbmc.executebuiltin('TakeScreenshot')


# ------------------------------------------------------------------ audio
def audio():
    while _player():
        pl = [p for p in (playerctl.rpc('Player.GetActivePlayers').get('result') or []) if p.get('type') == 'video']
        if not pl:
            return
        r = playerctl.rpc('Player.GetProperties', playerid=pl[0]['playerid'],
                          properties=['audiostreams', 'currentaudiostream']).get('result') or {}
        cur = (r.get('currentaudiostream') or {}).get('index')
        streams = r.get('audiostreams') or []
        rows = [('track', s['index'], '%s%s · %s %sch' % ('● ' if s['index'] == cur else '', s.get('language') or '?',
                                                         (s.get('codec') or '').upper(), s.get('channels') or ''))
                for s in streams]
        rows += [('delay', None, 'השהיית שמע (%s)' % _fmt(playerctl.audio_delay())),
                 ('boost', None, 'הגברת עוצמה והגדרות שמע')]
        i = _sel('שמע', [r_[2] for r_ in rows])
        if i < 0:
            return
        k, v, _ = rows[i]
        if k == 'track':
            playerctl.rpc('Player.SetAudioStream', playerid=pl[0]['playerid'], stream=v)
        elif k == 'delay':
            sync()
            return
        else:
            xbmc.executebuiltin('ActivateWindow(osdaudiosettings)')
            return


# ------------------------------------------------------------------ subtitle appearance (live)
def _setting(sid):
    return playerctl.rpc('Settings.GetSettingValue', setting=sid).get('result', {}).get('value')


def _set(sid, v):
    playerctl.rpc('Settings.SetSettingValue', setting=sid, value=v)


def appearance():
    items = [
        ('subtitles.fontsize', 'גודל כתובית', [28, 34, 40, 46, 52, 58, 64, 72]),
        ('subtitles.colorpick', 'צבע', [('FFFFFFFF', 'לבן'), ('FFFFFF00', 'צהוב'), ('FFE8BE5A', 'זהב'), ('FF00FFFF', 'תכלת')]),
        ('subtitles.bordersize', 'עובי מתאר', [0, 10, 25, 41, 60]),
        ('subtitles.backgroundtype', 'רקע לכתובית', [(0, 'ללא'), (1, 'צל'), (2, 'מלבן'), (3, 'מלבן מלא')]),
        ('subtitles.bgopacity', 'אטימות רקע', [0, 25, 35, 50, 75, 100]),
        ('subtitles.marginvertical', 'מיקום (מרווח מלמטה)', [0.0, 3.3, 6.0, 10.0, 15.0]),
        ('subtitles.charset', 'קידוד טקסט', [('DEFAULT', 'אוטומטי'), ('UTF-8', 'UTF-8'), ('CP1255', 'Windows-1255'),
                                              ('ISO-8859-8', 'ISO-8859-8')]),
    ]
    while True:
        rows = []
        for sid, name, _ in items:
            rows.append('%s   [%s]' % (name, _setting(sid)))
        i = _sel('הגדרות כתוביות – מתקדם (מוחל מיד)', rows)
        if i < 0:
            return
        sid, name, opts = items[i]
        labels = [o[1] if isinstance(o, tuple) else str(o) for o in opts]
        values = [o[0] if isinstance(o, tuple) else o for o in opts]
        cur = _setting(sid)
        j = _sel(name, labels, values.index(cur) if cur in values else 0)
        if j >= 0:
            _set(sid, values[j])                              # live: the next subtitle line uses it


# ------------------------------------------------------------------ subtitles
def subs_folder():
    f = ADDON.getSetting('subs_folder') or os.path.join(PROFILE, 'subtitles')
    os.makedirs(f, exist_ok=True)
    return f


def video_info():
    tag = xbmc.Player().getVideoInfoTag()
    title = tag.getTVShowTitle() or tag.getTitle() or xbmc.getInfoLabel('Player.Title')
    s, e = tag.getSeason(), tag.getEpisode()
    imdb = tag.getIMDBNumber() or xbmc.getInfoLabel('VideoPlayer.UniqueID(imdb)')
    tmdb_id = tag.getUniqueID('tmdb')
    release = WIN.getProperty('subs.player_filename') or xbmc.getInfoLabel('Player.Filename')
    return {'title': title, 'season': s if s > 0 else 0, 'episode': e if e > 0 else 0, 'imdb': imdb, 'tmdb': tmdb_id,
            'release': release, 'base': substore.video_base(title, s, e, xbmc.Player().getPlayingFile())}


def _imdb(info):
    if info['imdb'].startswith('tt') or not info['tmdb']:
        return info['imdb']
    try:
        from .common import tmdb
        kind = 'tv' if info['episode'] else 'movie'
        return tmdb('/%s/%s/external_ids' % (kind, info['tmdb'])).get('imdb_id') or ''
    except Exception:
        return ''


def wizdom_search(info):
    import requests
    imdb = _imdb(info)
    if not imdb:
        return []
    params = {'action': 'by_id', 'imdb': imdb}
    if info['episode']:
        params.update(season=info['season'], episode=info['episode'])
    res = requests.get('https://wizdom.xyz/api/search', params=params, timeout=15).json() or []
    for r in res:
        r['match'] = subfix.match_score(info['release'] or info['title'], r.get('versioname', ''))
    return sorted(res, key=lambda r: r['match'], reverse=True)


def wizdom_download(sub_id):
    import requests
    data = requests.get('https://wizdom.xyz/api/files/sub/%s' % sub_id, timeout=30).content
    z = zipfile.ZipFile(io.BytesIO(data))
    name = next(n for n in z.namelist() if n.lower().endswith('.srt'))
    return subfix.decode_bytes(z.read(name))


def load(path, player=None):
    """activate a subtitle file now (no restart) and remember it as the viewer's choice"""
    p = player or _player()
    if not p:
        return False
    p.setSubtitles(path)
    p.showSubtitles(True)
    WIN.setProperty('NovaTV.SubsChosen', p.getPlayingFile())
    return True


def auto_subtitles():
    """(1) no AI: Hebrew from Wizdom (best release match), else the AI server in machine-translation mode"""
    if not _player():
        return
    info = video_info()
    dlg = xbmcgui.DialogProgress()
    dlg.create('BN', 'מחפש כתוביות בעברית...')
    try:
        res = wizdom_search(info)
    except Exception as e:
        log('wizdom: %s' % e, xbmc.LOGWARNING)
        res = []
    if res:
        dlg.update(60, 'מוריד: %s' % res[0].get('versioname', '')[:60])
        try:
            text = wizdom_download(res[0]['id'])
            path = substore.save(subs_folder(), info['base'], 'he', 'dl', text=text)
            dlg.close()
            load(path)
            WIN.setProperty('NovaTV.SubsSource', 'wizdom')
            _note('כתוביות עבריות נטענו (%d%% התאמה)' % int(res[0]['match'] * 100))
            return
        except Exception as e:
            log('wizdom download: %s' % e, xbmc.LOGWARNING)
    dlg.close()
    _note('לא נמצאו כתוביות אנושיות – מתרגם אוטומטית (ללא AI)')
    WIN.setProperty('NovaTV.AIMode', 'mt')
    xbmc.executebuiltin('NotifyAll(plugin.video.nova,ai_now)')


def ai_subtitles():
    WIN.setProperty('NovaTV.AIMode', 'ai')
    xbmc.executebuiltin('NotifyAll(plugin.video.nova,ai_now)')


def _tracks():
    pl = [p for p in (playerctl.rpc('Player.GetActivePlayers').get('result') or []) if p.get('type') == 'video']
    if not pl:
        return None, [], None, False
    r = playerctl.rpc('Player.GetProperties', playerid=pl[0]['playerid'],
                      properties=['subtitles', 'currentsubtitle', 'subtitleenabled']).get('result') or {}
    return pl[0]['playerid'], r.get('subtitles') or [], (r.get('currentsubtitle') or {}).get('index'), bool(r.get('subtitleenabled'))


SRC_NAME = {'ai': 'AI', 'auto': 'תרגום אוטומטי', 'dl': 'הורדה'}


def picker(filter_lang=None, filter_src=None):
    """unified list: embedded / local folder / generated auto / generated AI / online; actions per entry"""
    while _player():
        info = video_info()
        pid, streams, cur, enabled = _tracks()
        rows = []
        head = lambda t: rows.append(('head', None, '[B][COLOR %s]%s[/COLOR][/B]' % (GOLD, t)))
        head('רצועות בסרטון')
        for s in streams:
            if filter_lang and (s.get('language') or '') != filter_lang:
                continue
            mark = '[COLOR limegreen]●[/COLOR] ' if (s['index'] == cur and enabled) else ''
            rows.append(('stream', s, '%s%s · %s' % (mark, s.get('language') or '?', (s.get('name') or '').split(' (')[0] or 'פנימית')))
        stored = substore.entries(subs_folder(), info['base'])
        for src, title in (('dl', 'תיקייה מקומית / הורדות'), ('auto', 'נוצרו – אוטומטי'), ('ai', 'נוצרו – AI')):
            group = [e for e in stored if e['source'] == src and (not filter_lang or e['lang'] == filter_lang)
                     and (not filter_src or filter_src == src)]
            if not group:
                continue
            head(title)
            for e in group:
                rows.append(('file', e, '%s · %s · %s%s\n[COLOR grey]%s[/COLOR]' % (
                    e['lang'], SRC_NAME[e['source']], time.strftime('%d/%m %H:%M', time.localtime(e['mtime'])),
                    '' if e['version'] == 1 else ' (v%d)' % e['version'], e['preview'][:120])))
        head('חיפוש ברשת')
        rows.append(('online', None, 'חיפוש כתוביות באתרים (Wizdom ועוד)'))
        rows.append(('filter', None, 'סינון לפי שפה / מקור'))
        i = _sel('כתוביות – בחירה', [r[2] for r in rows])
        if i < 0:
            return
        kind, val, _ = rows[i]
        if kind == 'stream':
            playerctl.rpc('Player.SetSubtitle', playerid=pid, subtitle=val['index'], enable=True)
            WIN.setProperty('NovaTV.SubsChosen', xbmc.Player().getPlayingFile())
        elif kind == 'file':
            _entry_actions(val)
        elif kind == 'online':
            online(info)
        elif kind == 'filter':
            j = _sel('סינון', ['הכול', 'עברית בלבד', 'אנגלית בלבד', 'AI בלבד', 'הורדות בלבד'])
            filter_lang, filter_src = [(None, None), ('he', None), ('en', None), (None, 'ai'), (None, 'dl')][max(0, j)]


def _entry_actions(e):
    acts = ['הפעל', 'הגדר כמשנית (שתי כתוביות)', 'סנכרון מחדש', 'שינוי שם', 'מחיקה']
    j = _sel(os.path.basename(e['path']), acts)
    if j == 0:
        load(e['path'])
    elif j == 1:
        primary = WIN.getProperty('NovaTV.PrimaryFile')
        if not primary or not os.path.exists(primary):
            _note('הפעל קודם כתובית ראשית מהרשימה')
            return
        with open(primary, 'rb') as f:
            a = subfix.parse_subtitles(subfix.decode_bytes(f.read()))
        with open(e['path'], 'rb') as f:
            b = subfix.parse_subtitles(subfix.decode_bytes(f.read()))
        out = os.path.join(PROFILE, 'dual')
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, 'BN dual %d.srt' % int(time.time()))
        subfix.write_srt(syncmath.merge_dual(a, b), path)
        load(path)
        WIN.setProperty('NovaTV.Dual', path)
    elif j == 2:
        load(e['path'])
        sync()
    elif j == 3:
        name = xbmcgui.Dialog().input('שם חדש', e['base'])
        if name:
            substore.rename(e['path'], name)
    elif j == 4:
        if xbmcgui.Dialog().yesno('BN', 'למחוק את הכתובית?'):
            os.remove(e['path'])
    if j == 0:
        WIN.setProperty('NovaTV.PrimaryFile', e['path'])


def online(info):
    dlg = xbmcgui.DialogProgress()
    dlg.create('BN', 'מחפש...')
    try:
        res = wizdom_search(info)
    except Exception:
        res = []
    dlg.close()
    rows = ['[%d%%] %s' % (int(r['match'] * 100), r.get('versioname', '')) for r in res[:40]]
    rows.append('חלון החיפוש של Kodi (כל השירותים)')
    i = _sel('תוצאות ברשת', rows)
    if i < 0:
        return
    if i == len(rows) - 1:
        xbmc.executebuiltin('ActivateWindow(subtitlesearch)')
        return
    text = wizdom_download(res[i]['id'])
    path = substore.save(subs_folder(), info['base'], 'he', 'dl', text=text)
    load(path)
    WIN.setProperty('NovaTV.PrimaryFile', path)


def subtitles():
    """the Subtitles menu of the spec (photo) + our actions"""
    while _player():
        pid, streams, cur, enabled = _tracks()
        busy = WIN.getProperty('NovaTV.AISubs')
        rows = []
        if busy:
            rows.append(('busy', '[COLOR %s]בהכנה: %s[/COLOR]' % (GOLD, busy)))
        rows += [('auto', 'הורד כתובית (אוטומטי, ללא AI)'),
                 ('ai', 'כתוביות AI'),
                 ('pick', 'בחר כתובית (כל הרצועות והכתוביות שנוצרו)'),
                 ('lang', 'שפת כתובית   [%s]' % (xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage') or '-')),
                 ('bg', 'רקע לכתובית'), ('size', 'גודל כתובית'), ('opacity', 'אטימות כתובית'),
                 ('adv', 'הגדרות כתוביות – מתקדם'),
                 ('off', ('כבה כתוביות' if enabled else 'הפעל כתוביות'))]
        i = _sel('כתוביות', [r[1] for r in rows])
        if i < 0:
            return
        k = rows[i][0]
        if k == 'auto':
            auto_subtitles()
            return
        if k == 'ai':
            ai_subtitles()
            return
        if k == 'pick':
            picker()
        elif k == 'lang':
            langs = sorted({s.get('language') or '?' for s in streams})
            j = _sel('שפת כתובית', langs)
            if j >= 0:
                s = next(s for s in streams if (s.get('language') or '?') == langs[j])
                playerctl.rpc('Player.SetSubtitle', playerid=pid, subtitle=s['index'], enable=True)
        elif k in ('bg', 'size', 'opacity'):
            sid, name, opts = {'bg': ('subtitles.backgroundtype', 'רקע לכתובית', [(0, 'ללא'), (1, 'צל'), (2, 'מלבן'), (3, 'מלבן מלא')]),
                               'size': ('subtitles.fontsize', 'גודל כתובית', [34, 40, 46, 52, 58, 64, 72]),
                               'opacity': ('subtitles.bgopacity', 'אטימות כתובית', [0, 25, 35, 50, 75, 100])}[k]
            labels = [o[1] if isinstance(o, tuple) else str(o) for o in opts]
            values = [o[0] if isinstance(o, tuple) else o for o in opts]
            cur_v = _setting(sid)
            j = _sel(name, labels, values.index(cur_v) if cur_v in values else 0)
            if j >= 0:
                _set(sid, values[j])
        elif k == 'adv':
            appearance()
        elif k == 'off':
            xbmc.Player().showSubtitles(not enabled)
            if not enabled:
                WIN.setProperty('NovaTV.SubsChosen', xbmc.Player().getPlayingFile())


def next_episode():
    """'הפרק הבא': the next playlist item, else the next episode by TMDb (plays through NovaTV)"""
    if xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(video),1)') and \
            xbmc.getInfoLabel('Playlist.Position(video)') != xbmc.getInfoLabel('Playlist.Length(video)'):
        xbmc.executebuiltin('PlayerControl(Next)')
        return
    p = _player()
    if not p:
        return
    tag = p.getVideoInfoTag()
    tmdb_id, s, e = tag.getUniqueID('tmdb'), tag.getSeason(), tag.getEpisode()
    if not (tmdb_id and s > 0 and e > 0):
        _note('אין פרק הבא')
        return
    from urllib.parse import urlencode
    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.nova/?%s)' % urlencode(
        {'a': 'play', 'm': 'episode', 'id': tmdb_id, 's': s, 'e': e + 1, 'q': '%s S%02dE%02d' % (tag.getTVShowTitle(), s, e + 1)}))
