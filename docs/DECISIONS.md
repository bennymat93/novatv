# Decisions – 1.4.0

## Main menu architecture (Phase 2)
Research: Kodi skins (Estuary, Arctic Horizon 2, Aeon Nox SiLVO), Android TV / Google TV, Plex and Apple TV all use
**one level**: a side or top menu of content types, and under each one horizontal rows (widgets) that open the
content directly. Nested sub-menus are avoided (Google TV removed "apps > app > section"; Plex moved libraries into
rows). The 10-foot rule: every piece of content at most 2 presses from the menu item.

**Structure (implemented):** one level, 8 items, rows under each:

| Menu item | Rows (direct access) |
|---|---|
| סרטים | search · top rated · by category · by year · by language |
| סדרות | search · top rated · category · year · language |
| טלוויזיה ורדיו | Israeli channels (posters) · channels of the world (flags + counts) · Israeli radio (posters) |
| מועדפים | movies · series · channels · radio · recently watched |
| ידע וטכנולוגיה | search · categories |
| אילוף כלבים | search · top rated · categories |
| BN | the hub: sources, accounts, backup, system status, device type, System Update |
| עזרה (last) | search help · guide · troubleshooting · speed test · about |

Under the logo: power · settings · **System Update** · search everywhere. Everything that existed stays reachable.

## Ticker (1.7)
- Kodi's own RSS control: it replaces the text only when a scroll lap ends, and it keeps the last good text when a fetch fails. That is exactly "refresh between cycles, never mid-scroll", with no skin scripting.
- Kodi reads RSS over http only, so the NovaTV service serves one combined feed on 127.0.0.1:51153.
- News:
  - ynet flashes RSS (StoryRss1854), fallback Walla breaking news (feed/22).
  - Both are free, official, Hebrew, and update within minutes.
- Weather:
  - Open-Meteo (no key; ECMWF/ICON models; geocoding in Hebrew).
  - The city is a setting, default Be'er Sheva.
- Rejected:
  - Kan / Maariv RSS (dead endpoints in tests).
  - OpenWeatherMap (needs a key).
  - Kodi's weather add-ons (need a user key and do not feed a ticker).

## Subtitle sync (Phase 4)
Root causes found:
1. **AI subtitles:** segment-level Whisper timestamps start up to ~1 s late.
   - Fix: word timestamps (`cue_times`).
2. **Cache key per title, not per file:** a second release of the same episode got the first release's timing.
   - Fix: per-release key `_release`.
3. **Downloaded subtitles are timed for another release** (intro length, 23.976 ↔ 25 fps).
   - Fix: automatic alignment (`server/subalign.py`, like alass/ffsubsync):
     - Silero VAD speech map;
     - FFT cross-correlation;
     - 7 frame-rate ratios.
   - Measured on real speech:
     - ±2.5 / 1.2 / 0.4 s offsets recovered within 0.1–0.2 s;
     - 25/23.976 drift recovered exactly;
     - an in-sync file is left untouched.
4. **The manual offset was forgotten between plays.**
   - Fix: remembered per video (`playerctl.remember_delay`).
- Not a cause: Kodi's own subtitle pipeline adds no delay; refresh-rate switching only affects TVs (profile).

## Weak connections (Phase 6)
- Test rig: `tools/netsim.py`, a shaping proxy with a token bucket, latency ±jitter and random drops.
  - Accuracy measured: 1.48 / 3.1 / 5.4 Mbps for 1.5 / 3 / 5 targets.
- Finding: inputstream.adaptive starts at the last measured bandwidth. After a fast session it opened at 1080p on a 1.5 Mbps link: **9 stalls per minute**.
- Fix: start at 1.5 Mbps, then let the adaptive selection climb (`adaptivestream.bandwidth.init`).
  - Result: 0 stalls at 1.5 / 3 / 5 Mbps; start in 2–3 s.
- IPTV HLS also goes through inputstream.adaptive (`useInputstreamAdaptiveforHls`).
- Cache per device profile (DEVICE_PROFILES.md).
- Multi-source failover: POV → other sources (existing), plus stream fallbacks in Phase 3.

## Name and logo in a plain Kodi
- An add-on cannot rename the Kodi app or change its launcher icon (fixed in the APK / exe).
- Done instead:
  - the BN splash on every device;
  - "BN Stream" shortcuts on Windows;
  - a one-time offer on Android to install the BN Stream app (backup first).
