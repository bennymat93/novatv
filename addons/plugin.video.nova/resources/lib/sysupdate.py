# -*- coding: utf-8 -*-
"""System Update: refresh every part of BN Stream in one go, then show a report.

Parts: add-on repositories + updates, every core/source add-on (installed, enabled, not broken), the POV
fallback hook, services and connections (Real-Debrid, Trakt, IPTV, AI subtitle server, Gemini, TMDb),
live TV channels + guide, radio directory, content cache. Every line that failed gets an "Auto-Fix" entry
right below it (a fix repairs, then checks the line again).
"""
import json
import os
import shutil
import time

import xbmc
import xbmcgui

from .common import monitor
import xbmcplugin

from .common import ADDON, T, load, save, log, now_str, ui_lang, PROFILE

S = {
    'title': ('עדכון מערכת', 'System Update', 'Обновление системы'),
    'running': ('מעדכן את כל רכיבי המערכת...', 'Updating every part of the system...', 'Обновляю все компоненты...'),
    'report': ('דוח עדכון מערכת', 'System Update report', 'Отчёт об обновлении'),
    'summary': ('%d עודכנו · %d תקינים · %d שגיאות', '%d updated · %d OK · %d errors', 'обновлено %d · в порядке %d · ошибок %d'),
    'fix': ('תיקון אוטומטי', 'Auto-Fix', 'Автоисправление'),
    'fix_all': ('תקן את כל השגיאות', 'Auto-Fix all errors', 'Исправить все ошибки'),
    'again': ('הרץ עדכון מערכת שוב', 'Run System Update again', 'Запустить обновление снова'),
    'fixed': ('תוקן', 'Fixed', 'Исправлено'),
    'not_fixed': ('עדיין לא תקין', 'Still not working', 'Всё ещё не работает'),
    'no_report': ('עוד לא בוצע עדכון מערכת', 'No System Update has run yet', 'Обновление ещё не запускалось'),
    'sec_update': ('עדכונים', 'Updates', 'Обновления'),
    'sec_addons': ('תוספים', 'Add-ons', 'Дополнения'),
    'sec_services': ('שירותים וחיבורים', 'Services & connections', 'Сервисы и подключения'),
    'sec_content': ('ערוצים, שרתים ותוכן', 'Channels, servers & content', 'Каналы, серверы и контент'),
    'internet': ('חיבור לאינטרנט', 'Internet connection', 'Интернет'),
    'repos': ('מאגרי תוספים ועדכונים', 'Add-on repositories & updates', 'Репозитории и обновления'),
    'autoupd': ('עדכון אוטומטי של תוספים', 'Automatic add-on updates', 'Автообновление дополнений'),
    'updated': ('עודכנו', 'updated', 'обновлено'),
    'uptodate': ('הכול מעודכן (%d תוספים)', 'everything up to date (%d add-ons)', 'всё актуально (%d)'),
    'skin': ('כפתור כתוביות AI בנגן', 'AI subtitle button in the player', 'Кнопка ИИ-субтитров в плеере'),
    'subsguard': ('הגנות שירות הכתוביות (All Subs)', 'Subtitle service guards (All Subs)', 'Защита сервиса субтитров (All Subs)'),
    'ytport': ('פורט YouTube (Windows)', 'YouTube port (Windows)', 'Порт YouTube (Windows)'),
    'hook': ('POV → חיפוש בכל המקורות', 'POV → search all sources hook', 'POV → поиск во всех источниках'),
    'iptv': ('ערוצי טלוויזיה ומדריך שידורים', 'TV channels & guide', 'ТВ-каналы и телепрограмма'),
    'pvr': ('נגן הטלוויזיה (IPTV Simple)', 'TV player (IPTV Simple)', 'ТВ-клиент (IPTV Simple)'),
    'radio': ('שרתי רדיו', 'Radio servers', 'Радиосерверы'),
    'cache': ('מטמון תוכן (TMDb)', 'Content cache (TMDb)', 'Кэш контента (TMDb)'),
    'cleared': ('נוקה ורוענן', 'cleared and refreshed', 'очищен и обновлён'),
    'missing': ('לא מותקן', 'not installed', 'не установлено'),
    'disabled': ('כבוי', 'disabled', 'выключено'),
    'broken': ('פגום', 'broken', 'повреждено'),
    'needs_user': ('דורש פעולה שלך: ', 'Needs you: ', 'Нужны ваши действия: '),
}


def s(k):
    return S[k][{'he': 0, 'en': 1, 'ru': 2}[ui_lang()]]


def _rpc(method, **params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    except Exception:
        return {}


def row(rid, section, name, ok, detail='', changed=False):
    return {'id': rid, 'section': section, 'name': name, 'ok': ok, 'detail': detail, 'changed': changed}


# ---------------------------------------------------------------- the parts
def installed_versions():
    r = _rpc('Addons.GetAddons', installed=True, properties=['version', 'name'])
    return {a['addonid']: (a.get('name') or a['addonid'], a.get('version', '')) for a in (r.get('result') or {}).get('addons', [])}


def check_internet():
    import requests
    try:
        requests.get('https://www.google.com/generate_204', timeout=8)
        return row('internet', 'update', s('internet'), True, 'OK')
    except Exception as e:
        return row('internet', 'update', s('internet'), False, str(e)[:80])


def check_autoupdate():
    v = (_rpc('Settings.GetSettingValue', setting='general.addonupdates').get('result') or {}).get('value')
    return row('autoupd', 'update', s('autoupd'), v == 0, {0: 'auto', 1: 'notify only', 2: 'never'}.get(v, str(v)))


def run_repos(progress=None):
    """refresh every repository and let Kodi install the updates; report what changed"""
    before = installed_versions()
    # never wait=True here: when a download fails at that moment Kodi's add-on manager and the waiting script
    # block each other and Kodi freezes (found by the deep tests). Send, then follow the versions below.
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.executebuiltin('UpdateLocalAddons')
    mon, start, last_change, cur = monitor(), time.time(), time.time(), before
    # updates are downloaded in the background: wait until nothing changed for 20 s (at most 3 min)
    while time.time() - start < 180:
        if mon.waitForAbort(5):
            break
        now = installed_versions()
        if now != cur:
            cur, last_change = now, time.time()
        if time.time() - start > 30 and time.time() - last_change > 20 and not xbmc.getCondVisibility('System.HasActiveModalDialog'):
            break
        if progress:
            progress(int(min(99, (time.time() - start) * 100 / 180)))
    changed = ['%s %s → %s' % (cur[a][0], before[a][1], cur[a][1]) for a in cur if a in before and cur[a][1] != before[a][1]]
    added = ['%s %s' % (cur[a][0], cur[a][1]) for a in cur if a not in before]
    detail = ('%d %s: %s' % (len(changed) + len(added), s('updated'), ', '.join(changed + added))) if (changed or added) \
        else s('uptodate') % len(cur)
    return row('repos', 'update', s('repos'), True, detail[:400], changed=bool(changed or added))


def core_addons():
    from .status import ADDONS
    from .providers import PROVIDERS, name_of, status as prov_status
    stable = prov_status()
    ids = list(ADDONS) + [(p[1], name_of(p).split(' – ')[0]) for p in PROVIDERS
                          if stable.get(p[0], {}).get('stable', True) and p[1] not in dict(ADDONS)]
    return ids


def check_addon(aid, name):
    r = _rpc('Addons.GetAddonDetails', addonid=aid, properties=['enabled', 'version', 'broken'])
    a = (r.get('result') or {}).get('addon')
    rid = 'addon:' + aid
    if not a:
        return row(rid, 'addons', name, False, s('missing'))
    if a.get('broken'):
        return row(rid, 'addons', name, False, '%s: %s' % (s('broken'), a['broken']))
    if not a.get('enabled'):
        return row(rid, 'addons', name, False, '%s %s' % (a.get('version', ''), s('disabled')))
    return row(rid, 'addons', name, True, a.get('version', ''))


def check_hook():
    from .providers import ensure_pov_hook
    if not xbmc.getCondVisibility('System.HasAddon(plugin.video.pov)'):
        return row('hook', 'addons', s('hook'), None, s('missing'))
    ok = ensure_pov_hook()
    return row('hook', 'addons', s('hook'), ok, 'OK' if ok else 'POV changed - idle detection is used instead')


def check_skin():
    import xbmcvfs
    from . import skinpatch
    xml = xbmcvfs.translatePath('special://home/addons/skin.fentastic/xml')
    if not os.path.isdir(xml):
        return row('skin', 'addons', s('skin'), None, s('missing'))
    try:
        n = skinpatch.apply(xml)
    except Exception as e:
        return row('skin', 'addons', s('skin'), False, str(e)[:100])
    if n:
        xbmc.executebuiltin('ReloadSkin()')
    return row('skin', 'addons', s('skin'), True, 'OK', changed=bool(n))


def check_subsguard():
    import xbmcvfs
    from . import subspatch
    d = xbmcvfs.translatePath('special://home/addons/service.subtitles.All_Subs')
    if not os.path.isdir(d):
        return row('subsguard', 'addons', s('subsguard'), None, s('missing'))
    try:
        n = subspatch.apply(d)
        plus = xbmcvfs.translatePath('special://home/addons/service.subtitles.all_subs_plus')
        if os.path.isdir(plus):
            n += subspatch.apply_plus(plus)
    except Exception as e:
        return row('subsguard', 'addons', s('subsguard'), False, str(e)[:100])
    return row('subsguard', 'addons', s('subsguard'), True, 'OK', changed=bool(n))


def check_ytport(fix=False):
    from . import ytport
    ok, detail = ytport.check(fix=fix)
    return row('ytport', 'addons', s('ytport'), ok, detail, changed='->' in detail)


def check_service(k):
    from . import accounts
    name = dict(accounts.ROWS)[k]
    ok, detail = accounts.check(k)
    return row('svc:' + k, 'services', name, ok, detail or (T('ok') if ok else T('missing')))


def run_iptv():
    from . import iptv
    n, errors = iptv.merge(notify=False)
    return row('iptv', 'content', s('iptv'), n > 0 and not errors,
               '%d %s%s' % (n, T('channels'), (' · ' + '; '.join(errors)) if errors else ''), changed=n > 0)


def check_pvr():
    n = len((_rpc('PVR.GetChannels', channelgroupid='alltv').get('result') or {}).get('channels', []))
    return row('pvr', 'content', s('pvr'), n > 0, '%d %s' % (n, T('channels')))


def check_radio():
    from .radio import _get
    try:
        n = len(_get('/stations/bycountrycodeexact/IL', limit=50))
    except Exception as e:
        return row('radio', 'content', s('radio'), False, str(e)[:80])
    return row('radio', 'content', s('radio'), n > 0, '%d' % n)


def run_cache():
    """drop cached TMDb answers and load fresh ones"""
    from .common import tmdb
    cdir = os.path.join(PROFILE, 'cache')
    n = len(os.listdir(cdir)) if os.path.isdir(cdir) else 0
    shutil.rmtree(cdir, ignore_errors=True)
    try:
        tmdb('/trending/movie/week')
        return row('cache', 'content', s('cache'), True, '%s (%d)' % (s('cleared'), n), changed=True)
    except Exception as e:
        return row('cache', 'content', s('cache'), False, str(e)[:80])


# ---------------------------------------------------------------- fixes
def fix(rid):
    """repair one line; returns the line checked again"""
    from . import accounts
    from .iptv import install_addon
    if rid == 'internet':
        monitor().waitForAbort(5)
        return check_internet()
    if rid == 'autoupd':
        _rpc('Settings.SetSettingValue', setting='general.addonupdates', value=0)
        return check_autoupdate()
    if rid == 'repos':
        return run_repos()
    if rid.startswith('addon:'):
        aid = rid.split(':', 1)[1]
        name = dict(core_addons()).get(aid, aid)
        det = (_rpc('Addons.GetAddonDetails', addonid=aid, properties=['enabled', 'broken']).get('result') or {}).get('addon')
        if det and not det.get('enabled') and not det.get('broken'):
            _rpc('Addons.SetAddonEnabled', addonid=aid, enabled=True)
            monitor().waitForAbort(2)
        else:                       # missing or broken: (re)install from the repository
            install_addon(aid, timeout=120)
            _rpc('Addons.SetAddonEnabled', addonid=aid, enabled=True)
        return check_addon(aid, name)
    if rid == 'hook':
        return check_hook()
    if rid == 'skin':
        return check_skin()
    if rid == 'ytport':
        return check_ytport(fix=True)
    if rid == 'subsguard':
        return check_subsguard()
    if rid.startswith('svc:'):
        k = rid.split(':', 1)[1]
        if k == 'server':
            from .subsnet import discover_server
            ADDON.setSetting('sub_server', ADDON.getSetting('sub_server') or 'http://127.0.0.1:8765')
            discover_server()
        elif k == 'iptv':
            from . import iptv
            iptv.merge(notify=False)
        else:                       # logins and keys: only the owner can enter them - open the right screen
            xbmcgui.Dialog().ok('BN Stream – ' + s('fix'), s('needs_user') + accounts.hint(k))
            accounts.action(k)
        return check_service(k)
    if rid == 'iptv':
        return run_iptv()
    if rid == 'pvr':
        from . import iptv
        iptv.configure_pvr()
        return check_pvr()
    if rid == 'radio':
        save('radio_cache.json', {})
        return check_radio()
    if rid == 'cache':
        return run_cache()
    return None


# ---------------------------------------------------------------- run + report
def run():
    """the System Update button"""
    from . import accounts
    pd = xbmcgui.DialogProgress()
    pd.create('BN Stream – ' + s('title'), s('running'))
    rows = []
    jobs = [(s('internet'), check_internet), (s('repos'), 'repos'), (s('autoupd'), check_autoupdate)]
    jobs += [(name, (lambda a=aid, n=name: check_addon(a, n))) for aid, name in core_addons()]
    jobs += [(s('hook'), check_hook), (s('skin'), check_skin), (s('subsguard'), check_subsguard), (s('ytport'), check_ytport)]
    jobs += [(name, (lambda k=k: check_service(k))) for k, name in accounts.ROWS]
    jobs += [(s('iptv'), run_iptv), (s('pvr'), check_pvr), (s('radio'), check_radio), (s('cache'), run_cache)]
    for i, (label, job) in enumerate(jobs):
        if pd.iscanceled():
            break
        base = int(i * 100 / len(jobs))
        pd.update(base, '%s\n%s' % (s('running'), label))
        try:
            if job == 'repos':
                r = run_repos(lambda p, b=base: pd.update(b, '%s\n%s  %d%%' % (s('running'), label, p)))
            else:
                r = job()
        except Exception as e:
            log('system update %s: %s' % (label, e), xbmc.LOGWARNING)
            r = row('err:%d' % i, 'update', label, False, str(e)[:120])
        rows.append(r)
    pd.close()
    rep = {'when': now_str(), 'ts': time.time(), 'rows': rows}
    save('sysupdate.json', rep)
    bad = [r for r in rows if r['ok'] is False]
    log('system update: %d rows, %d errors %s' % (len(rows), len(bad), [b['id'] for b in bad]))
    return rep


def summary(rep):
    rows = rep.get('rows', [])
    return s('summary') % (sum(1 for r in rows if r.get('changed')), sum(1 for r in rows if r['ok']),
                           sum(1 for r in rows if r['ok'] is False))


def _mark(ok):
    return '[COLOR limegreen]●[/COLOR]' if ok else ('[COLOR grey]○[/COLOR]' if ok is None else '[COLOR red]●[/COLOR]')


def listing(handle, url):
    """the report: one line per part; an Auto-Fix entry right below every line with an error"""
    rep = load('sysupdate.json', {})

    def add(label, target, plot='', folder=False):
        li = xbmcgui.ListItem(label)
        li.getVideoInfoTag().setPlot(plot)
        li.setArt({'icon': 'DefaultAddonService.png'})
        xbmcplugin.addDirectoryItem(handle, target, li, folder)
    if not rep:
        add(s('no_report'), url(a='sysupdate'))
    else:
        rows = rep['rows']
        add('[B][COLOR FFE8BE5A]%s  ·  %s[/COLOR][/B]' % (s('report'), rep['when']), url(a='noop'), summary(rep))
        add('[B]%s[/B]   [COLOR grey]%s[/COLOR]' % (summary(rep), rep['when']), url(a='noop'), summary(rep))
        if any(r['ok'] is False for r in rows):
            add('[B][COLOR gold]» %s[/COLOR][/B]' % s('fix_all'), url(a='sysfix', id='*'))
        section = None
        for r in rows:
            if r['section'] != section:
                section = r['section']
                add('[B][COLOR FFE8BE5A]%s[/COLOR][/B]' % s('sec_' + section), url(a='noop'))
            star = '  [COLOR FF5AB4E8]↑[/COLOR]' if r.get('changed') else ''
            add('%s  %s%s   [COLOR grey]%s[/COLOR]' % (_mark(r['ok']), r['name'], star, r['detail']),
                url(a='sysfix', id=r['id']) if r['ok'] is False else url(a='noop'), r['detail'])
            if r['ok'] is False:
                add('        [B][COLOR gold]» %s[/COLOR][/B]  [COLOR grey]%s[/COLOR]' % (s('fix'), r['name']),
                    url(a='sysfix', id=r['id']), r['detail'])
    add('[COLOR FF5AB4E8]%s[/COLOR]' % s('again'), url(a='sysupdate'))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def do_fix(rid):
    rep = load('sysupdate.json', {'rows': []})
    targets = [r for r in rep['rows'] if r['ok'] is False and (rid == '*' or r['id'] == rid)]
    pd = xbmcgui.DialogProgress()
    pd.create('BN Stream – ' + s('fix'), '')
    results = []
    for i, r in enumerate(targets):
        if pd.iscanceled():
            break
        pd.update(int(i * 100 / max(1, len(targets))), '%s\n%s' % (s('fix'), r['name']))
        try:
            new = fix(r['id']) if not r['id'].startswith('err:') else None
        except Exception as e:
            log('auto-fix %s: %s' % (r['id'], e), xbmc.LOGWARNING)
            new = dict(r, detail=str(e)[:120])
        if new:
            new['section'] = r['section']
            r.update(new)
        results.append(r)
    pd.close()
    save('sysupdate.json', rep)
    ok = [r for r in results if r['ok'] is not False]
    if len(results) == 1:
        r = results[0]
        msg = '%s: %s' % (s('fixed') if r['ok'] is not False else s('not_fixed'), r['name'])
    else:
        msg = '%s: %d/%d' % (s('fixed'), len(ok), len(results))
    xbmcgui.Dialog().notification('BN Stream', msg, xbmcgui.NOTIFICATION_INFO if len(ok) == len(results)
                                  else xbmcgui.NOTIFICATION_WARNING, 5000)
