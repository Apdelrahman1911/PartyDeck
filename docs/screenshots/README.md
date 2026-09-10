# Screenshot review gallery

This collection preserves **837 original app and renderer captures**, including failed attempts, and links to **four existing asset proofs**. Click a collection, then any thumbnail to open the full PNG. Every record includes its original filename, scenario, platform, pixel dimensions and full SHA-256; [manifest.json](manifest.json) also records source locations, exact revisions where known, CI runs, receipts and duplicate-source aliases.

[Open the published first batch](first-batch/README.md) for the 125 initially published native, shared-UI and first desktop 2D views. The collection pages below add complete source records and original-filename mappings without duplicating those images.

Use the latest native and shared-UI collections for current review. Earlier captures and Godot iterations are retained below for comparison. A screenshot shows a particular state; the run and fixture limits remain part of its evidence.

| Current reviewed collection | Images | Evidence scope |
| --- | ---: | --- |
| [Android optimized, test signed — CI 34428798269](android-34428798269/optimized-test-signed/README.md) | 31 | Full exercised flow passes, including actual Rules → Practice → confirmed leave/Home at 100% and 200%. The normal Rules label fits, but its lower rounded border remains clipped; the after-play Next round label is also clipped. |
| [Android debug — CI 34428798269](android-34428798269/debug/README.md) | 31 | Full exercised flow and both Rules routes pass; 30 named stages plus final 200% Home are retained. Rules button borders fit; the initial normal Rules-entered result retains a clipped Next round label. |
| [iOS native baseline — CI 34428798269](ios-34428798269/README.md) | 8 | Three UI and three native transport tests pass on iPhone 17 simulator, runtime 26.4.1. Eight original attachment mappings are retained; text scale was not recorded. |
| [Compose shared UI — exact CI layout fixtures, 34428798269](compose-ci-34428798269/README.md) | 65 | 21 layout tests pass. All original pixels match the earlier reviewed fixtures; exact CI revision and fresh source records are preserved separately. These remain JVM fixtures. |

## Godot native host attempts

| Collection | Images | Evidence scope |
| --- | ---: | --- |
| [Godot Android host — CI 34430556814](godot-android-34430556814/README.md) | 8 | All four entries fail initialization before Ready or gameplay. Final originals show the chooser's closed-before-ready message; process logs retain the display-density error and a 3D/200% exit timeout. |
| [Godot Android host — CI 34427418175](godot-android-34427418175/README.md) | 8 | All four 2D/3D × 100%/200% cases fail at match entry. Native chooser and covered final host originals are retained; no rendered game or accepted gameplay intent is established. |
| [Godot iOS probe — CI 34428221586](godot-ios-probe-34428221586/README.md) | 2 | One cancellation before engine construction passes; four tests fail. The native host shows Closed or Failed, with zero draw/Ready/iterations. Original metrics and four supplemental source recordings are retained. |

## Godot gameplay through the real authority

| Collection | Images | Evidence scope |
| --- | ---: | --- |
| [Godot 2D and 3D — final ordered desktop CI 34430556814](godot-desktop-34430556814/README.md) | 22 | Exact clean CI source and ordered PCK `26bfbb72…`; equal 42-view traces and both exits 0. Pixels match the corrected local originals, including the Crown winner and named explanation. Native entries in this workflow fail separately. |
| [Godot 2D and 3D — final ordered packed gameplay](godot-matched-packed-ordered-20260910/README.md) | 22 | Final PCK `26bfbb72…` executes equal 42-view traces with both exits 0. Pixels match the corrected v5 originals; all new source PNGs and receipts are preserved separately. |
| [Godot 2D and 3D — final matched packed v5 gameplay](godot-matched-packed-v5-20260910/README.md) | 22 | Equal 42-view authority traces, real input and both exits 0 at 430 × 932. The final 3D winner now has the correct Crown emblem and complete challenge/burnout explanation. |
| [Godot 2D and 3D — older desktop CI 34427418175](godot-desktop-34427418175/README.md) | 22 | Exact CI source, equal 42-view traces and clean desktop exits. This older source still has the wrong Star winner emblem and missing final explanation in 3D; the native jobs in the same workflow fail. |
| [Godot 2D and 3D — matched packed seed-2 gameplay](godot-matched-packed-20260910/README.md) | 22 | Equal 42-snapshot authority traces, real input, both exits 0. Desktop 430 × 932. The 3D winner still has the wrong rank emblem and missing final explanation. |
| [Godot 2D — first complete seeded match](godot-first-real-2d-input/README.md) | 11 | Real Button/authority gameplay, privacy and captures retained. Shutdown logged a loopback-close error; clean engine exit is unqualified. Desktop 430 × 932; no 2D/3D parity or native execution claim. |

## Godot prototype iterations

These are actual Godot capture files, including explicitly labeled blank parse-error screens in 3D v9. Iteration 01 uses synthetic structural data; later 2D iterations mostly use frozen Kotlin-authority projections, with an explicitly synthetic lobby-permission input where labeled. Iterations 09–10 use the real six-seat authority input for lobby confirmation. The 3D v1–v10 captures use authority-derived static inputs and retain both failures and later corrections. Desktop emulated-touch traces are labeled separately from native input. Static checks do not establish authority-accepted gameplay or native mobile accessibility. Every original in these reviewed batches is retained.

| Collection | Images | Stage |
| --- | ---: | --- |
| [Godot 2D — iteration 10, final compact Reveal and confirmation checks](godot-2d-iteration-10/README.md) | 14 | Complete initial Reveal at 900 × 740; both confirmation choices visible at 200%; repeat emulated drag/tap/privacy checks pass. |
| [Godot 2D — iteration 09, corrected gestures and authority edge cases](godot-2d-iteration-09/README.md) | 26 | Nine static reports pass; one/zero-card, truthful rank/Wild, burnout and six-seat confirmation. Case-specific seeds and frozen fixture tools retained. |
| [Godot 2D — iteration 08, action-drag failures](godot-2d-iteration-08/README.md) | 3 | All three failed attempts retained; ancestor probe identifies the cover panel stopping drag propagation. |
| [Godot 2D — iteration 07, six-seat layout and emulated hand drag](godot-2d-iteration-07/README.md) | 14 | Corrected 1280 × 800 layout and successful emulated hand drag; 900 × 740 Reveal clipping and failed 200% action drag retained. |
| [Godot 2D — iteration 06, header-width correction](godot-2d-iteration-06/README.md) | 5 | Header fixed; Reveal still below the initial viewport and diagnostic hand drag fails. |
| [Godot 2D — iteration 05, proof reflow and edge states](godot-2d-iteration-05/README.md) | 12 | Proof labels, forced challenge, observer and winner; failed desktop header and incomplete gesture probe retained. |
| [Godot 2D — iteration 04, compact confirmation and edge fixtures](godot-2d-iteration-04/README.md) | 7 | 200% confirmation corrected; eliminated spectator and failed three-card proof wrapping preserved. |
| [Godot 2D — iteration 03, compact layouts and outcomes](godot-2d-iteration-03/README.md) | 29 | Reveal/selection visibility improved; round/winner/old-proof states retained. The 200% lobby confirmation fails initial-viewport visibility. |
| [Godot 2D — iteration 02, authority-derived fixtures](godot-2d-iteration-02/README.md) | 16 | Desktop, phone, 200% text and short landscape; static renderer checks passed with recorded layout issues. |
| [Godot 2D — iteration 01, desktop structural fixture](history/godot-2d-iteration-01/desktop/README.md) | 4 | Early desktop structural fixture; known selection indicator and scrolling issues. |
| [Godot 2D — iteration 01, phone and landscape history](history/godot-2d-iteration-01/README.md) | 9 | Original phone/landscape captures and the failed 200% input-reachability attempt. |
| [Godot 3D — v10, final compact input and confirmation checks](godot-3d-20260910-v10/README.md) | 21 | Three focused cases pass. Persistent actor/rank and Show/Hide, corrected focused-card containment and readable 200% confirmation; emulated drag/tap/privacy receipts retained. |
| [Godot 3D — v9, parse-error screens](history/godot-3d-20260910-v9/README.md) | 3 | All three runs fail before the game scene renders; original blank outputs, diagnostics and parse-error logs retained. |
| [Godot 3D — v8, 200% card-containment failure](history/godot-3d-20260910-v8/README.md) | 3 | Initial, selected and failure captures retained; the focused card is clipped by two pixels after fourth-choice feedback. |
| [Godot 3D — v7, persistent context and six-seat failure](history/godot-3d-20260910-v7/README.md) | 40 | Ten cases pass; one 200% six-name case fails. Corrected observer/forced-challenge copy and confirmation contrast, plus emulated drag receipts. |
| [Godot 3D — v6, authority edge cases and layout defects](history/godot-3d-20260910-v6/README.md) | 52 | Sixteen static/runtime reports pass; one/zero-card, truthful rank/Wild, burnout, three-card proof and observer/eliminated states. Visual context/copy/focus defects retained. |
| [Godot 3D — v1, Camera failure and broken portrait roster](history/godot-3d-20260910-v1/README.md) | 1 | Failed camera/roster attempt; one actual frame. |
| [Godot 3D — v2, Camera corrected; portrait layout still broken](history/godot-3d-20260910-v2/README.md) | 8 | Local input/privacy passed; portrait roster and Play placement fail visual review. |
| [Godot 3D — v3, Portrait roster and Play visibility corrected](history/godot-3d-20260910-v3/README.md) | 4 | Portrait roster/Play improved; captions and selected markers still need correction. |
| [Godot 3D — v4, captions improved; defects retained](history/godot-3d-20260910-v4/README.md) | 22 | Large-text markers/back control, narrow hit overlap and wrong winner emblem fail visual review. Six runtime receipts pass; portrait is report-only. |
| [Godot 3D — v5, corrected winner and larger controls](godot-3d-20260910-v5/README.md) | 17 | Crown/final explanation and target overlap corrected; compact scrolled context and focus-outline limits remain. Five retained runtime receipts pass. |

## Earlier reviewed captures

| Historical collection | Images | Reason retained |
| --- | ---: | --- |
| [Android optimized, test signed — CI 34421746656](android-34421746656/optimized-test-signed/README.md) | 27 | Earlier full exercised flow passed, including 200% Join/hand/Play reachability. Rules and Next round labels are clipped; the Rules Practice button was captured without a tap. |
| [Android debug — CI 34421746656](android-34421746656/debug/README.md) | 27 | Earlier full exercised flow passed; final 200% Home and paired UI dumps remain retained. |
| [iOS — CI 34398824935](ios-34398824935/README.md) | 8 | Earlier three UI tests passed; native qualification remains bounded to this run. |
| [Compose shared UI — reviewed local layout fixtures](compose-shared/README.md) | 65 | Original JVM fixture review; exact working-tree capture revision was not recorded. Identical later CI originals have their own source records above. |
| [Android optimized, test signed — CI 34417204089](android-34417204089/optimized-test-signed/README.md) | 27 | Earlier optimized variant completed the exercised smoke flow while the overall workflow failed in debug. |
| [Android debug — CI 34417204089](android-34417204089/debug/README.md) | 23 | Earlier debug stopped at 200% Join validation while the notification shade covered the app. |
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
- Native captures were screened against their reviewed capture guards and Android UI dumps. Live invitation and share surfaces were not captured; the host lobby images precede invitation opening or follow its dismissal. Infrastructure/SystemUI preparation images and app-bundle icons are excluded. Run 34417204089 debug/final-screen.png is excluded because it shows the notification shade. Four Godot CI 34427418175 preparation PNGs, one baseline CI 34428798269 preparation PNG and four Godot CI 34430556814 preparation PNGs show Launcher before app installation; all are excluded with source paths, hashes, dimensions and reasons in the manifest.
- Compose invitation/QR/Join captures contain explicitly labeled synthetic fixture values, including their separately preserved exact-CI originals. `ShellLayoutTest.syntheticInvitation()` uses the documentation-only endpoint `192.0.2.44:42424` and deterministic fixture credentials. These are not live admission material.
- Godot iteration 01 contains synthetic recipient-safe structural data. Later static captures use frozen Kotlin-authority projections plus the explicitly synthetic 2D lobby-permission fixture where labeled; 2D iterations 09–10 and the 3D six-seat cases use the real authority-derived lobby input. Truthful-rank, truthful-Wild and burnout edge fixtures use seed 1; the other edge inputs use seed 2. The first-2D and matched packed collections record actual authority-accepted desktop gameplay; the paired runs also verify equal 2D/3D traces and clean exits. Exact older CI and later dirty-tree local provenance remain distinct, even where pixels match. Original reports, diagnostics and available fixture/source provenance are retained. No LAN or admission credentials are involved.
- Godot native Android and iOS attempts retain host screens and failed outcomes without claiming rendered gameplay. First-attempt Android final images and UI dumps are sequential; the 2D/100% Closing/Opening mismatch is explicit. Second-attempt final images return to the chooser after initialization fails; the 3D/200% exit timeout remains recorded. The iOS attachment name Diagnostic rendering is preserved alongside its failed initialization metrics; attachment names and failure flags do not override the actual test result.
- Failed runtime stages, historical layout defects and missing native qualification are recorded in the relevant collection. No retained candidate required credential redaction or omission.

For accepted findings and remaining native limits, see [the shared UI design review](../design-review.md), [the Godot design review](../../godot/reviews/design-review.md), and [the Godot asset documentation](../../godot/renderer/assets/README.md).

Verify all retained originals, receipts and referenced asset proofs from the repository root:

```sh
sha256sum -c docs/screenshots/SHA256SUMS
```
