# Last Light Godot bridge review

Status: **accepted within this bounded review scope, 2026-09-10**. Both findings below are fixed and covered by executed checks. Scope is the versioned renderer schema, Kotlin adapter, authority fixtures, and renderer controller behavior. Native rendering, native teardown, live multiplayer integration, and platform qualification require their separate evidence; this report does not establish production readiness.

## Existing authority and data contract

The shipping source of truth remains `core` and `session`. `LastLightEngine.viewFor` creates the recipient projection; `HostAuthority` binds gameplay actions to an authenticated seat and validates the command revision. The isolated `QualificationAuthorityDriver` calls the real core engine and has no multiplayer/session integration. The renderer receives no `GameState` and does not decide a challenge outcome, penalty, elimination, redeal, or winner.

The exact current `GameView` allowlist is:

| Field | Contents and relevant constraint |
| --- | --- |
| `viewerId` | Nullable recipient ID; unknown viewers project to null. |
| `phase` | `PLAYING`, `ROUND_ENDED`, or `FINISHED`. |
| `roundNumber`, `tableRank` | Positive round; required rank is `CROWN`, `MOON`, or `STAR`, never `WILD`. |
| `players` | Two to six public seats, each containing only `id`, `displayName`, `handCount`, `penaltyAttempts`, and `eliminated`. IDs are unique. Counts are zero through five; attempts are zero through six. |
| `yourHand` | At most five `{id, rank}` cards belonging only to the recipient. An unknown or eliminated recipient has none. Card ranks include `WILD`. |
| `turnPlayerId` | Nullable public current actor. |
| `latestClaim` | Nullable `{playerId, cardCount}`; count is one through three. Contains no card IDs or ranks. |
| `forcedChallenge` | Public rule-derived state; the renderer does not calculate a replacement rule. |
| `availableActions` | Recipient-specific `canPlay`, `canChallenge`, and `maxPlayableCards`. An unavailable play has maximum zero; a permitted play is limited to three and the recipient's actual hand size. |
| `roundOutcome` | Nullable public proof with `roundNumber`, `tableRank`, `claimantId`, `challengerId`, `revealedCards`, `truthful`, `penalizedPlayerId`, `penaltyAttempt`, and `burnedOut`. Reveals only the one to three challenged cards. Its own round number may be less than the current round; previous-round proof remains valid after redeal. |
| `winnerId` | Nullable public winner. |

The domain bounds player IDs at 64 characters and display names at 24. Session admission applies additional Unicode/name validation. The adapter must preserve those values safely rather than reinterpret names as markup or executable text. Public projection excludes opponents' cards, undealt and hidden discarded cards, pending private evidence, secret burnout steps, random-generator state, admission secrets, reconnect tokens, and transport identities.

`GameAction` has exactly two variants: `Play(playerId, cardIds)` and `Challenge(playerId)`. The trusted shell/session supplies `playerId`; renderer input may identify selected card IDs but cannot nominate an actor. Selection is one to three distinct IDs in the current recipient hand. Revealing or concealing that hand is local presentation state and emits no authoritative game action. Host continuation and session navigation remain session/shell operations.

## Reviewed boundary behavior

- Validate required fields and exact types before DTO decoding, including unknown fields and variants. Malformed input produces fixed errors without raw input, cards, or credentials. The complete native document and individual payload have independent 65,536-byte UTF-8 limits; renderer events have a 4,096-byte limit. Preflight bounds depth at 16 and values at 4,096.
- Check bridge protocol and game schema versions independently. Reject duplicate decoded member names before a JSON dictionary can overwrite them; an escaped spelling of a duplicate is still a duplicate.
- Preserve revisions and event sequences as canonical decimal strings from `0` through `Long.MAX_VALUE`. Signs, leading zeroes, numeric JSON values, fractions, exponents, and overflow fail. The actual renderer preserves adjacent revisions above `2^53` and echoes them exactly.
- Use a fresh presentation identity and `EngineEventGate` on entry. The gate checks identity, protocol, nonnegative strictly increasing accepted sequences, readiness, and closure. It does **not** validate an intent schema, selected cards, expected revision, or the latest accepted view.
- Bind intents to the exact current view revision and fixed trusted recipient. Reject stale/future revisions, wrong schemas, invalid selections, unavailable actions, and intents after closure. The adapter returns ordinary core actions or trusted host-control requests for authority validation. Malformed documents do not advance the gate; well-formed but stale/disabled intents consume their accepted event sequence.
- Accept only strictly newer view revisions. The owner advances the revision for control-only view refreshes as well. A new presentation uses a fresh gate and identity, with no old sequence or local hand reveal. Old view and lifecycle documents cannot target the replacement controller.
- Foreground and disposal commands must clear local private-hand reveal and stop interaction as appropriate. Queued old callbacks must remain bound to their original presentation. Renderer readiness or animation completion grants no game authority.

## Independent execution evidence

| Check | Result | Execution and inspection |
| --- | --- | --- |
| Kotlin bridge suite | **12 tests, 0 failures/errors/skips** | `review_environment` executed the full isolated `:bridge:jvmTest` suite under the shared Gradle lock. This reviewer authored the separate six-test `BridgeAdversarialReviewTest`, inspected the source fixes and both resulting XML files, and avoided a duplicate Gradle run. |
| GDScript strict JSON corpus | **61 cases, 0 failures** | Independently executed by this reviewer against the final `strict_json.gd` on Godot 4.7.2. |
| GDScript controller boundary | **107 checks, 0 failures** | Independently executed by this reviewer against the actual controller, validator, parser, and core-generated fixtures on Godot 4.7.2. |

The Kotlin review tests use real engine projections before and after a challenge and after redeal. They check every recipient and an unknown viewer against an independent field/card allowlist; systematically remove required fields, insert an unknown credential-shaped field, and quote numeric/boolean primitives; reject malformed events and forged actors/outcomes; test UTF-8 boundaries and exact maximum counters; and exercise readiness, stale/replayed input, fixed recipient identity, caller collection detachment, foreground suspension, closure, replacement, suppressed actions, and host controls.

The Godot runners copy only the needed actual scripts into temporary projects. They do not import the main renderer or modify its cache. Commands:

```sh
python3 godot/reviews/tests/strict_json_review.py
python3 godot/reviews/tests/renderer_boundary_review.py
```

The parser corpus covers valid Unicode and JSON primitives; duplicate and escaped-duplicate names; surrogate errors; comments, trailing commas, raw newline/tab characters and numeric grammar; nonfinite numbers; exact ASCII/UTF-8 byte limits; and depth/value-count boundaries. The controller checks exact schema/integer types, hidden and revealed hands, local selection without authority events, selection clearing on submission, pending input recovery across host/window foreground loss, authoritative view application, historical proof, winner, closure, replacement, and exact adjacent revisions above double precision.

Preserved evidence:

- `/tmp/partydeck-godot-environment-review/bridge-test-results/TEST-dev.partydeck.godot.bridge.BridgeAdversarialReviewTest.xml`: six tests in 0.281 seconds, SHA-256 `69ef91e879397723a8bcd60271e80e4ef91118e495f6c52a7038721331419f42`.
- `/tmp/partydeck-godot-environment-review/bridge-test-results/TEST-dev.partydeck.godot.bridge.LastLightBridgeTest.xml`: six tests in 0.100 seconds.
- `/tmp/partydeck-godot-strict-json-review-final.log` and `/tmp/partydeck-godot-renderer-boundary-review.log` record the Godot runs and tested source/fixture hashes.

The final tested parser SHA-256 is `0696e5741c915c42c5b386dd27b6ed3611f3b7a3780d8fb8e0fabd88d6f2f4b3`; controller SHA-256 is `4891269ee70a642e92e1871346ce135b2ee00c7f2b09166f96d0b1890f24de51`. All three tested GDScript files still matched their execution hashes at closure.

These are String-level parser and controller checks, not native byte-conversion or visual/native lifecycle tests. A raw NUL cannot be carried unchanged through Godot's JSON fixture loader and was excluded after confirming that test-data conversion, rather than the target scanner, replaced it. Native ingress conversion has a separate security review.

## Resolved findings

| Finding | Resolution and evidence |
| --- | --- |
| The Kotlin view decoder inherited optional `AvailableActions` defaults and accepted quoted primitive values, while the renderer required all fields and exact types. | `ViewJsonShape` now checks every required nested field and raw type before DTO decoding. Both the owner regression and this reviewer's systematic missing/unknown/quoted-field test passed in the independently executed suite. Core model defaults remain unchanged. |
| Submitting an intent retained selected cards until a later authoritative view, contrary to the agreed local-state contract. | `_send_intent` now clears selection before publishing pending state. The actual controller regression passed. It also confirms that local reveal/selection produces no authority event and that a play intent does not itself remove cards. |

The controller run additionally covers the security reviewer's pending-input/foreground recovery finding. The native current-revision gate remains necessary when an earlier request may already have reached authority.

## Fixture and scope closure

The generator source calls `QualificationAuthorityDriver`, which in turn uses real `LastLightEngine` operations. This reviewer checked all **15 fixture document digests** against the manifest and verified their native/event byte bounds. The manifest and source agree on deterministic tooling seed **2**, final round **14**, final revision **41**, two viewer plays, and two viewer challenges. The seed/provenance manifest is tooling data, separate from the renderer documents. Static fixtures establish projection compatibility; they are not live multiplayer or native host evidence.

No finding remains open within this schema/adapter/controller review. Actual scene rendering, native queue/thread/view ownership and teardown, Android/iOS execution, accessibility, physical networking, and production randomness injection remain with their assigned qualification owners.

## Authoritative research

Retrieved directly on 2026-09-09 before evaluating the new schema/adapter:

1. [Godot 4.7.2 JSON API source](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/JSON.xml) documents that both parse methods accept trailing commas, raw tabs/newlines in strings, lax numbers, and some invalid Unicode with cleanup. It also documents JSON number conversion to floating-point values. Parser success is insufficient proof of strict schema input.
2. [Godot 4.7.2 JSON implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/core/io/json.cpp) parses numeric tokens into `double` and assigns object members with `object[key] = v`, replacing prior equal decoded keys. Validation after parsing cannot recover those duplicate members.
3. [RFC 8259, sections 4 and 6](https://www.rfc-editor.org/rfc/rfc8259) explains non-interoperable duplicate-name handling and exact interoperable integer values from `-(2^53)+1` through `(2^53)-1` for binary64 implementations. Strict duplicate rejection and exact counter representation are PartyDeck boundary choices supported by those constraints.
4. [kotlinx.serialization 1.11.0 streaming decoder](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/formats/json/commonMain/src/kotlinx/serialization/json/internal/StreamingJsonDecoder.kt) explicitly permits quoted primitive values and uses `consumeBooleanLenient` for booleans. `isLenient = false` therefore does not establish exact wire primitive types; the adapter's raw shape validation is required.

Repository contracts inspected: `AGENTS.md`, `plan.md`, `docs/IMPLEMENTATION.md`, `core/.../GameModels.kt`, `core/.../GameAuthority.kt`, `core/.../LastLightEngine.kt`, `session/.../SessionCodec.kt`, `session/.../HostAuthority.kt`, `games/.../EmbeddedGameBridge.kt`, `games/.../EngineEventGate.kt`, and the existing `EngineBoundaryTest`.

## Public JSON preflight follow-up, 2026-09-10

**Accepted.** The new public `validateBoundedJson(document, maxBytes)` checks that the caller's limit is between one byte and the shared 65,536-byte ceiling, then delegates to the already reviewed strict scanner. It preserves strict grammar, Unicode/UTF-8 validation, duplicate decoded-key rejection, and depth/value-count bounds. It intentionally accepts any valid JSON root; callers still enforce their schema.

This reviewer independently executed the separate `BoundedJsonApiReviewTest`: **2 tests, 0 failures/errors/skips** in 0.063 seconds. The existing 12-test bridge suite was not changed or rerun. The new tests cover invalid caller limits, a one-byte valid scalar, the exact 16,384-byte Unicode boundary used by Android diagnostics, and rejection through the public API of single quotes, comments, trailing commas, extra documents, escaped duplicate keys, invalid surrogates, and a comment/deep-nesting input.

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification \
  :bridge:jvmTest --tests '*BoundedJsonApiReviewTest*' --console=plain
```

Gradle exited successfully. Independently inspected and preserved XML: `/tmp/partydeck-godot-bounded-json-api-review/TEST-dev.partydeck.godot.bridge.BoundedJsonApiReviewTest.xml`, SHA-256 `6989c06ae001e15eaa4763b6cfd36cc9b827e8db82eee4b3d557be2e2968a32d`.

The Android `RendererDiagnostics` call site invokes this helper before `JSONObject`, at its stricter 16,384-byte cap, and retains exact keys, typed fields, bounded geometry/collections, canonical counters, and a newly constructed output allowlist. Full `rect` and separate `clipRect` are both checked. This is a source review of that call site, coordinated with `review_security` and `network_transport`; the JVM wrapper test does not establish native delivery or Android execution. Directly retrieved [Android 16 `JSONTokener`](https://android.googlesource.com/platform/libcore/+/android-16.0.0_r1/json/src/main/java/org/json/JSONTokener.java) and [JSONObject](https://android.googlesource.com/platform/libcore/+/android-16.0.0_r1/json/src/main/java/org/json/JSONObject.java) on 2026-09-10 confirm the platform parser's permissive forms and why the strict preflight is required.

## Density and diagnostic geometry follow-up, 2026-09-10

**Accepted within the source and Linux runtime scope.** This reviewer inspected the owner's density/ScrollContainer evidence and independently executed **20 checks, zero failures**, against `main.gd` SHA-256 `de60c455f59ad22d9c9b8e6ffe011f2ee3f488adf297b8737910728f1e7b6e09` on official Godot 4.7.2. The source hash remained unchanged through execution. The check preserves desktop coordinates until native configuration, observes a 720 × 1050 physical viewport becoming 411.428558 × 600 logical units at density 1.75, and verifies the matching stretch transform. It covers nested clipping, separate full control bounds and clip regions, top-level controls and ancestors, CanvasLayer boundaries, omission of child SubViewport controls from root-coordinate diagnostics, fully clipped visibility, and request/sequence correlation.

The executed script is preserved byte-for-byte at `godot/reviews/tests/main_geometry_review.gd`, SHA-256 `0374b12fd688d010177a0bff0f14fbe39c751ceb54b56ef0437d1cd8ef5feee6`. It was run from `/tmp/partydeck-main-boundary-review.gd` with `--headless --path godot/renderer --script ... -- --manual-bridge`; the process exited zero. `/tmp/partydeck-main-boundary-review.log` and `/tmp/partydeck-main-boundary-review-evidence.json` preserve the result and hashes. This does not establish Android display or touch behavior.

Directly retrieved tagged [Window implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/main/window.cpp), [CanvasItem API](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/CanvasItem.xml), and [ScrollContainer implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/scroll_container.cpp) confirm the physical-size/logical-override calculation, viewport coordinate transform, and default `clip_contents` behavior. The additional canvas-boundary cases were independently executed rather than inferred from those descriptions.

## Matched desktop input and shutdown follow-up, 2026-09-10

**Accepted for the tested PCK.** `app_controller` executed the fresh packed 2D/3D comparison in `godot/qualification/build/comparison/matched-packed-20260910`. This reviewer independently audited its source, report, both results and logs, all 22 PNG digests/structures/dimensions and matching receipts, capture revision/view hashes, concealed/pending diagnostics, fresh presentation identities, and 42 recorded card/gameplay click points within their full visible bounds. The concealed and revealed captures for both modes were also visually inspected. Each mode records 21 bridge events, two viewer plays, two viewer challenges, 13 round advances, and 42 authority snapshots from revision 0 through 41, ending in round 14. The actual trace records are equal; independently recomputed SHA-256 is `79b5b2a6415a365d531da3488b7b87f1b2309f2b1208899ee5b4618da16be674`.

The probe loads the real renderer scene, finds actual Buttons, scrolls them into view, checks clipping, and injects mouse motion/press/release through `Input.parse_input_event`. The harness accepts the resulting events through the real adapter/core authority and compares each delivered public view. It checks disabled pending gameplay and cleared selection before accepting an event, plus privacy after authoritative updates, concealment, foreground loss, closure, and replacement. Tagged [Input documentation](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Input.xml), retrieved directly for this follow-up, confirms that this is engine input injection and has no operating-system effect. These results do not establish OS input, native touch, multiplayer, or device accessibility.

The corrected quit path queues its acknowledgment, drains partial writes with a one-second deadline, then disconnects and exits. The JVM receives the reply, waits for process exit, requires zero status, and rejects engine/script error lines before a passing result is saved. Both fresh logs contain no `ERROR:` or `SCRIPT ERROR:` lines; both exit codes are zero. Source review used the directly retrieved tagged [StreamPeer partial-write contract](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/StreamPeer.xml), [StreamPeerSocket lifecycle API](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/StreamPeerSocket.xml), and [OpenJDK 21 Process contract](https://github.com/openjdk/jdk21u/blob/jdk-21.0.10-ga/src/java.base/share/classes/java/lang/Process.java). The earlier `first-real-2d-input` cleanup failure is not acceptance evidence.

Artifact and audit provenance:

- Tested PCK SHA-256: `2c840bb8a20177aaed657cf5ae6f0bcee74964bc591d269ed741cd9e58365e35`; it still matched the report and every receipt at inspection.
- Report SHA-256: `e668179d24ce75b0fd472715abdf405be726764f69d6152485aff43c1adf8d46`.
- Recorded source fingerprint: `26426170ab4341d7ff72b3b387b3f70f5938376d0285f216d102fb27689f9637`. UI owners edited presentation scripts/tests after the run. Replacing only those later files with their committed versions reproduced this exact fingerprint; no working file was changed for that reconstruction. The retained run therefore qualifies its recorded artifact, and later UI changes need fresh integration evidence.
- Independent evidence audit: `/tmp/partydeck-matched-packed-review.py` and `/tmp/partydeck-matched-packed-review.json`; source reconstruction: `/tmp/partydeck-matched-source-reconstruction.json`.
