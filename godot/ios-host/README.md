# iOS native Godot probe

This isolated experiment targets a SwiftUI-owned native Godot view. It does not
modify `iosApp`, register an `EmbeddedGameFactory`, or qualify KMP integration.
The first stage compiles the exact engine and a native surface source probe;
an executable host and real rendering/input/lifecycle checks are a separate gate.

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
actual controller and overrides this declared hook so a future host can keep
its own UI policy. This is a source-coupled experiment, not a public Godot
embedding guarantee.

`GDTView.drawView` drains `CFRunLoopRunInMode` before calling its renderer. A
navigation callback can therefore re-enter the host while a draw is on the
stack. A runtime host needs an explicit draw-scope guard and deferred teardown;
main-thread confinement alone is insufficient. `apple_embedded_finish` calls
`Main::cleanup`, deletes its static OS pointer, and does not clear that pointer.
Cleanup must run exactly once after a completed initialization, with rendering
stopped. Initialization failure and a close during initialization need separate
handling. The desktop LibGodot implementation explicitly retains its instance
guard because engine reinitialization is not supported there. Repeated iOS
entry after cleanup remains unqualified.

No upstream source patch is applied by the first stage. A future surface API
would need changes to iOS bootstrap, the global view lookup, view-loop lifetime,
and parent-controller policy. The open native-window proposal is not an API
available in this release. Any such change must be recorded as a maintained
patch with its own initialization, cleanup, input, audio, resize, and scene tests.

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

The wrapper verifies the exact Git commit and clean tracked sources, installs
the hash-pinned SCons 4.11.1 wheel in its own virtual environment, and builds the
ordinary iOS export-template static archive with the custom probe module and
two compiler jobs. It uses the Compatibility/OpenGL renderer; both official
iOS compilation documentation and the pinned platform configuration limit the
Simulator to that renderer. This does not test device Metal or GPU performance.

All generated files stay under `godot/ios-host/build`:

- `upstream`: dependency checkout and generated build objects.
- `scons-cache`: reusable SCons object cache, keyed by the pinned source/toolchain/build inputs.
- `evidence`: source audit, tool versions, build log, archive hash/size, and symbol inventory.
- `artifacts/libpartydeck_godot_ios_probe.a`: combined native archive for the later host link.

The engine stage checks for the actual iOS bootstrap/finish symbols and probe
view-controller class. Its receipt explicitly records
`ios_runtime_executed: false` and `kmp_factory_qualified: false`.

The manual workflow's future `test` stage must compile and launch a separate
SwiftUI application, render a real Godot scene inside its child view, exercise
native input and the frozen bridge, pause/resume, and observe cleanup while the
host remains responsive. Until that harness is present, requesting `test`
fails after engine compilation rather than reporting an execution pass.

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
- [SCons wheel metadata](https://pypi.org/pypi/scons/4.11.1/json).
- [Open iOS view proposal](https://github.com/godotengine/godot-proposals/issues/1473).
- [Open native-window proposal](https://github.com/godotengine/godot-proposals/issues/14435).
