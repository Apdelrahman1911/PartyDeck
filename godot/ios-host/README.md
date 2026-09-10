# iOS native Godot qualification

This isolated experiment hosts an actual Godot view inside a SwiftUI application.
It does not modify `iosApp`, register an `EmbeddedGameFactory`, or qualify KMP
integration. The pinned engine compilation passed in
[run 34415851126](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34415851126).
The executable diagnostic and all five lifecycle tests passed in
[run 34431377938](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34431377938)
at `4f7776aba5809330fdd0197623a03f7a45cba3a1`. The separate Swift authority caller
compiled and linked in run `34434392993`. The next run, `34439760695`, passed
both normal-text full matches and secure-default Exit; its two 200% text cases
failed, so the complete authority gate remains open. Diagnostic success does
not qualify Last Light gameplay or re-entry.

## Verified source boundary

Godot's current stable release is **4.7.2-stable**, commit
`ed1daf0bf001b61586d9930840f2f1394092c079`, published 2026-08-18. The following
findings were checked against that exact source on 2026-09-09.

| Mechanism | What the source supplies | What it does not establish |
| --- | --- | --- |
| Godot-owned iOS export | `app.swift` owns `@main`, installs `GDTApplicationDelegate`, and hosts `GDTViewController` through `UIViewControllerRepresentable`. | Ownership and disposal inside an existing KMP application. |
| LibGodot C API | `libgodot.h` declares instance creation/destruction. Desktop platform implementations exist. | iOS support: its platform flags omit `library`, and `SConstruct` rejects either library mode. A desktop headless instance is not an iOS surface. |
| Internal iOS UIKit path | `apple_embedded_main` initializes the iOS OS object; `GDTViewRenderer` calls `Main::setup2`, starts the main loop, then iterates it. `GDTViewIOS` creates a real rendering layer. | A stable host-view injection contract, multiple instances, or tested teardown and re-entry. |

`DisplayServerAppleEmbedded` obtains the view from the class-wide
`GDTAppDelegateService.viewController`. The stock view controller also replaces
methods on its root controller's class in
`propagateUIPreferencesToRootViewController`. The source probe subclasses that
actual controller and overrides this declared hook so the native host keeps
its own UI policy. This is a source-coupled experiment, not a public Godot
embedding guarantee.

`GDTView.drawView` drains `CFRunLoopRunInMode` before calling its renderer. A
navigation callback can therefore re-enter the host while a draw is on the
stack. The runtime wraps that actual private draw selector, guards engine and
callback scopes, and defers queued work until all scopes have returned.
`apple_embedded_finish` calls
`Main::cleanup`, deletes its static OS pointer, and does not clear that pointer.
Cleanup must run exactly once after a completed initialization, with rendering
stopped. Initialization failure and a close during initialization need separate
handling. The desktop LibGodot implementation explicitly retains its instance
guard because engine reinitialization is not supported there. Repeated iOS
entry after cleanup remains unqualified.

The display-server constructor also changes `UIApplication.idleTimerDisabled`.
Preparation captures the shell's actual value, and every terminal drain restores
it, including cancellation before bootstrap and initialization failure. The
tests measure both prior values, rather than assuming the host always permits
screen sleep.

The earlier terminal gate used unmodified upstream source. The current engine
checkpoint applies the separately reviewed [four-file CoreAudio patch](patches/README.md)
for actual stop/callback observations and retirement of closed WAV playbacks.
Its deterministic patch and pristine/patched hashes are retained with every
build. This host remains coupled to iOS bootstrap, the global view lookup, the
private draw selector and controller policy. The open native-window proposal
is not an API available in this release.

## Executable host and lifecycle boundary

`PDGodotRuntime.h` exposes only Foundation/UIKit types to the SwiftUI host.
The host owns `@main` and its application delegate. After its container appears,
the runtime calls the actual `apple_embedded_main`, attaches a `GDTViewIOS`
subclass, checks `Main::setup2(false)`, then checks `Main::start()` and initializes
the resulting main loop. A renderer using `OS_AppleEmbedded::iterate()` drives
the real view. The diagnostic scene is ordinary GDScript; only it emits Ready.

The module registers the real `PartyDeckBridge` singleton before scene
initialization. It supplies `get_launch_document`, `command_received`, and
`renderer_event`, with the frozen version-one envelope and decimal-string
counters. Strict JSON preflight rejects duplicate decoded keys, invalid UTF-8
or surrogates, nonstandard syntax, over 16 levels, and over 4,096 values.
Documents are capped at 65,536 UTF-8 bytes, events at 4,096 bytes, commands at
16 entries/262,144 bytes, and events at 16 entries. No payload is logged.
All native access belongs to the main thread; one pending drain avoids an
unbounded dispatch queue. The common authority adapter still must validate
GameView semantics, recipient ownership, controls, and actions.

Foreground loss immediately installs an opaque UIKit cover and hides the
underlying accessibility content. A loss is retained even if resume arrives
before the safe drain. Godot receives concealment before resuming; the cover
leaves only after a later completed frame. Queued intents retain their foreground
generation and are checked again against foreground and current revision before
delivery. Close installs the same cover, stops scheduling frames, and performs
cleanup exactly once outside draw, engine, and callback scopes.

Cancellation before bootstrap creates no engine. A close during initialization
waits for the checked setup boundary. If setup fails before `Main::setup2`
succeeds, the runtime stops the view and quarantines the process; it does **not**
guess that forced cleanup is safe. Successful setup permits normal cleanup,
even when the scene has not started. The process guard refuses a second engine
construction. Quarantined initialization failure and unsupported re-entry
prevent qualification as a shipping `EmbeddedGameFactory`.

## Reproducible engine stage

On Linux, the source audit can run independently of Apple tools or the renderer:

```sh
bash godot/ios-host/build-probe.sh source
```

On the selected ARM64 macOS runner with Xcode 26.4.1:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
bash godot/ios-host/build-probe.sh engine
```

The wrapper verifies a pristine reference at the exact Git commit and creates
a fresh isolated engine checkout for every invocation. It rejects untracked
inputs, including ignored configuration/source files, then applies only the
four reviewed audio-file changes. It captures the exact native module files in
an immutable snapshot before compilation, installs the hash-pinned SCons 4.11.1
wheel in its own virtual environment, and builds the
ordinary iOS export-template static archive with the custom probe module and
two compiler jobs. It uses the Compatibility/OpenGL renderer; both official
iOS compilation documentation and the pinned platform configuration limit the
Simulator to that renderer. This does not test device Metal or GPU performance.
The supported `disable_path_overrides=no` option is required because this owned
host supplies its bundled project/pack paths to `--path` and `--main-pack`.
The custom module fails compilation if `OVERRIDE_PATH_ENABLED` is absent.
It also requires `sdl=no`, excluding the SDL joystick/gamepad subsystem from
this touch/hardware-keyboard host. The previous SDL-only device-query glue and
its symbol requirements have been removed.
The host constructs its argument list itself; it does not forward application
launch arguments or allow `godot_cmdline` injection.

All generated files stay under `godot/ios-host/build`:

- `upstream`: pristine, read-only dependency reference.
- `engine-checkouts/engine.*`: fresh patched engine checkout and its generated build objects.
- `module-snapshots/<digest>/modules`: exact read-only native module files supplied to SCons.
- `scons-cache`: reusable SCons object cache, keyed by the pinned source/toolchain/build inputs.
- `evidence`: reference/source audits, pre-build module inventory, tool versions, build log, archive hash/size, and symbol inventory.
- `artifacts/libpartydeck_godot_ios_probe.a`: combined native archive for the later host link.
- `artifacts/libpartydeck_godot_camera.a`: the auxiliary archive required by the iOS camera module.

The engine stage checks defined iOS bootstrap/finish symbols and the native
runtime/controller/owner/presentation classes. After compilation it rechecks the
snapshot and patched source bytes; the archive receipt uses the captured
pre-build module inventory. Its receipt explicitly records
`ios_runtime_executed: false` and `kmp_factory_qualified: false`.

On the same runner, execute the host gate:

```sh
bash godot/ios-host/build-probe.sh test
```

The wrapper retains the auxiliary camera archive, prepares an authority fixture
and a real diagnostic scene, compiles the SwiftUI host, and runs five XCTest
cases: rendering/pause/background/native touch/exit/reopen refusal; close inside
the actual draw run loop; immediate foreground loss/resume; cancellation before
bootstrap; and close inside the checked initialization boundary, followed by a
fresh process with a real missing-main-scene loader failure. Measurements
include actual iteration counts, layer class, render-loop state, OS/singleton
disappearance, cleanup count/depth, weak view/controller release, and restoration
of the shell's previous idle-timer policy. The tests
also check host responsiveness after cleanup. The diagnostic supplies malformed
and replayed bridge events before its real Ready/Exit round trip.

The host uses ordinary selective archive linking. Its link map and symbol audit
must show the host's entry point without pulling Godot's export-owned SwiftUI
app. `build/artifacts` retains the Simulator app, XCTest result, screenshots,
and measurement attachments, including artifacts from failed test runs. A
successful `native-host-result.json` requires all five actual XCTest cases to
start once and pass. Source checks or compilation cannot create that receipt.

The link in [run 34425278588](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34425278588)
identified four required platform glue symbols. Godot's reduced SDL 3.2.28 source
set omits the UIKit video file that defines `SDL_IsIPad` and `SDL_IsAppleTV`.
That earlier custom module extracted those two real `UIDevice.userInterfaceIdiom` queries
from the exact SDL commit named by Godot, retaining the original notice and
source hash. It also supplies the Apple exporter's empty-list initialization
hooks: this host selects no `.gdip` export plugins. The actual `PartyDeckBridge`
engine module registers independently through Godot's module lifecycle. The
current `sdl=no` build retains only the empty Apple export-plugin hooks. Native
linking with this glue passed in
[run 34428221586](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34428221586).
All five diagnostic tests executed, but only cancellation before bootstrap
passed. Retained app stderr identifies the initial engine failure exactly:
`Main::setup` refused `--path` because the template's default configuration
disables path overrides. The failed runtime snapshot reports one bootstrap,
zero setup2/Ready/iterations, and a quarantined OS; it also confirms the shell's
idle-timer policy was restored. Enabling the supported option fixed that
configuration mismatch. The five-test rerun above passed, including real
touch-to-Exit, full cleanup, draw-time deferred close, pre-start cancellation,
checked initialization cancellation, and actual missing-main-scene failure.
Actual bootstrap/setup2/start return codes are now retained (`-1` means that
stage was not attempted), and failed waits preserve measurements before ending
the test. No native scene-rendering or cleanup success is inferred from this
failed run.

## Retained engine checkpoint

`PDGodotEngineOwner.h` adds a separate owner and disposable presentation handle;
`PDGodotRuntime.close()` remains terminal. The retained owner keeps one native
engine/controller/view/layer, replaces the entire SceneTree for each lifetime,
and only grants another entry after a neutral empty-tree frame and an observed
CoreAudio callback-free shell interval. Native/authority Ready confirmation,
generation-bound delivery, lifecycle callbacks, input gating and deferred close
completion are distinct operations. A failed suspension quarantines the owner.

This source checkpoint does not constitute Apple compilation or same-process
runtime qualification. The [retained contract](DORMANCY.md) records the fixed
PCK/content limits, actual service observations, background rendering rule and
separate evidence required. The original five diagnostic tests and five
one-shot authority tests remain separate suites.

The optional `PARTYDECK_GODOT_PROBE_PCK=/absolute/path/partydeck-last-light.pck`
input bundles the shared pack after its companion receipt is verified with
`godot/tools/renderer.py check-pack`. Launching the built host with `--scene=2d`
or `--scene=3d` selects the corresponding real Last Light fixture presentation.
Those are projected snapshots, not a KMP authority/session loop. The default
five-test gate uses the clearly labeled diagnostic and does not qualify Last
Light gameplay, private-card pixel timing, device Metal, physical audio, or
engine reinitialization.

## Kotlin authority framework handoff

The real qualification authority exposes its Swift-facing contract in
[`IOS_FACADE.md`](../bridge/IOS_FACADE.md). After setting up JDK 21 and the Android SDK needed to
configure the isolated KMP build, the selected ARM64 macOS/Xcode runner can
produce the framework and its actual export header independently of Godot:

```sh
bash godot/ios-host/build-authority.sh
```

The script runs `:bridge:linkDebugFrameworkIosSimulatorArm64` in
`godot/qualification`, retains a framework archive under `build/artifacts`, and
copies the generated Objective-C header and module map into `build/evidence`.
It requires all nine facade/mode declarations in that actual header and
typechecks an import-only Swift source against the Simulator framework. The
receipt records binary/header hashes, the requested ARM64 architecture, and
module-import success separately from host/runtime qualification.
Framework compilation passed in
[run 34427976260](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34427976260)
at `cf6434df2fd32909f70feee68bfcb82e527e2b70`, alongside all twenty actual
Simulator bridge/facade tests. Independent review matched the framework/header
hashes and exact `PDGB` exports. Swift names include
`IosQualificationFactory.shared.create(presentationId:mode:randomness:reduceMotion:soundEnabled:textScale:)`,
`handleRendererEvent(document:)`, and `setForeground(isForeground:)`.
The import-only check does not qualify a Swift gameplay caller or native event
delivery; those remain separate gates.

## Separate authority host

`AuthorityHost.xcodeproj` owns a separate SwiftUI application and XCTest suite.
It reuses the real engine archive and verified shared PCK, and links the actual
static Kotlin framework. It leaves `ProbeHost` and its five diagnostic cases
separate. No shipping source or KMP factory is changed.

`AuthorityModel` serializes synchronous facade calls on the native main thread.
Each attempt creates a fresh UUID and the existing real qualification authority.
It supplies the facade's exact launch document, passes actual renderer events
to `handleRendererEvent`, delivers the returned documents in order, and invokes
the existing bounded opponent policy after acceptance and foreground recovery.
Ordinary rejection requests the facade's explicit newer-view refresh. The Swift
owner contains no game-rule implementation and does not construct renderer
intents or safe views. Command batches are limited to 16 documents, 65,536 UTF-8
bytes each and 262,144 bytes total; delivery failure closes the lifetime.

Foreground loss immediately covers UIKit before entering the facade, then
forwards the transition through the authority and renderer. Terminal outcomes,
unexpected facade errors, and native failures clear the callback, discard the
facade, and close the runtime. Receipts retain only coarse status/counters and
fixed error codes. Full engine cleanup remains terminal for this process;
another table currently requires relaunching the standalone comparison.

Normal launches use the facade's iOS Security-backed randomness. Only the
explicit `--reference-seed=2` argument selects the repeatable comparison.
Text scale follows the native body-text preference, bounded to the supported
`1...2` range; `--text-scale=1` and `--text-scale=2` are explicit qualification
inputs. They do not bypass authority or renderer validation.

The bridge's `get_display_scale()` uses the same pinned display-server scale
that converts the UIKit view bounds to Godot window pixels. The shared renderer
then presents in logical UIKit points. A separate read-only diagnostics signal
reports actual control/clip rectangles, local selection and private-binding
counts. It permits one outstanding request and at most 16,384 UTF-8 bytes, uses
the same strict JSON preflight, and requires exact fields, fixed groups, finite
bounded geometry, the bound presentation/mode, matching request/revision and
foreground, and an increasing canonical sequence. Diagnostics run only after
queued view commands drain. Old observations clear on view/foreground changes
and close; they never enter the authority or decide privacy-cover visibility.
The standalone host samples this channel at most twice per second for native
qualification. This is not a shipping per-frame bridge.

With the native engine/framework built and a current verified PCK available at
`../qualification/build/renderer/partydeck-last-light.pck`, run:

```sh
bash godot/ios-host/test-authority-host.sh build
bash godot/ios-host/test-authority-host.sh test
```

Prerequisites are `build-probe.sh engine` and `build-authority.sh`. Optional
`PARTYDECK_GODOT_AUTHORITY_FRAMEWORK`, `PARTYDECK_GODOT_AUTHORITY_RECEIPT`, and
`PARTYDECK_GODOT_AUTHORITY_PCK` select preserved build artifacts. The stager
checks both native archive hashes, the pinned engine/path option, the exact
current native module source inventory, all four framework receipt entries,
and the PCK's independent `check-pack` receipt before copying inputs. An older
archive cannot silently supply a different Objective-C runtime interface.

The authority gate has five independent cases: full seed-2 matches in 2D and
3D at both 100% and 200% text, plus secure-default launch and actual renderer
Exit. Tests use native taps/drags at the renderer's validated rectangles,
check UIKit/viewport agreement and complete clipping, and retain input geometry
and screenshots. Each reference match checks local reveal/select/hide without
authority changes, pause/background concealment, real play/challenge and
thirteen continuation inputs, round fourteen/revision forty-one/winner, then
authority-driven return and released native ownership. Secure-default testing
does not claim a complete random match.

`authority-host-build-result.json` records actual Swift linking separately from
`authority-host-test-result.json`, which requires all five named XCTest cases
to start once and pass. The app, `AuthorityHost.xcresult`, screenshots and
measurements are retained even after failure. The implementation is awaiting
its first native authority-host execution; no gameplay or dormant-engine pass
is currently claimed here.

## Sources

- [Stable release](https://github.com/godotengine/godot/releases/tag/4.7.2-stable).
- [Library build gate](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/SConstruct).
- [iOS build flags](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/ios/detect.py).
- [iOS bootstrap and finish](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/ios/main_ios.mm).
- [Actual SwiftUI export wrapper](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/app.swift).
- [View-controller policy hook](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/godot_view_controller.mm).
- [Native draw and display-link lifetime](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/godot_view_apple_embedded.mm).
- [iOS view lookup](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/apple_embedded/display_server_apple_embedded.mm).
- [Desktop LibGodot instance guard](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/macos/libgodot_macos.mm).
- [Official iOS compilation guide](https://github.com/godotengine/godot-docs/blob/stable/engine_details/development/compiling/compiling_for_ios.rst).
- [Official custom-module build guide](https://github.com/godotengine/godot-docs/blob/stable/engine_details/engine_api/custom_modules_in_cpp.rst).
- [SDL 3.2.28 UIKit device queries](https://github.com/libsdl-org/SDL/blob/7f3ae3d57459e59943a4ecfefc8f6277ec6bf540/src/video/uikit/SDL_uikitvideo.m).
- [Godot's generated Apple export-plugin hooks](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/export/editor_export_platform_apple_embedded.cpp).
- [SCons wheel metadata](https://pypi.org/pypi/scons/4.11.1/json).
- [Open iOS view proposal](https://github.com/godotengine/godot-proposals/issues/1473).
- [Open native-window proposal](https://github.com/godotengine/godot-proposals/issues/14435).
