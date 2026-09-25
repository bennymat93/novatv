# NovaTV – Kodi build (Hebrew / English / Russian)

Main menu: **Movies · Series · TV Channels · Radio · NovaTV** (history, favourites, accounts).

**User guide (English + Hebrew):** https://bennymat93.github.io/novatv/guide.html · [docs/GUIDE.md](docs/GUIDE.md)

## One place for everything (0.1.8)
BN (NovaTV) is the only add-on you open. POV, Idan+, YouTube, Internet Archive and the other stable official add-ons live inside it:
**Search all sources** queries them all at once, playing a title tries POV first and then every other source, and the
**central library** shows every source by category (incl. official Russian studio channels). Only add-ons that pass
`tools/provider_audit.py` (menu, search, real playback) are shown – see [docs/audit/providers.csv](docs/audit/providers.csv).

## Ready-to-use apps (no setup needed)
* **Android TV / phone:** [BN Stream 64-bit](https://github.com/bennymat93/novatv/releases/latest/download/BN-Stream-21.3-arm64-v8a.apk) · [32-bit](https://github.com/bennymat93/novatv/releases/latest/download/BN-Stream-21.3-armeabi-v7a.apk). The build is inside the APK and unpacked on first start.
* **Windows:** `BN-Stream-Setup-<version>.exe` from [Releases](https://github.com/bennymat93/novatv/releases/latest): Kodi + build, per-user install.

## Install on an existing Kodi 21 (Android TV / Windows / phone / tablet)
1. Settings → System → Add-ons → enable **Unknown sources**.
2. Settings → File manager → Add source → `https://bennymat93.github.io/novatv/` → name it `nova`.
3. Add-ons → Install from zip file → `nova` → `repository.nova-1.0.0.zip`.
4. Add-ons → Install from repository → NovaTV Repository → Program add-ons → **NovaTV Wizard** → Install.
5. Open **NovaTV Wizard** → *Fresh install*. Kodi closes; open it again.
6. NovaTV → **Accounts & Connections**: Real-Debrid, Trakt, IPTV (M3U + EPG), AI subtitle server, Gemini (optional).

## AI subtitle server (PC)
* Run `server\install_autostart.bat` once: the server starts now and at every Windows sign-in, hidden, and a supervisor restarts it if it stops (GPU: faster-whisper large-v3-turbo; translation: Gemini -> local NLLB-200).
* Status: `.venv11\Scripts\python server\supervisor.py status` · log: `server\logs\server.log` · remove: `supervisor.py uninstall`.
* TV boxes on the same network find the server by themselves; manual: Accounts -> AI Subtitle Server -> `http://<PC-IP>:8765`.
* `server\start_server.bat` runs it in a console window (for watching the log).
* Batch a whole series overnight:
  `.venv11\Scripts\python server
ova_subs.py batch "D:\Kukhnya\*.mkv" --title "Кухня"`

## Develop
* `python tools/release.py --version X --notes "..."` – **one command per release**: build, 21-check test suite, guide, APKs (build embedded), Windows installer (+ tests on the installed copy), push, gh-pages, GitHub release.
* `python tools/make_guide.py` – regenerate `docs/guide.html` + `docs/GUIDE.md` (also runs inside publish/release).
* `python tools/make_apk.py --version X` / `python tools/make_windows.py --version X` – single artifacts.
* `android/BnSetup.java` – first-start build installer inside the APK (`android/smali/BnSetup.smali` is its compiled form).
* `docs/audit/` – source audit CSVs (cloud vs. Israeli network).
* `python tools/make_build.py --version X` – build zip (base: Kodi-POV-IL FENtastic).
* `python tools/publish.py --gh-user bennymat93 --version X` – regenerate `site/` for GitHub Pages.
