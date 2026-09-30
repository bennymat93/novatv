# PLAN – v1.4.0 (UI overhaul, live TV/radio reliability, device profiles, full QA)

Source of truth for the version: `addons/plugin.video.nova/addon.xml` (release.py writes it). Skin = FENtastic, patched at
build time by `tools/make_build.py` from `brand/skin/*`. Order: 1.3.0 repository live first (tests), then this plan, then
the full test suite, then APKs + Windows installer as 1.4.0.

Owner decisions (30/09): Phase 3 = Israeli TV + Israeli radio + top ~10 channels per country in depth (60 s, fallbacks,
EPG translated to Hebrew); every other channel a quick 5 s check, dead ones removed, missing EPG -> KNOWN_ISSUES.
Phase 6 = local throttling proxy (bandwidth, latency, jitter, drops), no admin tools.

| # | Task | Files | Status |
|---|---|---|---|
| 1.1 | Menu item panels, dark gap, no overlap | make_build `home_panels` | done in 1.3.0 (re-verify all profiles) |
| 1.2 | Row panels incl. title, dark gap | make_build `home_panels` (grouplist itemgap -120) | done in 1.3.0 (re-verify on scroll/focus zoom) |
| 1.3 | Radio posters in the Israeli-channel style | tools/make_channel_art.py -> media/radio, radio.py | |
| 1.4 | "ערוצי ישראל" -> "ערוצים ישראליים"; only widget titles gold | strings.po, default.py, make_build HOME_WIDGETS, Includes_BNWidgets | |
| 1.5 | Channel count badge on country tiles; live totals `סרטים - 999` | Includes_BNWidgets, iptv.countries_list, status.py | |
| 1.6 | Version next to the logo; date `30.09.26, יום רביעי` next to clock | Home.xml patch (make_build), Variables_BN, service window props | |
| 1.7 | Bottom news + weather ticker (refresh between cycles, toggle) | new resources/lib/ticker.py, service.py, skin include, settings.xml | |
| 2 | Menu architecture research + one-level structure | docs/DECISIONS.md, make_build MENU | |
| 2.1 | "עזרה": guide HE/EN, troubleshooting table, search, About | new resources/lib/helpcenter.py, resources/help/*.json, MENU | |
| 2.2 | System Update icon between Settings and Search; backup + rollback; auto-fix | Home.xml patch, sysupdate.py | |
| 3 | Stream checker, fallbacks, EPG mapping + Hebrew translation, report | tools/stream_check.py, iptv.py, epg.py, reports/channels_report.md | |
| 4 | Subtitle sync: root cause, fps drift, per-video offset, audio auto-sync | server/nova_subs.py (/align), subfix/syncmath, service.py | started in 1.3.0 |
| 5 | First-run device wizard + 6 profiles | new resources/lib/profiles.py, docs/DEVICE_PROFILES.md | |
| 6 | Weak connection: cache per profile, adaptive, failover; throttled tests | profiles.py, advancedsettings, tools/netsim.py | |
| 7 | One-command test suite: static, streams/EPG, subtitles, UI shots, update flow, perf | tools/test_suite.py (+ new checks), reports/test_results.md | |
| D | CHANGELOG, KNOWN_ISSUES, release 1.4.0 (APK + Windows) | | |
