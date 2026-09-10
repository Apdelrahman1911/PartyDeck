# Android API 35 — CI 34503251315

[All collections](../README.md) · [Preserved evidence index](evidence-index.md) · [Copy/review binding](provenance/publication-review/partydeck-gallery-2815-publication-binding-v1.json) · [Completed visual review](provenance/publication-review/partydeck-gallery-after-2355-api35-visual-review-v1.json) · [Unchanged source mapping](provenance/source-map/capture-gallery-mapping.json)

Both ordinary debug and optimized smokes pass. Native debug passes 21 checks, including two guarded renderer-death checks; optimized passes 19 checks and explicitly skips the two renderer-death checks. Engine gameplay was not invoked. The frozen independent review records 262 JUnit tests in 41 suites with no failures/errors/skips, 155 passing host tests and 11 lint warnings. These results add no TalkBack or continuous-privacy acceptance.

Normal Standard hands and selection/actions fit. Several Round 1 reveal labels clip at a public-panel edge. Native old-PCK 2D initial Reveal fits narrowly while the cover bottom clips; 3D seats scroll horizontally. The optimized no-claim round-1 result fits the full Return to lobby action. The debug round-2 claim plus previous-round-review state continues below the body. Enlarged intermediate hand, Rules and Settings content requires scrolling; scrolled Play/Challenge and Rules → Practice fit. The enlarged debug invalid-Join button crosses the right viewport edge while the optimized counterpart fits. The optimized original named large-text-rules-practice-entered.png visibly shows a round result. Sequential PNG/XML are not atomic.

| Collection | Original PNGs | Original outcome and scope |
| --- | ---: | --- |
| [API 35 ordinary UI — debug](debug/README.md) | 31 | Original ordinary UI smoke passed. Visual review adds no native gameplay or accessibility outcome. |
| [API 35 native sessions — debug](godot-session/debug/README.md) | 82 | 21 native session checks passed, including two guarded renderer-death checks. Engine gameplay was not invoked; no continuous privacy or TalkBack acceptance. |
| [API 35 ordinary UI — optimized-test-signed](optimized-test-signed/README.md) | 31 | Original ordinary UI smoke passed. Visual review adds no native gameplay or accessibility outcome. |
| [API 35 native sessions — optimized-test-signed](godot-session/optimized-test-signed/README.md) | 68 | 19 native session checks passed; two renderer-death checks were explicitly skipped. Engine gameplay was not invoked; no continuous privacy or TalkBack acceptance. |
| [Compose JVM snapshots — CI 34503251315](compose-jvm/README.md) | 69 | Original JVM layout fixtures; not native Android renderer captures. |
| [API 35 emulator preparation — CI 34503251315](preparation/README.md) | 1 | Launcher/setup evidence only; no gameplay or native acceptance. |
