# Retained-engine native harness

This separate application exercises `PDGodotEngineOwner` and the real
`IosQualificationFactory` against the fixed Last Light PCK. It does not install
a production KMP factory. Each admitted entry creates a new Kotlin facade and
UUID; its commands use the native lifecycle generation captured before queuing.
All calls and callbacks stay on the native main thread. No game rules, copied
authority state, fabricated renderer events, or replacement engine live here.

The harness and XCTest sources have not yet been compiled or executed on macOS.
Linux validation covers Swift grammar, runner syntax, plist/XML structure, and
failure-receipt handling only. A grammar parser cannot verify Swift imports,
Objective-C selector names, actor isolation, UIKit behavior, or native lifecycle.

## Native cases

- `testRepeated2DAnd3DKeepOneDormantEngine` enters 2D, 3D, 2D, and 3D in one
  process. Every entry uses real Reveal, card-selection, Play, and Exit touches.
  It observes new presentation/SceneTree/scene identities, stable native engine,
  controller, view and layer identities, and one engine bootstrap. Each return
  checks destruction of the old ObjectIDs, the empty replacement tree, cleared
  private queues and callback bindings, and actual stopped native services.
- `testActiveAndDormantBackgroundTransitionsStayConcealed` reveals a hand before
  a coalesced native foreground loss/regain, an in-app pause, and actual Home /
  `XCUIApplication.activate()` transitions. It requires fresh concealed draws
  on resume. The same transitions in the dormant shell must leave display,
  audio callback and service-start counters unchanged.
- `testStaleFirstReadyAndCloseCompletionReentry` changes the native epoch before
  submitting the first accepted Ready projection. The stale atomic delivery
  must fail without consuming Ready confirmation. It then closes with actual
  native delivery queued, retains immediate native snapshots proving one new
  command/private document and its exact byte count, and rejects any delivery
  completion before close. Cancellation must finish before dormant close
  completion, which opens the next mode. Attempts to rebind old callbacks,
  deliver old commands, grant foreground, confirm Ready,
  query diagnostics, and close the old handle cannot change the replacement.

The host also attempts a valid fresh native acquisition while every close is
pending. Its exact refusal is retained. The close completion snapshot must be
dormant and expose zero retirement depth before another acquisition can succeed.
`sceneIdentity` may retain a retired numeric ObjectID for diagnostics; liveness
is proved by `oldSceneObjectsAbsent`, the new tree identity and its root-only
node count, rather than expecting remembered identifiers to become zero.

Dormant intervals require actual host-button input, advancing native-shell
sample timestamps, and unchanged monotonic engine/audio counters across at least
the native observation interval. Polling delays alone do not satisfy a check.
The Home observation follows the existing pinned iPhone simulator convention:
SpringBoard's actual hittable Safari and Messages dock icons, no alert, the
application state, hierarchy and screenshot are all retained. Return additionally
requires a real background scene transition observed by the application owner.

## Build and evidence

The coordinator applies the separate project/runner integration patch and builds
the current native archives and qualification Kotlin framework first. The
runner reuses `prepare-authority-host.py` to verify their existing receipts and
stage the fixed PCK. It performs no Gradle, engine build, or pack export itself.

```sh
bash godot/ios-host/test-retained-host.sh build
bash godot/ios-host/test-retained-host.sh test
```

Each stage refuses to overwrite `godot/ios-host/build/retained-host-<stage>`.
The test stage builds its own executable and retains logs, source/input hashes,
link symbols/map, XCResult, screenshots, JSON attachments, application journals,
and the simulator app. Test qualification requires the retained XCResult,
successful attachment/summary exports, a nonempty JSON summary, and all three
executed XCTest cases passing. A failed or incomplete run produces an unqualified
`evidence/result.json`; malformed input metadata retains its original file hash
and an explicit parsing or shape error in that receipt. The prior ProbeHost and
AuthorityHost suites are
unchanged and remain separate gates.

The source integration patch is supplied to the coordinator under
`/tmp/partydeck-retained-host-integration.patch`; it adds the separate Xcode
project, scheme, runner and receipt recorder. It changes no existing project or
workflow. `Host.xcconfig` uses the existing selective native archive link and
`PartyDeckGodotBridge.framework`, with `PDGodotEngineOwner.h` as its bridge header.

An unavailable simulator motion sensor is recorded as unavailable. No physical
motion shutdown, real audio-session interruption, device Metal behavior, store
signing, or production factory qualification follows from these tests.

## Primary sources

The native contract and checked engine revision are in [DORMANCY.md](../DORMANCY.md).
The harness read `PDGodotEngineOwner.h` and the actual native snapshot producers;
its retained-scene assumptions were checked against pinned Godot
`ed1daf0bf001b61586d9930840f2f1394092c079`:

- [OS_AppleEmbedded main-loop deletion](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/os_apple_embedded.mm).
- [SceneTree finalization](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/main/scene_tree.cpp).
- [XCUIApplication.activate](https://developer.apple.com/documentation/xcuiautomation/xcuiapplication/activate()).
- [XCUIApplication.state](https://developer.apple.com/documentation/xcuiautomation/xcuiapplication/state-swift.property).
- [XCUIDevice.press](https://developer.apple.com/documentation/xcuiautomation/xcuidevice/press(_:)).
- [XCUICoordinate.tap](https://developer.apple.com/documentation/xcuiautomation/xcuicoordinate/tap()).

Fetched source copies and SHA-256 records are retained at
`/tmp/partydeck-ios-retained-harness-research`. Temporary tree-sitter packages are
used only for Linux grammar checks; they are not application dependencies.
