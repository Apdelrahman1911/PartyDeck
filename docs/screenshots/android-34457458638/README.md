# Android API 36 — ordinary app smoke, CI 34457458638

[All screenshot collections](../README.md)

Both APKs pass the exercised ordinary app flow on the same emulator boot at 100% and 200% text. All **62 original app PNGs** are preserved: 30 named route captures and one final Home diagnostic per APK. The final diagnostics are captured at **200% text before environment restoration**.

- [Debug: 31 originals](debug/README.md), 86 steps and 65 native inputs.
- [Optimized, test signed: 31 originals](optimized-test-signed/README.md), 86 steps and 63 native inputs.
- [Original runtime outcomes](runtime-variants.json), [display/API receipt](display-configuration.json), [preparation receipt](preparation/preparation-result.json) and [owner’s final review](provenance/final-receipt.json).
- [Later gallery visual review](review/partydeck-gallery-1584-visual-review-34457458638.json), [source/archive audit](../android-34456441354/review/partydeck-gallery-1584-source-audit.json) and [exact smoke harness](source/scripts/smoke-android-ui.py).

Exact revision: `f11f92ed4ec4f91630396bf493ba2fd984f07bb9`. Display: 720 × 1600 pixels at 280 dpi. Package identity is receipt-based: the full 474 MB package artifact was not downloaded. The optimized executed-input and signing receipts agree. The archive digest matches published GitHub metadata, and all 413 extracted members byte-match the report ZIP. Copies of original runtime evidence, provenance, pinned sources and all 38 JUnit XML files remain linked through the main manifest; report ZIPs and APK binaries remain outside this gallery.

Both dedicated Rules Practice actions have complete labels and borders. Intermediate Rules, enlarged-hand and public-result checkpoints can clip at the viewport edge. The enlarged Play phase establishes reachability without submitting a play; neither APK records a native Next round tap. Earlier played-card observations and later autonomous public-result images remain separate evidence.

Preparation passes on its first attempt with the app absent and without a reboot. The pre-install Launcher PNG is excluded with its original source, dimensions, hash and reason in the manifest. Live invitation, QR and Sharesheet surfaces were intentionally omitted by the harness. Both runs have `godotSessionSmoke.requested=false`; this collection does not change any Godot qualification result. Physical-device, screen-reader, mixed-device LAN, camera-frame and store qualification remain outside this evidence.

The owner’s earlier identity/dimension-only scope is preserved. The later gallery review inspected all 62 app originals in 21 internal sheets. The successful run’s resource configuration does not establish a uniquely isolated cause for earlier failures.

[Later Next round input reconciliation](../android-34456441354/review/partydeck-gallery-1584-next-round-reconciliation.json).
