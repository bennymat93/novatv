# SRT Handling for a Hebrew-first Kodi 21 Build

Status: research notes for v1.1.0. Claims marked **[unverified]** were written from memory of the upstream sources and were not re-checked line by line against the current tree. Everything else refers to well-known, stable behaviour.

---

## 1. How VLC 3.x parses SRT robustly

### 1.1 Source map
| Concern | File / function (VLC 3.0.x) |
|---|---|
| Demuxer, format probing, cue parsing | `modules/demux/subtitle.c`: `Open()`, `TextLoad()`, `ParseSubRip()` / `ParseSubRipSubViewer()` via `ParseSubRipSubViewer(..., "%d:%d:%d,%d --> ...")`, `subtitle_ParseSubRipTiming()` **[unverified: exact helper name]** |
| Charset handling | `modules/demux/subtitle.c` (BOM check, `--subsdec-encoding`), `modules/codec/subsdec.c`: `OpenDecoder()` / `DecodeBlock()` (UTF-8 validation via `IsUTF8()` / `EnsureUTF8()`, fallback to `vlc_pgettext("GetACP", ...)` locale default) |
| Tag parsing (`<i>`, `<b>`, `<u>`, `<font>`, `{\an8}`) | `modules/codec/subsdec.c`: `CreateHtmlSubtitle()` / `ParseSubtitles()` and `HtmlCopy()`; `{\anN}` handled in `subsdec.c` `ParsePositionFlags` style code **[unverified: function names]** |
| Rendering / bidi | `modules/text_renderer/freetype/text_layout.c` (FriBiDi + HarfBuzz shaping, `LayoutParagraph()`), `freetype.c` |

### 1.2 Encoding detection
1. **BOM**: UTF-8 (`EF BB BF`), UTF-16 LE/BE BOMs are detected in the demuxer and the stream is converted/flagged as UTF-8. BOM bytes are stripped.
2. **Explicit option**: `--subsdec-encoding` overrides everything if set.
3. **UTF-8 validity**: without a BOM, `subsdec` checks whether the decoded block is valid UTF-8 (`IsUTF8()`); if valid, it is used as-is.
4. **Fallback charset**: otherwise it picks a default derived from the UI locale (Windows: `GetACP()` → e.g. CP1255 on Hebrew Windows; elsewhere a locale-to-charset table, `vlc_pgettext("GetACP", "CP1252")`-style translatable default) **[unverified: exact table]**. Per-block decision means a file that is mostly UTF-8 with one bad line is still handled line by line.

Lesson: *strict UTF-8 first, then a legacy fallback*, never the reverse (latin-1/cp1255 accept any byte and will "succeed" on UTF-8 input).

### 1.3 Timestamp tolerance
`ParseSubRip` accepts via `sscanf`-style patterns:
- `HH:MM:SS,mmm --> HH:MM:SS,mmm` and `.` instead of `,`.
- Fractions of 1–3 digits; VLC scales by digit count (`,5` = 500 ms) **[unverified: whether 1-2 digits are scaled or read as raw ms in 3.0.x; newer code scales]**.
- Extra whitespace around `-->` and trailing coordinates (`X1:... Y2:...`) are ignored.
- Missing hours (`MM:SS,mmm`) is **not** accepted in 3.x SRT path **[unverified]**; WebVTT demuxer (`modules/demux/webvtt/`) does accept `MM:SS.mmm`.
- Hours are parsed as `%d`, so `>99h` works.

### 1.4 Structure tolerance
- Index line is essentially ignored: the parser looks for the next line that matches the timing pattern, so blank, missing, duplicated or non-numeric indices do not break parsing.
- Text ends at the first empty line; multiple blank lines are skipped.
- `TextLoad()` reads the whole file into an array of lines once, so very long files are fine (memory-bound only). After parsing, cues are **sorted by start time** (`qsort` on `i_start`) **[unverified: sort present in 3.0 subtitle.c — believed yes]**.
- Overlapping cues are kept; the SPU renderer displays both simultaneously (stacked).

### 1.5 Tags
- `<i> <b> <u> <s>` and `<font color="..." face="..." size="...">` are converted to styled segments; unknown tags are stripped as text.
- `{\an1}`..`{\an9}` at the start of a line sets alignment (e.g. `{\an8}` top-center); other `{\...}` ASS overrides are stripped.
- Rendering uses FriBiDi, so logical-order Hebrew renders correctly with base direction taken from the paragraph's first strong character.

---

## 2. Kodi 21 (Omega) VideoPlayer and SRT

- **Parser**: `xbmc/cores/VideoPlayer/DVDSubtitles/DVDSubtitleParserSubrip.cpp` → text goes through `SubtitlesAdapter` / `CSubtitlesStyle` and is rendered by **libass** (since Kodi 20 all text subtitles go through libass: `OverlayRenderer` + `DVDSubtitlesLibass.cpp`). SRT tags are converted to ASS by `DVDSubtitleTagSami` / `CDVDSubtitleTagSami` (for `<i> <b> <u> <font color>`) **[unverified: exact converter class in v21]**.
- **Encoding**: `DVDSubtitleStream` / `CCharsetConverter`. Order: BOM (UTF-8/UTF-16) → valid UTF-8 → the value of **Settings → Player → Language → Character set** (`subtitles.charset`, default "Default" = GUI charset). For Hebrew set `subtitles.charset` = `CP1255` (Windows-1255 "Hebrew (Windows)"). UTF-8 with BOM always works regardless of the setting.
- **Supported**: `<i> <b> <u>`, `<font color>` (hex and named), `{\anN}` alignment (Kodi 20+). **Ignored/stripped**: `<font face/size>` mostly, other ASS overrides, positioning coordinates.
- **Bidi**: libass is built with FriBiDi; logical Hebrew renders RTL. libass by default uses base direction from the text; Kodi's style has no forced RTL base, so lines starting with LTR chars/punctuation get LTR base direction (the root of the punctuation issue, §3).
- **"Unable to create subtitle parser"**: logged by `CDVDFactorySubtitle::CreateParser()` when no parser recognises the first lines of the file. Typical causes: file not decodable/garbage from wrong encoding detection, UTF-16 without BOM, empty/zero-byte file, first cue with unparseable timestamp (e.g. `0:01:02.5` or missing hours), HTML/other format with `.srt` extension, or a leading garbage line before the first timing. Fix = normalise the file (§4) to clean UTF-8-BOM SRT.
- Timestamps: Kodi's SubRip parser uses `sscanf("%d:%d:%d%*c%d --> ...")` style **[unverified]**; comma and dot both accepted, missing hours not.

---

## 3. Hebrew-specific problems and fixes

### 3.1 Punctuation on the wrong side
Cause: text stored in logical order, but the paragraph base direction is resolved from the first strong character. If a line starts with `-`, a digit, English, or ends with `.`/`?`/`!` which are neutral, neutrals at the paragraph edge take the base direction. In an RTL paragraph that is correct; the bug appears when (a) the renderer forces LTR base, or (b) the file was produced by "fixing" for an LTR-only player (punctuation moved to the start of the line in logical text, e.g. `.שלום`).

Fixes:
- Prefix each Hebrew line with **RLM (U+200F)**: gives the paragraph a strong RTL char at the start, so base direction becomes RTL and trailing `. , ? ! :` land on the left (visual end). Works in libass/FriBiDi. **Recommended.**
- **RLE…PDF (U+202B…U+202C)** embedding: works in FriBiDi too, but explicit embeddings are sometimes dropped/rendered as boxes by fonts lacking the glyphs and survive badly through tag conversion; also imbalanced pairs across split lines break. Avoid. (U+2067 RLI/PDI isolates are cleaner but older libass/FriBiDi builds may not support them **[unverified for Kodi 21's bundled FriBiDi]**.)
- Undo "pre-reversed" punctuation: if a Hebrew line *starts* with `[.,?!:]+` and does not end with punctuation, move it to the end.

### 3.2 Leading dialogue dashes
`- שלום` should show the dash on the right. With RLM prefix (`‏- שלום`) it does. Legacy files often have the dash at the end (`שלום -`) — move it to the front when a Hebrew line ends with ` -`/`-`.

### 3.3 Mixed numbers / English
Digits and Latin runs are LTR runs inside RTL; FriBiDi handles them if the base is RTL. Problem cases are neutrals between an LTR run and line end (`ראיתי את Star Wars.`): with base RTL the `.` goes to the far left, correct. Add RLM after a trailing LTR run before the final punctuation (`Wars‏.`) to be safe.

### 3.4 Legacy encodings
- **CP1255 (Windows-1255)**: logical order, Hebrew letters at `0xE0–0xFA` (א=0xE0 … ת=0xFA), niqqud `0xC0–0xD2`. The dominant legacy Israeli subtitle encoding.
- **ISO-8859-8**: same letter range `0xE0–0xFA`. Plain `iso-8859-8` historically means **visual** order (text stored reversed); `iso-8859-8-i` means logical. Most `.srt` "ISO-8859-8" files are actually logical CP1255-compatible. Visual-order detection: frequency of final-form letters (ך ם ן ף ץ = 0xEA 0xED 0xEF 0xF3 0xF5) appearing at the *start* of words instead of the end. If final forms are mostly word-initial → visual → reverse each line.
- Distinguishing CP1255 vs ISO-8859-8: bytes `0x80–0x9F` (quotes `0x93/0x94`, dash `0x96`, ellipsis `0x85`) are valid in CP1255 but control chars in ISO-8859-8 → prefer CP1255; `0xA4` is ₪ in CP1255 and ¤ in 8859-8.
- Heuristic score: `hebrew_ratio = count(0xE0..0xFA) / count(bytes >= 0x80)`; >0.6 plus space-separated word structure ⇒ Hebrew legacy.

---

## 4. Our plan: `resources/lib/subfix.py` (stdlib only)

Python 3.8+ (Kodi 21 ships 3.8+). Modules used: `codecs`, `re`, `difflib`, `dataclasses`, `os`, `unicodedata`.

### 4.1 Data model
```python
@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str            # logical order, '\n' line breaks, tags preserved (normalised)
    align: int | None = None   # 1..9 from {\anN}
```

### 4.2 API
```python
def detect_encoding(data: bytes) -> tuple[str, float]:
    """Return (codec_name, confidence). Order: BOM(utf-8-sig/utf-16/utf-32) -> strict utf-8
    -> score cp1255 vs iso-8859-8 vs latin-1; pick highest score. Never raises."""

def score_hebrew(text: str) -> float:
    """0..1: share of letters in U+05D0..U+05EA among all letters, penalising C1 controls,
    U+FFFD and implausible symbols."""

def is_visual_hebrew(text: str) -> bool:
    """True if final letters (ךםןףץ) are mostly word-initial."""

def decode_bytes(data: bytes) -> str:
    """detect_encoding + decode; reverses lines if is_visual_hebrew; strips BOM; normalises
    newlines to '\n'; NFC."""

def parse_timestamp(s: str) -> int | None:
    """Tolerant: '[H+:]MM:SS[,.:]f{1,3}', spaces allowed, hours unbounded (>99), fraction
    scaled by digit count ('5'->500, '05'->50). Returns ms or None."""

def parse_subtitles(text: str) -> list[Cue]:
    """Tolerant SRT + WebVTT: finds any line containing '-->'; ignores index lines
    (missing/duplicate/non-numeric), 'WEBVTT' header, NOTE/STYLE blocks, VTT cue settings;
    text runs until blank line or next timing line."""

def normalise_tags(text: str) -> tuple[str, int | None]:
    """Keep <i>,<b>,<u>,<font color="#RRGGBB">; lowercase tags; convert VTT <c.color>
    to <font>; drop other tags and {\\...} overrides except leading {\\anN} (returned).
    Auto-close unbalanced tags."""

def repair_cues(cues: list[Cue], min_ms: int = 300, gap_ms: int = 1) -> list[Cue]:
    """Clamp negative times to 0; drop empty text (after tag strip) and end<=start
    where no fix possible (0-length -> end=start+min_ms if next cue allows);
    sort by (start,end); merge exact duplicates (same text & overlapping times);
    fix overlaps: prev.end = next.start - gap_ms if texts differ and overlap < 50%
    of prev duration, else merge text with '\n'."""

def fix_hebrew_line(line: str) -> str:
    """For lines containing Hebrew: move leading [.,?!:;]+ to end; move trailing ' -' to
    front; prefix RLM U+200F (idempotent); insert RLM between trailing LTR run and final
    punctuation. Strip existing RLE/PDF/LRE/LRM pairs first. Tags are skipped over."""

def fix_hebrew(cues: list[Cue]) -> list[Cue]: ...

def format_timestamp(ms: int) -> str:
    """'HH:MM:SS,mmm', hours zero-padded to >=2 digits (no cap)."""

def write_srt(cues: list[Cue], path: str) -> None:
    """Renumber 1..N, prefix {\\anN} when align set, CRLF-free '\n', encode 'utf-8-sig'.
    Atomic: write path+'.tmp' then os.replace."""

def fix_file(src: str, dst: str | None = None, hebrew: bool = True) -> dict:
    """Full pipeline; returns stats {encoding, confidence, cues_in, cues_out,
    dropped, merged, overlaps_fixed, visual_reversed}."""

# --- autoload matcher ---
RELEASE_TAGS: re.Pattern  # 2160p|1080p|720p|480p|x26[45]|h\.?26[45]|hevc|web-?dl|webrip|
                          # bluray|brrip|hdtv|dvdrip|hdr|dv|aac|ac3|ddp?5\.1|atmos|
                          # proper|repack|internal|remux|10bit + trailing -GROUP, [..], (..)

def normalise_name(name: str) -> str:
    """Lowercase, drop extension and language suffix (.he/.heb/.hebrew), replace ._- with
    space, remove RELEASE_TAGS and trailing release group, collapse spaces."""

def parse_episode(name: str) -> tuple[int, int] | None:
    """S01E02, 1x02, s1.e2 -> (1, 2)."""

def match_score(video: str, sub: str) -> float:
    """0 if parse_episode differ (both present, or only one present); else
    difflib.SequenceMatcher(None, normalise_name(video), normalise_name(sub)).ratio()."""

def find_best_subtitle(video_path: str, candidates: list[str],
                       threshold: float = 0.6) -> str | None:
    """Exact basename match wins; then highest match_score >= threshold; Hebrew-tagged
    names get +0.05 tie-break."""
```

Encoding scoring (inside `detect_encoding`): for each of `cp1255`, `iso-8859-8`, `latin-1` decode with `errors="replace"`; score = `score_hebrew` (for Hebrew codecs) minus 0.5×(ratio of U+FFFD + C1 controls). `cp1255` wins ties over `iso-8859-8`; `latin-1` is chosen only if both Hebrew scores < 0.2.

### 4.3 Unit tests (`tests/test_subfix.py`, `unittest`)
Encoding
1. UTF-8 with BOM → `utf-8-sig`, BOM absent from output text.
2. UTF-8 without BOM, Hebrew → `utf-8`.
3. UTF-16 LE/BE with BOM.
4. CP1255 Hebrew with `0x96` dash and `0x85` ellipsis → `cp1255`.
5. ISO-8859-8 logical Hebrew (no 0x80–0x9F bytes) → decodes to same text as cp1255.
6. Visual-order Hebrew → lines reversed, final letters at word end.
7. Latin-1 French file → `latin-1`, not Hebrew.
8. UTF-8 with one invalid byte → falls to legacy path, no exception.
9. Empty bytes / whitespace only → `[]`, no exception.

Parsing
10. Missing hours `01:02,500`. 11. Dot separator `00:00:01.500`. 12. 1- and 2-digit ms (`,5`→500, `,05`→50, `,50`→500). 13. Extra spaces `00:00:01 , 500  -->   00:00:02,000`. 14. `>99h` `123:00:00,000` round-trips. 15. Missing index lines. 16. Duplicate/non-numeric index lines. 17. Multiple blank lines between cues and none at EOF. 18. Index line glued to previous text without blank line. 19. WebVTT with header, NOTE, cue settings, `MM:SS.mmm`. 20. CRLF and lone CR line endings. 21. 50k-cue file parses in < 2 s.

Repair
22. Unsorted cues get sorted. 23. Empty-text cue dropped; tags-only cue (`<i></i>`) dropped. 24. 0-length cue (`end==start`) extended to `min_ms` or dropped if no room. 25. `end < start` handled. 26. Negative start clamped to 0. 27. Overlap trimmed (prev.end = next.start − 1). 28. Heavy overlap with different text merged. 29. Exact duplicates merged into one.

Tags
30. `<I>` → `<i>`; unclosed `<i>` auto-closed. 31. `<font color=red>` kept; `<font face=...>` stripped. 32. `{\an8}` preserved as `align=8` and re-emitted; `{\pos(..)}` stripped.

Hebrew
33. `.שלום` → `‏שלום.`. 34. `שלום -` → `‏- שלום`. 35. `ראיתי 3 סרטים?` unchanged except RLM prefix. 36. English inside Hebrew line with trailing `.` gets RLM before `.`. 37. Existing RLE/PDF stripped. 38. Idempotence: `fix_hebrew(fix_hebrew(x)) == fix_hebrew(x)`. 39. Pure-English line untouched.

Output
40. Written file starts with `EF BB BF`, renumbered from 1, timestamps `HH:MM:SS,mmm`. 41. Round-trip parse(write(cues)) == cues.

Matcher
42. `Show.S01E02.1080p.WEB-DL.x264-GRP.mkv` vs `show.s01e02.heb.srt` → match. 43. Same show, `S01E03` sub → 0. 44. Movie vs sub with different release tags → ≥ threshold. 45. Unrelated title → None. 46. `1x02` vs `S01E02` equal. 47. Exact basename beats higher-ratio fuzzy.
