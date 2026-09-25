# -*- coding: utf-8 -*-
"""AI Subtitle Generation button in the player and the subtitle window of the BN skin (skin.fentastic).

Pure Python (no Kodi modules): used by tools/make_build.py for new builds and by the service at start-up,
so boxes that update NovaTV from the repository get the button too (idempotent)."""
import os
import re

AI_RUN = 'RunPlugin(plugin://plugin.video.nova/?a=ai_subs_now)'
AI_LABEL = 'יצירת כתוביות AI'


def apply(xml):
    """'AI Subtitle Generation' next to the subtitle buttons of every player style and in the subtitle window.
    Returns how many skin files were changed (0 = already there)."""
    n = 0
    item = ('\n\t<item>\n\t\t<label>%s</label>\n\t\t<icon>osd/fullscreen/buttons/subs3.png</icon>\n'
            '\t\t<onclick>%s</onclick>\n\t\t<visible>!VideoPlayer.Content(LiveTV)</visible>\n\t</item>') % (AI_LABEL, AI_RUN)
    # item-list players (advanced, netflix): right after "search subtitles"
    for fn, rx in (('Includes_VideoOsd.xml', r'(<item id="107">.*?</item>)'),
                   ('Includes_VideoOsd1.xml', r'(<item id="107">.*?</item>)'),
                   ('Includes_VideoOsd2.xml', r'(<item>\s*<label>חפש כתובית</label>.*?</item>)')):
        p = os.path.join(xml, fn)
        t = open(p, encoding='utf-8', newline='').read()
        if AI_RUN not in t:
            t, k = re.subn(rx, lambda m: m.group(1) + item, t, count=1, flags=re.S)
            assert k, 'subtitle item not found in ' + fn
            open(p, 'w', encoding='utf-8', newline='').write(t)
            n += 1
    # simple player: a button after the DarkSubs button
    p = os.path.join(xml, 'Includes_VideoOsd3.xml')
    t = open(p, encoding='utf-8', newline='').read()
    if AI_RUN not in t:
        btn = ('\n\t\t\t\t\t<control type="button" id="700452">\n\t\t\t\t\t\t<description>BN AI subtitles</description>\n'
               '\t\t\t\t\t\t<width>225</width>\n\t\t\t\t\t\t<height>76</height>\n\t\t\t\t\t\t<label>[B]AI[/B] כתוביות</label>\n'
               '\t\t\t\t\t\t<font>font12</font>\n\t\t\t\t\t\t<align>center</align>\n\t\t\t\t\t\t<aligny>center</aligny>\n'
               '\t\t\t\t\t\t<textcolor>grey_a</textcolor>\n\t\t\t\t\t\t<focusedcolor>button_focus</focusedcolor>\n'
               '\t\t\t\t\t\t<texturenofocus />\n\t\t\t\t\t\t<texturefocus />\n'
               '\t\t\t\t\t\t<onclick>%s</onclick>\n\t\t\t\t\t\t<visible>!VideoPlayer.Content(LiveTV)</visible>\n'
               '\t\t\t\t\t</control>') % AI_RUN
        t, k = re.subn(r'(<control type="button" id="700451">.*?</control>)', lambda m: m.group(1) + btn, t, count=1, flags=re.S)
        assert k, 'DarkSubs button not found'
        open(p, 'w', encoding='utf-8', newline='').write(t)
        n += 1
    # Kodi's subtitle window (the default "search subtitles" of the player): a button above the services list
    p = os.path.join(xml, 'DialogSubtitles.xml')
    t = open(p, encoding='utf-8', newline='').read()
    if AI_RUN not in t:
        btn = ('<control type="button" id="7160">\n\t\t\t\t\t<description>BN AI subtitles</description>\n'
               '\t\t\t\t\t<left>20</left>\n\t\t\t\t\t<top>120</top>\n\t\t\t\t\t<width>280</width>\n\t\t\t\t\t<height>60</height>\n'
               '\t\t\t\t\t<label>[B]%s[/B]</label>\n\t\t\t\t\t<font>font12</font>\n\t\t\t\t\t<align>center</align>\n'
               '\t\t\t\t\t<aligny>center</aligny>\n\t\t\t\t\t<textcolor>FFE8BE5A</textcolor>\n'
               '\t\t\t\t\t<texturefocus colordiffuse="button_focus">colors/white.png</texturefocus>\n'
               '\t\t\t\t\t<texturenofocus colordiffuse="30FFFFFF">colors/white.png</texturenofocus>\n'
               '\t\t\t\t\t<focusedcolor>black</focusedcolor>\n'
               '\t\t\t\t\t<onleft>120</onleft>\n\t\t\t\t\t<ondown>150</ondown>\n'
               '\t\t\t\t\t<onclick>%s</onclick>\n\t\t\t\t</control>\n\t\t\t\t') % (AI_LABEL, AI_RUN)
        assert '<control type="list" id="150">' in t and '<onup>150</onup>' in t
        t = t.replace('<control type="list" id="150">', btn + '<control type="list" id="150">', 1)
        t = t.replace('<onup>150</onup>', '<onup>7160</onup>', 1)
        open(p, 'w', encoding='utf-8', newline='').write(t)
        n += 1
    return n
