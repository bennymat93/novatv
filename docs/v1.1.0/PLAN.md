# v1.1.0 plan (branch release/v1.1.0)

| Phase | Deliverable | Files | Risk |
|---|---|---|---|
| 0 | ARCHITECTURE, PLAN, DECISIONS | docs/v1.1.0 | – |
| 1 | research A–E | docs/v1.1.0/research | agents wrote from memory: verify Kodi facts on the real system |
| 2 | Option A (D1) | DECISIONS | – |
| 3 | **Player v2** per photos: top (clearlogo/title, episode + chapter line, clock, end time), bottom one row (time, סנכרון, כתוביות, transport with accent circle, הפרק הבא, שמע, מידע, gear), badges over the progress bar | `resources/skin/Includes_VideoOsdBN.xml`, icons | skin focus paths |
| 3 | Panels (Python, remote-first): **Sync** (native slider + coarse/fine sub & audio delay, bookmark sync, reset, remembered step), **Settings** (next-episode, audio, subtitles, advanced subtitles, video, audio stream, subtitle toggle, speed, aspect/zoom, volume boost, appearance with live preview), **Info** (codecs, resolution, fps, HDR, channels, subtitle source/file/encoding, delays) | `resources/lib/player_menus.py`, router, skin buttons | no delay setter → repeated actions |
| 3 | KEYMAP.md + keymap file | `resources/keymaps/bn.xml` installed to userdata/keymaps | conflicts with skin keys |
| 4.1 | Subtitle store: naming `<base>.<lang>.<src>.srt`, atomic, UTF-8 BOM, versions, cleanup policy, Kodi custom folder | `resources/lib/substore.py` | long/Unicode names |
| 4.2 | Subtitles menu: Auto (no AI) / AI / Choose generated + appearance items | `subsmenu.py` v2 | – |
| 4.3 | Picker: sections Embedded / Local / Auto / AI / Online, preview, date, match score, actions activate / secondary / re-sync / rename / delete, filter, remember source | `subsmenu.py` v2, `substore.py` | – |
| 4.4 | SRT robustness: encoding detection, repair, Hebrew punctuation, fuzzy autoload | `resources/lib/subfix.py` | – |
| 5 | PlaybackSession: reset track/on-off/delays/speed/zoom/loop/props/jobs, resume policy, session dump log | `service.py` | Kodi re-applies state late (done: again() pass) |
| 6 | pytest unit tests + Kodi stubs; JSON-RPC integration incl. soak ×50, failure modes, UI screenshots; TEST_REPORT with traceability | `tests/`, `tools/test_suite.py` | runtime |
| 7 | release 1.1.0: versions, CHANGELOG, repo, zips/APK/installer, fresh install + upgrade test, tag | release.py | Kodi mirrors (fallback in place) |
