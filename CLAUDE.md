# NovaTV (BN Stream) – project notes for Claude Code

Repo: https://github.com/bennymat93/novatv (branch `main`, GitHub Pages on `gh-pages`).
Kodi 21 build, UI in Hebrew / English / Russian. Owner: Benny.
User preferences: Python, standard library only unless asked; answer tersely; tables for comparisons.

## Layout
- `addons/plugin.video.nova` – main add-on (default.py router, resources/lib/*)
  - `iptv.py` – merges free + user M3U/EPG into one numbered list for pvr.iptvsimple
  - `accounts.py` – Accounts screen (RD, Trakt, IPTV, subtitle server, Gemini, TMDb) + locked profile rows
  - `preset.py` – password-locked pre-configured profile (NEW in 0.1.6)
  - `libraries.py` – 14 free official Kodi add-ons; `radio.py` – radio-browser; `backup.py`
- Movies/series come from POV (`plugin.video.pov`) + Real-Debrid.
- `server/nova_subs.py` – AI subtitle server (Windows, port 8765)
- `tools/` – make_build.py, publish.py, test_suite.py (portable Kodi in `testkodi/`), source_audit.py (NEW)

## Release commands
```
python tools/make_build.py --version X
python tools/test_suite.py --version X [--installed DIR]   # 21 checks via JSON-RPC
python tools/release.py --version X --notes "..."          # everything, see Status
python tools/publish.py --gh-user bennymat93 --version X
python tools/source_audit.py --out work/audit.json [--dead addons/plugin.video.nova/resources/dead_streams.json]
```

## Status (2026-09-24, v0.1.7)
Handoff steps 1-4 done. Release flow: `python tools/release.py --version X --notes "..."` (bump the version for every significant change;
it rebuilds zip, guide, both APKs and the Windows installer, tests testkodi AND the installed Windows copy, pushes main + gh-pages, creates the GitHub release).
- APK: package org.bn.stream. Java classes moved to org/bn/stream and libkodi.so's compiled-in "org.xbmc.kodi" patched in place (same length);
  native code looks up classes as <package>.<Class>. BnSetup unpacks assets/bn_build.zip into .kodi on first start (and on APK update; keeps userdata).
  Verified on the Android 14 x86_64 emulator (arm64 via ndk_translation). armv7 APK untested (no 32-bit ARM emulator).
- Signing key: work/apk/bn.keystore, backup C:/Users/benny/BN-signing-key/ (never commit; updates need the same key).
- Emulator: work/android (SDK license accepted by the user 2026-09-24), AVD "bn".
- Windows installer: Inno Setup 6 in %LOCALAPPDATA%/Programs/Inno Setup 6; tools/make_windows.py.

## What changed in 0.1.6
| Area | Change |
|---|---|
| iptv.py | FREE lists 3 -> 9 (Movies, Kids, Documentary, News, Music, English); English/News/Music default OFF (`FREE_OFF`) |
| iptv.py | Parser bug: names cut when `http-user-agent` attr contained commas -> regex split; output lines were corrupted |
| iptv.py | Country from `tvg-id` suffix (`.ru@SD`) + source list name; Israel group 9 -> 56, Russian 0 -> 670 |
| iptv.py | Block overflow: full group spills to 5000+ so other blocks keep their numbers |
| iptv.py | `with_headers()`: appends `|User-Agent=...&Referer=...` (playlist headers, else browser UA). ~940 streams return 403 to Kodi's UA |
| iptv.py | `dead_streams.json` filter (125 URLs, 404/410 only; 403 kept – geo/header) applied before dedupe |
| preset.py | Admin configures accounts -> "Create locked profile" -> backup zip encrypted (PBKDF2-SHA256 200k, HMAC-SHA256 stream, HMAC tag). "Unlock" + password restores and restarts Kodi. 5 wrong tries -> 10 min lock. Optional shipped file: `resources/preset.nvp` |
| addon.xml | version 0.1.6 |

## Cloud audit results (US server, before header fix)
| Section | Total | OK | Partial | Unverified | Fail |
|---|---|---|---|---|---|
| TV (9 lists, unique URLs) | 5,649 | 2,767 | 219 | 1,122 | 1,541 (1,172 = 403, 125 = 404) |
| Radio | 160 | 121 | 0 | 33 | 6 |
| Official libraries (Omega repo) | 14 | 14 | – | – | 0 |
| APIs (TMDB, RD, Trakt, Gemini, Pages, POV) | 6 | 6 | – | – | 0 |
Re-probe of the 403s: 915 fixed by browser UA, 27 by playlist headers, 227 still 403 (geo).

## Decisions / boundaries
- Do NOT add Anonymous TV wizard sources (Telemedia, Novix, etc.) – they stream unlicensed content. Grow only licensed/free sources (iptv-org, official Kodi add-ons, FAST channels, Real-Debrid via POV).
- Never commit credentials in clear text. Pre-configured access only via encrypted preset.nvp; warn that a public file is only as strong as its password.
- Real-Debrid / Trakt login is device-code on the box; don't ask the user to paste passwords in chat.
