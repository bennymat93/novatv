# Device profiles (1.4.0)

Chosen on the first start after installation (wizard), changeable in BN > Device type; applied at once through Kodi's
own settings (`resources/lib/profiles.py`, `plan()`), no restart. Values below are what `plan()` sets.

| Setting | TV / box + remote | Desktop / laptop | Touch screen | Car screen | Smartphone | Tablet |
|---|---|---|---|---|---|---|
| Skin zoom (`lookandfeel.skinzoom`) | 0 | 0 | 0 | 0 | 0 | 0 |
| Skin touch mode (on-screen Back, drag scrolling) | off | off | on | on | on | on |
| Mouse / pointer (`input.enablemouse`) | off | on | on | on | on | on |
| Screensaver | dim, 10 min | dim, 10 min | dim, 15 min | **never** | dim, 5 min | dim, 10 min |
| Dim on pause | yes | yes | yes | no | yes | yes |
| Refresh-rate switching (`videoplayer.adjustrefreshrate`) | on start/stop | off | off | off | off | off |
| Video cache (`filecache.memorysize`) | RAM/5/3, 64–512 MB | same | same | RAM/4/3 | RAM/4/3 | RAM/5/3 |
| Read-ahead (`filecache.readfactor`) | 4x | 4x | 4x | 10x | 10x | 5x |
| Buffer mode (`filecache.buffermode`) | all network files | same | same | same | same | same |
| Hardware decoding | MediaCodec (Android) / DXVA2 (Windows) | same | same | same | same | same |

## Why
- **TV / remote:** 10-foot UI as designed (zoom 0), D-pad focus navigation (FENtastic default), no pointer
  (a stray mouse pointer steals focus). Refresh-rate switching gives judder-free 23.976/25/50 fps on TVs; it is off
  elsewhere because laptop panels and phones cannot switch, and some car head units blank the screen for seconds.
- **Desktop / laptop:** mouse on, keyboard shortcuts (Help > Remote, keyboard and touch), same 10-foot layout.
- **Touch / phone / tablet:** FENtastic's touch mode (on-screen Back button in every window, drag scrolling). The rows are
  already large (a menu row is 95 px of 1080 = 9 % of the screen height, above the 44–48 dp guidance). Skin zoom was
  tested and dropped: Kodi's zoom scales from the centre and cuts the clock and logo off even at +4 % (1.4.2 tests).
- **Car:** never sleeps, no dimming, the deepest read-ahead (tunnels, cell hand-overs).
  Driving-safe use relies on the head unit's own lock-out; the BN home keeps TV & Radio one step from the start.
- **Cache:** Kodi holds about 3x `memorysize` in RAM, so a fifth of RAM / 3 keeps the video cache far from low-memory
  kills on 1–2 GB boxes. Values snap to Kodi's own list of sizes.

## Not possible from an add-on (documented in KNOWN_ISSUES.md)
- Portrait orientation: Kodi renders landscape only.
- GUI resolution / overscan: device specific; set in Settings > Display (Help > Troubleshooting explains it).
