# Session-backed Android Godot transport

`AndroidGodotPresentationHost` implements the common presentation factory seam. Its caller supplies the modes allowed by the packaged activation profile. Shipping exposure requires recorded qualification; the checked-in shipping list remains empty. Creating a factory is inert; `open` captures the selected 2D/3D mode and launch preferences, requires shell-owned sound (`soundEnabled=false`), and encodes the existing recipient-safe `EngineLaunch` with `LastLightWireCodec`.

The explicit build property `-PpartydeckGodotQualificationModes=2d,3d` enables both modes for qualification through the same picker and session path. The build writes the profile and canonical mode list into manifest metadata; malformed metadata fails closed. The runtime does not accept an activation override from an Intent or preference. CI's production-session opt-in passes this property before packaging and verifies the actual APK metadata against its recorded build expectation before executing the unchanged session checker. A qualification profile does not grant shipping acceptance.

The shell retains the controller, runtime, projection adapter, single renderer-event gate, and authority submission path. These Android classes never construct a session authority or qualification driver. Renderer actions remain typed `EngineEvent` values consumed by the common coordinator. Transport acknowledgements cannot acknowledge a game action or authority receipt.

| Component | Process | Responsibility |
| --- | --- | --- |
| `AndroidGodotPresentationHost` / `GodotPresentationSession` | shell | Factory, bounded command/event transport, registration and retirement |
| `GodotSessionBrokerService` | shell | Private explicit binding to the already-registered presentation |
| `SessionGodotActivity` / `GodotRendererConnection` | `:godot` | Covered native attachment, lifecycle facts, command delivery, native teardown |

The manifest must keep the service and Activity unexported, put only the Activity in `:godot`, and use the real shared Android renderer library and packaged Last Light PCK. Availability is empty while another registration is active or retiring. An absent registration after shell process recreation produces a null binding; launch extras cannot restore authority or a private hand.

## Binding and bounded admission

The shell installs one fresh presentation ID and 32-byte random handoff token before launching the child. Activity extras contain only that ID and token. The covered child binds with `BIND_AUTO_CREATE` and an explicit service component. The service binding action includes the nonsecret presentation ID: extras do not distinguish Android binding interfaces and must not be used for `onBind` / `onUnbind` routing. Each unbind callback is attributed to its exact action/registration; an old unbind cannot close a newer presentation.

The child sends HELLO with its reply Messenger. Both endpoints check `Message.sendingUid == Process.myUid()`, the exact presentation/token, protocol and primitive Bundle field set, and the pinned peer Binder. A second reply endpoint cannot replace the first. Wrong identities are ignored; malformed authenticated traffic closes only that lifetime. Payloads and tokens are never interpolated into diagnostics.

`GodotIpcInbox` intercepts Messenger's virtual `Handler.sendMessageAtTime` call on Binder ingress. UID/identity checks and immutable packet admission happen under one lock. The remote Message is never placed on the ordinary Handler queue. A separate main Handler drains at most eight packets per task, with at most one task scheduled. Admission failure also has one coalesced callback. The retained count/byte budgets include the callback currently executing. Framework transaction allocation/unparcelling occurs before this application boundary; this code does not claim to bound Android's Binder internals.

| Limit | Value |
| --- | --- |
| Launch or command document | 65,536 UTF-8 bytes |
| Renderer event document | 4,096 UTF-8 bytes |
| Retained packets per inbox/outbox | 16, including the in-flight item |
| Command inbox/outbox aggregate | 256 KiB |
| Event inbox/outbox and typed event buffer aggregate | 64 KiB |
| Per-packet accounting allowance | 512 bytes plus document UTF-8 bytes |
| Unacknowledged DATA messages | One per direction |
| Bind / DATA acknowledgement timeout | 10 seconds |
| Native process-death wait from `close()` | 2.5 seconds |
| Child notification wait after native cleanup | At most 2.5 seconds of scheduled main-thread time |

Documents with invalid UTF-16/UTF-8 conversion, unsupported fields, counter overflow, wrong transport sequence or ACK, queue overflow, and delivery exceptions fail closed. These are application quotas, not a claim about exact Binder parcel size. Binder's shared transaction buffer is not a per-message allowance.

The launch document is sent once. Lifecycle/event DATA waits until native accepts that launch behind its cover. The latest pre-bind lifecycle is queued before a native launch callback can publish newer facts or Ready. Command ACK normally follows the plugin's native delivery callback; event ACK means admission to the bounded typed queue. Explicit ACK disposition marks an obsolete command as superseded without pretending it was rendered. One-shot Close, Abort, native-cleanup, Back/Leave, and standard-table controls bypass stalled DATA. Back/Leave requests existing shell exit handling; standard-table closes only the presentation.

## Lifecycle and Ready ordering

`reportLifecycle` advances a nonwrapping generation for every report, including repeated boolean facts. Started/resumed/focused are the actual Android facts, including during closing; a separate closing flag denies input. Pre-bind facts may coalesce, so generations may skip. The session publishes the new generation before the platform lifecycle callback. After applying those facts, the native owner calls `PartyDeckController.refreshPresentationLifecycle(id)`, ensuring a fresh view and foreground command even when effective foreground did not change.

`onOpening(id, deadlineMillis)` supplies the broker's stored elapsed-realtime deadline to the shell visibility owner. This bounds uncertainty while the child is covered and binding/bootstrap has not yet returned lifecycle facts; it grants no input. HELLO at or after the same deadline cannot obtain the launch document. Handler execution still depends on Android scheduling, so elapsed deadline checks also guard a delayed HELLO.

The common coordinator captures `LifecycleBoundEmbeddedGameSession.lifecycleGeneration` when it enqueues each command, before suspension. IPC carries that captured value unchanged. `GodotCommandEpoch` discards commands whose generation no longer matches the child. The first command's Ready confirmation remains latched if that command is superseded; only the first current command passes `acceptReady=true` to the Activity. The common bridge remains the only Ready/event validator.

Native local lifecycle/focus loss immediately conceals the surface, accessibility descendants and input before IPC. The Activity's own generation also invalidates a delivery callback after later local loss. Uncovering requires delivery plus a fresh draw for the current generation. Player intents retain their child lifecycle generation and are dropped if it becomes stale or noninteractive before typed delivery; Ready, Failed, and Exit are retained independently of interactivity. The bounded stream retains initial Ready/Failed until its single common subscriber attaches. Synthetic terminal failure uses a sequence above every observed renderer sequence; exhausted sequence space closes the stream with an exception.

## Retirement and verification limits

Closing immediately clears shell command completions, queued projections/events, and private launch references. The inbox scrubs queued documents while retaining lifecycle/terminal metadata. The child continues reporting actual lifecycle facts during native close. Binder death recipients on both sides are removed on disposal; ServiceConnection loss, binding death, null binding and explicit unbind are handled.

Native cleanup completion is separate from renderer process death. The broker retains the identity and death watch after `NATIVE_CLOSED`, including across normal service destruction. Only reply Binder death, or a definitive failure before any Activity launch, releases the registration and permits another renderer. A late HELLO for a closing lifetime receives Close and never the launch document. A missing or hung child after the close deadline leaves a quarantined registration; it does not fabricate `onClosed`. ViewModel disposal removes the session-owner callbacks while that minimal retirement state remains. Only `SessionGodotActivity` may terminate its own verified `:godot` process after native teardown; the broker never kills a supplied PID or the shell.

Back/Leave can happen before the ServiceConnection callback. After immediate cover and native cleanup, `reportNativeClosed(afterNotification)` briefly retains the binding so a late connection can send HELLO, the pending return control, and native-cleanup notification. `GodotCloseHandshake` permits the main-thread completion callback only after cleanup plus authenticated parent Close, known connection failure, or its bounded notification deadline. Dispose/unbind/finish/own-process exit then run in that callback. Deadline expiry does not claim that the shell received an exit request, and the shell still waits for actual Binder death before allowing re-entry. Failed native teardown retains the Activity's immediate owned-process termination path.

`GodotIpcWindowReviewTest`, `GodotCommandEpochReviewTest`, and `GodotCloseHandshakeReviewTest` cover bounded in-flight accounting, exact ACKs, sequence exhaustion/disposal, superseded commands, retained Ready confirmation, and teardown/notification ordering. Compilation and these plain JVM tests do not qualify Binder scheduling, process priority, native draw/teardown, early-opening Back delivery, repeated Activity entry, accessibility, or real LAN gameplay. Those require instrumented/native/device execution before a mode is advertised as qualified. A service binding is a documented process-priority dependency, not a process-survival guarantee.

Primary platform sources used for this implementation:

- [Android bound services](https://developer.android.com/develop/background-work/services/bound-services) and [process lifecycle](https://developer.android.com/guide/components/activities/process-lifecycle).
- AOSP Messenger UID capture and Handler dispatch: [API 26 Handler](https://android.googlesource.com/platform/frameworks/base/+/android-8.0.0_r1/core/java/android/os/Handler.java), [API 36 Handler](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/os/Handler.java), and [Message](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/os/Message.java).
- Binding-interface identity and callback attribution: [Service](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/app/Service.java), [Intent.filterEquals](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/content/Intent.java), [ServiceRecord](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/services/core/java/com/android/server/am/ServiceRecord.java), and [ActiveServices](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/services/core/java/com/android/server/am/ActiveServices.java).
- [IBinder death handling](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/os/IBinder.java), [ServiceConnection](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/core/java/android/content/ServiceConnection.java), and [TransactionTooLargeException](https://developer.android.com/reference/android/os/TransactionTooLargeException).
