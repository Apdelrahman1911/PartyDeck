**Independent final preservation review passes within the requested scope. No unresolved preservation finding remains.**

Reviewer: `/root/package_inclusion`, 2026-09-11. Run `34554200601`, attempt `1`, head `253e9656a360a4411cab858484e1bd3dc2093a46`, native job `103123585125`.

The preserved native outcome is **3D passed; 2D failed at “Observe fresh, current production renderer diagnostics.”; the combined gate failed**. The completed run and native job both concluded `failure`. This review adds no native execution or acceptance.

The three supplied final pins match:

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `FROZEN.json` | 70,886 | `aad308fc0c7f812569bbabfc5608039b05957bbb681b2c063ff605e10f06e50c` |
| `final-evidence-handoff-v1.json` | 41,531 | `0bc0d62382d6418cbff1dd7d3b1f5001ebe8a9e4d95647f9be9280b3109c6bb0` |
| `final-preservation-audit-v1.json` | 166,226 | `90547f1ffc2ad5352e2f026d7b8149b581e4c325ce84acd8bf9fd5d14683ab90` |

All 264 metadata files match their size/hash pins and are mode `0444`. The canonical metadata tree contains exactly those files plus `FROZEN.json`; the separately frozen source subtree was excluded from traversal. All nine canonical aliases have their recorded targets and resolve successfully. The freeze record is read-only. Inputs checked directly remained stable through the review.

All 148 selected working originals, totaling 15,284,316 bytes, match their original member receipts and current byte/hash pins. Both owned job logs, totaling 3,302,001 bytes, match their collection receipts and final API job identity/conclusion. The five completed audit/configuration reports match their pins. Independently enumerating their local references reproduces exactly the 294 recorded referents: 141 checked directly by bytes/hash, 152 reconciled to the approved source receipts, and one ZIP reference reconciled to the verified archive receipts. Direct hashing covered 421 distinct inode contents, totaling 22,864,542 bytes; duplicate aliases reused the same digest.

The three complete original ZIPs exist at their recorded physical paths, are mode `0444`, and have the expected combined size of 254,343,350 bytes. Saved download API objects equal the final original artifact API objects, including IDs, names, sizes, run/head and digests. Those digests and sizes agree with the pinned integrity and final preservation receipts. All 1,655 member entries retain valid size/hash/CRC records, and the selected-original sets reconcile exactly. **Full ZIP hashes and member-stream CRC verification reuse the pinned completed receipts; this review did not open, rehash or extract a ZIP.**

The native archive inventory accounts for 1,492 original XCResult files (169,087,179 bytes), the app tarball, one recording, 12 linker maps and the engine symbol dump as archive-only originals. Required exported summaries, result receipts, logs, attachment metadata and selected files remain locally available. Every exported attachment has an original inventory referent; the original gate's attachment hash list matches the exported set plus its manifest.

The pinned final API metadata, retained dispatch and all four jobs agree on run/head/attempt and the focused production selection. Collection completed with exit code `0`, three expected artifacts, two owned logs, no missing expected artifacts, no collection errors and no preserved partial transfers. The collector, decoder and source pins remain those approved in the earlier preparation review. That review's preparation-only scope remains separate from the completed collector/native evidence.

Source preservation reuses the independently approved preparation receipt at `/tmp/partydeck-ios-rerun-preparation-review-34554200601-v1-x3jjt5hg/REVIEW.md` (SHA-256 `47cd86369309c1bd1f76644e3daed8002701cfcb49fedf0f41d16e246ceb347d`). Its exact source-freeze and binding pins still match. The 152 source referents reconcile to both source inventories, within the approved 223-file subset containing 222 donor hardlinks and one changed Swift blob. No source payload or donor hardlink was read, statted, traversed or modified during this review.

The current producer PCK hash `541ded4c5074b56a9e320882a23f357ff8162520fac099e32567ac3a678f2751` matches the approved source expectation, original producer receipt, staged native inputs and recorded packaged app PCK. All 132 renderer inputs, four tools and nine native module source references reconcile to the approved source pins. The source/producer/native binding points to the exact final package and outcome reports. The nested app receipt reconciles its archive-member hash, executable, plist, nine resources and qualification activation to the preserved original link/input receipts. The recorded app inspection covers an arm64 Simulator Mach-O and 189 regular tar members. Its prior byte inspection is reused without restreaming the app; standalone native archive hashes remain runner-receipt evidence.

The original test log and native job log independently record each named case starting once: 2D failed after 282.554 seconds and 3D passed after 401.939 seconds. The diagnostics failure occurs at test-log line 8680 and native-log line 12515, with reported Swift line 112. The original summary reports two tests, one pass, one failure and zero skips/expected failures. The original gate records exit `65` and incomplete passing evidence; both evidence exports exited `0`. These originals agree with the final handoff.

The completed native log contains zero malformed-observation diagnostic markers. This establishes neither cause nor success; no cause was inferred. Attachment metadata preserves six 2D PNGs, 21 3D PNGs and a sole MP4 belonging to 2D. The one documented 3D round-1 body-scroll gesture records no authority intent and `authority_unavailable_not_exercised` for Challenge. No pixels, recording or raw XCResult data were decoded or viewed.

`REVIEW.json` retains all 1,445 passing checks and their direct/reused evidence distinctions. `check-preservation.py` is the independent checker, which completed with exit code `0`. All outputs are private under this review directory; shared source, Git, Gradle, CI, frozen evidence and donor modes were not changed. The frozen handoff's pending-review field is intentionally left intact; this report supplies the separate final-review supplement.
