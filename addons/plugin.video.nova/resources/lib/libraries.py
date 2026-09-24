# -*- coding: utf-8 -*-
"""Free, legal libraries from the official Kodi repository - installed on first use."""
import xbmc
import xbmcgui
import xbmcplugin

from .common import T

# (addon id, he, en, ru, category)
LIBRARIES = [
    ('plugin.video.plutotv', 'Pluto TV – מאות ערוצים וסרטים', 'Pluto TV – hundreds of free channels & movies', 'Pluto TV – сотни каналов и фильмов', 'tv'),
    ('plugin.video.crackle', 'Crackle – סרטים וסדרות', 'Crackle – free movies & series', 'Crackle – фильмы и сериалы', 'movies'),
    ('plugin.video.archive.org', 'Internet Archive – סרטים קלאסיים (כולל רוסיים)', 'Internet Archive – classic films (incl. Soviet)', 'Internet Archive – классика (в т.ч. советское кино)', 'movies'),
    ('plugin.video.composite_for_plex', 'Plex – סרטים חינם', 'Plex – free movies', 'Plex – бесплатные фильмы', 'movies'),
    ('plugin.video.youtube', 'YouTube', 'YouTube', 'YouTube', 'video'),
    ('plugin.video.dailymotion_com', 'Dailymotion', 'Dailymotion', 'Dailymotion', 'video'),
    ('plugin.video.vimeo', 'Vimeo', 'Vimeo', 'Vimeo', 'video'),
    ('plugin.video.twitch', 'Twitch – שידורים חיים', 'Twitch – live streams', 'Twitch – стримы', 'video'),
    ('plugin.video.ted.talks', 'TED – הרצאות', 'TED Talks', 'TED – лекции', 'docs'),
    ('plugin.video.nasa', 'NASA', 'NASA', 'NASA', 'docs'),
    ('plugin.video.redbull.tv', 'Red Bull TV – ספורט אתגרי', 'Red Bull TV – extreme sports', 'Red Bull TV – экстрим', 'sport'),
    ('plugin.video.nhklive', 'NHK World – חדשות', 'NHK World – news', 'NHK World – новости', 'news'),
    ('plugin.video.arteplussept', 'ARTE – תרבות ותעודה', 'ARTE – culture & documentaries', 'ARTE – культура и документалистика', 'docs'),
    ('plugin.video.pbskids', 'PBS Kids – ילדים', 'PBS Kids', 'PBS Kids – детям', 'kids'),
]
LANG = {'he': 1, 'en': 2, 'ru': 3}


def menu(handle, url):
    from .common import ui_lang
    col = LANG[ui_lang()]
    for row in LIBRARIES:
        aid, label = row[0], row[col]
        installed = xbmc.getCondVisibility('System.HasAddon(%s)' % aid)
        li = xbmcgui.ListItem(label if installed else '%s  [COLOR grey](%s)[/COLOR]' % (label, T('lib_install')))
        li.setArt({'icon': 'special://home/addons/%s/icon.png' % aid if installed else 'DefaultAddonVideo.png',
                   'thumb': 'special://home/addons/%s/icon.png' % aid if installed else 'DefaultAddonVideo.png'})
        if installed:
            xbmcplugin.addDirectoryItem(handle, 'plugin://%s/' % aid, li, True)
        else:
            xbmcplugin.addDirectoryItem(handle, url(a='lib_install', id=aid), li, False)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def install(aid):
    from .iptv import install_addon
    xbmcgui.Dialog().notification('BN', '%s: %s' % (T('lib_install'), aid), xbmcgui.NOTIFICATION_INFO, 3000)
    if install_addon(aid):
        xbmc.executebuiltin('ActivateWindow(Videos,plugin://%s/,return)' % aid)
    else:
        xbmcgui.Dialog().ok('BN', '%s\n%s' % (T('bk_fail'), aid))
