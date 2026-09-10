# Retained iOS engine contract

This is the source contract for the next qualification milestone. Native
same-process re-entry has not passed yet. The successful five-case `ProbeHost`
gate remains the separate one-shot policy: `PDGodotRuntime.close()` performs
terminal full cleanup, and another engine initialization is refused.

## Ownership

The comparison shell owns one `PDGodotEngineOwner`, which retains one initialized
engine, controller, view and rendering layer for one fixed verified PCK. A
`PDGodotPresentation` is a disposable handle bound to a monotonically increasing
native generation. Each entry has a new Kotlin facade, presentation UUID,
revision/sequence gate, container and entire renderer scene. No old handle can
send commands, change foreground, close or receive events for a later entry.
The qualification owner rejects reused identifiers and caps issued handles at
1,024 per process. Lifecycle epochs advance before native callbacks reach the
common authority; a queued delivery must carry the epoch captured at enqueue.
The authority confirms Ready through its own latch after accepting the actual
renderer event. Stale command delivery cannot consume that confirmation.
Production uses `deliverDocument:lifecycleGeneration:confirmReady:completion:`:
the native drain rechecks the captured epoch, delivers through the actual scene
bridge, then confirms Ready and completes outside draw/engine scopes. The
older `sendDocument` return value means queue admission only. Cancelled work
drops private documents immediately and completes false at the next safe drain.
Native terminal loss has a separate unsequenced failure callback; it never
fabricates an authority event sequence. Close completion succeeds only after
the dormant observation.

Application activity and background state are distinct facts. An inactive
foreground alert has `applicationBackgrounded=false`. The owner accepts both
facts together and exposes `lifecycleGeneration`, `nativeForeground` and
`applicationBackgrounded` in its snapshot. Public lifecycle epochs change with
native facts; the common authority's wire foreground grant is separate and
cannot remove a native application/interruption cover. A current restrictive
wire grant is valid during a common lifecycle transition. Input generations
also advance across effective foreground changes, rejecting old gestures.

The retained engine may keep generic fonts, textures, buffers, workers and other
engine allocations. Dormancy does not mean zero memory use, engine
reinitialization, secure heap/GPU erasure or a shipping KMP factory.

## Leave and re-entry

1. Synchronously close the old native/authority gates, cover UIKit and hide
   accessibility, disable input producers, clear queued documents, diagnostics
   and handler closures, and invalidate the presentation generation.
2. Wait for a main-thread boundary outside draw, engine, delivery,
   `Main::is_iterating()` and deferred-flush scopes. Send the existing renderer
   close while its scene still exists. Stop feedback and native audio/motion.
   Scene/GPU teardown requires an active application and the retained native
   EAGL context; a background close covers and stops services immediately, then
   waits for activation before issuing OpenGL work.
3. Use the maintained [iOS-only main-loop access wrappers](patches/main-loop-access.patch)
   to call the pinned private `OS_AppleEmbedded` delete/set operations. Finalize
   and delete the complete old SceneTree before constructing its replacement.
   Immediately install and initialize an empty fresh
   SceneTree with the same fixed root-window settings and native-owned quit
   policy. The native view/layer stays alive and registered with the display
   server. There is no null-main-loop interval across asynchronous turns.
4. Drain input and ordinary deferred work while no recipient scene exists,
   retire already-stopped audio playbacks, and present a neutral empty-tree frame
   under the cover. Verify old scene ObjectIDs are absent, the tree has only its
   root, bridge connections/queues are empty and no private document or callback
   remains. Stop the display link, detach the native surface, restore the
   shell's actual prior idle-timer policy and observe audio callback quiescence
   across a native-shell interval before reporting `dormant`.
5. On entry, attach the same retained surface under a cover. Perform a covered
   iteration on the empty tree before installing `res://main.tscn`; this consumes
   idle elapsed time without running a new scene's animations with that delta.
   It is not a reset of Main's private timing state. Instantiate a fresh whole
   scene, deliver only its launch projection, deliberately unpause it, and
   require its own Ready and completed concealed draw before accepting input
   and removing the cover.

`Main::start()`, `SceneTree.quit()`, `Main::cleanup()` and
`apple_embedded_finish()` are not re-entry mechanisms. Full engine cleanup
remains terminal. Any incomplete teardown or service-suspension failure keeps
the surface covered, quarantines the owner and refuses later entries.
For an in-app pause, one covered frame applies the renderer's deferred concealed
state without restarting audio. Background OpenGL work remains prohibited.
The host owns the pinned draw-loop boundary and rechecks activity after its
nested UIKit run loop before touching the layer. UIKit layout only requests
work; actual layer/buffer layout runs at a safe active drain with the retained
context. The draw path checks context assignment before binding the layer's
published native FBO. A frame qualifies only after observing the engine's
drawn-frame counter advance, checking the actual drawable attachment, and
checking `EAGLContext.presentRenderbuffer`'s result. Covered frames force redraw
despite the project's low-processor mode. A failed presentation quarantines
the owner. Concealment diagnostics must follow scene reconciliation, and a
later successfully presented frame precedes uncovering. Covered foreground
sampling has a finite attempt limit and fails explicitly if concealment never
appears.

## Fixed-content deferred-work limit

The verified pack has no autoloads, script static variables, worker tasks,
SceneTree timers or recipient-bearing shared resources. Its tweens are node
bound and explicit deferred calls target scene nodes. Whole-scene destruction
clears suspended GDScript await states and invalidates those deferred Node
ObjectIDs; ordinary engine dispatch releases their queued arguments.

Use the existing MessageQueue flush and normal covered empty-tree frames, with
a finite number of drain attempts and residual-work checks. Never clear the
global queue. This is an audited fixed-content path, not a hard execution-time
or callback-count bound for arbitrary scripts: upstream `flush()` can execute
work appended by callbacks during that same flush. Adding persistent scripts,
plugins, workers or recipient-capturing global callables invalidates this
qualification contract and requires another source review.

## Services

The supported `sdl=no` build option excludes SDL joystick/gamepad input and its
independent event producers from this touch/keyboard qualification. The source
sets SDL's joystick-thread hint, but that alone does not prove a joystick thread
runs on iOS. The native subclass gates touch and
hardware-key sequences by accepted begin event and lifetime generation.
Upstream focus loss can dispatch buffered input while the old tree still exists,
after the native/authority gates close. The explicit retirement and re-entry
input drains run against the empty tree. The retained controller does
not create a Godot software keyboard for a game with no text-entry controls.

The pinned view's real `motionManager` getter exposes its CMMotionManager. The
owner stops device-motion updates and observes `isDeviceMotionActive`; an
unavailable simulator sensor is recorded as unavailable rather than tested.

CoreAudio is the only accepted audio driver. A narrow maintained iOS patch must
observe its actual active flag, start/stop attempts and OSStatus, callback entry
count and in-flight callbacks, including callbacks which only return silence.
Dummy fallback cannot qualify as suspended CoreAudio. AudioServer playbacks
marked for deletion can otherwise survive stopping the AudioUnit. The proposed
owner-only retirement hook runs on the main thread after successful stop and
zero in-flight callbacks. It rechecks those facts under the selected driver's
lock, preflights all of at most 64 live builtin WAV playbacks, accepts only
already-stopped playbacks and uses the existing deletion helpers. It rejects
unexpected streams, native sample playback, audio input, callbacks or effects.
All SafeList iterator scopes end before destruction; checked cleanup runs on
the main thread outside the driver lock and covers both bus-detail graveyard
generations. The live-playback cap is not a hard total-work bound on those
graveyards. Existing bus sample buffers and pending mix offset must be neutral
before a later AudioUnit start. The active flag and callback observations must
be atomic, including callbacks that only return silence. The exact patch and
provenance are reviewed separately before native qualification.

Foreground or audio-interruption recovery may resume Godot only while a current
presentation and the application both permit it. The export-owned Godot app
delegate is never installed. One owner-lifetime interruption observer preserves
Begin/End facts across native-shell intervals; dormant notifications perform
no renderer delivery, scene work or service resume. Its registration generation
rejects obsolete callbacks after terminal removal. Presentation event/lifecycle
callbacks remain bound to their disposable handle. The common close gate also
stops motion after partial initialization or quarantine.

## Evidence required

The separate retained suite must demonstrate shell → 2D → shell → 3D → shell
in one process, fresh UUID/generation/facade/scene on each entry, real renderer
input and Ready, no stale-handle mutation, cleared private bindings, stable
engine/view/layer identity, stopped display link/audio callbacks/motion while
dormant, and native-shell responsiveness. Foreground and interruption events in
the shell must keep Godot dormant. Failure and terminal cleanup remain explicit
separate outcomes. Receipts identify the exact engine patch, native module,
Kotlin framework, pack, executable and executed test cases.

## Checked upstream source

All findings use Godot `ed1daf0bf001b61586d9930840f2f1394092c079`:

- `drivers/apple_embedded/os_apple_embedded.mm`: main-loop deletion and lifecycle.
- `scene/main/scene_tree.cpp`: initialization/finalization, pending scenes,
  timers/tweens and whole-scene replacement.
- `scene/main/window.cpp`: root-window enter/exit and display callback binding.
- `modules/gdscript/gdscript.cpp`: destruction of pending function states.
- `core/object/message_queue.cpp`: normal deferred dispatch and lack of a bound.
- `core/input/input.cpp`: buffered dispatch and pressed-state release.
- `main/main.cpp`, `main/main_timer_sync.cpp`: current-loop lookup, root setup
  and retained timing state.
- `drivers/apple_embedded/godot_view_apple_embedded.mm`: rendering and motion.
- `drivers/apple_embedded/godot_view_controller.mm`: keyboard input forwarding.
- `drivers/sdl/joypad_sdl.cpp`, `platform/ios/detect.py`: joystick thread and
  supported build exclusion.
- `drivers/coreaudio/audio_driver_coreaudio.mm`,
  `servers/audio/audio_server.cpp`: actual AudioUnit and playback lifetimes.
