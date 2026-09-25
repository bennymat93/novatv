# -*- coding: utf-8 -*-
"""NovaTV background service:
 * watch history with date + time for every played item
 * AI Hebrew subtitles when no Hebrew subtitle was found
 * periodic IPTV merge
 * open NovaTV on start
"""
import os
import threading
import time
from urllib.parse import urlencode

import xbmc
import xbmcgui

from resources.lib.common import ADDON, T, load, save, now_str, log, PROFILE
from resources.lib.subsnet import discover_server

HEB_CODES = ('heb', 'he', 'hebrew', 'iw')
WIN = xbmcgui.Window(10000)


def status(text):
    """Status visible to skins as $INFO[Window(Home).Property(NovaTV.AISubs)]."""
    WIN.setProperty('NovaTV.AISubs', text)


class Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.session = 0

    def onAVStarted(self):
        self.session += 1
        sid = self.session
        try:
            self.record_history()
        except Exception as e:
            log('history: %s' % e, xbmc.LOGWARNING)
        if self.isPlayingVideo() and ADDON.getSettingBool('ai_subs'):
            threading.Thread(target=self.subtitle_flow, args=(sid,), daemon=True).start()

    def onPlayBackStopped(self):
        self.session += 1
        status('')

    onPlayBackEnded = onPlayBackStopped

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
        active = (xbmc.getInfoLabel('VideoPlayer.SubtitlesLanguage') or '').lower()
        if xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled') and active in HEB_CODES:
            return True
        for i, lang in enumerate(self.getAvailableSubtitleStreams()):
            if (lang or '').lower() in HEB_CODES:
                self.setSubtitleStream(i)
                self.showSubtitles(True)
                return True
        return False

    # ------------------------------------------------------------ "subtitles ready before watching"
    def hold(self):
        """pause at the start while Hebrew subtitles are prepared (setting ai_prepare)"""
        if not xbmc.getCondVisibility('Player.Paused'):
            self.pause()
        self._held = True
        self._held_at = time.time()
        self._bar = xbmcgui.DialogProgressBG()
        self._bar.create('NovaTV', T('sub_check'))

    def held(self):
        """still holding? the viewer pressing Play ends the hold"""
        if getattr(self, '_held', False) and (not xbmc.getCondVisibility('Player.Paused')
                                              or time.time() - self._held_at > 240):   # never hold longer than 4 min
            self.release()
        return getattr(self, '_held', False)

    def release(self):
        if getattr(self, '_bar', None):
            try:
                self._bar.close()
            except Exception:
                pass
            self._bar = None
        if getattr(self, '_held', False):
            self._held = False
            if xbmc.getCondVisibility('Player.Paused'):
                self.pause()

    def subtitle_flow(self, sid):
        try:
            self._subtitle_flow(sid)
        except RuntimeError as e:          # playback ended while we were still reading it: nothing to do
            log('AI subs: playback ended (%s)' % e)
        finally:
            self.release()

    def _subtitle_flow(self, sid):
        mon = xbmc.Monitor()
        wait = int(ADDON.getSetting('ai_wait') or 25)
        path = self.getPlayingFile() if self.isPlayingVideo() else ''
        if xbmc.getCondVisibility('PVR.IsPlayingTV | PVR.IsPlayingRadio | VideoPlayer.Content(livetv)'):
            return                                   # live TV: no end, nothing to transcribe ahead
        network = path.startswith(('http://', 'https://'))
        kind = self.getVideoInfoTag().getMediaType()
        # pause only films and episodes; clips (YouTube, Archive extras) just start
        if network and kind in ('movie', 'episode') and ADDON.getSettingBool('ai_prepare'):
            self.hold()
        # give embedded tracks + All_Subs (human Hebrew) the first chance
        for i in range(wait * 2):
            if mon.waitForAbort(0.5) or sid != self.session:
                return
            if self.has_hebrew():
                return
            if getattr(self, '_bar', None):
                self._bar.update(int(i * 50 / (wait * 2)), 'NovaTV', T('sub_check'))
        if sid != self.session or not self.isPlayingVideo():
            return
        if not network:
            log('AI subs: not a network stream (%s)' % path[:60])
            return
        import requests
        discover_server()                       # re-find the PC if its address changed
        base = ADDON.getSetting('sub_server').rstrip('/')
        tag = self.getVideoInfoTag()
        job = {'url': path, 'title': tag.getTVShowTitle() or tag.getTitle(), 'season': tag.getSeason(),
               'episode': tag.getEpisode(), 'imdb': tag.getIMDBNumber(), 'tmdb': tag.getUniqueID('tmdb'),
               'position': self.getTime(), 'gemini_key': ADDON.getSetting('gemini_key')}
        try:
            r = requests.post(base + '/jobs', json=job, timeout=10)
            r.raise_for_status()
            job_id = r.json()['id']
        except Exception as e:
            log('AI subs server: %s' % e, xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('NovaTV', T('ai_noserver'), xbmcgui.NOTIFICATION_WARNING, 5000)
            return
        xbmcgui.Dialog().notification('NovaTV', T('ai_start'), xbmcgui.NOTIFICATION_INFO, 5000)
        loaded_upto, last_note, down_since, warned = 0.0, 0, 0, False
        srt_path = os.path.join(PROFILE, 'ai_%s.he.srt' % job_id)
        while sid == self.session and not mon.abortRequested():
            try:
                r = requests.get('%s/jobs/%s' % (base, job_id), timeout=10)
                if r.status_code == 404:        # server restarted: hand the job over again (it resumes)
                    job['position'] = self.getTime() if self.isPlayingVideo() else job['position']
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
            if self.held():
                bar = getattr(self, '_bar', None)
                if bar:
                    bar.update(50 + min(49, pct // 2), 'NovaTV', '%s %d%%' % (T('ai_prepare'), pct))
            # (re)load when a meaningful new chunk is ready or when finished
            if ready - loaded_upto >= 120 or (done and ready > loaded_upto):
                try:
                    data = requests.get('%s/jobs/%s/srt' % (base, job_id), timeout=20).content
                    with open(srt_path, 'wb') as f:
                        f.write(data)
                    self.setSubtitles(srt_path)
                    self.showSubtitles(True)
                    loaded_upto = ready
                    if self.held() and (done or ready >= job['position'] + 120):
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


def main():
    mon = xbmc.Monitor()
    threading.Thread(target=discover_server, daemon=True).start()
    player = Player()
    if ADDON.getSettingBool('open_on_start'):
        xbmc.sleep(2500)
        xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.nova/,return)')
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
    threading.Timer(600, backup_job).start()      # 10 min after start, at most once a week

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
    threading.Timer(45, binary_job).start()

    def startup_job():
        """tell the viewer when everything is up: add-ons, services, how much content"""
        try:
            import json as _json
            start = time.time()
            while not mon.abortRequested() and time.time() - start < 180:
                r = _json.loads(xbmc.executeJSONRPC(_json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'PVR.GetChannels',
                                                                'params': {'channelgroupid': 'alltv'}})))
                if (r.get('result') or {}).get('channels') and time.time() - start > 20:
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
