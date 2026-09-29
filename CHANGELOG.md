# Changelog

## 1.2.2
- **Home screen:**
  - Every widget row and the main menu sit on a rounded panel a little lighter than the screen (8% white).
  - The search tile is smaller (560x315) and still centred.
- **All_Subs:** it keeps its own hearing-impaired tag setting. Only AI subtitles drop sound tags, as requested.
- **TED Talks removed:** its Kodi mirror downloads kept failing. The add-on install check uses NASA.

## 1.2.1
- **Google Drive is active.** OAuth client "BN Stream Kodi" (TV sign-in), the app is published, and there is a privacy policy page (docs/privacy.html -> site). Verified against a real Drive: sign-in with a code, a 6 MB resumable backup upload, a byte-identical restore, sync overwrite and delete.
- **The BN player comes back after updates.** It is set once per version, after the skin has loaded, and read back. Before, a one-time flag set too early, or a skin update, left installs updated from the repository on another player style. The viewer's own choice is kept until the next version.
- release.py pushes the repository right after the tests, before the APKs and the installer.

## 1.2.0
**Main menu:** "טלוויזיה ורדיו" and "מועדפים" entries. The default colours are BN gold.

**Movies and Series home screens:**
- A big centred search tile.
- Top rated, as big posters.
- "By category", "by year" and "by language" as tiles: modern gold line icons with the name under them. 11 languages.

**TV & Radio home screen:**
- Israeli channels as 3D posters, main channels first.
- "Channels of the world": one tile per country (accurate 3D flag and name), which opens that country's channels.
- Israeli radio.

**Search all sources** is shown as a search-box tile.

**AI subtitles** no longer contain sound descriptions ([מוזיקה], [Music], ♪, (צחוק)). All_Subs also removes them from downloaded subtitles.

**Google Drive** (sign in with a code on the TV): backups and restore, sync of favourites, history and IPTV sources between devices, subtitle upload, and a BN Stream folder under Videos. It is active once the build's OAuth client is set.

**Audit fixes:**
- All_Subs no longer sends viewing data to a third-party repository.
- All_Subs debug flood and the dead Subscene source are off.
- Invalid POV setting fixed.
- A false "subtitles failed" message after a successful AI load is gone.
- Unused code removed.

## 1.1.2
- Episode search is exact. Root cause: the episode's "search all sources" and the "POV found nothing" fallback searched only the show name (or show + episode name), so a Season 1 and a Season 2 Episode 5 search were the same query with the same results and cache key, and nothing filtered by season/episode.
  - Now the season/episode is passed along, the query states it in the show's language, and only exact matches are listed (new `epmatch.py`: S2E5 / S02E05 / 2x05 / Season 2 Episode 5 / Hebrew / Russian, whole numbers, ranges excluded, show name required).
  - "No exact matches" when nothing fits.
- The YouTube cache key is the normalised query and the fallback answer expires after 6 h.
- A source answering after the search deadline is dropped.

## 1.1.1
- AI subtitle server reachable outside home: when the saved address and the home network do not answer, NovaTV uses the server's Tailscale address (setting "Subtitle server outside home", default the PC in the owner's tailnet). Needs Tailscale on the Kodi device, signed in to the same account.

## 1.1.0
**Player (BN OSD v2).** The layout follows the reference photos:
- Top: clearlogo, episode and chapter lines, a clock and the end time.
- Bottom: time, סנכרון, כתוביות, transport, הפרק הבא, שמע, מידע and a gear button.
- Codec badges and a thin progress bar with a buffer layer.
- An info panel with the poster, the plot and technical details.
- Remote-first navigation through an explicit left/right chain.

**Panels.**
- Sync: coarse steps, bookmark sync and reset.
- Subtitles: download, language, background, size, opacity, off, Auto (no AI), AI, and a picker of generated subtitles.
- Settings: next episode, audio, subtitles (basic and advanced), video, audio stream, toggle subtitles, speed, zoom, A-B loop, jump and screenshot.
- Audio.

**Subtitle store.**
- One folder, which is also Kodi's custom subtitle folder.
- Files are named `<video>.<lang>.<source>.srt`, written as UTF-8 with a BOM through an atomic write, with a version suffix.
- A cleanup policy.
- A unified picker. Each entry can be activated, set as a secondary subtitle (dual subtitles), re-synced, renamed or deleted.

**SRT robustness.** Encoding detection (BOM, UTF-8, cp1255), tag normalisation, repair of overlapping and broken cues, and Hebrew RTL fixes.

**Auto subtitles.** Wizdom by IMDb ID, then machine translation. No AI is used.

**Zero-state playback.** Every video starts with:
- delays at 0, speed 1 and the normal view;
- the A-B loop and the info panel cleared;
- resume of the same video set by a setting (default: ask);
- a session dump line in the log.

**Keys.** VLC-style keys (docs/v1.1.0/KEYMAP.md).

**Tests.**
- 57 unit tests (pytest).
- New integration checks: player panels, a zero-state soak ×50, and a longer BN player walk.
