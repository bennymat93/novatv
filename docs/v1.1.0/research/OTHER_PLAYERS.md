# Other Players: Subtitle/Player Features Worth Adopting (v1.1.0 research)

Scope: Kodi 21 "Omega" build, Windows + Android TV, Hebrew-first, remote-control UI.
Constraint: implementation via Python add-ons (`xbmc`, `xbmcgui`, `xbmcvfs`), skin XML, JSON-RPC, and built-in actions. No core (C++) patches.

Legend: **Feasibility** = Feasible / Partial / Not feasible. **Priority** = P0 (v1.1.0 must), P1 (next), P2 (nice to have).
`[UNVERIFIED]` = written from documentation memory / community sources, not tested in this build; verify before relying on it.

---

## 1. OpenSubtitles movie hash (used by BS.Player, MPC-HC, PotPlayer, mpv scripts, Kodi subtitle add-ons)

Exact algorithm ("OSHash"):

1. `hash = filesize` (64-bit unsigned).
2. Read the **first 65536 bytes** (64 KiB) as 8192 little-endian unsigned 64-bit integers; add each to `hash`, modulo 2^64.
3. Read the **last 65536 bytes** of the file the same way and add them, modulo 2^64.
4. Output: 16 lowercase hex digits, zero-padded (`"%016x"`).
5. Files smaller than 64 KiB (some implementations: < 128 KiB) are rejected.

```python
import struct, xbmcvfs
def oshash(path):
    f = xbmcvfs.File(path); size = f.size()
    if size < 65536 * 2: raise ValueError("file too small")
    h = size
    for off in (0, size - 65536):
        f.seek(off, 0); buf = f.readBytes(65536)
        h = (h + sum(struct.unpack("<8192Q", buf))) & 0xFFFFFFFFFFFFFFFF
    f.close(); return "%016x" % h
```

Notes: only 128 KiB is read, so it works over SMB/NFS/HTTP (range requests) via `xbmcvfs`. Streams without known size or seekability (most debrid/HLS streams from add-ons) **cannot** be hashed -> fall back to name/IMDb/season/episode search. A hash match means "same exact release", so sync is almost always correct.

---

## 2. Feature table

| # | Feature | Reference player & how exposed | Kodi 21 feasibility (how) | Network / API key | Pri |
|---|---|---|---|---|---|
| 1 | **Hash-based automatic subtitle download** | BS.Player: on file open, computes OSHash, queries its subtitle servers (OpenSubtitles + own DB), auto-loads best match in preferred language. MPC-HC: "Subtitle database" download dialog (Ctrl+D) by hash. | **Feasible.** Service add-on listens `xbmc.Player.onAVStarted`, computes hash (sec. 1), queries provider, downloads to `special://temp`, calls `xbmc.Player().setSubtitles(path)`. Kodi's own subtitle add-on framework (`xbmc.subtitle.module`, "search" / "download" actions) also supports passing `hash` if the add-on implements it. Language order: `he` > `en`. | Yes. **OpenSubtitles REST API (api.opensubtitles.com/api/v1) requires an API key (`Api-Key` header) plus a registered User-Agent; downloads additionally require user login (JWT) and are quota-limited per day.** Legacy XML-RPC API is deprecated/shut down `[UNVERIFIED exact shutdown date]`. Wizdom / Ktuvit (Hebrew) - no official public key scheme; scraping-based, may break `[UNVERIFIED]`. | P0 |
| 2 | **Subtitle search fallback (name/IMDb/episode)** | PotPlayer: Subtitle menu -> "Search subtitles online" dialog with list. MPC-HC: search dialog with results list. | **Feasible.** Use `ListItem`/`VideoPlayer.IMDBNumber`, `TVShowTitle`, `Season`, `Episode` infolabels; show results in `xbmcgui.Dialog().select()` (remote-friendly). Already how a4kSubtitles etc. work. | Same as #1 (key for OpenSubtitles). | P0 |
| 3 | **Subtitle delay / sync by keys** | MPC-HC: F1/F2 = -/+ 100 ms `[UNVERIFIED default binding]`. PotPlayer: `<` / `>` = -/+ 0.5 s, `?` reset. mpv: `z`/`Z` = -/+ 0.1 s (`sub-delay`). | **Feasible (built-in).** Kodi actions `SubtitleDelayMinus`, `SubtitleDelayPlus`, `SubtitleDelay` (slider). Map to remote keys in `keymaps/*.xml` (e.g., long-press left/right in FullscreenVideo when OSD hidden, or colour buttons). Step size = `subtitles.delay` step fixed at 0.1 s in core `[UNVERIFIED if configurable]`. Read current value: JSON-RPC does not expose subtitle delay directly `[UNVERIFIED]`; infolabel `VideoPlayer.SubtitlesDelay` `[UNVERIFIED name]`. | None | P0 |
| 4 | **sub-step / sub-seek (sync to next/prev line)** | mpv: `sub-seek ±1` jumps playback to next/prev subtitle line; `sub-step ±1` shifts delay so next/prev line appears **now** (Ctrl+Shift+Left/Right). PotPlayer: similar "sync to current line" `[UNVERIFIED]`. | **Partial.** Not in Kodi core. Python can parse the loaded .srt/.ass file itself (we know the path if we downloaded it), know `xbmc.Player().getTime()`, compute delta to nearest cue, then apply delay by sending N x `SubtitleDelayPlus/Minus` actions (0.1 s granularity) or rewriting a shifted copy of the file and reloading via `setSubtitles`. Embedded (MKV) subs: not accessible -> not feasible. | None | P1 |
| 5 | **Automatic audio-based sync (alass / ffsubsync / autosubsync-mpv)** | mpv script **autosubsync-mpv** (key `n`): extracts audio with ffmpeg, runs ffsubsync or alass, writes `*_retimed.srt`, reloads. **ffsubsync**: WebRTC VAD (or auditok) turns audio into a 0/1 speech signal at 100 Hz; subtitle cues become a 0/1 signal; FFT cross-correlation finds best offset; also searches framerate ratios (e.g., 23.976/25). **alass**: aligns against a reference (another subtitle or VAD-derived speech segments); handles **splits** (ad breaks / cut scenes) with a split-penalty dynamic-programming search, not just a constant offset. | **Partial / Windows only realistically.** Needs ffmpeg + ffsubsync (Python + numpy + webrtcvad native) or alass binary. Windows: ship `alass-cli.exe` + `ffmpeg.exe` in an add-on, call via `subprocess`, reference = other subtitle (sub-to-sub, no audio needed) or audio. Android TV: subprocess of bundled ARM binaries is fragile, heavy on CPU, and requires local file access; streams are not local -> **Not feasible** on Android in v1.1.0. Cheap alternative for both: **sub-to-sub alignment** (align Hebrew sub to an English sub already in sync, e.g. embedded track text not accessible -> only for external subs). | Optional (none for local processing). | P2 (Win P1 for sub-to-sub) |
| 6 | **Dual / secondary subtitles** | BS.Player: two simultaneous subtitle tracks (one top, one bottom) `[UNVERIFIED exact UI]`. PotPlayer: "Secondary subtitle" (Alt+S cycle `[UNVERIFIED]`). mpv: `secondary-sid`, rendered at top, `secondary-sub-visibility`. | **Partial.** Kodi 21 renders only one subtitle stream. Workaround: Python merges two external SRTs into one ASS file (Hebrew bottom, English top via `\an8` / separate Styles), then `setSubtitles(merged.ass)`. Works for external/downloaded subs only; embedded tracks not extractable from Python. | None (beyond #1 downloads) | P1 |
| 7 | **Subtitle position control** | BS.Player: move subs up/down by keys, margin setting. MPC-HC: position/margins in Subtitle Renderer settings. mpv: `sub-pos` (0-100), `r`/`R`. | **Feasible (built-in).** Kodi 21 settings `subtitles.align` (manual/bottom/top/inside video) and vertical margin `subtitles.marginvertical` `[UNVERIFIED key name]`; set via JSON-RPC `Settings.SetSettingValue`. Interactive: built-in window "Subtitle position" calibration (`ActivateWindow(SubtitlePosition)` / Video calibration) `[UNVERIFIED id]`. Expose as two OSD buttons (Up/Down) calling a script that nudges the setting. | None | P1 |
| 8 | **Subtitle styles (font, size, colour, border, background)** | MPC-HC: "Default style" dialog (font, outline, shadow, colour, alpha). mpv: `sub-font`, `sub-font-size`, `sub-border-size`, `sub-back-color`, `sub-ass-override`. | **Feasible.** Kodi 21 has font, size, colour, border size/colour, background type/opacity, bold/italic, "override ASS styles" in Settings > Player > Subtitles. Set via JSON-RPC `Settings.SetSettingValue` (`subtitles.fontsize`, `subtitles.colorpick`, ... `[UNVERIFIED exact ids, check Settings.GetSettings]`). Build 3-4 presets ("TV large", "Hebrew bold yellow", "Minimal") in a skin dialog. Hebrew font must include Hebrew glyphs (Arial / Noto Sans Hebrew). | None | P1 |
| 9 | **Autoload with fuzzy filename matching** | mpv: `sub-auto=fuzzy` (built-in) plus scripts (autoload.lua, "autosub" which calls subliminal to download). MPC-HC/PotPlayer: load subs from same folder / `Subs/` subfolder with partial name match. | **Feasible.** Kodi already loads same-basename subs and `subtitles.custompath`. Python can add fuzzy match (normalize, strip release tags, match SxxEyy) in same folder + `Subs/`, then `setSubtitles`. Only for local/SMB files. | None | P2 |
| 10 | **Subtitle encoding / RTL handling** | MPC-HC/PotPlayer: auto-detect codepage (Windows-1255 for Hebrew). | **Feasible.** Kodi setting `subtitles.charset` = Hebrew (Windows-1255); downloader should transcode to UTF-8 before loading. Fix RTL punctuation (leading/trailing `.,?!-`) - common Hebrew SRT issue - by inserting RLM (U+200F) `[UNVERIFIED that Kodi's bidi needs it in 21]`. | None | P0 |
| 11 | **Remember per-file delay / track** | mpv: `watch-later` stores `sub-delay`. PotPlayer: remembers per-file. | **Partial.** Kodi stores per-file video settings (incl. subtitle delay) in its video DB when "Save for this file" / default behaviour `[UNVERIFIED for add-on streams]`. Add-on streams (plugin://) often not persisted -> store `{file_id/imdb+S/E: delay, sub path}` in add-on data JSON and reapply on `onAVStarted`. | None | P1 |
| 12 | **Subtitle download cache / "subtitle database" upload** | MPC-HC/BS.Player: can upload hash+sub pairs to OpenSubtitles. | **Not worth it.** Upload needs account and API key; skip. Local cache (hash -> chosen sub) is feasible and cheap. | Upload: key + login | P2 |

---

## 3. Remote-control notes

- Every feature above must be reachable with D-pad + OK + Back (+ optional colour/menu keys). Avoid keyboard-only bindings (mpv/PotPlayer style).
- Proposed OSD "Subtitles" panel: [Download (auto)] [Search] [Sync -/+] [Sync to line] [Position] [Style preset] [Dual subs].
- Show a toast (`xbmcgui.Dialog().notification`) with the current delay after each step, in Hebrew.

---

## 4. Adopt now (ranked, max 10)

1. **Hash-first auto-download on playback start** (OSHash, Hebrew > English, fall back to IMDb/S/E search). Requires OpenSubtitles API key + user login; bundle the build's API key, ask user for credentials. (P0)
2. **Remote-mapped sync keys** using built-in `SubtitleDelayMinus/Plus` + on-screen delay toast. (P0)
3. **Manual search dialog** (select list) for when auto picks wrong. (P0)
4. **Encoding normalisation + Hebrew RTL punctuation fix** before `setSubtitles`. (P0)
5. **Per-title memory** of chosen subtitle and delay for plugin streams. (P1)
6. **Style presets** via `Settings.SetSettingValue` (TV-readable Hebrew). (P1)
7. **Position up/down** OSD buttons via subtitle alignment/margin settings. (P1)
8. **Sync-to-line (sub-step emulation)** for external subtitles. (P1)
9. **Dual subtitles via merged ASS** (Hebrew bottom + English top). (P1)
10. **alass sub-to-sub auto-sync on Windows** (ship alass-cli; Android deferred). (P2)

Services summary: only #1/#3 (and optional Hebrew providers) need network. **OpenSubtitles.com REST API: API key mandatory, login needed for downloads, daily download quota.** Everything else is offline.
