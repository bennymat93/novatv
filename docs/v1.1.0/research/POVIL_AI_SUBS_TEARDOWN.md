# POV-IL AI subtitles (MoranSubs, service.subtitles.kodipovilai 0.2.565) – teardown

Source: the POV-IL base build zip (`work/Kodi-POV-IL-FENtastic-test-0.1.178.zip`), extracted read-only to `work/povilai/`.
~95k lines of Python. Behaviour summary; no code reused.

## How it works
| Aspect | MoranSubs | BN (ours, v0.2.5) |
|---|---|---|
| Source of text | existing subtitles (Wizdom, Ktuvit, OpenSubtitles, community pool), **embedded text tracks extracted from the stream** (`embedded_extract.py`, throttled so the debrid provider does not 429 the player), English shown while Hebrew cooks | audio transcription (Whisper large-v3-turbo on the PC GPU); YouTube captions; All_Subs for human subs |
| Translation engine | Gemini (default `gemini-3.5-flash-lite`), per-model free-tier RPM gate (`_gemini_rate_gate`), Google "rescue" for failed blocks, gender-aware Hebrew (`arabic_gender.py`, cast context) | Gemini → mtrans (Google endpoints + MyMemory) → local NLLB |
| Chunking / context | chunks of cues with **previous-N-lines context** (`_build_prev_context_by_idx`), sub-chunk retries | 240 s audio chunks; previous 6 lines as context |
| Timing | keeps source timings exactly; repairs mistyped timestamps on every cache hit (`_reapply_rtl_fix_in_place`) | Whisper segment times |
| Hebrew post-processing | RTL punctuation fix applied on delivery, validation "mostly Hebrew" (`_is_mostly_hebrew`) | RLE (U+202B) prefix per line |
| Caching | local cache + **community pool** by source hash (Telegram) | server cache per job |
| Sync | `subsync.py`/`sync_align.py`: aligns subtitle to audio/embedded timing | none |
| UI | pyxbmct chooser window with flags, match %, colour by kind, stays open; progressive swap-in | BN subtitle window (select list), progress property |
| Errors / limits | 429 backoff per model, deadline per stage, abandon stale selection when the viewer switched | server retry on 404, error message |

## Improvements to port (ranked)
1. **Translate existing text instead of transcribing** when a non-Hebrew subtitle exists (embedded text track, All_Subs/online English) – faster and more accurate than speech-to-text. → server stage "text-source" (extract embedded text track with ffmpeg; YouTube captions already done).
2. **Keep source timings exactly** and validate the output (same cue count, mostly Hebrew) – already in mtrans batches; extend to Gemini path.
3. **Previous-lines context across chunks** for the LLM (we send 6 lines; make it configurable) and a **rate gate** for Gemini free tier.
4. **Hebrew punctuation fix** on delivery (RLM + move . , ? ! to the logical end) – `subfix.py`.
5. **Stale-selection guard** – a result is applied only if the viewer still has the same video and has not picked another subtitle (we have gen + SubsChosen).
6. **Chooser that stays open, colour-coded by kind, with match %** – picker v2 with sections and preview.
7. Community pool – not adopted (privacy, infrastructure).
