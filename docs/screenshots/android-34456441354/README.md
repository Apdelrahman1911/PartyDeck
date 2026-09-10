# Android API 35 — ordinary app smoke, CI 34456441354

[All screenshot collections](../README.md)

Both APKs pass the exercised ordinary app flow on the same emulator boot at 100% and 200% text. All **62 original app PNGs** are preserved: 30 named route captures and one final Home diagnostic per APK. The final diagnostics are captured at **200% text before environment restoration**.

- [Debug: 31 originals](debug/README.md), 87 steps and 67 native inputs.
- [Optimized, test signed: 31 originals](optimized-test-signed/README.md), 86 steps and 64 native inputs.
- [Original runtime outcomes](runtime-variants.json), [display/API receipt](display-configuration.json), [preparation receipt](preparation/preparation-result.json) and [owner’s final review](provenance/review/final-native-review-receipt.json).
- [Later gallery visual review](review/partydeck-gallery-1584-visual-review-34456441354.json), [source/archive audit](review/partydeck-gallery-1584-source-audit.json) and [exact smoke harness](source/scripts/smoke-android-ui.py).

Exact revision: `dad1c11741bd4322bb8b2afb9f18f3db5f50c919`. Display: 720 × 1600 pixels at 280 dpi. Both downloaded APK byte hashes match the executed-input receipts; the original package audit is retained. The archive digest matches published GitHub metadata, and all 413 extracted members byte-match the report ZIP. Copies of original runtime evidence, provenance, pinned sources and all 38 JUnit XML files remain linked through the main manifest; report ZIPs and APK binaries remain outside this gallery.

Both dedicated Rules Practice actions have complete labels and borders. Intermediate Rules, enlarged-hand and public-result checkpoints can clip at the viewport edge. The enlarged Play phase establishes reachability without submitting a play; debug records one native Next round tap during 200% practice setup, while optimized records none. Earlier played-card observations and later autonomous public-result images remain separate evidence.

Preparation passes on its first attempt with the app absent and without a reboot. The pre-install Launcher PNG is excluded with its original source, dimensions, hash and reason in the manifest. Live invitation, QR and Sharesheet surfaces were intentionally omitted by the harness. Both runs have `godotSessionSmoke.requested=false`; this collection does not change any Godot qualification result. Physical-device, screen-reader, mixed-device LAN, camera-frame and store qualification remain outside this evidence.

The original owner visually reviewed the 60 named route originals in ten paired sheets. This later gallery review inspected two final diagnostics and two overlapping after-play originals, covering all 62 in combination.

[Later Next round input reconciliation](review/partydeck-gallery-1584-next-round-reconciliation.json).
