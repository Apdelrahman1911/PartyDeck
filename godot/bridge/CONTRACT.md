# Last Light Godot bridge, version 1

This isolated adapter uses the existing `GameView`, `GameAction`,
`EmbeddedGameBridge`, and `EngineEventGate`. Both 2D and 3D presentations consume
the same documents. Presentation style changes no rules, authority, or actions.
Only the native owner has a real `LastLightEngine`; Godot renders projected
views and requests intents. The qualification driver and generated fixtures are
not multiplayer/session integration.

## Dependencies and checked sources

The isolated qualification build reuses repository pins: Kotlin 2.4.20,
`kotlinx-serialization-json` 1.11.0, and the existing core/games source. No Godot,
Compose, transport, or platform API is needed by the common adapter.

- [Godot 4.7.2 JSON documentation](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/JSON.xml)
  documents permissive parsing and floating-point JSON numbers. Every revision
  and sequence is therefore a canonical nonnegative decimal **string**, from
  `"0"` through `"9223372036854775807"`; no signs, leading zeroes, fractions, or
  exponent notation. Both implementations preflight strict JSON before parsing.
- [kotlinx.serialization 1.11.0 tree reader](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/formats/json/commonMain/src/kotlinx/serialization/json/internal/JsonTreeReader.kt)
  assigns object keys into a map. A separate bounded preflight rejects duplicate
  decoded keys, including escaped equivalents, before they could be overwritten.
- [Strict JSON configuration](https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-json/kotlinx.serialization.json/-json-builder/is-lenient.html)
  and [unknown-key rejection](https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-json/kotlinx.serialization.json/-json-builder/ignore-unknown-keys.html)
  are explicitly enabled. Envelopes and intents accept only their documented
  fields, types, and enum values. Unpaired Unicode surrogates, trailing commas,
  nonstandard numbers, extra documents, and excessive nesting fail preflight.
- The pinned [streaming decoder](https://github.com/Kotlin/kotlinx.serialization/blob/v1.11.0/formats/json/commonMain/src/kotlinx/serialization/json/internal/StreamingJsonDecoder.kt)
  permits some quoted primitives, while core `AvailableActions` has constructor
  defaults. `ViewJsonShape` checks every required key and exact JSON type before
  DTO decoding, so those library/model conveniences cannot relax the wire schema.

## Native document envelopes

The entire serialized document, independently of `EnginePayload`, must fit
65,536 UTF-8 bytes. Renderer-to-native event documents have a tighter 4,096-byte
limit. JSON nesting is limited to 16 levels. Strings are not log messages or
credentials. All objects reject missing and unknown fields.

Every native document contains `protocolVersion: 1`, `presentationId` (a unique,
nonblank, control-free string of at most 128 characters for this lifetime), and
`type`. Additional fields are:

| Type | Additional fields | Bridge meaning |
| --- | --- | --- |
| `launch` | `gameId: "last-light"`, `presentationMode: "2d"` or `"3d"`, `revision`, `schemaId: "last-light-view-v1"`, `payload`, `preferences` | `EngineLaunch` plus renderer preferences |
| `view` | `revision`, `schemaId: "last-light-view-v1"`, `payload` | `EngineCommand.ShowView` |
| `foreground` | `isForeground: boolean` | `EngineCommand.SetForeground` |
| `close` | None | Native session `close()`; terminal and idempotent |

`preferences` always contains `reduceMotion: boolean`, `soundEnabled: boolean`,
and `textScale: number` (finite, between 1 and 2 inclusive). Kotlin defaults are
false, true, and 1. Preferences are launch-only in version 1.

The view payload is exactly:

```json
{"game": "the serialized GameView object, not a string", "controls": {"isHost": true, "canSendAction": true, "canAdvanceRound": false, "canReturnToLobby": false}}
```

The `game` value is the existing recipient-specific `GameView` object. It has
public seat counts/fuse attempts, only the recipient's own cards, the public
claim count, available-action flags, and public challenge proof. Unknown or
eliminated recipients have no private hand. A retained `roundOutcome` may belong
to a previous round; its own `roundNumber` must be displayed accurately. An
unresolved claim contains no card IDs/ranks. No authority state, other hand,
undealt card, future burnout step, credential, or random generator is accepted.

The native owner supplies controls. They may disable otherwise legal actions
(for example while paused). Advance requires host permission and a round result;
return-to-lobby requires host permission but may be enabled during any game
phase, matching the current session contract. Controls do not grant the renderer
authority to change a game result.

## Renderer events

Every event has `protocolVersion`, `presentationId`, `sequence`, and `type`.
`sequence` is a decimal string, starts with any nonnegative value, and must
strictly increase for events accepted by `EngineEventGate`.

| Type | Additional fields | Bridge meaning |
| --- | --- | --- |
| `ready` | None | `EngineEventBody.Ready` |
| `intent` | `expectedRevision`, `schemaId: "last-light-intent-v1"`, `payload` | `EngineEventBody.PlayerIntent` |
| `exit` | None | `EngineEventBody.ExitRequested` |
| `failed` | `reason` | `EngineEventBody.Failed` |

Failure reason is one of `INITIALIZATION_FAILED`, `INVALID_PAYLOAD`,
`RENDERER_LOST`, or `INTERNAL_ERROR`. An intent payload is exactly one of:

```json
{"type":"play","cardIds":["r1-c0"]}
{"type":"challenge"}
{"type":"advance_round"}
{"type":"return_to_lobby"}
```

A play has one to three unique nonblank, control-free card IDs of at most 64
characters. It never supplies a player/actor ID, rank, claim result, outcome, or
RNG seed. The adapter binds the actor to the presentation's trusted recipient,
checks exact current revision, foreground state, native controls, own-card
membership and available actions, then returns an ordinary `GameAction` or
host-control request. Existing core/session code must still accept the action.

## Lifecycle and privacy

One adapter/gate belongs to one presentation ID and one recipient. It starts in
the foreground and requires Ready before intents. A malformed document cannot
advance the gate; a structurally valid but stale/disabled intent consumes its
accepted event sequence but cannot mutate authority. A view update must have a
strictly greater revision; the native owner advances it for control-only view
updates too. New launches require a new ID and gate. Failure, exit, or close
prevents later input; backgrounding prevents gameplay intents immediately.
Native owners may call the qualification driver's `refreshView()` after a
rejected submission to reconcile the renderer at a newer presentation revision
without changing core state. Foreground loss also clears local pending state;
resuming does not replay a rejected action.

Hand reveal and selection are local UI state, not authority intents. They emit
no engine event. Start concealed and clear reveal/selection on every newer view,
foreground loss, and close. A submission also clears selection locally. The
recipient's ranks are authorized projection data, but must not appear on hidden
card fronts, public labels, logs, or screenshots taken while concealed.

The renderer exposes the native singleton `PartyDeckBridge`: signal
`command_received(document: String)`, `get_launch_document(): String`, and
`renderer_event(document: String)`. Thread dispatch, native ownership, bounded
queues, engine lifecycle, and physical/platform qualification remain host duties.

## Qualification entry points

`LastLightWireCodec` encodes launch/commands/close and decodes events.
`LastLightBridgeAdapter` owns the trusted view, revision, controls and event gate.
`QualificationAuthorityDriver` owns a real `LastLightEngine` and private state;
its public `view` and outbound `documents` are recipient projections only.
Caller-supplied `Random` must be platform-CSPRNG backed for a live qualification
session. Reproducible fixtures/tests deliberately supply a deterministic seed.

Run focused tests and regenerate fixtures through the isolated build:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification :bridge:jvmTest :bridge:generateFixtures
```

The JVM main class `dev.partydeck.godot.bridge.GenerateFixtures` takes exactly
one output-directory argument. The Gradle task defaults to `godot/bridge/fixtures`
and accepts `-Ppartydeck.fixtures.dir=/absolute/path`. The manifest records
generation provenance; static fixture loading proves presentation compatibility
only. A real authority/renderer event round trip must be executed separately.

## Bridge milestone evidence

The owner passed six focused JVM tests. Independent verification then ran all
twelve tests, including six separately authored adversarial tests: no failures,
errors, or skips. Coverage includes exact private-card projection, public proof
from the previous round, malformed and duplicate-key input, required view
fields/types, UTF-8 bounds, full-width counters, recipient/revision/lifecycle
gates, paused permissions, and a complete actual-authority match.

The fixed seed-2 scenario performs two viewer plays, two viewer challenges, and
finishes in round 14. Independent generation reproduced all fifteen document
files and the manifest byte for byte. Manifest SHA-256:
`79b71d6dd1d9ff43fd667482f4323aec9a1bf7720d4964315cdb3dab1a68038e`.
The reviewer records are in `godot/reviews`; generated view files contain no
seed. The tooling-only manifest records the reproducible fixture seed.

These checks qualify the codec, native action gate, and local core-authority
driver. They do not qualify renderer execution, native embedding, or production
multiplayer. This driver has no authenticated peers, session credentials,
network discovery, reconnect logic, or transport. A production integration must
map accepted intents through the existing controller/session authority and use
its recipient-specific `GameView` and permission controls.
