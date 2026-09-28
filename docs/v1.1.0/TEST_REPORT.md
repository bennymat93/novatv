# v1.1.0 test report

**Result:** runs 16 and 17 in a row were both green, 48/48 each, on a fresh testkodi install of `dist/NovaTV-1.1.0.zip`, Windows portable Kodi 21.3 (D9).

**How to reproduce:**
- `python tools/test_suite.py --version 1.1.0` runs the whole suite.
- `--only "a,b" --repeat N` runs selected checks N times, for flaky or crash hunting.

**Logs:**
- `work/suite_110_run*.log`
- Kodi logs of crashes, with the `.dmp`: `work/crash-*.log`

## Unit tests (pytest)
`.venv11/Scripts/python -m pytest tests -q` gives **57 passed**. It covers `subfix`, `substore` and `syncmath`:
- encoding detection (BOM, UTF-8, cp1255, latin-1)
- timestamp parsing and repair
- tag normalisation
- overlapping and broken cues
- Hebrew RTL
- atomic UTF-8 BOM writes
- store naming, versioning and cleanup
- bookmark sync maths
- dual-subtitle merge

## Traceability
| Spec requirement | Implementation | Verified by |
|---|---|---|
| **Phase 3 – OSD per photos** (logo, episode/chapter, clock, end time, bottom row, badges, info panel) | `resources/skin/Includes_VideoOsdBN.xml`, `skinpatch.bn_player` | `BN player` (remote walks the 11 buttons, names read back), screenshot `work/shot_osd.png` |
| Remote-first navigation, keymap | explicit onleft/onright chain; `resources/keymaps/bn_player.xml`, `KEYMAP.md` | `BN player`, `Skin windows + AI button` |
| **Panels** (Sync, Subtitles, Settings, Audio, picker) | `resources/lib/player_menus.py`, router actions in `default.py` | `Player panels open` (5/5 open while playing), `BN subtitle window` |
| **Phase 4 – subtitle store** (naming, BOM, atomic, versions, cleanup, Kodi custom folder) | `substore.py`, `subfix.write_srt`, service start-up | pytest; `AI Hebrew subtitles end-to-end` (the result is stored) |
| Auto (no AI) / AI / choose generated | `player_menus.auto_subtitles/ai_subtitles/picker`, server mode `mt` | `Machine translation fallback`, `AI Subtitle Generation button`, `BN subtitle window` |
| SRT robustness, Hebrew RTL | `subfix.py` | pytest |
| **Phase 5 – zero-state session** (delays, speed, view, A-B, properties, jobs) | `service.py` `zero_state()`, SESSION_PROPS | `Zero-state soak` (×50 starts, delays and view mode reset), `Subtitles reset between videos`, `Subtitles reset on next episode` |
| Resume of the same video (setting, default ask) | `resume_same` setting, `zero_state()` | code review (Kodi's own resume dialog = "ask") |
| Session dump log line | `session start: {...}` | seen in every run log |
| **Failure modes** | AI server down, silent video, nothing playing | `AI: silent video, nothing loaded`, `AI button with nothing playing` |
| **Regression** (all 0.2.x features) | – | the 40 other checks |
| Stability: no crash, no thread leak, clean quit | fixes below | `No thread leak`, `No tracebacks`, `Kodi log clean`, `Clean shutdown` (under 30 s) |

## Defects found and fixed during testing
| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Kodi crash (python3.8.dll+0xdfec1) when a video closed | New `player_menus` created and freed `xbmc.Player()` on every menu pass. This is the 0.2.2 crash pattern. | One shared Player (`_pl()`) |
| 2 | Same crash, rarer | All_Subs (third party) created `xbmc.Player()` every 10 ms in its search wait loop and every 100 ms in its overlay, and one-off Players in worker threads | `subspatch` guards v5 and v6: an InfoLabel check and one Player and Monitor per process |
| 3 | The subtitle flow touched the player while it was closing | Missing guard | `same_video()` and `isPlayingVideo()` checked before reading streams; the store uses the job's title data |
| 4 | Kodi needed up to 2 min to quit | All_Subs replayed queued play notifications and a retry search round after the quit | Guards v5, v7 and v8 (no search when quitting or idle, duplicate notifications dropped, no retry on quit) |
| 5 | `VideoPlayer.SubtitlesName` label shown literally | Not a Kodi 21 label | Removed |

Note: a suspected "reversed Hebrew" on the OSD was a misreading of a scaled-down screenshot. Full-resolution crops show correct Hebrew everywhere. The label-over-button layout added for it is harmless and was kept.

## Accepted, documented
- **D12:** Kodi may stop All_Subs after 5 s at quit, when a network search was already in flight. The quit stays under 30 s.
- **Third-party noise excluded from "no tracebacks":**
  - YouTube add-on HTTP 429 on its own caption fetch.
  - An add-on unregistered while System Update's Auto-Fix reinstalls it.
