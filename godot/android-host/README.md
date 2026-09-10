# Android Godot comparison host

This standalone app offers **Play Last Light · 2D** and **Play Last Light · 3D**.
Both load the real shared Godot project and use `QualificationAuthorityDriver`
with the existing Last Light rules. The shipping `androidApp`, its networking,
and its Compose game catalog are separate.

Normal practice uses Android `SecureRandom`. **Use the reference match** is an
explicit chooser option that uses the audited seed `2` and the same four-seat
roster for reproducible comparisons. The seed never enters a renderer document.
The reference option does not persist; normal launch remains random. Reduced
motion and sound preferences persist in this app's private preferences.

## Build and run

From the repository root, with the Android SDK configured:

```sh
python3 godot/tools/renderer.py pack --godot /opt/partydeck-godot/godot
env ANDROID_HOME=/opt/android-sdk flock /tmp/partydeck-gradle.lock ./gradlew \
  -p godot/qualification :androidHost:assembleDebug :androidHost:testDebugUnitTest --console=plain
adb install -r godot/qualification/build/modules/androidHost/outputs/apk/debug/androidHost-debug.apk
adb shell am start -n dev.partydeck.godot.compare/.ComparisonActivity
```

The generated asset task verifies the canonical pack and source freshness before
copying only `partydeck-last-light.pck` into Android assets. The pack receipt is
build evidence, not a shipped asset. Godot receives the fixed native arguments
`--main-pack res://partydeck-last-light.pck --rendering-method gl_compatibility --xr-mode off`.
No external intent supplies a filesystem path, engine arguments, or a view.

XR is disabled explicitly because this comparison uses conventional 2D/3D views.
In Godot 4.7.2, the Android renderer-selection path reads `xr/shaders/enabled`
before that setting is registered and logs a missing-property warning at error
severity. The supported `--xr-mode off` option bypasses that lookup. Setting the
project value to its default `false` is insufficient because export omits default
values; the engine error checks remain strict.

Native input/background/re-entry checks live in `../android-checks/`. A successful
APK build or a Godot setup callback alone does not establish runtime acceptance.

## Native ownership and threading

`ComparisonActivity` runs in the default app process and never initializes a
Godot singleton. Its non-exported `GodotGameActivity` runs in `:godot` and hosts
an actual AndroidX `GodotFragment`, implementing `GodotHost`. A per-process guard,
single-top Activity and disabled chooser buttons prevent a second live host.
The chooser requires the old engine process to disappear before another launch.

One main-thread authority owns the entire local practice match. This is an
isolated practice host, **not** online session integration: putting a shipping
network authority in the KMP shell would require a separately designed process
boundary and native session ownership. This app declares no network permission.

`getHostPlugins()` registers one runtime `PartyDeckBridgePlugin`; there is no
manifest plugin auto-discovery entry. Exact Godot singleton surface:

| Member | Meaning |
| --- | --- |
| `get_launch_document(): String` | Frozen recipient-safe launch, retained before scene subscription |
| `renderer_event(document: String)` | Strict Ready, intent, exit or failure event |
| `command_received(document: String)` | Signal for a safe view, foreground change or close |
| `get_display_scale(): Double` | Android `displayMetrics.density`, independent of font scale |
| `diagnostics_requested(request_id: String)` | Optional read-only qualification signal |
| `renderer_diagnostics(document: String)` | Correlated geometry/privacy evidence; never an authority input |

The scene connects signals before reading the launch document. Native code keeps
outgoing delivery paused until native setup **and** an accepted renderer Ready.
Events are capped at 4,096 UTF-8 bytes, diagnostics at 16,384, and launch/commands
at 65,536. A 32-item incoming FIFO has one main-thread delivery in flight. A
16-item outgoing FIFO has one render delivery in flight; it waits until after
Godot's own queued `nativeEmitSignal` before releasing the next item. Overflow
terminates the comparison. Queued work rechecks the current lifetime.

The adapter binds the trusted recipient and validates protocol, presentation,
sequence, revision, foreground state, action availability and own-card selection.
Only the core authority can apply an action. Other seats use the authority
driver's bounded policy with their own safe projections. Native bot activity
has a distinct evidence counter from accepted player intents.

## Privacy and lifetime

A native opaque cover blocks game input and hides its accessibility descendants
before `onPause`, focus loss or Close. The adapter rejects background actions
synchronously, while Godot receives its coarse foreground signal asynchronously.
On entry/return, the cover waits for the current foreground command's native
delivery and two subsequent `onGLDrawFrame` observations. An older foreground
epoch cannot uncover a newer background/close. Actual buffer presentation and
absence of private-face flashes still require the runtime capture checks.

API 33+ disables Recents screenshots with `setRecentsScreenshotEnabled(false)`;
foreground comparison screenshots remain possible. API 26–32 keeps `FLAG_SECURE`
for the game window, so external screenshots are intentionally unavailable.
The native cover supplements that platform protection. Godot clears local hand
reveal/selection and stops feedback when backgrounded.

Close invalidates the authority and incoming bridge immediately, replaces waiting
commands with a terminal Close, and allows at most 250 ms for native delivery.
It then calls upstream `Godot.destroyAndKillProcess()`. The final app-private
evidence write precedes killing **only** `:godot`; the chooser remains alive.
No engine restart in an existing process is claimed. Activity recreation ends
the transient comparison instead of restoring a stale Fragment/session.

The public Godot plugin API cannot cancel the final JNI signal Runnable already
queued inside `emitSignal()`. At most one such emission is in flight; closed
authority gates reject its callbacks, the native cover stays up, and the process
is disposed. This limitation is not represented as cancellable same-process
native teardown.

Cloud backup and device transfer are explicitly disabled for app files and
preferences with the Android 12 extraction rules, alongside the older backup
flags. Qualification evidence and a previous practice choice are not restored
onto another installation.

The upstream renderer-exit wait is 1,500 ms and may force-quit on timeout. Both
ordinary termination and that fallback can invoke the same public callbacks.
`nativeTerminating`, `nativeForceQuitCallback` and elapsed-time evidence therefore
do **not** prove graceful cleanup by themselves. Runtime checks also reject
the upstream log `Unable to exit the renderer within ... Force quitting the process`.

## Evidence and native controls

Debug `run-as dev.partydeck.godot.compare cat files/godot-qualification.json`
reads a single atomic, app-private snapshot. Writes run off the main thread;
only the latest unwritten snapshot is retained. Nothing is exported by a provider
or logged as a game document. Counters/revisions are exact decimal strings.

Stable native resource IDs: `launch_2d`, `launch_3d`, `reference_scenario`,
`reduce_motion`, `sound_enabled`, `chooser_status`, `host_status`, `exit_game`,
`refresh_diagnostics`, `engine_container`, `privacy_cover`, `native_notices`.

Evidence includes presentation/mode/PID/task identity; `readyAccepted`; separate
received/accepted intent and bot counters; current revision; native lifecycle,
cover and teardown observations; and a public summary of phase, round, hand
**count**, available actions and legitimate outcome flags. It includes no card
rank/ID, opponent hand, future outcome, random state, credential or raw event.

`diagnosticsRequested` and `diagnostics.requestId` correlate an explicit native
**Refresh status** with the actual scene response. Requests are coalesced to at
most two per second, with one in flight and a two-second timeout. Diagnostics
pass the shared strict JSON preflight before Android's permissive `JSONObject`,
then an exact typed allowlist. Stale presentation, request, revision and sequence
are rejected. There are at most 32 control records, each with a known group,
card index, visible/enabled/selected flags and bounded finite `rect`/`clipRect`.
`rect` is the whole button; `clipRect` is the root viewport intersected with all
clipping ancestors, so the checker can reject obscured taps. Private
face/label **counts** come from real scene nodes.

The renderer viewport/rectangles use Godot root-viewport logical units. Native
`engineSurface` is the actual render view's on-screen position and size in physical
pixels. The checker maps `surface.x + rect.x * surface.width / viewport.width`
(and equivalently for y), accounting for native header/system insets and Android
density. Native text uses Android font scale; renderer `preferences.textScale`
is independently clamped to 1–2.

## Supported scope and upstream sources

This is a portrait-phone qualification app. The exact upstream library guide
states **one engine instance per process** and says automatic resizing/orientation
events are unsupported and can crash. The manifest follows its fixed-orientation
configuration, and runtime size/orientation configuration changes end the table.
Android can override orientation/resizability policies on some form factors;
split-screen, freeform, fold changes and arbitrary surface recreation remain
unqualified. These restrictions do not change the production Compose baseline.

Godot 4.7.2 has no native mobile AccessKit support. The chooser, status, privacy
cover and exit are native accessible controls; Godot card/action accessibility
is an explicit production gate. Geometric test taps are not TalkBack support.

Verified published dependency: `org.godotengine:godot:4.7.2.stable`, paired with
explicit compile dependency `androidx.fragment:fragment-ktx:1.8.6` because Godot's
POM declares Fragment at runtime scope. Runtime plugin annotations are retained
by `proguard-rules.pro` for the independently built optimized variant.

- [Exact Maven POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom)
- [Matching published sources](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable-sources.jar)
- [Official Android library guide](https://github.com/godotengine/godot-docs/blob/4.7/tutorials/platform/android/android_library.rst)
- [GodotHost callbacks and runtime plugins](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java/lib/src/main/java/org/godotengine/godot/GodotHost.java)
- [GodotFragment lifecycle](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java/lib/src/main/java/org/godotengine/godot/GodotFragment.java)
- [Godot teardown and render dispatch](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java/lib/src/main/java/org/godotengine/godot/Godot.kt)
- [Upstream Activity explains process restart](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java/lib/src/main/java/org/godotengine/godot/GodotActivity.kt)
- [Plugin reflection, emitSignal and draw hooks](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java/lib/src/main/java/org/godotengine/godot/plugin/GodotPlugin.java)
- [Android renderer selection and XR lookup](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/android/java_godot_lib_jni.cpp#L539-L550)
- [Supported XR mode launch option](https://github.com/godotengine/godot/blob/4.7.2-stable/main/main.cpp#L1991-L2008)
- [XR shader setting default](https://github.com/godotengine/godot/blob/4.7.2-stable/servers/rendering/rendering_server.cpp#L3812-L3814)
- [Project export skips settings equal to their default](https://github.com/godotengine/godot/blob/4.7.2-stable/core/config/project_settings.cpp#L1255-L1276)

**Open source notices** on the native chooser exposes the exact bundled Godot,
LLVM/libc++ and font texts, and the MPL certificate source-availability note with
an offline copy of the unchanged source. The short notes appear before full
license/source files, and each file can be opened separately without an engine.
The AndroidX/Kotlin/kotlinx and transitive notices include a mapping for all
41 distinct resolved external artifacts. Reviewed source, extraction and byte
hash provenance is in `docs/runtime-notices-provenance.json`.

## Verification status

Owner `compileDebugKotlin` and `testDebugUnitTest` passed against the actual AAR;
four focused tests cover retained startup messages, stalled-consumer bounds,
closed-lifetime callback rejection and terminal delivery acknowledgment. Those
tests do not substitute for the independently owned native input, rendering,
background, close/re-entry, process-death and optimized-package qualification.
The corrected `lintDebug` and current four unit tests passed together in 11 seconds
on 2026-09-10, with zero lint errors and eight classified warnings.

The first full lint pass identified an API-27 navigation-bar style in the
API-26 base resource; it is now isolated in `values-v27`. Remaining expected
lint warnings concern the explicitly chosen target36, the Godot-matched
Fragment1.8.6 pin, isolated literal dependency declarations, and Godot's
documented orientation/resizing limitations. None of those checks is suppressed.
