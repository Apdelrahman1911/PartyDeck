All four Android engine-action scenarios in **34515669045 / 0f00f17** are supported by their original XML and JSON: Reveal, select slot 0, one Play, an immediate same-round Standard public result, and teardown to Home. This is an independent read of the originals, with no native execution or media viewing.

| Variant | Mode | Baseline/result round | Native owner observations | Immediate Standard outcome |
| --- | --- | --- | --- | --- |
| Debug | 2D | 2 | 49 | Concrete round result |
| Debug | 3D | 1 | 49 | Concrete round result |
| Optimized CI-signed | 2D | 1 | 49 | Concrete round result |
| Optimized CI-signed | 3D | 1 | 51 | Concrete round result |

Each case begins with a human-turn baseline containing five visible unchecked cards. Original native observations then show input counters **0 → 2 → 4 → 6**, a revealed five-slot hand, only slot 0 selected, and concealed/cleared state after Play. Exact pre-input XML matches the action records, and each touch maps to the current visible, enabled, fully clipped control. Exactly three engine tap receipts exist per case—one Reveal, one selection, one Play—with no corrective swipes. The native source increments the input counter for admitted motion events before dispatch, so the counter sequence is supporting input evidence, not a gameplay authority counter.

All 198 original owner records preserve their scenario's child PID/UID, Activity/window record, task, configuration, and display. Entry and selected captures preserve the original shell/task and current native owner. The immediate outcome XML precedes the later Standard capture, contains the same baseline round and concrete verdict/challenge/claim, and has no session problem panel. Standard and Home captures preserve the shell/task with the renderer child absent. Home contains no game table, hand, or Leave confirmation.

**Remaining unchecked Standard cards are not directly observed in this run.** All four current concealed-return, outcome, and later Standard XMLs contain **zero card nodes** because they show public results. The visible-card selection check is therefore vacuous at those outcomes. The five unchecked baseline cards and native selection clearing are observed separately; neither proves an unobserved remaining Standard hand.

Frozen old run **34506173394 / d06f83a** has different evidence: its two 2D cases directly observe a five-to-four hand change with four unchecked visible cards; its two 3D cases use the same-round public-result branch. The checker, observation helper, and Android native input/observation source are byte-identical between these two heads. That preserves comparison of the predicates, but the older hand observations and acceptance are not transferred to the current pack/run.

The Standard result is an action-specific inference from the recipient `GameView`, after a single engine Play. The 3D results include subsequent opponent actions. No internal authority acceptance receipt or session revision is exposed; `projectionRevision` and generation remain renderer observation fields. Session continuity is supported by the baseline, sampled shell/task/native ownership, ordered action/outcome receipts, same public round, and teardown. It is not an independently exposed authority session-ID proof.

`original-action-review.json` pins each original, the current collector source binding, old freeze, and exact source excerpts. Build/JUnit/APK/PCK-byte verification remains with `network_transport`; this review does not independently qualify packaging, distribution signing, adaptive layouts/fonts, pixels, TalkBack, physical devices/LAN, or iOS. No source files, deadlines, predicates, frozen collections, or original artifacts were changed.
