# Independent review of the frozen frame reconciliation

No source blocker was found in the frozen implementation. This review is by `/root/ui_shell`; it did not edit the renderer or independently execute the owner's 111-check suite. The reviewed bytes are copied under `sources/`, with the owner's freeze hashes verified in `provenance.json`.

The new boundary removes the specific application path found in run 34439587132: focus and bridge callbacks replace the table's CPU state and set bounded flags, while main's always-processing callback rereads the latest controller state and performs scene/resource changes. Neither table subscribes directly to the controller's state signal. There are no queued private-state dictionaries to replay after a background burst.

Pinned Godot 4.7.2 source supports this placement. `OS_Android::main_loop_iterate` always calls `Main::iteration` from the GL draw callback; low-processor mode decides whether to draw/swap afterward. `SceneTree::process` processes nodes before its final message/transform/accessibility flush. `Node::_can_process` permits `PROCESS_MODE_ALWAYS` while the SceneTree is paused. `Main::iteration` processes that tree before RenderingServer synchronization/drawing. The project uses the normal main rendering thread and neither scene selects a worker process group. Thus the new callbacks run in the context-valid engine step, unlike the Android GL event queue that could run before EGL surface restoration.

Reviewed behavior:

- The controller still immediately conceals the hand, clears selection, rejects background/closed input, and advances its admitted revision. Each existing table immediately replaces its CPU snapshot with the sanitized current publication.
- Main mounts and applies the presentation before releasing the single retained Ready document. Close clears pending Ready, and failed initialization emits Failed without releasing the held Ready. The unchanged protocol gate permits increasing, noncontiguous sequence numbers.
- The always-processing main drains closed/background state even while the table itself is paused. Its closed-state branch removes the presentation before any later draw. Guards reject commands after tree exit or queued deletion.
- Both tables now defer history, lobby-dialog, resize, and feedback construction to frame reconciliation. Their current-control checks reject input from an unapplied revision; detached or queued-for-deletion button callbacks also check node lifetime. Controller checks still decide whether the action is allowed.
- Scroll/focus continuations run on engine `process_frame`, with tree/lifetime/current-layout checks. They are not dispatched from the Android event queue. The quiet flag survives a brief foreground loss followed by regain before the next frame, so coalescing does not silently retain existing playback.
- The added regression assertions cover deferred mounting/Ready, synchronous privacy/input rejection, no callback-time hierarchy mutation, paused bursts, stale controls, deferred dialog/history changes, brief audio loss, Close winning over pending reveal, and failed or closed initialization. Their registry doubles are explicitly desktop tests and do not impersonate executed Android EGL/JNI.

The existing native cover remains necessary until the concealed latest state has been reconciled. Each plugin `onGLDrawFrame` callback runs after `GodotLib.step` and before EGL swap; the existing two-callback gate must not be described as direct evidence of two buffer swaps. Under low-processor mode the step can occur without a draw. The native captures and strict process-log checks remain the qualification gate for actual resume behavior.

The qualifier change is compatible with this boundary: it no longer requests diagnostics before the guarded foreground-draw callback, rechecks readiness when the scheduled request executes, and retains the existing 2,000 ms response timeout. No checker assertion or native timing limit was relaxed.

The normal-text 2D Reveal clipping is a separate layout observation. Initial and resumed captures differ in content scroll, and that issue is being probed in an isolated source copy. It is not a blocker to the source correctness of this frame dispatch correction, and no clipping change is included in the reviewed hashes.
