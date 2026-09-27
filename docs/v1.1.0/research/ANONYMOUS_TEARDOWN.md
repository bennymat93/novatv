# Anonymous TV build – teardown (behaviour analysis only, no code reused)

Sources examined (read-only, `work/anon/`, never installed): repository `vip200/repowizard` (the owner's
`repository.wizard.zip`), wizard `plugin.program.Anonymous` 8.1.7, its bundled skin `skin/packages1.zip`
(a modified **skin.estuary 9.9.9**), plus 7 photos of the owner's TV running the full build (skin `skin.anonymoustv`,
downloaded by the wizard from kodivip.com – not fetched; the photos are the visual spec).

## Runtime components
| Component | What it does | Notes |
|---|---|---|
| `plugin.program.Anonymous` (wizard) | installs/updates the build (zip from kodivip.com), APK/EXE links, RD details, log sender | `startup.py` = `xbmc.service`: hourly `update_tele` via `threading.Thread(every(3600))` with **`time.sleep`, no abort check** (keeps Kodi from quitting); deletes thumbnails; backs up settings |
| Skin (Estuary mod / skin.anonymoustv) | the whole player UX | all player features are **skin XML + Kodi builtins**, no Python player hooks |
| Subtitle service | Kodi `subtitlesearch` window (DarkSubs/All_Subs-type service) | the OSD "כתוביות" button = `ActivateWindow(SubtitleSearch)` |
| Timers.xml | OSD auto-close timer that pauses while a settings dialog is open | nice touch |

No `xbmc.Player`/`xbmc.Monitor` subclasses in the wizard: nothing resets state between videos (so no zero-state).

## Player OSD (from the photos + skin XML)
- **Top-left**: show clearlogo ("ריצ'ר"); next to it `פרק: S4E1 - <title>` and `קטע: Scene 02 - 02/04` (chapter).
- **Top-right**: big clock, `שעת סיום: 19:38`.
- **Bottom bar**, single row, left→right: `31:46 / 46:21` | text buttons `סנכרון`, `כתוביות` | transport icons
  prev, rewind, **play/pause in a pink circle**, stop, forward, next | text buttons `הפרק הבא`, `שמע`, `מידע` | gear icon.
- Thin progress bar above the row (pink), buffer marker `<>`, badges `1080P`, `DOLBY DIGITAL PLUS`, `5.1`.
- **Info** (`מידע`): poster at the left, title + plot text box over the video.
- **Sync** (`סנכרון`): Kodi's native subtitle-delay slider ("היסט כתוביות 0.000s") at the top.
- **Settings** (gear): list dialog "הגדרות": הגדרות הפרק הבא, הגדרות אודיו, הגדרות כתוביות, הגדרת כתוביות – מתקדם,
  הגדרות וידאו, החלף זרם שמע (`eng`), Toggle subtitle (`heb`), מהירות ניגון (custom tempo window 1110).
  In the skin XML this is `Custom_1101_SettingsList` → osdaudiosettings / osdsubtitlesettings / osdvideosettings,
  `AudioNextLanguage`, `NextSubtitle`, `PlayerProgramSelect`, `PlayerResolutionSelect`, tempo window.
- **Subtitles menu**: הורד כתובית, שפת כתובית, רקע לכתובית, גודל כתובית, אטימות כתובית, כבה כתוביות (toggle).

## Ideas worth adopting (impact / effort)
| # | Idea | Impact | Effort | Adopt |
|---|---|---|---|---|
| 1 | One-row OSD: time left, subtitle/sync text buttons, centred transport, info/audio/next right, gear | high | M | yes – BN player v2 |
| 2 | Clearlogo + episode/chapter line + clock + end time on top | high | S | yes |
| 3 | Codec badges (resolution, audio codec, channels) over the progress bar | med | S | yes |
| 4 | Gear → one settings list (audio, subtitles, video, audio stream, subtitle toggle, speed) | high | S | yes (Python list, remote-first) |
| 5 | Subtitles menu with appearance items (language, background, size, opacity, off) | high | S | yes + our generation actions |
| 6 | Tempo control window | med | S | yes (speed item) |
| 7 | OSD auto-close paused while dialogs are open | low | S | later |
| 8 | Hourly background updater with `time.sleep` | – | – | **no** (blocks exit; we use waitForAbort) |
