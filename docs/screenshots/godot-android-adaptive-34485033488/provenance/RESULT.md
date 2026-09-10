Run **34485033488** at `fc431ee775990943dfe152f4f20fb9365db4e72d` remains **failed and unqualified**. The producer succeeded and all four installations passed. Each consumer then failed its first `2d-landscape.initial-landscape` check.

| Consumer | First recorded failure | Original states / stills |
|---|---|---|
| Debug, normal text | UI dump timed out after 1.281382 seconds during Standard preparation | 9 / 2 |
| Optimized, normal text | UI dump timed out after 1.795178 seconds during Standard preparation | 9 / 2 |
| Debug, 200% text | Godot Activity was not observed within 45 seconds after the logged picker action | 131 / 6 |
| Optimized, 200% text | Godot Activity was not observed within 45 seconds after the logged picker action | 135 / 6 |

The earliest recorded error is the optimized normal-text case at `2026-09-10T14:01:58.8504653Z`, in original `job-102899856314.log`. UI diagnosis is separate; a logged tap does not prove delivery or identify a product callback failure.

All six original ZIPs and 2,471 extracted artifact members match GitHub's digests and their retained inventories. All five original job logs, every extracted immutable-source member, six checker pins, three APK inputs and four installed copies were independently verified. APK metadata enables qualification `2d,3d`; target SDK is 36. The optimized runtime uses the recorded disposable CI identity. Every APK contains source-current PCK `d6adbba1b5cbd6a1ac3a5754e4294363eae70ae9540af4ba12040cd4cfff44e0` (136 entries, 1,549,656 bytes).

All **284 original raw process receipts** have the exact `ps -A -n -w -o PID,UID,NAME` argv, successful exit status, verified stdout/stderr lengths and hashes, and matching state text. Exact-source parser replay reproduces the original Activity/WM/process observations: 282 samples attribute MainActivity, two remain unattributed, and no sample observes a renderer. The prior parser and raw-process evidence defects are closed for this run.

Only initial Compose-shell landscape setup was entered. No adaptive check passed; **92 of 96 named scopes were unexecuted**. Held touch, native rotation, reentry, native leave, split-screen, and 3D remain unqualified. The 16 original stills were verified and visually reviewed; no transition video exists. The large-text final stills show the Standard table rather than a remaining picker dialog.

Original archives, source, API snapshots, logs and artifact members are retained beside the separate `audit-v1/` reports. `evidence-freeze.json` binds the original inventory and derived reports. No source edits, builds, app/device/native runs, CI dispatches or duplicate checker suites were performed by this audit. Read-only APK tools and exact-source pure content/parsing checks were used. Earlier freezes remain unchanged.
