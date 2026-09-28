# Changelog

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
