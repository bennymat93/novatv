# -*- coding: utf-8 -*-
"""NovaTV background service:
 * watch history with date + time for every played item
 * AI Hebrew subtitles when no Hebrew subtitle was found, or on request (player button)
 * every new video starts clean (no subtitles / settings carried over; only 'watched' is kept)
 * periodic IPTV merge
 * open NovaTV on start
"""
import os
import re
import threading
import time
from urllib.parse import urlencode

import xbmc
import xbmcgui

from resources.lib.common import monitor

from resources.lib.common import ADDON, T, load, save, now_str, log, PROFILE
from resources.lib.subsnet import discover_server

HEB_CODES = ('heb', 'he', 'hebrew', 'iw')
WIN = xbmcgui.Window(10000)


def status(text):
    """Status visible to skins as $INFO[Window(Home).Property(NovaTV.AISubs)]."""
    WIN.setProperty('NovaTV.AISubs', text)


def forget_file_settings(path):
    """Kodi remembers subtitle/audio track, delays, zoom ... per file (MyVideos 'settings' table).
    Drop them for a played stream so the next start of any video begins clean (history/watched are kept)."""
    import glob
    import sqlite3
    import xbmcvfs
    dbs = sorted(glob.glob(os.path.join(xbmcvfs.translatePath('special://database/'), 'MyVideos*.db')),
                 key=lambda f: int(re.sub(r'\D', '', os.path.basename(f)) or 0))
    if not dbs or not path:
        return 0
    con = sqlite3.connect(dbs[-1], timeout=10)
    try:
        cur = con.execute("DELETE FROM settings WHERE idFile IN (SELECT files.idFile FROM files JOIN path ON "
                          "files.idPath = path.idPath WHERE path.strPath || files.strFilename = ? OR files.strFilename = ?)",
                          (path, path))
        con.commit()
        return cur.rowcount
    finally:
        con.close()


class Flow:
    """Subtitles for ONE video. A flow never touches a later video: every step checks it still owns the player."""

    def __init__(self, player, forced):
        self.p = player
        self.gen = player.gen
        self.file = player.file
        self.forced = forced
        self.cancelled = False
        self.held = False
        self.held_at = 0
        self.bar = None

    def same_video(self):
        return self.gen == self.p.gen and self.p.active

    def alive(self):
        return self.same_video() and not self.cancelled

    # ------------------------------------------------------------ "subtitles ready before watching"
    def hold(self):
        """pause at the start while Hebrew subtitles are prepared (setting ai_prepare)"""
        if not xbmc.getCondVisibility('Player.Paused'):
            self.p.pause()
        self.held, self.held_at = True, time.time()
        self.bar = xbmcgui.DialogProgressBG()
        self.bar.create('NovaTV', T('sub_check'))

    def still_held(self):
        """the viewer pressing Play ends the hold; never hold longer than 4 min"""
        if self.held and (not xbmc.getCondVisibility('Player.Paused') or time.time() - self.held_at > 240):
            self.release()
        return self.held

    def release(self):
        if self.bar:
            try:
                self.bar.close()
            except Exception:
                pass
            self.bar = None
        if self.held:
            self.held = False
            # only un-pause the video we paused - never the next one
            if self.same_video() and xbmc.getCondVisibility('Player.Paused'):
                self.p.pause()

    def run(self):
        try:
            self._run()
        except RuntimeError as e:          # playback ended while we were still reading it: nothing to do
            log('subtitles: playback ended (%s)' % e)
        except Exception as e:
            log('subtitles: %s' % e, xbmc.LOGWARNING)
        finally:
            self.release()
            if self.p.flow is self and not self.alive():
                status('')

    def _run(self):
        p, mon = self.p, monitor()
        if xbmc.getCondVisibility('PVR.IsPlayingTV | PVR.IsPlayingRadio | VideoPlayer.Content(livetv)'):
            if self.forced:
                xbmcgui.Dialog().notification('NovaTV', T('ai_nolive'), xbmcgui.NOTIFICATION_WARNING, 4000)
            return                                   # live TV: no end, nothing to transcribe ahead
        path = self.file
        network = path.startswith(('http://', 'https://'))
        use_ai = self.forced or ADDON.getSettingBool('ai_subs')
        if not self.forced:
            kind = p.getVideoInfoTag().getMediaType()
            # pause only films and episodes; clips (YouTube, Archive extras) just start
            if use_ai and network and kind in ('movie', 'episode') and ADDON.getSettingBool('ai_prepare'):
                self.hold()
            # this video's own Hebrew track or a human Hebrew subtitle (All_Subs) gets the first chance
            wait = int(ADDON.getSetting('ai_wait') or 25)
            for i in range(wait * 2):
                if mon.waitForAbort(0.5) or not self.alive():
                    return
                if p.has_hebrew():
                    return
                if self.bar:
                    self.bar.update(int(i * 50 / (wait * 2)), 'NovaTV', T('sub_check'))
                self.still_held()
            if not use_ai or not self.alive():
                return
        if not network:
            log('AI subs: not a network stream (%s)' % path[:60])
            if self.forced:
                xbmcgui.Dialog().notification('NovaTV', T('ai_nonet'), xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        import requests
        discover_server()                       # re-find the PC if its address changed
        base = ADDON.getSetting('sub_server').rstrip('/')
        tag = p.getVideoInfoTag()
        job = {'url': path, 'title': tag.getTVShowTitle() or tag.getTitle(), 'season': tag.getSeason(),
               'episode': tag.getEpisode(), 'imdb': tag.getIMDBNumber(), 'tmdb': tag.getUniqueID('tmdb'),
               'position': p.getTime(), 'gemini_key': ADDON.getSetting('gemini_key')}
        try:
            r = requests.post(base + '/jobs', json=job, timeout=10)
            r.raise_for_status()
            job_id = r.json()['id']
        except Exception as e:
            log('AI subs server: %s' % e, xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('NovaTV', T('ai_noserver'), xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        xbmcgui.Dialog().notification('NovaTV', T('ai_forced') if self.forced else T('ai_start'),
                                      xbmcgui.NOTIFICATION_INFO, 5000)
        status('%s 0%%' % T('ai_progress'))
        loaded_upto, last_note, down_since, warned = -1.0, 0, 0, False
        srt_path = os.path.join(PROFILE, 'ai_%s.he.srt' % job_id)
        while self.alive() and not mon.abortRequested():
            try:
                r = requests.get('%s/jobs/%s' % (base, job_id), timeout=10)
                if r.status_code == 404:        # server restarted: hand the job over again (it resumes)
                    job['position'] = p.getTime() if self.alive() else job['position']
                    r = requests.post(base + '/jobs', json=job, timeout=10)
                st = r.json()
                down_since, warned = 0, False
            except Exception:
                down_since = down_since or time.time()
                if time.time() - down_since > 120 and not warned:
                    xbmcgui.Dialog().notification('NovaTV', T('ai_noserver'), xbmcgui.NOTIFICATION_WARNING, 5000)
                    warned = True
                    discover_server()
                    base = ADDON.getSetting('sub_server').rstrip('/')
                if mon.waitForAbort(5):
                    return
                continue
            pct = int(st.get('progress', 0))
            status('%s %d%%' % (T('ai_progress'), pct))
            now = time.time()
            if now - last_note > 60 and st.get('state') != 'done':
                xbmcgui.Dialog().notification(T('ai_progress'), '%d%% · %s' % (pct, st.get('stage', '')),
                                              xbmcgui.NOTIFICATION_INFO, 3000, False)
                last_note = now
            ready = float(st.get('ready_until', 0))
            done = st.get('state') == 'done'
            if self.still_held() and self.bar:
                self.bar.update(50 + min(49, pct // 2), 'NovaTV', '%s %d%%' % (T('ai_prepare'), pct))
            # load the first part as soon as it exists, then again for every meaningful new chunk and at the end
            first = loaded_upto < 0 and ready > 0
            if first or ready - loaded_upto >= 120 or (done and ready > loaded_upto):
                try:
                    data = requests.get('%s/jobs/%s/srt' % (base, job_id), timeout=20).content
                    if not self.alive():
                        return
                    with open(srt_path, 'wb') as f:
                        f.write(data)
                    p.setSubtitles(srt_path)      # adds the file and makes it the active track
                    p.chosen = self.gen
                    p.showSubtitles(True)
                    log('AI subtitles loaded up to %ds (%s)' % (ready, 'button' if self.forced else 'auto'))
                    loaded_upto = ready
                    if self.still_held() and (done or ready >= job['position'] + 120):
                        self.release()      # the first part is subtitled: start watching
                except Exception as e:
                    log('AI subs load: %s' % e, xbmc.LOGWARNING)
            if done:
                status('')
                xbmcgui.Dialog().notification('NovaTV', T('ai_ready'), xbmcgui.NOTIFICATION_INFO, 4000)
                return
            if st.get('state') == 'error':
                status('')
                xbmcgui.Dialog().notification('NovaTV', '%s: %s' % (T('error'), st.get('error', '')[:80]),
                                              xbmcgui.NOTIFICATION_ERROR, 6000)
                return
            if mon.waitForAbort(5):
                return


class Player(xbmc.Player):
    """Every new video starts clean: no subtitles, pause, job or status left over from the previous one.
    Only the history ('watched') is carried over."""

    def __init__(self):
        super().__init__()
        self.gen = 0            # bumped on every start/end: flows of an older video stop by themselves
        self.file = ''
        self.active = False
        self.flow = None
        self.chosen = 0         # gen whose subtitles were deliberately switched on
        self.lock = threading.Lock()

    def playing_file(self):
        try:
            return self.getPlayingFile() if self.isPlayingVideo() else ''
        except RuntimeError:
            return ''

    def onAVStarted(self):
        path = self.playing_file()
        if not path:
            return
        if self.active and path == self.file:
            return          # the same video announced again (stream switch): keep what the viewer chose
        self.begin(path)
        try:
            self.record_history()
        except Exception as e:
            log('history: %s' % e, xbmc.LOGWARNING)
        self.start_flow(forced=False)

    def begin(self, path):
        with self.lock:
            if self.flow:
                self.flow.cancelled = True
            self.gen += 1
            self.file, self.active, self.flow = path, True, None
        status('')
        self.chosen = 0
        gen = self.gen
        try:
            self.showSubtitles(False)      # subtitles must be chosen (or generated) for THIS video
        except RuntimeError:
            pass

        def again():
            # on playlist auto-advance (next episode) Kodi applies the item's saved subtitle state a moment
            # AFTER onAVStarted: switch off again unless this video's subtitles were chosen in the meantime
            for delay in (1.0, 2.0):
                if monitor().waitForAbort(delay) or gen != self.gen or self.chosen == gen:
                    return
                try:
                    self.showSubtitles(False)
                except RuntimeError:
                    return
        threading.Thread(target=again, daemon=True).start()

    def finish(self):
        with self.lock:
            if self.flow:
                self.flow.cancelled = True
            self.gen += 1
            ended, self.file, self.active, self.flow = self.file, '', False, None
        status('')
        if ended.startswith(('http://', 'https://')):
            # Kodi stores the file's settings right after the stop: clear them once it has
            def later():
                monitor().waitForAbort(6)
                try:
                    n = forget_file_settings(ended)
                    if n:
                        log('cleared %d stored player setting(s) of the last video' % n)
                except Exception as e:
                    log('player settings reset: %s' % e, xbmc.LOGWARNING)
            threading.Thread(target=later, daemon=True).start()

    def onPlayBackStopped(self):
        self.finish()

    onPlayBackEnded = onPlayBackStopped
    onPlayBackError = onPlayBackStopped

    def start_flow(self, forced):
        with self.lock:
            if self.flow:
                self.flow.cancelled = True
            flow = self.flow = Flow(self, forced)
        threading.Thread(target=flow.run, daemon=True).start()

    def ai_now(self):
        """'AI subtitles' button: generate Hebrew AI subtitles for this video, even when others exist"""
        path = self.playing_file()
        log('AI subtitles requested for %s' % path[:80])
        if not path:
            xbmcgui.Dialog().notification('NovaTV', T('ai_noplay'), xbmcgui.NOTIFICATION_WARNING, 4000)
            return
        if not (self.active and path == self.file):     # started before the service was running
            with self.lock:
                self.gen += 1
                self.file, self.active = path, True
        self.start_flow(forced=True)

    # ------------------------------------------------------------ history
    def record_history(self):
        if not self.isPlayingVideo():
            return
        tag = self.getVideoInfoTag()
        tmdb_id = tag.getUniqueID('tmdb') or xbmc.getInfoLabel('VideoPlayer.UniqueID(tmdb)')
        show = tag.getTVShowTitle()
        s, e = tag.getSeason(), tag.getEpisode()
        if show and e > 0:
            label = '%s  S%02dE%02d  %s' % (show, s, e, tag.getTitle())
            key = 'tv:%s:%s:%s' % (tmdb_id or show, s, e)
            play = ('plugin://plugin.video.nova/?' + urlencode({'a': 'play', 'm': 'episode', 'id': tmdb_id, 's': s, 'e': e,
                                                                'q': '%s %s' % (show, tag.getTitle())})) if tmdb_id else ''
        else:
            label = tag.getTitle() or xbmc.getInfoLabel('Player.Title')
            key = 'movie:%s' % (tmdb_id or label)
            play = ('plugin://plugin.video.nova/?' + urlencode({'a': 'play', 'm': 'movie', 'id': tmdb_id, 'q': label})) if tmdb_id else ''
        entry = {'key': key, 'label': label, 'when': now_str(), 'ts': time.time(), 'play': play,
                 'plot': tag.getPlot(), 'thumb': xbmc.getInfoLabel('Player.Art(thumb)'),
                 'fanart': xbmc.getInfoLabel('Player.Art(fanart)')}
        hist = [h for h in load('history.json', []) if h.get('key') != key]
        hist.insert(0, entry)
        save('history.json', hist[:2000])

    # ------------------------------------------------------------ subtitles
    def has_hebrew(self):
        """a Hebrew track of the playing video (embedded, or added by All_Subs) -> make it the active one"""
        active = (xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage') or '').lower()
        if xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled') and active in HEB_CODES:
            self.chosen = self.gen
            return True
        for i, lang in enumerate(self.getAvailableSubtitleStreams()):
            if (lang or '').lower() in HEB_CODES:
                self.chosen = self.gen
                self.setSubtitleStream(i)
                self.showSubtitles(True)
                return True
        return False


class Monitor(xbmc.Monitor):
    """NotifyAll(plugin.video.nova,ai_now) from the player's AI button / NovaTV"""

    def __init__(self, player):
        super().__init__()
        self.player = player

    def onNotification(self, sender, method, data):
        if sender == 'plugin.video.nova' and method.endswith('ai_now'):
            threading.Thread(target=self.player.ai_now, daemon=True).start()


def main():
    monitor()               # the shared Monitor is created here, on the main thread, and lives until exit
    player = Player()
    mon = Monitor(player)
    try:        # boxes updated from the repository: add the AI subtitle button to the installed skin once
        import xbmcvfs
        from resources.lib import skinpatch
        skin_xml = xbmcvfs.translatePath('special://home/addons/skin.fentastic/xml')
        if os.path.isdir(skin_xml) and skinpatch.apply(skin_xml):
            log('AI subtitle button added to the skin')
            xbmc.executebuiltin('ReloadSkin()')
    except Exception as e:
        log('skin button: %s' % e, xbmc.LOGWARNING)
    try:        # YouTube's local server port inside a range Windows reserved -> no YouTube playback
        from resources.lib import ytport
        ytport.check(fix=True)
    except Exception as e:
        log('YouTube port: %s' % e, xbmc.LOGWARNING)
    try:        # All_Subs updates itself and loses its guards: put them back (takes effect at its next start)
        import xbmcvfs
        from resources.lib import subspatch
        subs_dir = xbmcvfs.translatePath('special://home/addons/service.subtitles.All_Subs')
        if os.path.isdir(subs_dir) and subspatch.apply(subs_dir):
            log('All_Subs guards applied')
        plus_dir = xbmcvfs.translatePath('special://home/addons/service.subtitles.all_subs_plus')
        if os.path.isdir(plus_dir) and subspatch.apply_plus(plus_dir):
            log('All Subs Plus exit guard applied')
    except Exception as e:
        log('All_Subs guards: %s' % e, xbmc.LOGWARNING)
    threading.Thread(target=discover_server, daemon=True).start()
    if ADDON.getSettingBool('open_on_start'):
        xbmc.sleep(2500)
        xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.nova/,return)')
    def later(delay, job):
        """run a job after a delay in a background thread that never keeps Kodi from quitting
        (threading.Timer is not a daemon: Kodi waited for it on exit, killed the service and could crash)"""
        def run():
            if not monitor().waitForAbort(delay):
                job()
        threading.Thread(target=run, daemon=True).start()

    # Player callbacks are delivered on this thread while it waits, so long jobs
    # (IPTV / EPG download) must run in their own thread.
    def iptv_job():
        try:
            from resources.lib import iptv
            iptv.merge(notify=False)
        except Exception as e:
            log('iptv merge: %s' % e, xbmc.LOGWARNING)

    def backup_job():
        try:
            from resources.lib import backup
            backup.auto_backup()
        except Exception as e:
            log('auto backup: %s' % e, xbmc.LOGWARNING)
    later(600, backup_job)      # 10 min after start, at most once a week

    def binary_job():
        # platform-specific add-ons (video streams of YouTube, Pluto, ... need inputstream.adaptive) are not
        # shipped inside the Android app: install the right build for this device from the Kodi repository
        try:
            from resources.lib.iptv import install_addon
            for aid in ('inputstream.adaptive',):
                if not xbmc.getCondVisibility('System.HasAddon(%s)' % aid):
                    log('installing %s for this platform: %s' % (aid, install_addon(aid)))
        except Exception as e:
            log('binary add-ons: %s' % e, xbmc.LOGWARNING)
    later(45, binary_job)

    def startup_job():
        """tell the viewer when everything is up: add-ons, services, how much content"""
        try:
            import json as _json
            start = time.time()
            # a first start installs the TV add-on and loads channels (~2-5 min): announce after that,
            # so the table never shows "0 channels" just because it was too early
            while not mon.abortRequested() and time.time() - start < 420:
                r = _json.loads(xbmc.executeJSONRPC(_json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'PVR.GetChannels',
                                                                'params': {'channelgroupid': 'alltv'}})))
                busy = WIN.getProperty('NovaTV.iptv_busy') == '1'
                if (r.get('result') or {}).get('channels') and not busy and time.time() - start > 20:
                    break
                if mon.waitForAbort(5):
                    return
            while xbmc.getCondVisibility('System.HasActiveModalDialog') and not mon.abortRequested():
                if mon.waitForAbort(2):
                    return
            from resources.lib import status as _status
            data = _status.announce()
            if ADDON.getSettingBool('status_on_start') and not xbmc.getCondVisibility('Player.HasMedia'):
                _status.show_dialog(data)
        except Exception as e:
            log('startup status: %s' % e, xbmc.LOGWARNING)
    threading.Thread(target=startup_job, daemon=True).start()

    def pov_hook_job():
        from resources.lib import providers
        providers.ensure_pov_hook()

    last_iptv = time.time() - 12 * 3600 + 120      # first refresh 2 minutes after start
    last_hook = 0
    while not mon.abortRequested():
        if time.time() - last_hook > 1800:             # POV may have auto-updated: keep NovaTV's fallback hook
            last_hook = time.time()
            threading.Thread(target=pov_hook_job, daemon=True).start()
        hours = int(ADDON.getSetting('iptv_refresh_h') or 12)
        from resources.lib import iptv as _iptv
        if _iptv.all_m3u(_iptv.sources()) and time.time() - last_iptv > hours * 3600:
            last_iptv = time.time()
            threading.Thread(target=iptv_job, daemon=True).start()
        if mon.waitForAbort(5):
            break
    del player


if __name__ == '__main__':
    main()
