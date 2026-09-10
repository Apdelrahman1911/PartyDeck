# Screenshot review gallery

This collection preserves **325 original app and renderer captures** and links to **four existing asset proofs**. Click a collection, then any thumbnail to open the full PNG. Every record includes its original filename, scenario, platform, pixel dimensions and full SHA-256; [manifest.json](manifest.json) also records source locations, exact revisions where known, CI runs, receipts and duplicate-source aliases.

[Open the published first batch](first-batch/README.md) for the 125 initially published native, shared-UI and first desktop 2D views. The collection pages below add complete source records and original-filename mappings without duplicating those images.

Use the latest native and shared-UI collections for current review. Earlier captures and Godot iterations are retained below for comparison. A screenshot shows a particular state; the run and fixture limits remain part of its evidence.

| Current reviewed collection | Images | Evidence scope |
| --- | ---: | --- |
| [Android optimized, test signed — CI 34417204089](android-34417204089/optimized-test-signed/README.md) | 27 | Latest optimized variant passed the full exercised smoke flow, including 200% Join/hand/Play reachability. |
| [Android debug — CI 34417204089](android-34417204089/debug/README.md) | 23 | Latest debug variant stopped at 200% Join validation while the notification shade covered the app. |
| [iOS — CI 34398824935](ios-34398824935/README.md) | 8 | 3 UI tests passed; native qualification remains bounded to this run. |
| [Compose shared UI — reviewed layout fixtures](compose-shared/README.md) | 65 | JVM layout fixtures; exact working-tree capture revision not recorded. |

## Godot gameplay through the real authority

| Collection | Images | Evidence scope |
| --- | ---: | --- |
| [Godot 2D and 3D — matched packed seed-2 gameplay](godot-matched-packed-20260910/README.md) | 22 | Equal 42-snapshot authority traces, real input, both exits 0. Desktop 430 × 932. The 3D winner still has the wrong rank emblem and missing final explanation. |
| [Godot 2D — first complete seeded match](godot-first-real-2d-input/README.md) | 11 | Real Button/authority gameplay, privacy and captures retained. Shutdown logged a loopback-close error; clean engine exit is unqualified. Desktop 430 × 932; no 2D/3D parity or native execution claim. |

## Godot prototype iterations

These are actual Godot-rendered images. Iteration 01 uses synthetic structural data; iterations 02–03 mostly use frozen Kotlin-authority projections, with an explicitly synthetic lobby-permission fixture in iteration 03. The 3D v1–v4 captures use authority-derived static data and retain their camera, layout and winner-display failures. Static checks do not establish authority-accepted gameplay or native mobile accessibility. Every original in these reviewed batches is retained.

| Collection | Images | Stage |
| --- | ---: | --- |
| [Godot 2D — iteration 03, compact layouts and outcomes](godot-2d-iteration-03/README.md) | 29 | Reveal/selection visibility improved; round/winner/old-proof states retained. The 200% lobby confirmation fails initial-viewport visibility. |
| [Godot 2D — iteration 02, authority-derived fixtures](godot-2d-iteration-02/README.md) | 16 | Desktop, phone, 200% text and short landscape; static renderer checks passed with recorded layout issues. |
| [Godot 2D — iteration 01, desktop structural fixture](history/godot-2d-iteration-01/desktop/README.md) | 4 | Early desktop structural fixture; known selection indicator and scrolling issues. |
| [Godot 2D — iteration 01, phone and landscape history](history/godot-2d-iteration-01/README.md) | 9 | Original phone/landscape captures and the failed 200% input-reachability attempt. |
| [Godot 3D — v1, Camera failure and broken portrait roster](history/godot-3d-20260910-v1/README.md) | 1 | Failed camera/roster attempt; one actual frame. |
| [Godot 3D — v2, Camera corrected; portrait layout still broken](history/godot-3d-20260910-v2/README.md) | 8 | Local input/privacy passed; portrait roster and Play placement fail visual review. |
| [Godot 3D — v3, Portrait roster and Play visibility corrected](history/godot-3d-20260910-v3/README.md) | 4 | Portrait roster/Play improved; captions and selected markers still need correction. |
| [Godot 3D — v4, captions improved; defects retained](history/godot-3d-20260910-v4/README.md) | 22 | Large-text markers/back control, narrow hit overlap and wrong winner emblem fail visual review. Six runtime receipts pass; portrait is report-only. |

## Earlier reviewed captures

| Historical collection | Images | Reason retained |
| --- | ---: | --- |
| [Android debug — CI 34413839964](android-34413839964/debug/README.md) | 24 | Earlier API 35 run, failed at 200% Join invitation focus; original failure frames retained. |
| [Android optimized, test signed — CI 34413839964](android-34413839964/optimized-test-signed/README.md) | 24 | Earlier API 35 run, failed at 200% Join invitation focus; original failure frames retained. |
| [Earlier Android optimized review — c73a659](history/android-c73a659/README.md) | 21 | Earlier API 36 run; incomplete large-text Join flow and final-rule coverage. |
| [Earlier Compose review — first render](history/compose-first-review/README.md) | 7 | First-render comparisons, including the original layout defects. |

## Asset proofs

These link to repository-owned originals rather than creating duplicate copies. They qualify artwork or imports, not complete app scenes.

| Original proof | Source and hash |
| --- | --- |
| <a href="../../assets/previews/asset_sheet.png"><img src="../../assets/previews/asset_sheet.png" alt="Shared artwork contact sheet" width="240"></a> | **[Shared artwork contact sheet](../../assets/previews/asset_sheet.png)**<br>Asset overview, not an app screenshot.<br>1440 × 1320 px<br>SHA-256: <code>18bee9ed19707fb5d411259a149a1f36fe78ac2af98f2bcd4b7063a9cacc5929</code><br>Last path commit: <code>7a4f8b80597472ac1fb2aac498c7db3a5dda7dfe</code> |
| <a href="../../assets/previews/launcher_masks.png"><img src="../../assets/previews/launcher_masks.png" alt="Launcher mask proof" width="240"></a> | **[Launcher mask proof](../../assets/previews/launcher_masks.png)**<br>Launcher icon masking proof, not a device screenshot.<br>1440 × 620 px<br>SHA-256: <code>9a865cc8564cd113a6dc55a9632875b4b03d21daee6154045e97b47aa91cf4b8</code><br>Last path commit: <code>7a4f8b80597472ac1fb2aac498c7db3a5dda7dfe</code> |
| <a href="../../godot/renderer/assets/proofs/cards.png"><img src="../../godot/renderer/assets/proofs/cards.png" alt="Godot card asset proof" width="240"></a> | **[Godot card asset proof](../../godot/renderer/assets/proofs/cards.png)**<br>Card art at review sizes; asset proof, not a rendered app scene.<br>1440 × 960 px<br>SHA-256: <code>49f489aee1319a3d77d2444b75c59da371980da3827c64746ca0dbb8bd2d39a6</code><br>Last path commit: <code>83943390a78a075c77a71695c7cf7e59349474ee</code> |
| <a href="../../godot/renderer/assets/proofs/godot_rank_imports.png"><img src="../../godot/renderer/assets/proofs/godot_rank_imports.png" alt="Godot imported-rank proof" width="240"></a> | **[Godot imported-rank proof](../../godot/renderer/assets/proofs/godot_rank_imports.png)**<br>Actual Godot-imported SVG rasters composed onto paper; asset import proof, not a rendered app scene.<br>1152 × 360 px<br>SHA-256: <code>ebc84812671781de4dab325670bd22b7f21daf5b0c19a25a0301779f1cac9690</code><br>Last path commit: <code>80abb1a2cb7c653a31f50fe9ec4440413c7badae</code> |

The [Godot import report](../../godot/renderer/assets/proofs/import_verification.json) covers 47 loaded resources and 24 SVG comparisons. It was generated with `godot/tools/prepare_assets.py --check --godot /opt/partydeck-godot/godot` using Godot `4.7.2.stable.official.ed1daf0bf` (binary SHA-256 `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`). Report SHA-256: `2b4016138bc1e57e74e34fa1320ff9830d5ee89f89da6f14cff85c81eb86f786`.

## Provenance and capture safety

- Original PNG bytes are preserved. Original capture filenames are retained in each record; the first-batch iOS gallery uses readable repository filenames mapped back to the original UUID filenames. Inline thumbnails display the same files at a smaller width; no image is redrawn, redacted or recompressed. Distinct scenario records remain separate even when their image bytes match.
- Native captures were screened against their reviewed capture guards and Android UI dumps. Live invitation and share surfaces were not captured; the host lobby images precede invitation opening or follow its dismissal. Infrastructure/SystemUI preparation images and app-bundle icons are excluded. Run 34417204089 debug/final-screen.png is also excluded because it shows the notification shade; its source/hash/reason are recorded in the manifest.
- Four Compose invitation/QR/Join captures contain explicitly labeled synthetic fixture values. `ShellLayoutTest.syntheticInvitation()` uses the documentation-only endpoint `192.0.2.44:42424` and deterministic fixture credentials. These are not live admission material.
- Godot iteration 01 contains synthetic recipient-safe structural data. Later static captures use frozen Kotlin-authority projections plus the explicitly synthetic 2D lobby-permission fixture. The first-2D and matched packed collections record actual authority-accepted desktop gameplay; only the latter verifies matching 2D/3D traces and clean exits. Original reports, diagnostics and available fixture/source provenance are retained. No LAN or admission credentials are involved.
- Failed runtime stages, historical layout defects and missing native qualification are recorded in the relevant collection. No retained candidate required credential redaction or omission.

For accepted findings and remaining native limits, see [the shared UI design review](../design-review.md), [the Godot design review](../../godot/reviews/design-review.md), and [the Godot asset documentation](../../godot/renderer/assets/README.md).

Verify all retained originals, receipts and referenced asset proofs from the repository root:

```sh
sha256sum -c docs/screenshots/SHA256SUMS
```
