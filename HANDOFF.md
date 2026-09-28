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
- [OSD v2 written] Includes_VideoOsdBN.xml rewritten per photos (top logo/פרק/קטע/clock/שעת סיום; bottom time | סנכרון כתוביות | transport (201 play) | הפרק הבא שמע מידע | gear 706; badges; info panel via Home prop BN.OSDInfo, cleared per session). plugin addon.xml -> 1.1.0. Built dist/NovaTV-1.1.0.zip. Full suite run 1 started -> work/suite_110_run1.log (t_bn_player walks 11 buttons now).
  [next] read suite log, fix failures, screenshot work/bn_player.png, add integration tests (zero-state soak x50, panels, picker), TEST_REPORT.md, CHANGELOG, release.py --version 1.1.0.
- [run1] crash found in "AI Hebrew subtitles end-to-end": flow touched the player (getAvailableSubtitleStreams/getVideoInfoTag) while the video was closing -> guarded (same_video + isPlayingVideo) and substore now uses job title/season/episode. VideoPlayer.SubtitlesName is not a Kodi 21 label -> removed from dump + info panel. New tests t_player_panels + t_zero_state_soak (BN_SOAK env, default 50) added to test_suite. CHANGELOG.md created. Next: rebuild, run suite twice green, TEST_REPORT.md, release.
- [run1 done] 45/47 (fails: the crash, now fixed; t_subs_menu retargeted to ?a=subs_pick). The OSD screenshot showed reversed Hebrew on text buttons (Kodi button labels are not bidi-shaped) -> text drawn by label controls over transparent-label buttons (BNText/BNLabel). Run 2 (with the new panels + soak x50 tests) started -> work/suite_110_run2.log.
- [run2] 46/48: crash fix OK, new tests (panels, soak x50, picker, BN player) all PASS. The 2 fails were test allowlists (new actions called via GetDirectory; YouTube add-on 429 on timedtext = third party) -> fixed in test_suite. Run 3 started -> work/suite_110_run3.log. Need runs 3+4 green, then TEST_REPORT.md + release.
- [run3] 45/48: soak flaky at start 46 (single read at 1.5 s; now polls up to 6 s and names the field), panels test's Back hit a notification so a settings select stayed open -> plugin killed + 121 s quit (test now waits for select/slider only and closes until gone). Runs 4+5 started back-to-back (work/suite_110_run4.log, run5.log).
- [runs 4+5] 46/49 and 42/48. Kodi crash again at CloseFile (AI silent video test) - both 1.1.0 crashes happen when a video closes while All_Subs (DarkSubs) runs ~10 search threads; dumps were lost (testkodi reinstalled) -> suite now copies the .dmp next to work/crash-*.log. Run 5 extra fails look like network (radio IL 0, lib install, Mosfilm, System Update 600 s) - recheck. Slow quit 104-121 s persists (investigate: who blocks exit). test_suite got --only "a,b" --repeat N. Crash hunt running: --only "silent video,end-to-end" --repeat 10 -> work/crashhunt.log.
- [crash hunt] --repeat fixed (skip-passed only when repeat==1). 30/30 AI/silent/before-play runs, no crash -> rare, not reproducible alone; dumps now kept for next time.
- [slow quit root cause] after the 50-start soak, All_Subs ran queued automatic searches with nothing playing and after Application.Quit (Subscene 403 retry loop) -> Kodi killed it after ~2 min. subspatch: guard v5 (MARK5) at temporary_pop_and_get_subtitles: no search when Kodi quits or no video plays; applied on top of v4, idempotent (verified on a copy). t_all_subs_guard checks v4+v5. Verifying: --only "Zero-state,All_Subs guards,Clean shutdown" -> work/quithunt2.log.
- [real crash cause, likely] All_Subs engine.py created xbmc.Player() every 10 ms in its search wait loop (and general.py's overlay every 100 ms + a Monitor) in worker threads = the 0.2.2 crash pattern; v4 only fixed autosub.py. Also the engine loop ignored quit (the 2-min exit). subspatch v5 now patches general.py (_BN_MON module Monitor, overlay loop), engine.py (Player.HasMedia InfoLabel instead of Player objects, _bn_quit() stops source threads like the time-out) - verified idempotent on a copy. Next: rebuild, full suite x2 (work/suite_110_run6/7.log).
- [runs 6+7] 47/48, 46/49. Quit 120 s -> 32 s (v5 works; still >30). Crash again (BN subtitle window) - dump kept: python3.8.dll+0xdfec1 = the 0.2.2 pattern. Cause in OUR new code: player_menus created/freed xbmc.Player() on every menu pass (7 places) -> one shared Player _pl(). Verifying: --only "BN subtitle window,Player panels,AI Subtitle Generation button" --repeat 8 -> work/crashhunt2.log. Open: run6 "AI button: human subtitle not active first" (flaky?), run7 tracebacks x3, quit 32 s.
- [runs 8+9] 46/49, 46/48. Crash again (silent video) - dump: again python3.8.dll+0xdfec1 in a Python thread (stack scan: no symbols). Remaining object churn = All_Subs one-off xbmc.Player() calls in worker threads on every video start (general/engine/sub_window/bsplayer) -> guard v6: one _BN_PLAYER in general.py, imported by the others. Quit 55 s = All_Subs replaying ~50 queued OnPlay notifications after quit -> v6 in autosub: handler returns when nothing plays / Kodi quits. v6 verified on a copy (idempotent, parses). t_all_subs_guard checks v4+v5+v6. Next: rebuild, full suite x2 (runs 10/11).
- [runs 10+11] run10 48/48 GREEN (no crash). run11 47/48: quit 120 s - All_Subs still replayed the OnPlay backlog (during quit the video still counts as playing, v6 check passes). Guard v7: skip an OnPlay for the video handled <60 s ago (_bn_done). Verified on a copy. Next: rebuild, runs 12+13.
- [runs 12+13] 46/48 x2, NO crash in runs 10-13 (4 in a row). Left: quit 32 s = All_Subs "retry in all languages" 2nd search round during quit -> guard v8 (engine: retry only while media plays and not quitting). AI button test setup retries SetSubtitle (startup flow may switch once). Tracebacks = idanplus "Unknown addon id" while System Update Auto-Fix reinstalled it -> exempt add-ons named in the "[NovaTV] system update" errors row. Next: rebuild, runs 14+15.
- [GREEN x2] runs 16+17 48/48 each. "Reversed Hebrew" was my misreading of downscaled screenshots (crops: correct). docs/v1.1.0/TEST_REPORT.md written. Next: merge release/v1.1.0 -> main, python tools/release.py --version 1.1.0 (zip, APKs, installer, guide, tests, push, GitHub release).
