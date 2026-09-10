# Last Light renderer prototypes

This real Godot 4.7.2 project contains both the 2D and 3D Last Light presentations. The Kotlin shell owns authority, navigation, networking, preferences and lifetime. The same scenes serve the standalone comparisons and the implemented Android/iOS session adapters. Mobile Godot styles remain behind explicit qualification profiles; Standard table remains the shipping default.

## Run

From the repository root, use the verified editor installed by [the packaging tools](../tools/README.md). The development installation used for Linux evidence is `/opt/partydeck-godot/godot`, verified against the official archive and release checksums. Exporting a resource PCK does not require the separate 1.28 GB export-template archive.

```sh
flock /tmp/partydeck-godot.lock /opt/partydeck-godot/godot --headless --path godot/renderer --editor --import

/opt/partydeck-godot/godot --path godot/renderer -- \
  --presentation=2d --launch-file="$PWD/godot/bridge/fixtures/launch-2d.json"

/opt/partydeck-godot/godot --path godot/renderer -- \
  --presentation=3d --launch-file="$PWD/godot/bridge/fixtures/launch-3d.json"
```

Close one preview before opening the other. A standalone fixture allows local reveal, selection and concealment; submitted intents have no authority loop. For a playable match or an automated full-match comparison, use [the JVM authority runner](../comparison/README.md). To choose either style in an existing mobile session, follow [the session preview instructions](../README.md#build-isolation). Use [the packaging commands](../tools/README.md) to produce and verify one PCK containing both presentations.

## Runtime boundary

The frozen wire schema is [CONTRACT.md](../bridge/CONTRACT.md). The root scene exposes `receive_document(String) -> bool` and emits `bridge_event(String)`. Connect the event signal before injecting launch. `--manual-bridge` suppresses fixture/native auto-launch for an embedding driver.

An Android `PartyDeckBridge` singleton supplies `command_received(String)`, `get_launch_document() -> String`, and `renderer_event(String)`. Optional prototype diagnostics use `diagnostics_requested(String requestId)` and `renderer_diagnostics(String)`. The native host's display density is supplied separately through `get_display_scale()`, independent of the wire preference `textScale`. Desktop preview units remain unchanged. The iOS host can call the same root method/signal through its own native module.

The controller strictly validates input before mutation. Revisions and sequences are canonical decimal strings through `Long.MAX_VALUE`; Godot's permissive JSON decoder and floating-point number representation are not used to validate those counters. Unknown fields, duplicate members, malformed Unicode/numbers, oversized input and invalid safe-view references are rejected. A fresh presentation lifetime requires a new root/controller.

Each presentation implements `bind(controller)`, CPU-only `store_state(state)`, and frame-only `apply_state(state)`. The main scene owns reconciliation. Controller changes immediately replace the table's latest CPU snapshot and mark one pending update; an always-processing `_process` reads the controller's current state and updates scene resources. No private state snapshots are queued for later replay. Local history, lobby, resize and sound callbacks also request frame work. Button callbacks reject a newer controller revision until that view has been applied to the scene, and reject detached or closing owners.

Every new view, foreground loss and Close synchronously conceals the controller's hand and clears selection. Concealed CPU hand entries have no rank binding; terminal state discards the private hand. The next engine frame removes old private scene bindings, stops grouped sound and pauses presentation processing as needed. A brief foreground loss remains latched for audio shutdown even if foreground returns before that frame. Close takes precedence over pending presentation work, and Ready is released only after a successful initial frame reconciliation. No presentation resolves truth, penalty, randomness or a winner.

Native hosts own the immediate opaque cover before platform snapshots and must keep it over the old surface until command delivery and a fresh reconciled foreground frame have completed. In pinned Android Godot, an event queued on the GL thread can execute before EGL restores its current surface; being on that thread alone does not authorize scene resource work. Actual native engine teardown and retained-engine qualification remain host responsibilities.

A locally permitted lobby return keeps its event immediate and suspends new draw work while the host decides. The pending page retains its resources instead of rebuilding them ahead of the host's queued Close. The controller remains open to a valid newer view, foreground cancellation or Close; those paths and scene removal restore the exact previous `RenderingServer.render_loop_enabled` setting. The property setter only stores a CPU Boolean, so this change stays safe in the existing state callback. It does not acknowledge Close, extend native deadlines or guarantee that Android performs no EGL swap.

## 3D construction

The table uses an orthographic Camera3D in a real SubViewport, a bounded set of CylinderMesh/BoxMesh/PlaneMesh instances, one light, and no shadows or postprocessing. Card faces are wordless original PartyDeck textures with independent upright rank labels. Projected Control hit targets drive the shared controller; play never requires precision mesh picking or dragging. Selection uses a visible check and border with an optional 140 ms lift. Reduced Motion shows the settled state immediately.

Short landscape uses a table plus a scrolling information panel; compact or enlarged text uses scrollable controls with the table rank, current actor and hand toggle pinned above them. Selection preserves scroll and keyboard focus, keeping the focused card inside the visible area after feedback reflows the layout. Reused raster card/rank assets, original vectors, licensed fonts and generated audio are inventoried in [assets/manifest.json](assets/manifest.json). Full engine/native notices are in [licenses/README.txt](licenses/README.txt); font notices are under `assets/licenses/`.

## Verification and limits

The 3D source checker captures actual OpenGL frames and routes mouse motion/press/release through the engine. It checks local reveal/selection/cover/background and public-card projection, without simulating an accepted action:

```sh
flock /tmp/partydeck-godot.lock xvfb-run -a \
  /opt/partydeck-godot/godot --path godot/renderer \
  --rendering-method gl_compatibility --audio-driver Dummy \
  --script res://tests/three_d_scene_check.gd -- --manual-bridge \
  --check-fixture=/absolute/path/to/godot/bridge/fixtures/launch-3d.json \
  --check-output=/absolute/path/to/new-evidence-directory \
  --check-width=390 --check-height=844 --check-text-scale=1
```

For a compact scrolling layout, add `--check-touch-drag=true` to check emulated touch dragging from a card and taps with slight motion. With a fixture that grants live-match host permission, `--check-lobby=true` checks confirmation, cancellation and the single confirmed return intent. These flags extend the local input check; native touch and authority acceptance have separate runners.

Static scene checks, full authority runs, pack checks and native checks have separate evidence. Reviewers independently executed 61 strict-parser cases and 107 actual-controller checks; see [the bridge review](../reviews/bridge-review.md). Every captured/reviewed app image is preserved by the repository screenshot gallery, including superseded visual iterations.

Linux captures use Godot 4.7.2, OpenGL Compatibility, Mesa llvmpipe and Xvfb. They establish real rendering/input on that stack. Mobile screen readers, native snapshot timing, touch feel, device GPU/frame-time budgets, sustained memory and physical-network behavior require their own platform execution. Tagged Godot AccessKit support is desktop-only; Control semantics do not establish TalkBack or VoiceOver support. The native accessible controls path remains a production gate.

## Checked sources

- [Official Godot 4.7.2 release](https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable) and [release checksums](https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt).
- [Camera3D](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Camera3D.xml), [BaseMaterial3D](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/BaseMaterial3D.xml), and [SubViewport](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/SubViewport.xml) for actual scene APIs.
- [JSON](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/JSON.xml) and its [implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/core/io/json.cpp) for strict-preflight and exact-counter requirements.
- [Control](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Control.xml), [Window](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Window.xml), and [CanvasItem](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/CanvasItem.xml) for responsive layout, native display scale and root-viewport diagnostics.
- [RenderingServer.force_draw](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/RenderingServer.xml) for a fresh static-scene capture under low-processor mode.
- [RenderingServer implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/servers/rendering/rendering_server.cpp) for the CPU-only render-loop flag and [Android iteration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/android/os_android.cpp) for the independent EGL-swap decision.
- [Android GLSurfaceView](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/android/java/lib/src/main/java/org/godotengine/godot/gl/GLSurfaceView.java) and [GodotRenderer](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/android/java/lib/src/main/java/org/godotengine/godot/gl/GodotRenderer.java) for event-queue ordering, EGL surface creation and frame callbacks.
- [Main iteration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/main.cpp), [SceneTree processing](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/main/scene_tree.cpp), and [Node process modes](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/main/node.cpp) for frame reconciliation before draw, buffered input before scene processing, and processing while paused.
- [Design review and mobile support evidence](../reviews/design-review.md) for shared readability, input, privacy and platform acceptance.
