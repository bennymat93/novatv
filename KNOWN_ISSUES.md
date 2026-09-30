# Known issues – 1.4.0

Nothing here is hidden or faked. Each item says what was tried.

| # | Area | Issue | What was tried / why it stays |
|---|---|---|---|
| 1 | Name / icon | In a plain Kodi (installed by link), the device home screen still shows "Kodi". | The launcher name and icon belong to the Kodi app (fixed inside its APK / exe). Done instead: the BN splash, "BN Stream" shortcuts on Windows, and a one-time offer on Android to install the BN Stream app. |
| 2 | Israeli TV | Paid cable channels (HOT Cinema/Comedy/Zone/Drama/8, Sport 5 family, Yes, Disney/Junior/Luli/Hop/Nick Jr IL, Viva) are no longer listed. | The free playlists carry them only through restream servers (iptvhd.ru, freeott.top, mcquack.net). These are unlicensed copies, and most already answer 403. Owner rule: licensed sources only. Legal replacements don't exist without a HOT / Yes / Partner subscription. |
| 3 | Israeli TV | Keshet 12, Reshet 13, 24, Kan Educational and Knesset have no public direct stream (the broadcasters sign their URLs). | They play through Idan+ (the official players). The failover order is main feed, then Idan+'s backup feeds. If Idan+ breaks after a broadcaster changes its site, these channels wait for an Idan+ update. |
| 4 | EPG | No free guide exists for some channels: Hop, Luli, Junior, BabyFirst, Angel TV, Hala, Ma'an, Kabbalah (partly) and many world channels. | Checked sources: epgshare01 (used, 40 countries), open-epg (moved behind a login), iptv-org epg (needs a grabber per site; site scrapers break often). Coverage is listed per channel in reports/channels_report.md. |
| 5 | EPG | "English" guide language shows the guide's own language. | The free guides are published in one language per channel (Hebrew for Israel). Only a translation to Hebrew is generated (cached); translating Hebrew to English is not done. |
| 6 | World TV | Only a quick check (does it open within 12 s) for channels beyond the first 10 of each country. | Owner decision 30/09: a 60 s test × ~6,000 channels would take about 100 hours. Dead ones go to dead_streams.json and are filtered. |
| 7 | Subtitles | Auto-sync needs the subtitle server (the home PC, or Tailscale away from home). | It runs VAD + cross-correlation on the audio, which is too heavy for TV boxes. Without the server, manual sync (remembered per video) is still there. |
| 8 | Subtitles | Auto-sync handles .srt from All_Subs. ASS and embedded tracks are not re-timed. | Embedded tracks are timed by the release itself (same file), so they are in sync by definition. ASS files are rare in Hebrew sources. |
| 9 | Device profiles | No portrait mode on phones. | Kodi renders landscape only. |
| 10 | Weak network | Packet loss is simulated as connection drops, not real per-packet loss. | Real loss needs a driver (clumsy, admin rights). Owner decision: local proxy only. |
