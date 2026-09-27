# BN Stream (NovaTV) – HANDOFF

Last update: 2026-09-27 – MISSION v1.1.0 started on branch release/v1.1.0 (0.2.6 never published; live = 0.2.5)
Repo: https://github.com/bennymat93/novatv (main + gh-pages + releases). Local: `C:\Users\benny\kodi-build`.
Read `CLAUDE.md` first (layout, rules, history). This file = current state + open work + exact next steps.

## Owner rules (must follow)
- Every significant change: bump version, rebuild zip + both APKs + Windows installer, EN+HE guide, push main + gh-pages + GitHub release
  (`python tools/release.py --version X --notes "..."`). Everything local must be in the repo, never secrets/keys.
- Verify end-to-end before publishing (release.py does it: full suite on testkodi, Android emulator test, installed Windows copy).
- Stop on the first failing check, fix the ROOT cause, then resume from that check (not from the start):
  a rerun of release.py with the same version continues (work/release_state.json + test_suite --stop-on-fail --resume).
- Answer the owner in Hebrew, short. Don't add Anonymous-TV/Telemedia/unlicensed sources.
- Do NOT touch the owner's Raspberry Pi (he cancelled that; he once typed a password in chat – never use it).
- The owner's own Kodi: `C:\Users\benny\AppData\Local\BN Stream\` (kodi.exe -p, portable_data). Tests must never close it
  (test_suite.kill_kodi only kills testkodi/work/wintest copies; tests wait while his Kodi is open).

## Published
| Version | What |
|---|---|
| 0.2.1 | AI subtitle button, every video starts clean, System Update + Auto-Fix |
| 0.2.3 | stability (Monitor/Player crashes, PVR restart crash, freezes), All_Subs guards v4, bundled TV add-on, up-to-date official add-ons |
| 0.2.4 | YouTube `WinError 10013`: port 50152 is in Windows' reserved ranges -> 51152 (build preset + ytport.py at start + System Update row) |
| 0.2.5 | subtitles fixed + BN subtitle window + no-AI fallback (see below) |
Live repo serves **0.2.5**. 0.2.2 was never published.

## v0.2.5 – PUBLISHED 2026-09-27 (all checks passed: 45 testkodi, Android 9/9, installed Windows 11/11)
Owner's reports: "AI subtitles loaded" but nothing on screen; wants better subtitle control (AI in the list, turn on by hand);
wants a non-AI machine-translation fallback so there are ALWAYS subtitles; wants a better player (like the "Anonymous" wizard's).

### Root causes found
1. YouTube plays via the YouTube add-on's local proxy (`http://127.0.0.1:51152/youtube/manifest/dash?file=<id>.mpd`):
   the PC server could not read audio from it -> every chunk empty -> server said "done" with 0 cues and CACHED it.
2. Server `job_key` stripped the URL query -> ALL YouTube videos shared one job id / cache.
3. Kodi flow loaded the empty SRT anyway, said "loaded"; Kodi log: `CVideoPlayerSubtitle::OpenStream - Unable to create subtitle parser`.
4. Reloading the same SRT path: Kodi does not re-add a path it already has -> later chunks never showed.
5. Two copies of the subtitle server were running (start_server.bat + supervisor). Killed both; supervisor now runs one.

### Done (code in working tree, compiled, lint clean)
- `server/nova_subs.py`:
  - `youtube_id()`, job_key `yt_<id>`; `resolve_source()` -> yt-dlp bestaudio URL (yt-dlp installed in `.venv11`).
  - `youtube_captions()`: YouTube's Hebrew (human or YouTube auto-translate) first, else original captions + mtrans; whole video in ~5 s.
    `mtrans.unroll()` removes YouTube's rolling auto-caption duplicates.
  - never "done" with 0 cues (error "no audio could be read" / "no speech found"); empty caches ignored+deleted.
  - translate(): Gemini -> mtrans (Google endpoints -> MyMemory) -> local NLLB (last). mtrans imported from the add-on lib (sys.path).
- `addons/plugin.video.nova/resources/lib/mtrans.py` (NEW, shared box+server): Google dict-chrome-ex (batch POST) -> Google gtx
  -> MyMemory; each batch validated (line count, Hebrew present), failing batches go to the next engine; last resort keeps source.
  Note: Google gtx answers "Sorry" (throttled) from this PC; dict-chrome-ex works.
- `service.py` Flow: sends `youtube_id`; never loads an SRT without `-->`; per-version file names in `profile/ai/<job>/`
  (`BN AI.he.srt` complete, `BN AI 12m.he.srt` partial) = readable track names; confirms the track appeared;
  `ai_empty` message instead of "loaded"; Window props `NovaTV.AISrt` (last AI file for this video) and `NovaTV.SubsChosen`
  (viewer picked by hand -> never overridden/switched off); "fastest source wins": if Hebrew from All_Subs/YouTube appears before
  the AI's first part, it stays on screen and the AI result only goes to the BN subtitle window.
- `resources/lib/subsmenu.py` (NEW) + router `?a=subs_menu` + skinpatch `_menu_button()` ("כתוביות BN" in all 4 OSD styles):
  every track (AI marked, current highlighted), turn AI on by hand (also a saved AI file), AI progress, generate AI, off/on,
  search (subtitlesearch), sync (Action(SubtitleDelay)). Reopens after a pick.
- YouTube add-on: `kodion.subtitle.languages.num=2` (Kodi language + YouTube auto-translation) – build preset + `ytport.ensure_subtitles()`
  at service start (only if still 0). With the owner's Premium login YouTube gives Hebrew captions on the box without the PC.
- Tests added: t_ai_no_audio (test/silent.mp4, new file), t_subs_menu, t_machine_translation, t_server_youtube_captions;
  t_ai_subs_end_to_end / t_ai_button updated to the new file layout (`profile/ai/*/*.he.srt`, track names "BN AI").
  Already passed standalone: ai_no_audio, subs_menu, reset between videos / next episode, skin windows, machine translation
  (90 lines in 0.5 s), server YouTube captions (208 cues in 4 s).
- addon.xml version already set to 0.2.5; `dist/NovaTV-0.2.5.zip` built earlier (before the fallback work) – rebuild.

### Next steps (exact)
1. Player UI ("Anonymous wizard" player): NOT started. Could not find that wizard online or on disk. Ask the owner for its repo URL /
   zip / screenshots; then analyse its OSD (layout, buttons, remote navigation) and build a similar OSD in the BN skin
   (skin.fentastic, via a skinpatch-like build step). Never import its content sources.

### Known limits (tell the owner honestly)
- Non-YouTube video + PC server off: subtitles come only from All_Subs (human Hebrew, or its own machine translation of foreign subs,
  setting auto_translate=true). A video with no subtitles anywhere and no server cannot get subtitles (no text to translate).
- Embedded text subtitle tracks in MKV are not yet used as a translation source (server would need to read the whole file).

## MISSION v1.1.0 (owner prompt, 2026-09-27) – ACTIVE
Owner pasted a full spec ("Kodi build v1.1.0 – VLC-grade player, next-gen subtitle system, zero-state playback") + 7 TV photos
of the Anonymous player (OSD bar, Sync slider, Subtitles menu, Settings menu, Info panel) as the visual spec.
Docs live in docs/v1.1.0/ (ARCHITECTURE, PLAN, DECISIONS, KEYMAP, TEST_REPORT, research/*). Work on branch release/v1.1.0,
release as v1.1.0 only after the full suite is green twice. Progress log: see "v1.1.0 progress" below (append every step).

### v1.1.0 progress
- [start] branch release/v1.1.0 created; 0.2.6 work (BN player + icons) is included.
- [phase 0+1 done] docs/v1.1.0: ARCHITECTURE, PLAN, DECISIONS (D1-D11), research/VLC_MATRIX, SRT_HANDLING, OTHER_PLAYERS (agents, from memory: verify Kodi facts), ANONYMOUS_TEARDOWN, POVIL_AI_SUBS_TEARDOWN.
- [phase 4 core done] resources/lib/subfix.py (encodings, tolerant SRT/VTT, repair, Hebrew RLM fixes, atomic BOM write, fuzzy match), substore.py (<base>.<lang>.<src>[.vN].srt, versions, entries+preview, cleanup, rename), syncmath.py (bookmark sync, steps, dual merge {n8}, AI chunking). tests/ (pytest + Kodi stubs): 57 passed. Run: .venv11/Scripts/python -m pytest tests -q
- [phase 3/4/5 code, untested in Kodi] playerctl.py (delays/speed/view/state, verified labels+actions on Kodi 21; SetViewMode takes only viewmode; tempo disabled for test file),
  player_menus.py (sync / settings / audio / appearance / subtitles / picker / online (Wizdom verified) / auto_subtitles / next_episode),
  router actions sync_menu settings_menu audio_menu subs_pick next_episode (subs_menu -> player_menus.subtitles),
  service: zero_state() at start (delays 0, speed 1, view normal, resume_same policy, 'session start' log), SESSION_PROPS cleared,
  ab_loop thread, AI flow mode ai/mt (NovaTV.AIMode) + store to substore + PrimaryFile, Kodi subtitle folder (storagemode=1, custompath),
  cleanup policy at start, keymap install (resources/keymaps/bn_player.xml, docs KEYMAP.md). Server: mode 'mt' skips Gemini, key suffix _mt.
  New settings: subs_folder, subs_cleanup, subs_keep_last, subs_pref_source, opensubs_key, resume_same, sync_step.
- [next] OSD v2 per photos (Includes_VideoOsdBN.xml: top logo/episode/chapter/clock/end time; bottom time | סנכרון כתוביות | transport | הפרק הבא שמע מידע | gear; badges; info overlay), then build + live tests.

## v0.2.6 – superseded by v1.1.0 (never published): BN player (not released)
- "Anonymous" wizard found: `C:\Users\benny\Downloads\Compressed\repository.wizard.zip` -> GitHub `vip200/repowizard` ->
  `plugin.program.Anonymous` 8.1.7 (downloaded for READING ONLY to `work/anon/`, never installed/imported).
  Its skin (`skin/packages1.zip`) = customised Estuary: VideoOSD = one row of big icon buttons (prev, rew, play/pause, stop,
  fwd, next | next episode, change source, channels, guide, episode list, info, bookmarks, settings, sync, subtitles),
  Hebrew labels, progress bar with times, title on top.
- Our own on that pattern (nothing copied): `addons/plugin.video.nova/resources/skin/Includes_VideoOsdBN.xml`
  (include `videosd_bn`, button include `BNOsdButton`, row id 201 = VideoOSD default control, play/pause togglebutton 603):
  prev, rewind, play/pause, stop, forward, next | BN subtitles (subs_menu), AI subtitles, subtitle sync, audio
  (osdaudiosettings), picture (osdvideosettings), bookmarks, info, episode list (only when playlist > 1).
  Focused button's name shown big under the row (System.CurrentControl; button labels are transparent text).
- `skinpatch.bn_player(xml)`: copies the file, registers it in Includes.xml, adds
  `<include condition="String.IsEqual(Skin.String(__chooseplayer),__bnplayer)">videosd_bn</include>` to VideoOSD.xml.
  Runs in make_build (via skinpatch.apply) AND at service start (existing installs).
- Default: make_build `bn_player_default()` (skin settings.xml __chooseplayer=__bnplayer); service sets it ONCE on existing
  installs (hidden setting `bn_player_set`); a later choice of the owner is kept.
- Tested live in testkodi: t_bn_player PASS (row focused, Hebrew names, subs button opens the BN window); screenshot
  work/bn_player.png sent to the owner. Lesson: an <image> separator inside the grouplist stopped Right navigation - removed.
- Owner said the first design was wrong -> redesigned: own icon set `tools/make_osd_icons.py` (PIL, uniform style) ->
  `resources/skin/icons/<name>_nf.png` (normal) + `<name>_fo.png` (gold circle + dark icon, pre-drawn: a plain button has one
  texture per state; radiobutton showed "( )" in System.CurrentControl). skinpatch copies icons to skin `media/bn/`
  (textures are resolved inside the skin; special:// paths via $VAR did not load). Times on separate labels, Hebrew-first
  ("מסתיים ב־..."), dark panels top/bottom. Screenshot sent (work/bn_player.png). t_bn_player PASS.
- Next: `python tools/release.py --version 0.2.6 --notes "..."` (running), then update this file.

## Useful facts
- Subtitle server: `server/nova_subs.py serve --port 8765`, supervisor `server/supervisor.py` (pythonw, Startup shortcut),
  log `server/logs/server.log`, cache `server/cache/<job>.json`. Restart = kill `nova_subs.py serve` processes; supervisor restarts.
- Testkodi: `testkodi/` (portable). Installed-copy test: `work/wintest`. Android: `work/android` (AVD "bn"),
  `tools/android_test.py` (grants MANAGE_EXTERNAL_STORAGE via appops; deletes leftover app data first; ignores emulator's own crashes).
- Helper scripts I used live in the session scratchpad (not needed): edits are all in the repo.
