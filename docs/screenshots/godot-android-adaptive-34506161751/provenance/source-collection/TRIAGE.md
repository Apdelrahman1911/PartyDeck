Run **34506161751**, attempt **1**, concluded **failure** at exact head `d06f83aa8f6905be515faf0f58690634714e5a2d`.

The 96 planned adaptive scopes contain **15 passed, 1 failed, 8 unsupported, 72 not-reached**. 4 installations passed.

| Consumer | Overall result | Named checks reached | First reported failure |
| --- | --- | --- | --- |
| debug / 1.0x | failed | 2d-landscape.held-rotation: unsupported; 2d-landscape.initial-landscape: passed | 2d-landscape.held-rotation: Expected visible 'game-play' within 45 seconds: Command '['adb', '-s', 'emulator-5554', 'shell', 'uiautomator', 'dump', '/sdcard/partydeck-ci-godot-session-ui.xml']' timed out after 0.6041529009999067 seconds |
| debug / 2.0x | failed | 2d-landscape.held-rotation: failed; 2d-landscape.initial-landscape: passed | Input ended before the concealed return was observed. |
| optimized-test-signed / 1.0x | failed | 2d-landscape.held-rotation: unsupported; 2d-landscape.initial-landscape: passed | 2d-landscape.held-rotation: Expected visible 'game-play' within 45 seconds: Command '['adb', '-s', 'emulator-5554', 'shell', 'uiautomator', 'dump', '/sdcard/partydeck-ci-godot-session-ui.xml']' timed out after 0.39980641300007846 seconds |
| optimized-test-signed / 2.0x | unsupported | 2d-landscape.held-rotation: unsupported; 2d-landscape.initial-landscape: passed; 2d-landscape.native-leave-home: passed; 2d-landscape.portrait-reentry-standard: passed; 2d-seascape.held-rotation: unsupported; 2d-seascape.initial-landscape: passed; 2d-seascape.native-leave-home: passed; 2d-seascape.portrait-reentry-standard: passed; 2d-split.support: unsupported; 3d-landscape.held-rotation: unsupported; 3d-landscape.initial-landscape: passed; 3d-landscape.native-leave-home: passed; 3d-landscape.portrait-reentry-standard: passed; 3d-seascape.held-rotation: unsupported; 3d-seascape.initial-landscape: passed; 3d-seascape.native-leave-home: passed; 3d-seascape.portrait-reentry-standard: passed; 3d-split.support: unsupported | None recorded |

The audit records every reached and unreached 2D/3D scope separately.

An unsupported held-rotation check can be followed by a recovery failure while the stage name still says held-rotation. The named check and overall result are retained separately. Recorded MP4 validation establishes media structure/decoding only; startup-unavailable originals stay unavailable, and no recording establishes concealment timing or pixel privacy without its separate review.

Independent verification covered **6 original ZIPs**, **5 original job logs**, **4,436 extracted files**, **444 raw process receipts**, **444 state JSON records**, **125 PNG/XML pairs** and **7 retained original MP4s**. Same-run producer inputs, installed APK bytes, all eight reviewed checker pins, producer/wrapper pins and exact source/parser bindings were checked.

The single complete source archive is retained by game_domain and verified by reference in source-reuse.json. Historical gallery members may remain solely inside that retained archive; the source owner records the extraction inventory. Verified identical extracted APK copies use hardlinks while all original paths, content bytes and ZIPs remain preserved.

This adaptive workflow does not execute engine gameplay assertions. Production run 34506173394 owns that separate runtime scope. No new Android/device/build execution or visual review was performed by this collector.

[Originals audit](triage/originals-audit.json), [raw process audit](triage/raw-process-audit.json), [first errors](triage/first-failures.json), [source reuse](source-reuse.json), [storage receipt](triage/apk-storage-deduplication.json), and [publication mapping](triage/capture-publication-inventory.json) retain exact paths and hashes.
