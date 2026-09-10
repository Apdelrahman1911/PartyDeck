Independent retained-evidence review: iOS run 34439760695

Frozen commit: f85f8158054ab70cc3f981c23a6854bb7b0630b6
All timestamps below are 2026-09-10 UTC.

| Case | Actual result | Scope |
| --- | --- | --- |
| 2D/200% | Failed, scrollBound, 64.925 s | One play, round 1/revision 2; no Next tap. |
| 2D normal | Passed, 98.874 s | Actual Home, same-presentation concealed resume, full reference match and ReturnToLobby cleanup. |
| 3D/200% | Failed, Home predicate, 249.331 s | Home UI within deadline conflicts with raw state 4; native pause/private clearing observed; no Home resume or match proof. |
| 3D normal | Passed, 500.713 s | Actual Home, same-presentation concealed resume, full reference match and ReturnToLobby cleanup. |
| Secure renderer Exit | Passed, 25.387 s | Secure launch, Ready, Exit and cleanup only; no gameplay proof. |

Aggregate: 3 passed, 2 failed, terminal TEST FAILED. The last runner's two-test zero-failure subtotal is not the five-case aggregate.

2D/200% Next timeline (renderer diagnostic sequence, not acceptedDiagnostics):

| Source line | Time | Sequence | Next y | Clip |
| --- | --- | --- | --- | --- |
| 73385 | 05:17:55.824419 | 49 | 343 | [16, 211, 346, 411] |
| 74239 | 05:17:56.326155 | 50 | -235 | [16, 211, 346, 468] |
| 76014 | 05:17:57.068152 | 51 | -235 | [16, 211, 346, 468] |
| 80136 | 05:17:59.105986 | 54 | 63 | [16, 211, 346, 468] |
| 80846 | 05:17:59.546136 | 55 | 115 | [16, 211, 346, 468] |
| 81911 | 05:18:00.332730 | 56 | 160 | [16, 211, 346, 468] |
| 82976 | 05:18:00.862023 | 57 | 160 | [16, 211, 346, 468] |
| 87098 | 05:18:02.768356 | 60 | 481 | [16, 211, 346, 468] |
| 88163 | 05:18:03.407555 | 61 | 670 | [16, 211, 346, 468] |
| 89583 | 05:18:04.082041 | 62 | 675 | [16, 211, 346, 468] |
| 91003 | 05:18:04.790767 | 63 | 675 | [16, 211, 346, 468] |
| 95125 | 05:18:06.731107 | 65 | 675 | [16, 211, 346, 468] |
| 95480 | 05:18:06.932487 | 66 | 341 | [16, 211, 346, 468] |

Next is 338 x 72 logical points throughout. Three native 234-point drags used 500 pixels/s and no end hold: downward at elapsed 53.86 s and 57.75 s, then upward at 61.70 s. The eight-iteration budget also counted five geometry changes. The last sequence 66 (acceptedDiagnostics/requestId 67) places Next at [16,341,338,72], fully inside [16,211,346,468], but another stable observation was never reached. The frozen stability guard correctly declined to tap changing geometry; the shared retry quota ended before stability could be confirmed. Smaller geometry-directed drags and separate bounded settling/drag quotas are justified; full-visibility and actual-action checks should remain.

3D/200% Home chronology:

- 05:23:35.437: Home starts; 35.927: synthesized event completes (0.489932 s).
- 05:23:36.326: SpringBoard SBRootFolderController ViewDidAppear.
- 05:23:37.196: app scene ViewDidDisappear; 37.231: switcher/deck ViewDidDisappear.
- 05:23:55.942: 20-second deadline receipt still says enteredBackground=false, observedApplicationState=4.
- 05:23:55.976–56.290: screenshot requested/completed. Engine reviewer directly sees Home in the original FC2F83FD PNG.
- 05:23:56.358647: app metric stream line 347486 says paused, foreground=false, privacy cover=true, renderLoopActive=false, private/selected counts 0, iterations 631, bootstrap 1. Renderer sequence 134 / acceptedDiagnostics 135.
- 05:23:57.091: UITest runner PID 10373 exits 75. At 57.101, AuthorityHost PID 16826 is explicitly confirmed alive.

This supports a discrepancy in XCTest state observation, with actual Home UI inside the deadline. It does not prove the underlying cause or satisfy the frozen test's acceptance predicate. SpringBoard foreground alone is insufficient: the later normal 3D session reports it foreground for a notification overlay at 05:31:26. No stable Home AX identifier was substantiated in the retained hierarchy logs. A future public Home-icon observation must be retained and validated, with the raw-state discrepancy preserved.

Both normal runs finish at round 14/revision 41, winner seat-4 (Orbit), plays 2, challenges 2, continuations 13, opponents 24. Before/after Home presentation IDs match and bootstrap stays 1; privacy cover count rises 1 to 2 and background transitions 1 to 4, while revision/action counts remain unchanged and resumed cards/selection are concealed. ReturnToLobby and secure Exit receipts show cleanup 1/depth 0, released view/controller/authority, absent OS singleton/bridge, stopped loop, empty queues, restored idle policy and working shell counter 1. Secure Exit has no game actions.

The inspected crash candidate is searchd PID 3616, not AuthorityHost. Native severity excerpts contain five unsupported mouse_get_position lines, one per app process. These findings do not establish general crash immunity.

No source edits, Git mutations, native reruns or independent app-binary hashing were performed. Both 200% cases remain failed; no KMP-factory, retained-runtime, physical-device, store-signing or complete matrix qualification is claimed.

Full receipt: final-native-diagnosis.json
SHA-256: b6c8d5eea80b9c4eebb1acbd5fe24dfd930a309968ab5a504b144c51afbda771
