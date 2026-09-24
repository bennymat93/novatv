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

import xbmc
import xbmcgui

from resources.lib.common import ADDON, T, load, save, now_str, log, PROFILE

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
            play = ('plugin://plugin.video.pov/?mode=play_media&mediatype=episode&tmdb_id=%s&season=%s&episode=%s'
                    % (tmdb_id, s, e)) if tmdb_id else ''
        else:
            label = tag.getTitle() or xbmc.getInfoLabel('Player.Title')
            key = 'movie:%s' % (tmdb_id or label)
            play = ('plugin://plugin.video.pov/?mode=play_media&mediatype=movie&tmdb_id=%s' % tmdb_id) if tmdb_id else ''
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

    def subtitle_flow(self, sid):
        mon = xbmc.Monitor()
        wait = int(ADDON.getSetting('ai_wait') or 25)
        # give embedded tracks + All_Subs (human Hebrew) the first chance
        for _ in range(wait * 2):
            if mon.waitForAbort(0.5) or sid != self.session:
                return
            if self.has_hebrew():
                return
        if sid != self.session or not self.isPlayingVideo():
            return
        path = self.getPlayingFile()
        if not path.startswith(('http://', 'https://')):
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
        loaded_upto, last_note = 0.0, 0
        srt_path = os.path.join(PROFILE, 'ai_%s.he.srt' % job_id)
        while sid == self.session and not mon.abortRequested():
            try:
                st = requests.get('%s/jobs/%s' % (base, job_id), timeout=10).json()
            except Exception:
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
            # (re)load when a meaningful new chunk is ready or when finished
            if ready - loaded_upto >= 120 or (done and ready > loaded_upto):
                try:
                    data = requests.get('%s/jobs/%s/srt' % (base, job_id), timeout=20).content
                    with open(srt_path, 'wb') as f:
                        f.write(data)
                    self.setSubtitles(srt_path)
                    self.showSubtitles(True)
                    loaded_upto = ready
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


def discover_server():
    """Find the PC subtitle server on the LAN (UDP broadcast) if the saved address is dead."""
    import socket
    import requests
    base = ADDON.getSetting('sub_server').rstrip('/')
    try:
        requests.get(base + '/health', timeout=2)
        return
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(2)
    try:
        for _ in range(3):
            s.sendto(b'NOVASUBS?', ('255.255.255.255', 8766))
            try:
                data, addr = s.recvfrom(64)
            except socket.timeout:
                continue
            if data.startswith(b'NOVASUBS '):
                url = 'http://%s:%s' % (addr[0], data.split()[1].decode())
                ADDON.setSetting('sub_server', url)
                log('subtitle server discovered at %s' % url)
                return
    finally:
        s.close()


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

    last_iptv = time.time() - 12 * 3600 + 120      # first refresh 2 minutes after start
    while not mon.abortRequested():
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
