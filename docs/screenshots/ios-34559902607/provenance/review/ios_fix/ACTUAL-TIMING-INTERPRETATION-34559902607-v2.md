Both production cases passed in run **34559902607**, source `39405bb0fd6ba0214e70ed251aab1f9f571dc9aa`. Their first accepted native observations show successful preparation and confirmed Ready. The 3D case also contains a **completed 18.735 s iteration maximum**, already present at its first saved native observation. Its cause and the historical failure cause remain unproven.

The table reports measured elapsed seconds at the first accepted native observation. The two cases ran in separate processes.

| Case | Observation sequence | Preparation | Creation | Cold bootstrap | Max iteration | Max draw |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2D | 743 | 2.170623 | 0.021280 | 1.834162 | 3.634828 | 3.652810 |
| 3D | 853 | 2.946736 | 0.042020 | 2.568111 | 18.735130 | 18.763824 |

Both entries were ACTIVE in the expected mode, foreground, with an attached surface and applied/concealed renderer. Preparation was `succeeded`, creation and bootstrap were `returned`, `bootstrapCount=1`, `readyEvents=1`, and the port confirmed Ready. Draws/iterations/presented frames were 12/12/10 for 2D and 17/16/13 for 3D. The independent result review owns behavior acceptance.

The native timing accumulator records the largest duration of one completed scope. It therefore establishes **at least one completed 18.763823875 s draw** and **at least one completed 18.735129875 s iteration**, rather than an accumulated total. Scopes are inclusive and can contain nested work or waits; the two maxima do not identify or uniquely pair the calls that attained them.

Both maxima had completed by observation 853, the first accepted retained native document. That document already reports 17 draws, 16 iterations and 13 presented frames. It does not supply the first visible-frame uptime or the maximizing-call completion time, so the delay cannot be placed before or after the first visible frame or assigned to that frame. The original attachment time, 2026-09-11T04:39:58.276000+00:00, is not a simultaneous observation timestamp for `lastDocument`.

Across the 30 accepted native documents, through final cleanup sequence 1378, neither maximum increases. This shows **no higher sampled completed maximum**. It does **not** establish that later stalls stopped: equal or shorter stalls can recur without changing a maximum, and the accepted fields contain no duration series or threshold count. The successful native case does not grant production-ready performance acceptance.

The eight retained preparation records below stayed identical within their respective observed native generations. Generations 2 and 3 were first saved **after closure**, with the controller in COMPOSE and `lastCloseSucceeded=true`. Their case labels identify the test, not an active renderer mode in those documents.

| Case | Native generation | First sequence | First saved state | Preparation s | Creation s |
| --- | ---: | ---: | --- | ---: | ---: |
| 2D | 1 | 743 | ACTIVE | 2.170623 | 0.021280 |
| 2D | 2 | 1017 | COMPOSE, closed | 0.047466 | 0.007213 |
| 2D | 3 | 1103 | COMPOSE, closed | 0.082239 | 0.021714 |
| 2D | 4 | 1216 | ACTIVE | 0.093134 | 0.010004 |
| 3D | 1 | 853 | ACTIVE | 2.946736 | 0.042020 |
| 3D | 2 | 1122 | COMPOSE, closed | 0.288555 | 0.131540 |
| 3D | 3 | 1190 | COMPOSE, closed | 0.075266 | 0.011283 |
| 3D | 4 | 1241 | ACTIVE | 0.063438 | 0.006862 |

Each case kept one process and `bootstrapCount=1` through native generations 1–4. Bootstrap phase and duration were retained first-bootstrap values, not new measurements for each reentry. Generation 4 first appeared active in session generation 3; final cleanup appeared in session generation 4 while native generation remained 4. Final drain maxima were 0.059387 s for 2D and 0.064733 s for 3D.

The 64 accepted documents comprise 29 from 2D and 35 from 3D. Of these, 54 contain nonnull preparation/native records and 10 explicitly contain null preparation (5 per case); no preparation key is missing. Every nonnull preparation is succeeded/returned with finite positive durations. No failed, rejected, in-flight or zero-duration preparation sample was observed. All fallback fields are present and null; all observed native failure/quarantine flags are false and failed-presentation counters are zero. This describes the retained samples, not continuous coverage.

Preparation measures accepted Swift entry through the existing preparation completion, before its external callback. Creation measures synchronous preflight/container creation. Cold bootstrap measures its actual native initialization scope after guards, excluding prior waiting, retained warm-up, neutral retirement and later gameplay. Native maxima measure completed scopes using system uptime. These intervals can overlap and must not be added or subtracted to assign costs. `returned` alone proves timing completion, not readiness.

The **316.893 s** 2D and **532.216 s** 3D values are whole XCTest case durations. Attachment time does not make a retained `lastDocument` simultaneous with capture or identify initial entry, Ready, first frame or the slow callback. No physical-device, release-performance, shipping or historical-fix acceptance follows from this single successful Debug Simulator run.

No causal correction or timeout change is justified. The earlier focused failure (run `34554200601`, source `253e9656`) remains unresolved. Prior source analysis found that its sole first-2D draw/iteration/frame was mandatory neutral retirement before counted normal gameplay and normal Ready forwarding; that historical evidence was not re-audited here. The later pass does not explain it.

A concrete next measurement, **proposed but not executed**, is a bounded qualification trace using the existing native stage fields `completedCount`, `lastSeconds`, `maxSeconds`, `lastCompletedUptime` and `maxCompletedUptime`, joined to process/presentation identity. Add Ready-confirmation and first successful current concealed-frame presentation markers on the same system-uptime clock. Record bounded draw/iteration events of at least 1 second, plus total/truncated counts, to distinguish early delays from recurring later stalls; that threshold is a diagnostic filter, not a performance budget. Capture entry, interaction, reentry and pre-cleanup context on an actual rerun. A narrow schema/code candidate needs review before this collection. These measurements would locate stages and recurrence; CPU/GPU attribution still requires a platform performance trace. No timeout change is proposed.

The [machine-readable interpretation](/root/projects/PartyDeck/artifacts/evidence-storage/restart-20260911T0457/ios_fix/ACTUAL-TIMING-INTERPRETATION-34559902607-v2.json) preserves exact values, all eight first-per-generation original pointers, context, source boundaries and limits. The [bounded extraction](/root/projects/PartyDeck/artifacts/evidence-storage/restart-20260911T0457/ios_fix/ACTUAL-TIMING-OBSERVATION-ROWS-34559902607-v1.json) records the 64 originals read and verified against the [collector handoff](/root/projects/PartyDeck/artifacts/evidence-storage/34559902607/timing-review-inputs-v1.json). The [independent result review](/root/projects/PartyDeck/artifacts/evidence-storage/restart-20260911T0457/ios_review/dedicated-native-results-independent-review-v1.json) separately binds executions and source-scoped behavior.

Original first native entries:

- 2D: [97880D77-5655-41C9-AB05-EFFDB26BC821.json](/root/projects/PartyDeck/artifacts/evidence-storage/34559902607/ios-reports-and-simulator-app/build/ci/ios/godot-session/attachments/97880D77-5655-41C9-AB05-EFFDB26BC821.json), sequence 743, original ordinal 38, attached 2026-09-11T04:32:54.921000+00:00; SHA-256 `fc94478ebe19c60ac0834de06d1155f3c3d5ca8bd91b413005b4467154d998e4`.
- 3D: [6B7971DF-9563-4180-BF60-BAAFCCFD6218.json](/root/projects/PartyDeck/artifacts/evidence-storage/34559902607/ios-reports-and-simulator-app/build/ci/ios/godot-session/attachments/6B7971DF-9563-4180-BF60-BAAFCCFD6218.json), sequence 853, original ordinal 46, attached 2026-09-11T04:39:58.276000+00:00; SHA-256 `53540a16117f915a4f8ae6f7c01265dac2dc0a7937603639c0aefb9d620ab92a`.

Report author: `ios_fix`. Version 2 adds explicit per-scope, first-view, later-stall and next-measurement limits. Earlier frozen records, including version 1, remain unchanged. No production code was changed and no native execution was performed for this interpretation.
