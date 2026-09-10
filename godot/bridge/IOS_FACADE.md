# iOS qualification authority facade

`IosQualificationAuthority` owns one existing `QualificationAuthorityDriver`.
Swift receives safe native JSON documents and coarse receipt data. The facade
adds no rules, game strategy, networking, queues, renderer implementation, or
multiplayer/session authority. The driver uses its existing four-seat roster,
real random opener, Last Light engine, bridge gate and safe-view opponent policy.

## Construction and supported surface

The iOS-only `IosQualificationFactory.create` has six required arguments:

```kotlin
fun create(
    presentationId: String,
    mode: PresentationMode,
    randomness: IosQualificationRandomness,
    reduceMotion: Boolean,
    soundEnabled: Boolean,
    textScale: Double,
): IosQualificationAuthority
```

The native owner supplies a fresh presentation ID, such as its UUID string, for
each lifetime. Existing bridge validation checks the ID and preferences.
`PresentationMode.TWO_D` and `THREE_D` select the real presentations.
`IosQualificationRandomness.REFERENCE_SEED_2` explicitly chooses the same seed-2
authority scenario used by the desktop comparison. `SECURE` uses iOS
`SecRandomCopyBytes` for every nonempty random draw. Secure mode has no seeded
fallback. Randomness choice and receipt counters are native-only metadata;
they are never added to renderer view documents.

The factory and mutating operations use `@Throws(Exception::class)`. Kotlin's
Objective-C export maps those errors to Swift `throws`/`NSError`; ordinary
bridge rejections are returned as data. A construction or unexpected runtime
error ends the attempted lifetime: the host closes/releases its owned resources
and surfaces the error. Generated Objective-C header and Swift spellings must
be checked by the macOS framework/host build before integration.

| Facade entry | Result |
| --- | --- |
| `launchDocument: String` | Initial recipient-safe launch for native preparation; empty after terminal close. Use it for initial launch only. |
| `status()` | Coarse lifecycle, authority phase/revision and receipt counters; no hand, claim or game state. |
| `handleRendererEvent(document)` | Passes the exact event to the existing driver; returns resulting safe commands and an explicit outcome. |
| `advanceOtherPlayers()` | Invokes the driver's existing bounded opponent policy; returns its ordered safe views, or `NO_CHANGE`. |
| `refreshView()` | Explicitly requests the driver's newer presentation revision after a rejected submission, without changing core state. |
| `setForeground(isForeground)` | Delegates immediately to the driver's foreground validation and returns its foreground command. |
| `close()` | Terminal and idempotent; returns the driver's close document. |

Every operation result has an `outcome`, immutable `commands: List<String>`, a
non-null `reasonCode`, and an `IosQualificationStatus`. Normal success uses an
empty reason string. `REJECTED` carries the exact `BridgeRejection` enum name;
`AUTHORITY_REJECTED` carries the exact core rejection name. `RENDERER_FAILED`
carries the accepted renderer failure name. Lobby return, Exit and renderer
failure have distinct terminal outcomes and include an idempotent driver close
command. Later renderer input still reaches the driver's closed gate and is
rejected; native refresh/foreground/opponent operations after close return
`REJECTED` with `CLOSED` and no commands.

Lifecycle is `WAITING_FOR_READY`, `READY`, or `CLOSED`. The bridge-local phase
enum is a direct mapping of the actual authority's `PLAYING`, `ROUND_ENDED`, or
`FINISHED` phase. Revision is a canonical decimal string. Status also has round
number, public winner ID (empty before a winner), foreground state, and these
counters:

- `acceptedRendererEvents`: bridge-accepted events, including Ready and terminal
  events. A bridge-accepted event rejected by the core still counts here.
- `acceptedViewerPlays` and `acceptedViewerChallenges`: renderer actions accepted
  by the real authority.
- `roundsAdvanced`: real authority-accepted continuation requests.
- `acceptedOpponentActions`: accepted actions from the existing bounded policy.

Status is receipt data. Swift must not use it to decide game outcomes, invent
views, or accept renderer actions itself.

## Native ownership

The native host serializes synchronous calls on its chosen owner thread and
owns bounded event/command queues. It supplies `launchDocument` to preparation,
passes actual renderer events to `handleRendererEvent`, and delivers returned
commands in order. After an accepted action it can invoke `advanceOtherPlayers`
and deliver those views too. Continue remains a real renderer intent; the
facade never automatically starts another round.

A rejection emits no automatic refresh. An open native owner can explicitly
call `refreshView()` to settle pending UI using the driver's newer revision.
Foreground transitions must reach the facade as well as the renderer. The
native owner retains its existing foreground-generation checks and drops stale
queued callbacks. The facade does not schedule or replay callbacks.

On a terminal outcome, deliver the final close command as appropriate and
discard the facade. It clears its cached launch document, but the host must
also clear its own retained strings/queues. Every re-entry needs a new facade,
presentation ID, authority/gate and renderer controller.

## Framework and validation

Root owns the static `PartyDeckGodotBridge` framework configuration for
`iosArm64` and `iosSimulatorArm64`, with bundle ID
`dev.partydeck.godot.bridge`. The supported facade uses only bridge-local types,
strings, primitive values and immutable string lists. It does not require
exporting the core/games APIs or enabling transitive exports. Those modules
remain implementation dependencies of the linked authority.

Focused common-code validation passed on 2026-09-10:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification \
  :bridge:jvmTest --tests dev.partydeck.godot.bridge.IosQualificationFacadeTest \
  --console=plain
```

Four tests cover full matches in both modes against independently constructed
real drivers, exact output-command equality, rejection/foreground/refresh
behavior, actual accepted Exit/Failed events, idempotent close, and replacement
identity/gate isolation. Each reference match reaches round 14 with two viewer
plays, two viewer challenges, and thirteen actual continuations. The original
fifteen fixture documents and their manifest remain unchanged.

These JVM tests qualify the common facade's delegation and lifecycle. They do
not compile the iOS Security binding or prove Swift linking, native event
delivery, touch, suspension, or a playable native match. The macOS framework
build, generated-header check, and actual native loop must provide that evidence.

## Checked sources

- Existing [driver](src/commonMain/kotlin/dev/partydeck/godot/bridge/QualificationAuthorityDriver.kt)
  and [bridge contract](CONTRACT.md): accepted events, foreground/revision gates,
  safe projections, continuation and terminal behavior.
- Existing [iOS platform service](../../composeApp/src/iosMain/kotlin/dev/partydeck/app/IosPlatformServices.kt):
  verified pinned-byte-array `SecRandomCopyBytes` integration. The new facade
  uses that pattern without changing shipping sources.
- Apple's [SecRandomCopyBytes](https://developer.apple.com/documentation/security/secrandomcopybytes(_:_:_:)):
  cryptographically secure output, `kSecRandomDefault`, adequate destination
  size, and mandatory `errSecSuccess` checking before consuming bytes.
- Kotlin's [Objective-C interoperability](https://kotlinlang.org/docs/native-objc-interop.html):
  `@Throws`/`NSError`, enum and immutable-list export, and generated Swift names.
- Kotlin's [native binary configuration](https://kotlinlang.org/docs/multiplatform/multiplatform-build-native-binaries.html):
  framework targets and explicit dependency exports. Only dependencies used
  directly by Swift require export.
