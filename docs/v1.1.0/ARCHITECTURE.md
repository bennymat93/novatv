# BN Stream – architecture before v1.1.0 (state of v0.2.5/0.2.6)

## Components
| Path | Role |
|---|---|
| `addons/plugin.video.nova` (NovaTV) | main add-on: `default.py` router, `service.py` (player/state service), `resources/lib/*` |
| `service.py` | `Player` (xbmc.Player): `gen` counter per video, `begin()` on onAVStarted (subtitles off, clear props), `finish()` on stop/end/error (deletes the stream's MyVideos `settings` row after 6 s); `Flow` = one subtitle job per video (hold/pause, wait for Hebrew, AI server job, load SRT, fastest source wins); `Monitor` (NotifyAll `ai_now`); timers via `later()`; startup: skin patch, All_Subs guards, YouTube port/subtitles, BN player default |
| `resources/lib/subsmenu.py` | BN subtitle window (select list of tracks, AI on by hand, generate, search, sync) |
| `resources/lib/mtrans.py` | machine translation without AI (Google dict-chrome-ex batch → Google gtx → MyMemory), SRT/VTT parse, unroll YouTube captions |
| `resources/lib/skinpatch.py` | patches skin.fentastic at build time and at runtime: AI buttons, "כתוביות BN", BN player (`Includes_VideoOsdBN.xml` + icons → skin media/bn) |
| `resources/lib/subspatch.py` | guards for third-party All_Subs / All Subs Plus |
| `resources/lib/sysupdate.py` | System Update + Auto-Fix |
| `resources/lib/ytport.py` | YouTube HTTP port (Windows reserved ranges) + YouTube Hebrew captions setting |
| `server/nova_subs.py` | PC subtitle server :8765 (Whisper GPU, Gemini/mtrans/NLLB, YouTube captions via yt-dlp, cache) + `supervisor.py` |
| skin.fentastic (+ BN patches) | UI; 5 player styles incl. `__bnplayer` |
| service.subtitles.All_Subs | third-party subtitle search/autosub (patched guards) |
| `tools/` | make_build, make_apk, make_windows, release (checkpointed), test_suite (JSON-RPC, 49 checks, stop/resume), android_test, make_guide, make_osd_icons |

## Playback pipeline
TMDb list → `?a=play` → POV (Real-Debrid) or fallback source → Kodi VideoPlayer → `Player.onAVStarted` → `begin()` →
`Flow`: embedded/All_Subs Hebrew (wait) → AI server job (YouTube: captions) → load `profile/ai/<job>/BN AI*.he.srt`.

## State stores
MyVideos `settings`/`bookmark` tables (per file), Window(10000) props (`NovaTV.AISubs`, `NovaTV.AISrt`, `NovaTV.SubsChosen`,
`NovaTV.iptv_busy`), skin strings (`__chooseplayer`), addon settings, `profile/*.json` (history, favourites, iptv, sysupdate).

## Features that exist (regression list)
menus/lists (movies, series, languages, genres, years, Kukhnya), radio, accounts, favourites, history, IPTV merge + numbering +
free channels, libraries + on-demand install, backup, locked profile, hub search, central library + Russian, POV fallback,
startup status, AI subtitles (auto, button, silent-video safety, YouTube captions), subtitle reset between videos / next episode,
BN subtitle window, machine translation, System Update + Auto-Fix, All_Subs guards, YouTube port, clean shutdown, no thread leak.
