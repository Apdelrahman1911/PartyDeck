# iOS focused production diagnostic stills — CI 34550903117

This batch preserves **two original PNG attachments** with separate 2D/3D case identities and export timestamps. Pixel review by **/root/pixel_d1_land** records **one direct view, one reviewed byte match and zero unviewed images**.

Source revision: `ac2200aed8d170e55009257a9ab5b48ef0b02081`. Both production tests failed at the initial Home observation decode with `category=data_corrupted, path=$, bytes=512`. No observation JSON or body-scroll attachment was retained. The diagnostic identifies the reported category, location and byte count; its implementation cause remains unestablished.

The reviewer observed Home, readable actions and the source-identified qualification Q badge, with no clipping or overlap in these pixels. These stills do not establish successful Practice entry, gameplay, body scrolling, control reachability or continuous privacy. The two recordings remain archive-only and unviewed.

[Capture manifest](manifest.json) · [Attributed pixel review](provenance/review/review.json) · [Collector handoff](provenance/collector/final-evidence-handoff-v1.json)

## 2D production failure — Home

<a href="godot-session/attachments/E1016319-35B8-4FA1-A9D7-770A73A5AFA2.png"><img src="godot-session/attachments/E1016319-35B8-4FA1-A9D7-770A73A5AFA2.png" width="240" alt="2D production failure — Home"></a>

**Direct view** · /root/pixel_d1_land · 1206 × 2622 · 298,227 bytes.

Original: `E1016319-35B8-4FA1-A9D7-770A73A5AFA2.png`; SHA-256 `440efa98eaaead8f980601c6a6bba66e2497ef3f33a9e3079853b726b3894a9c`.

Test: `PartyDeckGodotSessionUITests/testProduction2DPracticeSession()`. Export timestamp: `1789091843.398`. The original `isAssociatedWithFailure=false` export flag is preserved; the failed case outcome is bound separately.

[Attributed observation and diagnostic limits](provenance/review/review.json).

## 3D production failure — Home

<a href="godot-session/attachments/07493D56-3236-421F-B007-0E8512019F5B.png"><img src="godot-session/attachments/07493D56-3236-421F-B007-0E8512019F5B.png" width="240" alt="3D production failure — Home"></a>

**Reviewed byte match** · /root/pixel_d1_land · 1206 × 2622 · 298,227 bytes.

Original: `07493D56-3236-421F-B007-0E8512019F5B.png`; SHA-256 `440efa98eaaead8f980601c6a6bba66e2497ef3f33a9e3079853b726b3894a9c`.

Test: `PartyDeckGodotSessionUITests/testProduction3DPracticeSession()`. Export timestamp: `1789091853.799`. The original `isAssociatedWithFailure=false` export flag is preserved; the failed case outcome is bound separately.

Exact bytes match the [directly viewed 2D attachment](godot-session/attachments/E1016319-35B8-4FA1-A9D7-770A73A5AFA2.png); this retains its own 3D case identity and timestamp.

[Attributed observation and diagnostic limits](provenance/review/review.json).
