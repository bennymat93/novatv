# v1.1.0 decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **Option A**: keep Kodi's internal VideoPlayer; VLC-grade features via skin OSD + Python + JSON-RPC/builtins | Option B (external VLC via playercorefactory) cannot keep our OSD/menus, loses resume/watched tracking in plugins, is not available the same way on Android TV and causes a visible app switch – fails the acceptance list |
| D2 | Build keeps its name **BN Stream**; "Anonymus TV" in the brief is the reference build, not ours | the repo, APK package (org.bn.stream) and installer are BN Stream |
| D3 | Layout, hierarchy and interaction copied from the Anonymous photos; accent colour stays **BN gold** instead of pink | brand consistency with the rest of the build; everything else follows the photos |
| D4 | Subtitle storage = local folder `special://profile/addon_data/plugin.video.nova/subtitles/` (setting `subs_folder`), registered as Kodi's custom subtitle folder | the brief's location is a Google Drive **web link**, not a folder Kodi can write to. On Windows the owner can point the setting at his "Google Drive for desktop" folder (`G:\My Drive\...`) to sync it |
| D5 | Version **1.1.0** for plugin.video.nova (and the build/APK/installer) | brief |
| D6 | Dual subtitles = one merged SRT: primary cues + secondary cues prefixed `{\an8}` (top) | Kodi 21 has no secondary subtitle stream |
| D7 | "Auto subtitles" sources: Wizdom (Hebrew, no key) → YouTube captions / auto-translate → server text sources + machine translation (mtrans). OpenSubtitles **hash** search only when the owner adds his own API key (setting) | OpenSubtitles REST needs an API key + login; we never ship someone else's key |
| D8 | Resume of the **same** video: setting `resume_same` (ask / always / never), default **ask**; a new video never inherits the previous stop time | brief; Kodi bookmarks are per file, we additionally clear per-file settings of the previous stream |
| D9 | Integration tests run on a portable Windows Kodi 21 driven by JSON-RPC (no Xvfb on this Windows host); Android via the emulator | same code path; Xvfb is Linux-only |
| D10 | Sync menu keeps Kodi's native delay slider (as in the photo) and adds our Python panel for coarse steps, audio delay, bookmark sync, reset, remembered step | slider = exact look of the spec; Python adds what the slider cannot |
| D11 | Delays are applied with repeated `SubtitleDelayPlus/Minus` (0.1 s) / `AudioDelayPlus/Minus` (0.025 s); current value read from `Player.SubtitleDelay` / `Player.AudioDelay` | Kodi has no JSON-RPC setter for delays |

## D12 – All_Subs may be stopped by Kodi at quit
All_Subs (third party) runs its automatic search in network threads. Guards v5–v8 (resources/lib/subspatch.py) stop it from starting work when Kodi quits or when nothing plays, and they drop queued play notifications. A search that is already in flight when the quit arrives can still take longer than 5 s, and Kodi then stops the script. The quit itself stays under 30 s. The clean-shutdown test accepts this for All_Subs only. Every other service must stop by itself.
