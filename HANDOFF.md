# BN Stream (NovaTV) – HANDOFF

Last update: 2026-09-27 03:10 – v0.2.5 PUBLISHED
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

## Useful facts
- Subtitle server: `server/nova_subs.py serve --port 8765`, supervisor `server/supervisor.py` (pythonw, Startup shortcut),
  log `server/logs/server.log`, cache `server/cache/<job>.json`. Restart = kill `nova_subs.py serve` processes; supervisor restarts.
- Testkodi: `testkodi/` (portable). Installed-copy test: `work/wintest`. Android: `work/android` (AVD "bn"),
  `tools/android_test.py` (grants MANAGE_EXTERNAL_STORAGE via appops; deletes leftover app data first; ignores emulator's own crashes).
- Helper scripts I used live in the session scratchpad (not needed): edits are all in the repo.
