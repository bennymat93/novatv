# -*- coding: utf-8 -*-
"""User guide (English + Hebrew) generated from the project itself, so it is current on every release.

  python tools/make_guide.py            -> docs/guide.html, docs/GUIDE.md (+ site/guide.html when site/ exists)

Dynamic parts: version (addon.xml), free TV lists + libraries (source files), download links,
last test run (work/test_report.json) and the changelog (git log "vX.Y.Z:" commits).
Hebrew blocks are dir="rtl"; English and every code/path/URL are dir="ltr".
"""
import html
import json
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA = os.path.join(ROOT, 'addons', 'plugin.video.nova')
GH = 'bennymat93'
REL = 'https://github.com/%s/novatv/releases/latest/download/' % GH
SITE = 'https://%s.github.io/novatv/' % GH


def facts():
    ver = re.search(r'name="NovaTV" version="([^"]+)"', open(os.path.join(NOVA, 'addon.xml'), encoding='utf-8').read()).group(1)
    iptv = open(os.path.join(NOVA, 'resources', 'lib', 'iptv.py'), encoding='utf-8').read()
    free = re.findall(r"\('(iptv-org [^']+)', 'https://", iptv)
    off = re.search(r'FREE_OFF = \{([^}]*)\}', iptv).group(1)
    libs = re.findall(r"^\s+\('\w+', '(plugin\.video\.[\w.\-]+)'", open(os.path.join(NOVA, 'resources', 'lib', 'providers.py'), encoding='utf-8').read(), re.M)
    sp = os.path.join(NOVA, 'resources', 'providers_status.json')
    if os.path.exists(sp):
        bad = {v['addon'] for v in json.load(open(sp, encoding='utf-8')).values() if not v.get('stable', True)}
        libs = [x for x in libs if x not in bad]
    tests = []
    rp = os.path.join(ROOT, 'work', 'test_report.json')
    if os.path.exists(rp):
        tests = json.load(open(rp, encoding='utf-8'))
    try:
        log = subprocess.check_output(['git', 'log', '--format=%ad\t%s', '--date=short'], cwd=ROOT, encoding='utf-8')
    except Exception:
        log = ''
    changes = []
    for line in log.splitlines():
        d, _, subj = line.partition('\t')
        m = re.match(r'v?(\d+\.\d+\.\d+):\s*(.+)', subj)
        if m:
            changes.append((m.group(1), d, m.group(2)))
    return {'ver': ver, 'free': free, 'free_off': [f for f in free if f in off], 'libs': sorted(set(libs)),
            'tests': tests, 'changes': changes, 'date': time.strftime('%Y-%m-%d')}


def c(s):
    """code / path / URL - always left-to-right, even inside Hebrew text"""
    return '<code dir="ltr">%s</code>' % html.escape(s)


def a(url, text=None):
    return '<a dir="ltr" href="%s">%s</a>' % (url, html.escape(text or url))


# ------------------------------------------------------------------ content (en, he)
def sections(f):
    apk64, apk32, exe = REL + 'BN-Stream-21.3-arm64-v8a.apk', REL + 'BN-Stream-21.3-armeabi-v7a.apk', REL + 'BN-Stream-Setup-%s.exe' % f['ver']
    exe_latest = 'https://github.com/%s/novatv/releases/latest' % GH
    free_en = ', '.join(x.replace('iptv-org ', '') for x in f['free'])
    off_en = ', '.join(x.replace('iptv-org ', '') for x in f['free_off'])
    S = []
    S.append(('install', 'Installation', 'התקנה', '''
<h3>Android TV box / phone / tablet</h3>
<ol>
<li>Download the app: {a64} (most boxes and phones from the last years) or {a32} (older 32-bit boxes).</li>
<li>Open the file and allow installing from this source if Android asks.</li>
<li>Open <b>BN Stream</b>. The first start takes up to a minute while the build is prepared. Everything is ready: skin, languages, menus, channels.</li>
</ol>
<p>BN Stream installs next to a regular Kodi and does not touch it. Installing a newer APK over the old one updates the add-ons and keeps your accounts, history and favourites.</p>
<h3>Windows PC</h3>
<ol>
<li>Download {exe} from {rel}.</li>
<li>Run it. No administrator rights are needed; it installs to {dir}.</li>
<li>Open <b>BN Stream</b> from the desktop or Start menu. It is ready immediately.</li>
</ol>
<p>Running a newer setup over an existing installation keeps your personal data.</p>
<h3>Existing Kodi 21 (any device)</h3>
<ol>
<li>Settings &rarr; System &rarr; Add-ons &rarr; enable <b>Unknown sources</b>.</li>
<li>Settings &rarr; File manager &rarr; Add source &rarr; {site} &rarr; name it {nova}.</li>
<li>Add-ons &rarr; Install from zip file &rarr; {nova} &rarr; {repozip}.</li>
<li>Add-ons &rarr; Install from repository &rarr; NovaTV Repository &rarr; Program add-ons &rarr; <b>NovaTV Wizard</b>.</li>
<li>Open the wizard &rarr; <i>Fresh install</i>. Kodi closes; open it again.</li>
</ol>'''.format(a64=a(apk64, 'BN Stream 64-bit (arm64)'), a32=a(apk32, 'BN Stream 32-bit (armv7)'), exe=c('BN-Stream-Setup-%s.exe' % f['ver']),
                 rel=a(exe_latest, 'GitHub Releases'), dir=c(r'%LOCALAPPDATA%\BN Stream'), site=c(SITE), nova=c('nova'),
                 repozip=c('repository.nova-1.0.0.zip')), '''
<h3>סטרימר אנדרואיד / טלפון / טאבלט</h3>
<ol>
<li>מורידים את האפליקציה: {a64} (רוב הסטרימרים והטלפונים מהשנים האחרונות) או {a32} (סטרימרים ישנים של 32 ביט).</li>
<li>פותחים את הקובץ, ואם אנדרואיד שואל, מאשרים התקנה מהמקור הזה.</li>
<li>פותחים את <b>BN Stream</b>. בפתיחה הראשונה ההכנה לוקחת עד דקה. אחר כך הכול מוכן: עיצוב, שפות, תפריטים וערוצים.</li>
</ol>
<p>BN Stream מותקנת לצד Kodi רגיל ולא משנה אותו. התקנת APK חדש מעל הישן מעדכנת את התוספים ושומרת חשבונות, היסטוריה ומועדפים.</p>
<h3>מחשב Windows</h3>
<ol>
<li>מורידים את {exe} מ-{rel}.</li>
<li>מריצים. לא צריך הרשאות מנהל. ההתקנה נכנסת לתיקייה {dir}.</li>
<li>פותחים את <b>BN Stream</b> מהשולחן או מתפריט התחל. הכול מוכן מיד.</li>
</ol>
<p>התקנה של גרסה חדשה מעל קיימת שומרת את הנתונים האישיים.</p>
<h3>Kodi 21 קיים (בכל מכשיר)</h3>
<ol>
<li>הגדרות &larr; מערכת &larr; תוספים &larr; מפעילים <b>מקורות לא ידועים</b>.</li>
<li>הגדרות &larr; מנהל קבצים &larr; הוספת מקור &larr; {site} &larr; קוראים לו {nova}.</li>
<li>תוספים &larr; התקנה מקובץ zip &larr; {nova} &larr; {repozip}.</li>
<li>תוספים &larr; התקנה ממאגר &larr; NovaTV Repository &larr; תוספי תוכנה &larr; <b>NovaTV Wizard</b>.</li>
<li>פותחים את האשף &larr; <i>התקנה נקייה</i>. Kodi נסגר; פותחים אותו שוב.</li>
</ol>'''.format(a64=a(apk64, 'BN Stream 64-bit (arm64)'), a32=a(apk32, 'BN Stream 32-bit (armv7)'), exe=c('BN-Stream-Setup-%s.exe' % f['ver']),
                 rel=a(exe_latest, 'GitHub Releases'), dir=c(r'%LOCALAPPDATA%\BN Stream'), site=c(SITE), nova=c('nova'),
                 repozip=c('repository.nova-1.0.0.zip'))))
    S.append(('first', 'First steps (5 minutes)', 'צעדים ראשונים (5 דקות)', '''
<ol>
<li>BN menu &rarr; <b>Accounts &amp; Connections</b> &rarr; <b>Real-Debrid</b>: a code appears on screen; enter it at {rd} on your phone. Movies and series play through Real-Debrid.</li>
<li>Optional: <b>Trakt</b> (same code method) to sync what you watched.</li>
<li>Optional: <b>IPTV</b> &rarr; add your own M3U / EPG links. Free channels already work without it.</li>
<li>Optional: <b>AI Subtitle Server</b> &mdash; see the section below.</li>
</ol>
<p>Never type passwords into chats or messages; the boxes use on-screen codes only.</p>'''.format(rd=c('real-debrid.com/device')), '''
<ol>
<li>תפריט BN &larr; <b>חשבונות וחיבורים</b> &larr; <b>Real-Debrid</b>: מופיע קוד על המסך, ומזינים אותו בכתובת {rd} בטלפון. סרטים וסדרות מתנגנים דרך Real-Debrid.</li>
<li>לא חובה: <b>Trakt</b> (באותה שיטת קוד), לסנכרון מה שצפיתם.</li>
<li>לא חובה: <b>IPTV</b> &larr; מוסיפים קישורי M3U / EPG משלכם. הערוצים החינמיים עובדים גם בלי זה.</li>
<li>לא חובה: <b>שרת כתוביות AI</b> &mdash; ראו בהמשך.</li>
</ol>
<p>אף פעם לא מקלידים סיסמאות בצ'אט או בהודעות. במכשירים מתחברים רק עם קוד שמופיע על המסך.</p>'''.format(rd=c('real-debrid.com/device'))))
    S.append(('menu', 'Main menu', 'התפריט הראשי', '''
<table>
<tr><th>Item</th><th>What it does</th></tr>
<tr><td>Search all sources</td><td>One search across every source at once: movies &amp; series, Israeli broadcasters, YouTube, free libraries, live channels and radio.</td></tr>
<tr><td>Movies / Series</td><td>Search, trending, popular, top rated, genres, languages (Hebrew, English, Russian) and years. Long-press an item for favourites or to choose a source.</td></tr>
<tr><td>TV</td><td>One numbered channel list with a TV guide (now / next). Kan 11 is on 11 and Keshet 12 on 12.</td></tr>
<tr><td>Radio</td><td>Israeli, Russian and Hebrew-language stations, plus a world top list.</td></tr>
<tr><td>History</td><td>What you watched, with date and time.</td></tr>
<tr><td>Favourites</td><td>Movies and series you saved.</td></tr>
<tr><td>Central library</td><td>{nlibs} video sources by category (Israel, Russian, movies, documentaries, news, kids, sport...), all opened inside BN.</td></tr>
<tr><td>Accounts &amp; Connections</td><td>Real-Debrid, Trakt, IPTV, AI subtitles, Gemini, TMDb, locked profile.</td></tr>
<tr><td>Backup &amp; Restore</td><td>Save or restore everything personal.</td></tr>
</table>'''.format(nlibs=len(f['libs'])), '''
<table>
<tr><th>פריט</th><th>מה הוא עושה</th></tr>
<tr><td>חיפוש בכל המקורות</td><td>חיפוש אחד בכל המקורות בבת אחת: סרטים וסדרות, השידורים הישראליים, YouTube, הספריות החינמיות, ערוצים חיים ורדיו.</td></tr>
<tr><td>סרטים / סדרות</td><td>חיפוש, טרנדי, פופולרי, מדורג, ז'אנרים, שפות (עברית, אנגלית, רוסית) ושנים. לחיצה ארוכה על פריט: מועדפים או בחירת מקור.</td></tr>
<tr><td>טלוויזיה</td><td>רשימת ערוצים אחת ממוספרת עם לוח שידורים (עכשיו / הבא). כאן 11 בערוץ 11, קשת 12 בערוץ 12.</td></tr>
<tr><td>רדיו</td><td>תחנות מישראל, מרוסיה ובעברית, ורשימת המובילות בעולם.</td></tr>
<tr><td>היסטוריה</td><td>מה צפיתם, עם תאריך ושעה.</td></tr>
<tr><td>מועדפים</td><td>סרטים וסדרות ששמרתם.</td></tr>
<tr><td>הספרייה המרכזית</td><td>{nlibs} מקורות וידאו לפי נושא (ישראל, ברוסית, סרטים, תעודה, חדשות, ילדים, ספורט ועוד), וכולם נפתחים בתוך BN.</td></tr>
<tr><td>חשבונות וחיבורים</td><td>Real-Debrid, Trakt, IPTV, כתוביות AI, Gemini, TMDb ופרופיל נעול.</td></tr>
<tr><td>גיבוי ושחזור</td><td>שמירה ושחזור של כל הנתונים האישיים.</td></tr>
</table>'''.format(nlibs=len(f['libs']))))
    S.append(('hub', 'One place for everything', 'מקום אחד לכל התוכן', '''
<p>BN is the only app you use. Every other video add-on (POV, Idan+, YouTube, Internet Archive, Dailymotion, Vimeo and the free libraries) is managed inside BN and works as one big library.</p>
<ul>
<li><b>Search all sources</b> (first item in the BN menu, and the search button on the home screen): one query runs on every source at the same time, and the results come back in one list, grouped by source.</li>
<li><b>Playing a movie or episode:</b> BN first asks POV (Real-Debrid). If POV finds nothing, BN automatically searches all other sources for the same title and shows what it found.</li>
<li><b>Central library:</b> every source by category. <b>Russian</b> has the official channels of Mosfilm, Soyuzmultfilm, Smeshariki, Belarusfilm and Kinopoisk, plus Soviet films from the Internet Archive.</li>
<li><b>Sources &amp; add-ons</b> (in the central library): switch each source on or off, open its settings, or install all stable sources at once.</li>
</ul>
<p>Only sources that passed the automatic stability check are shown; the check runs again before every version.</p>
<h3>The BN list view</h3>
<p>Every list of movies, series, episodes and videos opens in the BN view: the backdrop of the title you are on fills the screen, the selected row is marked in gold, and on the left you see everything at once: title, year, rating, runtime, age rating, genres, tagline, the full plot, director and cast.</p>
<h3>When BN starts</h3>
<p>Once everything is up, a message says "BN Stream is ready", followed by a status table: every add-on with its version, every service (Real-Debrid, Trakt, IPTV, AI subtitles, Gemini, TMDb) and how much content is available: movies, series, live channels, radio stations, sources. You can open it any time from <b>System status</b> in the BN menu, and turn the start-up table off in the settings.</p>
<h3>Subtitles before you watch</h3>
<p>When a movie or episode starts, BN pauses it and checks for Hebrew subtitles. If there are none, it prepares AI subtitles for the first part and then starts playing (at most 4 minutes; pressing Play continues right away).</p>''', '''
<p>BN היא האפליקציה היחידה שצריך. כל שאר תוספי הווידאו (POV, עידן+, YouTube, ארכיון האינטרנט, Dailymotion, Vimeo והספריות החינמיות) מנוהלים בתוך BN ועובדים כספרייה אחת גדולה.</p>
<ul>
<li><b>חיפוש בכל המקורות</b> (הפריט הראשון בתפריט BN, וגם כפתור החיפוש במסך הבית): חיפוש אחד רץ בכל המקורות בבת אחת, והתוצאות חוזרות ברשימה אחת מחולקת לפי מקור.</li>
<li><b>ניגון סרט או פרק:</b> BN פונה קודם ל-POV (Real-Debrid). אם POV לא מוצא כלום, BN מחפש אוטומטית את אותו שם בכל שאר המקורות ומציג מה שנמצא.</li>
<li><b>הספרייה המרכזית:</b> כל המקורות לפי נושא. ב<b>ברוסית</b> נמצאים הערוצים הרשמיים של מוספילם, סויוזמולטפילם, סמשריקי, בלרוספילם וקינופויסק, וגם סרטים סובייטיים מארכיון האינטרנט.</li>
<li><b>מקורות ותוספים</b> (בתוך הספרייה המרכזית): הפעלה וכיבוי של כל מקור, פתיחת ההגדרות שלו, או התקנה של כל המקורות היציבים בבת אחת.</li>
</ul>
<p>מוצגים רק מקורות שעברו את בדיקת היציבות האוטומטית, והבדיקה רצה שוב לפני כל גרסה.</p>
<h3>תצוגת הרשימות של BN</h3>
<p>כל רשימה של סרטים, סדרות, פרקים וסרטונים נפתחת בתצוגת BN. תמונת הרקע של הכותר שעומדים עליו ממלאת את המסך, השורה הנבחרת מסומנת בזהב, ובצד מופיע הכול בבת אחת: שם, שנה, דירוג, אורך, סיווג גיל, ז'אנרים, שורת תיאור, העלילה המלאה, במאי ושחקנים.</p>
<h3>כש-BN עולה</h3>
<p>כשהכול מוכן מופיעה ההודעה "BN Stream מוכן לשימוש", ואחריה טבלת מצב: כל תוסף והגרסה שלו, כל שירות (Real-Debrid, Trakt, IPTV, כתוביות AI, Gemini, TMDb), וכמה תוכן זמין: סרטים, סדרות, ערוצים חיים, תחנות רדיו ומקורות. אפשר לפתוח אותה בכל רגע מ<b>מצב המערכת</b> בתפריט BN, ולכבות את הטבלה בעלייה דרך ההגדרות.</p>
<h3>כתוביות לפני הצפייה</h3>
<p>כשסרט או פרק מתחיל, BN עוצר אותו לרגע ובודק אם יש כתוביות בעברית. אם אין, הוא מכין כתוביות AI לחלק הראשון ורק אז מתחיל לנגן (עד 4 דקות לכל היותר; לחיצה על Play ממשיכה מיד).</p>'''))
    S.append(('tv', 'TV channels', 'ערוצי טלוויזיה', '''
<p>Free lists from the iptv-org community index: {free}. Switched off by default (large): {off}. Turn lists on or off under Accounts &rarr; IPTV.</p>
<p>Channels that are confirmed dead (HTTP 404) are filtered out automatically. Channels are grouped (Israel, News, Movies, Kids, Sport, Documentary, Music, Russian, Other). Some free channels are geo-blocked or change often; if one does not play, try another.</p>'''.format(free=html.escape(free_en), off=html.escape(off_en)), '''
<p>רשימות חינמיות מהמאגר הקהילתי iptv-org: <span dir="ltr">{free}</span>. כבויות כברירת מחדל (גדולות): <span dir="ltr">{off}</span>. מדליקים ומכבים רשימות בחשבונות &larr; IPTV.</p>
<p>ערוצים שמתים בוודאות (HTTP 404) מסוננים אוטומטית. הערוצים מקובצים (ישראל, חדשות, סרטים, ילדים, ספורט, תעודה, מוזיקה, רוסית, אחר). חלק מהערוצים החינמיים חסומים גאוגרפית או משתנים; אם ערוץ לא מתנגן, נסו אחר.</p>'''.format(free=html.escape(free_en), off=html.escape(off_en))))
    S.append(('subs', 'AI Hebrew subtitles (PC server)', 'כתוביות AI בעברית (שרת במחשב)', '''
<ol>
<li>On the PC run {auto} once. The server starts now and at every Windows sign-in, runs hidden, and restarts itself if it ever stops. Check it with {status}; its log is {log}.</li>
<li>TV boxes on the same home network find the server automatically. To set it manually: Accounts &rarr; AI Subtitle Server &rarr; {url}.</li>
<li>Optional: a Gemini key (Accounts &rarr; Gemini) gives better translation; without it a local translator is used.</li>
</ol>
<p>Translate a whole series overnight:</p>
<pre dir="ltr">{batch}</pre>'''.format(bat=c(r'server\start_server.bat'), auto=c(r'server\install_autostart.bat'), url=c('http://<PC-IP>:8765'),
                       status=c(r'.venv11\Scripts\python server\supervisor.py status'), log=c(r'server\logs\server.log'),
                       batch=html.escape(r'.venv11\Scripts\python server\nova_subs.py batch "D:\Kukhnya\*.mkv" --title "Кухня"')), '''
<ol>
<li>במחשב מריצים פעם אחת את {auto}. השרת עולה מיד ובכל כניסה ל-Windows, רץ ברקע, ומפעיל את עצמו מחדש אם נעצר. בודקים שהוא פועל עם {status}, והיומן שלו נמצא ב-{log}.</li>
<li>סטרימרים באותה רשת ביתית מוצאים את השרת לבד. הגדרה ידנית: חשבונות &larr; שרת כתוביות AI &larr; {url}.</li>
<li>לא חובה: מפתח Gemini (חשבונות &larr; Gemini) נותן תרגום טוב יותר. בלעדיו משתמשים במתרגם מקומי.</li>
</ol>
<p>תרגום של סדרה שלמה בלילה:</p>
<pre dir="ltr">{batch}</pre>'''.format(bat=c(r'server\start_server.bat'), auto=c(r'server\install_autostart.bat'), url=c('http://<PC-IP>:8765'),
                       status=c(r'.venv11\Scripts\python server\supervisor.py status'), log=c(r'server\logs\server.log'),
                       batch=html.escape(r'.venv11\Scripts\python server\nova_subs.py batch "D:\Kukhnya\*.mkv" --title "Кухня"'))))
    S.append(('profile', 'Locked pre-configured profile', 'פרופיל מוגדר מראש נעול', '''
<p>Set up all accounts on one device, then Accounts &rarr; <b>Create locked pre-configured profile</b> and choose a password (8+ characters). The file is encrypted and can be exported to USB or a network folder.</p>
<p>On another device: Accounts &rarr; <b>Unlock pre-configured profile</b> &rarr; password. Everything is connected and Kodi restarts. After 5 wrong passwords it locks for 10 minutes. A shared file is only as safe as its password.</p>''', '''
<p>מגדירים את כל החשבונות במכשיר אחד, ואז חשבונות &larr; <b>צור פרופיל מוגדר מראש (נעול בסיסמה)</b> ובוחרים סיסמה (8 תווים לפחות). הקובץ מוצפן, ואפשר לייצא אותו ל-USB או לתיקיית רשת.</p>
<p>במכשיר אחר: חשבונות &larr; <b>פתח פרופיל מוגדר מראש</b> &larr; סיסמה. הכול מתחבר ו-Kodi נפתח מחדש. אחרי 5 סיסמאות שגויות הוא ננעל ל-10 דקות. קובץ ששותף מוגן רק כמו הסיסמה שלו.</p>'''))
    S.append(('backup', 'Backup & restore', 'גיבוי ושחזור', '''
<p>BN menu &rarr; Backup &amp; Restore &rarr; <b>Back up now</b> &rarr; pick a folder (USB, local or network). The file {f} contains accounts, history, favourites, IPTV sources and settings. An automatic copy is also kept on the device every week (last 3).</p>
<p><b>Restore</b>: choose a backup, confirm, Kodi closes; open it again.</p>'''.format(f=c('BN-backup-YYYYMMDD-HHMM.zip')), '''
<p>תפריט BN &larr; גיבוי ושחזור &larr; <b>גבה עכשיו</b> &larr; בוחרים תיקייה (USB, מקומית או ברשת). הקובץ {f} כולל חשבונות, היסטוריה, מועדפים, מקורות IPTV והגדרות. בנוסף נשמר במכשיר עותק אוטומטי כל שבוע (שלושת האחרונים).</p>
<p><b>שחזור</b>: בוחרים גיבוי, מאשרים, Kodi נסגר; פותחים אותו שוב.</p>'''.format(f=c('BN-backup-YYYYMMDD-HHMM.zip'))))
    S.append(('update', 'Updates', 'עדכונים', '''
<ul>
<li><b>Android</b>: install the newest APK over the old one.</li>
<li><b>Windows</b>: run the newest setup.</li>
<li><b>Any Kodi</b>: BN menu &rarr; NovaTV Wizard &rarr; <i>Update</i> (keeps accounts, history and favourites).</li>
</ul>''', '''
<ul>
<li><b>אנדרואיד</b>: מתקינים את ה-APK החדש מעל הישן.</li>
<li><b>Windows</b>: מריצים את קובץ ההתקנה החדש.</li>
<li><b>כל Kodi</b>: תפריט BN &larr; NovaTV Wizard &larr; <i>עדכון</i> (שומר חשבונות, היסטוריה ומועדפים).</li>
</ul>'''))
    S.append(('help', 'Troubleshooting', 'פתרון בעיות', '''
<table>
<tr><th>Problem</th><th>Fix</th></tr>
<tr><td>A movie has no sources</td><td>Check Real-Debrid is connected (Accounts). Long-press &rarr; choose source.</td></tr>
<tr><td>A TV channel does not play</td><td>Free channels can be offline or geo-blocked; try another one. Accounts &rarr; IPTV &rarr; refresh.</td></tr>
<tr><td>No TV channels at all</td><td>Accounts &rarr; IPTV &rarr; refresh and wait a minute; large lists take time.</td></tr>
<tr><td>AI subtitles unavailable</td><td>Make sure the PC server is running and on the same network.</td></tr>
<tr><td>Everything is broken</td><td>Restore a backup, or NovaTV Wizard &rarr; Fresh install.</td></tr>
</table>''', '''
<table>
<tr><th>בעיה</th><th>פתרון</th></tr>
<tr><td>לסרט אין מקורות</td><td>בודקים ש-Real-Debrid מחובר (חשבונות). לחיצה ארוכה &larr; בחירת מקור.</td></tr>
<tr><td>ערוץ לא מתנגן</td><td>ערוצים חינמיים יכולים להיות מושבתים או חסומים גאוגרפית; נסו ערוץ אחר. חשבונות &larr; IPTV &larr; רענון.</td></tr>
<tr><td>אין ערוצים בכלל</td><td>חשבונות &larr; IPTV &larr; רענון, ומחכים דקה. רשימות גדולות לוקחות זמן.</td></tr>
<tr><td>כתוביות AI לא זמינות</td><td>בודקים שהשרת במחשב פועל ונמצא באותה רשת.</td></tr>
<tr><td>הכול לא עובד</td><td>משחזרים גיבוי, או NovaTV Wizard &larr; התקנה נקייה.</td></tr>
</table>'''))
    if f['tests']:
        ok = sum(1 for t in f['tests'] if t['ok'])
        rows = ''.join('<tr><td>%s</td><td>%s</td></tr>' % (html.escape(t['test']), '&#10003;' if t['ok'] else '&#10007;') for t in f['tests'])
        S.append(('quality', 'Quality check of this version', 'בדיקת האיכות של הגרסה', '<p>Automated checks: %d/%d passed.</p><table dir="ltr">%s</table>' % (ok, len(f['tests']), rows),
                  '<p>בדיקות אוטומטיות: <span dir="ltr">%d/%d</span> עברו.</p><table dir="ltr">%s</table>' % (ok, len(f['tests']), rows)))
    ch = ''.join('<li><b dir="ltr">%s</b> <span dir="ltr">(%s)</span>: <span dir="ltr">%s</span></li>' % (v, d, html.escape(t)) for v, d, t in f['changes'])
    S.append(('changes', 'Version history', 'היסטוריית גרסאות', '<ul>%s</ul>' % ch, '<ul>%s</ul>' % ch))
    return S


CSS = '''
:root{--bg:#0d0f14;--card:#161a22;--fg:#e9e6df;--mut:#a6a196;--gold:#e8be5a;--line:#2a2f3a;--code:#1f2430}
@media (prefers-color-scheme: light){:root{--bg:#faf8f3;--card:#fff;--fg:#1d1b17;--mut:#6b665c;--gold:#9a7418;--line:#e4dfd3;--code:#f1ede4}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,"Segoe UI",Arial,sans-serif}
header{padding:28px 16px 12px;max-width:960px;margin:auto}h1{margin:0;color:var(--gold);font-size:28px}.sub{color:var(--mut)}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:2}
nav div{max-width:960px;margin:auto;padding:8px 16px;display:flex;gap:8px;flex-wrap:wrap}
nav button{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 14px;cursor:pointer;font:inherit}
nav button[aria-pressed=true]{border-color:var(--gold);color:var(--gold)}
main{max-width:960px;margin:auto;padding:8px 16px 48px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 20px 14px;margin:14px 0}
h2{color:var(--gold);font-size:20px}h3{font-size:17px;margin-bottom:4px}a{color:var(--gold)}
code{background:var(--code);padding:1px 6px;border-radius:5px;font-family:Consolas,monospace;font-size:.92em;unicode-bidi:isolate;direction:ltr}
pre{background:var(--code);padding:12px;border-radius:8px;overflow-x:auto;direction:ltr;text-align:left}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:start;vertical-align:top}
[dir=rtl] td,[dir=rtl] th{text-align:right}[dir=ltr] td,[dir=ltr] th{text-align:left}
.toc a{margin-inline-end:14px;white-space:nowrap}[hidden]{display:none}
'''


def page(f):
    S = sections(f)
    out = []
    for lang, dirn, title, sub in (('en', 'ltr', 'BN Stream &mdash; User Guide', 'Version %s &middot; updated %s'),
                                   ('he', 'rtl', 'BN Stream &mdash; מדריך למשתמש', 'גרסה %s &middot; עודכן %s')):
        idx = 1 if lang == 'en' else 2
        body = ''.join('<section id="%s-%s"><h2>%s</h2>%s</section>' % (lang, s[0], s[idx], s[idx + 2]) for s in S)
        toc = ''.join('<a href="#%s-%s">%s</a>' % (lang, s[0], s[idx]) for s in S)
        out.append('<div lang="%s" dir="%s" id="lang-%s"><header><h1>%s</h1><div class="sub">%s</div><p class="toc">%s</p></header><main>%s</main></div>'
                   % (lang, dirn, lang, title, sub % ('<span dir="ltr">%s</span>' % f['ver'], '<span dir="ltr">%s</span>' % f['date']), toc, body))
    return '''<!DOCTYPE html><html lang="he"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BN Stream Guide</title><style>%s</style></head><body>
<nav><div><button data-l="he" aria-pressed="true">עברית</button><button data-l="en" aria-pressed="false">English</button></div></nav>
%s
<script>
function show(l){document.querySelectorAll('[id^=lang-]').forEach(function(d){d.hidden=d.id!=='lang-'+l});
document.querySelectorAll('nav button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.l===l)});
document.documentElement.lang=l;try{localStorage.setItem('bnlang',l)}catch(e){}}
document.querySelectorAll('nav button').forEach(function(b){b.onclick=function(){show(b.dataset.l)}});
var l='he';try{l=localStorage.getItem('bnlang')||(location.hash.indexOf('#en')===0?'en':'he')}catch(e){}show(l);
</script></body></html>
''' % (CSS, '\n'.join(out))


def markdown(f):
    """GitHub view: HTML blocks with dir= so Hebrew renders RTL and code LTR."""
    S = sections(f)
    parts = ['# BN Stream &mdash; User Guide / מדריך למשתמש', '',
             '<p dir="ltr">Version %s &middot; updated %s &middot; <a href="%sguide.html">open the web version</a></p>' % (f['ver'], f['date'], SITE), '',
             '<p dir="ltr"><a href="#english">English</a> &middot; <a href="#hebrew">עברית</a></p>', '',
             '<a id="english"></a>', '', '<div dir="ltr" lang="en">', '']
    for s in S:
        parts += ['<h2>%s</h2>' % s[1], s[3], '']
    parts += ['</div>', '', '<a id="hebrew"></a>', '', '<div dir="rtl" lang="he">', '']
    for s in S:
        parts += ['<h2>%s</h2>' % s[2], s[4], '']
    parts += ['</div>', '']
    return '\n'.join(parts)


def main():
    f = facts()
    docs = os.path.join(ROOT, 'docs')
    os.makedirs(docs, exist_ok=True)
    p = page(f)
    open(os.path.join(docs, 'guide.html'), 'w', encoding='utf-8').write(p)
    open(os.path.join(docs, 'GUIDE.md'), 'w', encoding='utf-8').write(markdown(f))
    if os.path.isdir(os.path.join(ROOT, 'site')):
        open(os.path.join(ROOT, 'site', 'guide.html'), 'w', encoding='utf-8').write(p)
    print('guide %s: docs/guide.html, docs/GUIDE.md (%d versions in history)' % (f['ver'], len(f['changes'])))


if __name__ == '__main__':
    main()
