# NovaTV (continues as TeleNova)

> From 3.1.0 this project is **TeleNova**: https://github.com/bennymat93/TeleNova . This repository keeps serving
> updates to boxes that installed the NovaTV build (TeleNova 3.1.0 and its Telegram engine 3.1.0).

Kodi 21 build and add-on repository: Hebrew / English / Russian interface, one catalogue for movies and series,
merged IPTV with automatic numbering, radio, AI Hebrew subtitles, and a built-in Telegram engine.

**Install:** Kodi > Settings > File manager > Add source > `https://bennymat93.github.io/novatv/` > Add-ons >
Install from zip file > `repository.nova-1.0.0.zip`, then install **NovaTV Wizard** from the repository.
Guides: [user guide](https://bennymat93.github.io/novatv/guide.html) ·
[adding sources](https://bennymat93.github.io/novatv/sources_guide.html)

## Add-ons in this repository

| Add-on | Version | What it does |
| --- | --- | --- |
| `plugin.video.nova` | 3.1.0 | The hub: TMDb catalogue, search across every source, IPTV, radio, history, favourites, accounts, subtitles |
| `plugin.video.telescope` | 3.1.0 | TeleScope AI, the Telegram engine: exact movie / episode matching, link and speed testing, range-streaming proxy |
| `plugin.program.novawizard` | 0.2.1 | Installs and updates the build |
| `resource.uisounds.nova` | 1.0.0 | Navigation sounds |
| `repository.nova` | 1.0.0 | This repository |

## 3.0.0 – Telegram is part of the build

- NovaTV installs `plugin.video.telescope` from this repository by itself (builds installed before 1.7.0 included).
- **Search all sources** lists Telegram results next to TMDb, the other add-ons, live channels and radio.
  An episode search lists only the exact season and episode.
- **Playing a movie or an episode**: when POV / Real-Debrid has nothing, the source list starts with Telegram links
  that TeleScope matched by TMDb id and tested (first megabyte downloaded, container checked, speed measured).
  Setting *Telegram first* asks Telegram before POV.
- Long-press on a movie or an episode: **Telegram sources (choose)**.
- Main menu: **Telegram – TeleScope AI** (Chiko Media channels, my channels and groups, login and status).
- Login: an installed and logged-in Telemedia add-on is reused; otherwise phone or QR login with your own
  `api_id` / `api_hash` from my.telegram.org. Only chats your account has joined are searched.
- The TMDb and Gemini keys entered in NovaTV are shared with the Telegram engine.

### Fixes in this release

- TeleScope 3.0.0: first-run setup failed with "No compatible wheel for pyaes" (pyaes publishes only a source
  archive) - it is now installed from the source archive, downloads are retried, and login retries the setup.
- Movies > Search and Series > Search also list the files the Telegram engine finds for the same text.

- Wizard 0.2.1: an *update* no longer deletes add-ons that were installed from the repository after the build was
  made; the partly downloaded build file is removed after a cancelled, failed or corrupt download.
- NovaTV: the "searching all sources" progress bar no longer stays on screen when a source search fails;
  duplicate `IsPlayable` property on movie rows removed.
- Repository: old `plugin.video.nova` packages (1.5.1 – 1.6.3, about 325 MB) removed; only 3.0.0 is kept.

### Hub API of the Telegram engine (for other add-ons)

```
plugin://plugin.video.telescope/?mode=hub&q=<text>
plugin://plugin.video.telescope/?mode=hub&type=movie|tv&tmdb=<id>[&season=..&episode=..][&title=..]
```

Both return a plain folder of playable items and never open a dialog.

## Notes

- The full build package and the BN Stream apps are attached to the GitHub releases; `build.json` points the wizard
  to the current build package.
- Content availability depends on the services and Telegram chats each user has access to.
