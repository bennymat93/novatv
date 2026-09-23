# NovaTV – Kodi build (Hebrew / English / Russian)

Main menu: **Movies · Series · TV Channels · Radio · NovaTV** (history, favourites, accounts).

## Install on Kodi 21 (Android TV / Windows / phone / tablet)
1. Settings → System → Add-ons → enable **Unknown sources**.
2. Settings → File manager → Add source → `https://bennymat93.github.io/novatv/` → name it `nova`.
3. Add-ons → Install from zip file → `nova` → `repository.nova-1.0.0.zip`.
4. Add-ons → Install from repository → NovaTV Repository → Program add-ons → **NovaTV Wizard** → Install.
5. Open **NovaTV Wizard** → *Fresh install*. Kodi closes; open it again.
6. NovaTV → **Accounts & Connections**: Real-Debrid, Trakt, IPTV (M3U + EPG), AI subtitle server, Gemini (optional).

## AI subtitle server (PC)
* `server\start_server.bat` – runs the server (GPU: faster-whisper large-v3-turbo; translation: Gemini → local NLLB-200, no quota).
* `server\install_autostart.bat` – start it automatically at Windows login.
* On the TV box: Accounts → AI Subtitle Server → `http://<PC-IP>:8765`.
* Batch a whole series overnight:
  `.venv11\Scripts\python server\nova_subs.py batch "D:\Kukhnya\*.mkv" --title "Кухня"`

## Develop
* `python tools/make_build.py --version X` – build zip (base: Kodi-POV-IL FENtastic).
* `python tools/publish.py --gh-user bennymat93 --version X` – regenerate `site/` for GitHub Pages.
