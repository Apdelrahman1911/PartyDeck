# Application controller research and proposal

Owner: application controller implementation stream. Researched and implemented 2026-09-09. The frozen coordination notes and qualification section describe the completed implementation; the illustrative contract fragments preserve the original design rationale. Source files are the final API reference.

## Verified foundations

| Source | Verified behavior | Consequence for PartyDeck |
| --- | --- | --- |
| [Kotlin StateFlow API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/-state-flow/) | StateFlow always has a value, never completes normally, conflates equal values using `Any.equals`, and is thread safe. Errors and completion must be represented explicitly. | Publish immutable `AppUiState` through a read-only StateFlow. Connection loss, shutdown, and recoverable errors are explicit state. Do not use a state collector as a guaranteed delivery channel for every animation or acknowledgment. |
| [Kotlin CoroutineScope API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-coroutine-scope/) | An entity-owned scope must be cancelled when its owner is no longer needed. A parent cancellation cancels its children. `SupervisorJob` can isolate sibling failures. | One explicitly owned controller scope, one child job per active session, and cancellation of session jobs on leave or replacement. Preserve cancellation exceptions rather than presenting them as connection errors. |
| [Kotlin Mutex API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.sync/-mutex/) | Coroutine mutual exclusion is available in common code; Mutex is non-reentrant. | Authority transitions need one serial owner. The implementation uses a bounded event queue, with socket writes outside that owner, avoiding lock re-entry and network waits inside authority transitions. |
| [Android NSD lifecycle guidance](https://developer.android.com/develop/connectivity/wifi/use-nsd) | Discovery is expensive and should be enabled and disabled according to application lifecycle and need. Starting discovery and resolving a found service are separate callback operations. | Browse only during a join/reconnect batch with an invited service identity. Stop after Welcome, exhausted attempts, cancellation, actual background, or leave. Temporary permission-alert inactivity still preserves the initial join. |
| [Kotlin withLock](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.sync/with-lock.html), [coroutineScope](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/coroutine-scope.html), and [cancelAndJoin](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/cancel-and-join.html) | A mutex serializes an action; a lexical coroutine scope waits for its children; cancelAndJoin waits for cancelled work to finish and is itself cancellable. | Use a client-loop lifetime mutex to finish old native cleanup before any replacement loop starts. Run discovery concurrently with connection attempts, then cancel/join it and stop browsing in a NonCancellable finalizer. Discovery exceptions must not abort a working direct invitation. |
| [Kotlin Flow.first](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/first.html) and [withTimeoutOrNull](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/with-timeout-or-null.html) | `first(predicate)` waits for a matching value and cancels collection; timeout cancellation can occur before a resource result reaches its caller. | Wait at most five seconds for the exact invited service after a recoverable transport connection failure, within the existing attempt deadline. Preserve the original full certificate pin and track acquired links through cancellation. |
| [Compose Multiplatform lifecycle](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-lifecycle.html) | Compose provides common LifecycleOwner support. iOS background maps to `ON_STOP`; desktop main-dispatcher support requires the Swing coroutine dispatcher when those lifecycle scopes are used. | Shared UI can observe lifecycle, but transport survival is a separate concern. Platform owners explicitly forward foreground changes. A desktop target must provision its dispatcher if adopted. |
| [Compose Multiplatform ViewModel](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-viewmodel.html) | Common ViewModel support exists. Common `viewModel` creation needs an explicit initializer because non-JVM platforms lack the JVM reflection-based creation path. Shared Compose examples collect StateFlow using `collectAsState()`. | A root ViewModel wrapper is viable, but the controller itself can remain a plain common class with injected dependencies. Avoid a controller per screen and avoid reflection-dependent factories. |
| [Android ViewModel overview](https://developer.android.com/topic/libraries/architecture/viewmodel) | A ViewModel remains until its owner is cleared and survives owner configuration changes. SavedStateHandle is a separate process-restoration mechanism. | Retain the controller through Activity recreation. Do not imply that a retained controller, socket, or host authority survives process death. |
| [Apple application lifecycle](https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle) | Background apps should minimize work; background scenes eventually suspend and may be disconnected to reclaim resources. Foreground/background and final cleanup are distinct transitions. | No guaranteed background host service. Pause bots and feedback in background, then reconnect or resynchronize clients on return. Temporary background must not permanently close the owner. |
| [Kotlin coroutine testing](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/) | `runTest`, TestScope, and TestCoroutineScheduler allow virtual-time coroutine tests. Work on uninjected production dispatchers does not automatically use virtual time. | Inject scope/dispatcher and bot/reconnect timing so critical flow tests remain fast and deterministic. |
| [Java SecureRandom](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/security/SecureRandom.html) and [Kotlin Random](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/-random/) | SecureRandom provides cryptographically strong random output; Kotlin Random is an abstract random-source boundary that can be adapted. | Inject a native CSPRNG-backed Random for every authority output. Seeded deterministic generators are confined to tests and independent practice strategy. Native implementations are reviewed by their platform/security streams. |

Dependency versions belong to the coordinator's verified toolchain lock. This proposal adds no version pins. Current documentation pages can show differing lifecycle versions, so their examples must not be copied into the build independently.

### Frozen implementation coordination

The coordinator approved public contracts in `composeApp/src/commonMain/kotlin/dev/partydeck/app/controller`. `PlatformServices.kt` and `AppUiState.kt` are now the concrete source of truth; the earlier illustrative fragments in this research document explain the rationale. The public implementation constructor is `PartyDeckController(services: PlatformServices, transportFactory: LanTransportFactory, parentScope: CoroutineScope)`. The controller owns a child supervisor job, leaving cancellation of the supplied owner scope to the platform. The Compose entry point is `dev.partydeck.app.PartyDeckApp(controller)`.

Protocol contracts are in `dev.partydeck.session`; the safe game models are in `dev.partydeck.core`. The transport factory is `dev.partydeck.transport.LanTransportFactory`. Its versioned `LanInvitation` encodes the endpoint, pinned certificate SHA-256, session identifier, and room admission secret. The host's invitation is intentionally shareable, whereas a seat's resume credential is never exposed to UI state.

`PlatformServices.gameRandom(): Random` supplies an adapter whose every output comes from the platform CSPRNG. A secure initial seed for Kotlin's deterministic generator is insufficient for secret deck/fuse outcomes; independent security review corrected the original seed-only proposal before implementation. Separately, `secureToken(): String` must return exactly 32 directly CSPRNG-generated bytes encoded as 64 lowercase hexadecimal characters for admission/resume tokens; deriving these secrets from a seeded Kotlin random generator is prohibited. The native services also supply `copyText(String)` and `shareText(String)` for explicit invitation buttons, because the full pinned invite is too long to expect people to transcribe. Clipboard implementations should use their verified native sensitive-content facilities where available.

The native controller methods include `setForeground`, `setBackgrounded`, `setSystemReduceMotion`, `close`, and suspending `awaitClosed`. Foreground means interactive visibility, while background means actual OS background. `requestBack(): Boolean` returns false at Home for native default handling and consumes other Back actions; session Back exposes `leaveConfirmationRequested` in state. Copy feedback is represented by a localizable `UiNotice`, suppressed when the platform already provides its own confirmation. `FeedbackCue.LIGHT_OUT` distinguishes a burned-out fuse from the safe round-end cue. Native scanner capability/result callbacks fill a validated invitation form without joining automatically.

## Ownership and dependency direction

`Compose UI -> PartyDeckController -> session runtime -> pure HostAuthority / byte transport`

The controller owns navigation, editable forms, persisted preferences, foreground state, a single active runtime, pending user actions, and presentation of recoverable problems. It never validates game truth or computes penalty outcomes. The session module owns protocol validation, authentication binding, deduplication, roster/session rules, and player-specific snapshots. The game module owns Last Light rules. The transport owns listeners, sockets, framing, connection state, and its own resource cleanup.

The session authority is synchronous and has no coroutine or transport dependency. The controller package supplies these runtime adapters:

- `AuthoritySessionRuntime`: serialize incoming peer messages through HostAuthority, publish the host's sanitized snapshot, and deliver each outgoing message only to its bound recipient.
- `ClientSessionRuntime`: handshake, retain private reconnect credentials in memory, consume authoritative snapshots, and send typed intents with request IDs and expected revisions.
- Practice is a mode of the same `AuthoritySessionRuntime`: register the human and bots through the same authority using in-memory peer bindings; no sockets and no alternate game rules.

The adapters implement one narrow interface used by PartyDeckController: observed player-visible session/connection state, typed commands, execution-availability transition, and close. Neither raw wire frames nor `GameState` reach Compose. A host possesses the authority internally, but its UI receives precisely the same sanitized `SessionView` shape as a client.

All authority mutations are serialized, with socket IO outside the authority owner. The client's separate connection-loop lifetime mutex protects only connection/discovery replacement: it stays owned until native cleanup finishes, while commands and message processing continue independently. Async completions also carry a monotonically increasing controller session-generation marker; a late join, old collector, or reconnect response cannot revive a session after leave or overwrite a newer session.

## Proposed UI contract

```kotlin
enum class AppScreen { HOME, HOST, JOIN, SESSION, SETTINGS, HOW_TO }

data class AppSettings(
    val displayName: String = "Guest",
    val soundEnabled: Boolean = true,
    val hapticsEnabled: Boolean = true,
    val reduceMotion: Boolean = false,
)

data class AppUiState(
    val screen: AppScreen = AppScreen.HOME,
    val displayName: String = "Guest",
    val joinAddress: String = "",
    val settings: AppSettings = AppSettings(),
    val systemReduceMotion: Boolean = false,
    val connection: ConnectionUiState = ConnectionUiState.Idle,
    val session: SessionView? = null,
    val invitation: HostInvitation? = null,
    val pendingAction: PendingAction? = null,
    val problem: UiProblem? = null,
) {
    val effectiveReduceMotion: Boolean
        get() = settings.reduceMotion || systemReduceMotion
}
```

These are contract proposals, not library APIs. Final type/package names depend on the coordinator's session and transport freeze. Avoid copying the session roster, game phase, or game projection into competing UI fields. `SESSION` renders lobby, game, or results from the authoritative session phase. Settings/how-to opened during a session need a known return destination; pressing Back on a session should request leave confirmation in the UI rather than silently leaving an authority active behind Home.

`ConnectionUiState` distinguishes idle, starting host, connecting, active host/client, reconnecting, and disconnected. Include attempt/retry availability where useful. Practice is explicitly labeled practice. A socket being connected is insufficient to mark the session active: handshake and initial sanitized snapshot must complete first.

`PendingAction` includes action kind and request identity. One in-flight user command disables repeated submissions until acknowledged, rejected, timed out, or reconciled with a fresh snapshot. Maintain IDs privately in the runtime if the UI only needs the action kind. Clear selected cards when they are no longer in the authoritative hand; card selection itself can remain local UI state.

`UiProblem` carries a stable code, unique occurrence ID, and a bounded recovery action such as retry connection, edit invite, dismiss, or return home. Localized copy belongs to the UI. Never render arbitrary peer-supplied exception strings. No private resume token, unrevealed cards, shuffled deck, or credentials appear in AppUiState or logs. A shareable invitation is deliberately displayable; its transport format must remain distinct from player resume credentials.

Proposed public operations:

```text
navigate(screen), setDisplayName(value), setJoinAddress(value)
host(), join(), startPractice()
setReady(value), startGame(), playCards(cardIds), challenge(), nextRound()
leaveSession(), retryConnection(), dismissProblem()
updateSettings(settings), setSystemReduceMotion(value)
setForeground(value), setBackgrounded(value), close(), awaitClosed()
```

`navigate` must not route to a nonexistent session or move to host/join while another runtime remains active. `leaveSession` immediately detaches the visible session and cancels its actions/collectors, then completes bounded departure and resource cleanup. Generation guards prevent those old completions from affecting a later table. Host start and continuation eligibility comes from validated session state; the UI can explain why a control is unavailable without duplicating authority decisions. Future games add feature-specific commands/projections at the session boundary instead of taking over application lifecycle.

## Platform service and lifecycle contract

Proposed public shared service interfaces:

```kotlin
interface SettingsStore {
    suspend fun load(): AppSettings
    suspend fun save(settings: AppSettings)
}

enum class FeedbackCue { CLICK, CARD_PLAY, CHALLENGE, ROUND_END, WIN }

interface Feedback {
    fun play(cue: FeedbackCue, settings: AppSettings)
    fun setForeground(value: Boolean)
    fun close()
}
```

Android and iOS owners agree on this direction. The platform implementation owns native persistence and feedback resources. Only expose settings with working effects. Save small preferences, not full host game state or resume secrets. Loading must not overwrite a newer edit made while asynchronous persistence work was running; saves must be serialized or coalesced so an old write cannot win. Persistence failure preserves the user's in-memory choice and reports that it could not be saved.

The Android owner retains the controller through a ViewModel and reattaches feedback to the current window. The iOS owner is a SwiftUI-retained exported Kotlin handle owning the UIViewController and controller. `scenePhase` forwards both interactive and actual-background transitions; permanent disposal calls close. Controller/runtime cleanup is registered before acquiring resources and runs in NonCancellable finalizers, including when the platform has already cancelled the parent owner scope. `awaitClosed` lets deterministic tests and desktop shutdown wait for cleanup.

`setForeground(false)` immediately conceals private UI, increments a durable privacy epoch, pauses practice bot delays, and stops feedback. It leaves a first LAN join alive while a permission alert is visible. If an alert outlasts the bounded initial handshake, returning interactive automatically retries that unadmitted connection. `setBackgrounded(true)` separately pauses/closes the client connection while retaining its private seat credential; return from actual background authenticates a Resume and accepts a fresh snapshot. Neither event destroys the retained controller.

The coordinator deliberately preserves the host authority/listener across sharing and task switching. This preserves an invitation when native Share opens another app. It does not promise background availability: the OS can suspend the host, peers can time out, and clients reconnect or explicitly retry after it returns. Explicit Leave/close or process death ends the host. Practice stays in memory with bots paused. There is no host migration or promised process-death restoration.

System Reduce Motion is runtime state, supplied by platform observers through `setSystemReduceMotion`; effective motion preference is system request OR user preference. Only the user preference is persisted. Observers and feedback resources are removed/released on final close.

## Host, join, reconnect, and failure behavior

1. Host validates the display name, opens a real transport listener, obtains invitation details, creates SessionAuthority, binds the local host, and publishes a lobby snapshot. Failure closes partially acquired resources and leaves the host form retryable.
2. Join validates the invite through the transport's parser, establishes the connection, completes protocol join, then publishes the initial session snapshot. An abandoned or superseded join cannot publish into a later session.
3. Gameplay always sends an intent, request ID, and expected revision. Actor identity comes from session peer binding, not from an untrusted action payload. The authority provides each player's redacted response.
4. A rejected or stale action surfaces the specific recoverable problem and refreshes state. The controller does not optimistically deal cards or independently advance rounds.
5. On client disconnection, preserve the latest snapshot for context, disable gameplay controls, and attempt bounded reconnect while outside actual OS background. The implemented policy allows five attempts with 0.5/1/2/4/4-second delays, an eight-second connection/admission attempt deadline, and a 30-second retry-window limit. Initial admission permits one bounded attempt within a ten-second window; explicit Retry starts another window. Each attempt can make one exact-service fallback after a network connection failure, within the same attempt deadline. These are application policy limits, not platform guarantees.
6. Reconnect proves the private resume credential, replaces the old peer binding, and receives a full fresh snapshot. Do not blindly replay a queued gameplay action. A lost acknowledgment is reconciled using the session's duplicate-request semantics and authoritative state; an unresolved old action must not block the UI forever.
7. Failure after the retry window offers explicit Retry and Leave. A known ended session, invalid credential, or version mismatch stops retries. Local-network permission denial immediately ends the current batch and its discovery without discarding the seat credential or permanently marking the session terminal; explicit Retry can resume the same seat after permission is restored. Explicit session end clears the private hand, credentials, and game controls; temporary connection loss alone can retain read-only context. Host termination ends the initial architecture's session; starting another lobby is the recovery.

Invitations with a Bonjour/NSD service name start best-effort discovery concurrently with the direct connection. A direct host remains usable when discovery is unavailable or its startup is still suspended. After `UNAVAILABLE`, `TIMED_OUT`, or `IO_ERROR` from transport connection establishment, the runtime waits at most five seconds for the exact invited `DiscoveredHost.serviceName`, then tries that endpoint with the original full certificate SHA-256 pin. It retains the invitation's service identity, session ID, admission secret, and private seat credential; it never substitutes another table based on display name or retries a different endpoint after authentication/permission/protocol failure. A service-only iOS endpoint remains valid because the native driver resolves its service identity. Address-only invitations never browse.

This policy was checked against the actual [callback adapter](../../transport/src/commonMain/kotlin/dev/partydeck/transport/CallbackLanTransport.kt), [Android NSD implementation](../../transport/src/androidMain/kotlin/dev/partydeck/transport/AndroidNsdDiscovery.kt), and [Java connection driver](../../transport/src/javaMain/kotlin/dev/partydeck/transport/JavaLanDriver.kt) with the transport owner. `startDiscovery` completes when browsing starts, while Android resolution finishes later and has a five-second per-resolution deadline. The Java connection driver captures its direct/cached candidates when each connect call begins, so a delayed first discovery result needs the controller's bounded retry. Stopping discovery clears shared results and native caches. Each batch therefore keeps browsing alive through Welcome or failure and stops it in cancellation-safe cleanup; connected play, Home, and actual background do not browse. Old cleanup completes before even a repeatedly replaced retry can acquire a new scan.

| Condition | Controller behavior |
| --- | --- |
| Invalid name/invite | Keep form and edits; identify field-level problem. |
| Host listener fails or join times out | Close partial resources; offer retry/edit. |
| Incompatible protocol or rejected credentials | Explain with a stable problem code; stop automatic retry. |
| Stale revision or invalid turn | Accept authoritative state; clear pending control and present recoverable rejection. |
| Network interruption | Preserve read-only snapshot; disable actions; show bounded reconnect. |
| Host is gone | Offer retry or leave; never show a fake migrated authority. |
| Background/foreground | Pause work that cannot be useful; resume from current state, not elapsed presentation timers. |
| Controller close or session leave | Cancel collectors, delays, retries and pending requests; close listener/peers; ignore late results. |

## Offline practice behavior

Start one local human host and a small fixed bot roster through the same SessionAuthority join/ready/start paths. This is a playable learning mode and also exercises real lobby/game orchestration. It must be visually labeled so it cannot be mistaken for nearby devices.

The bot decision function accepts only its own player-specific projection and an injected random source. It may inspect its hand, public hand counts, the required rank, and the previous public claim. It must never inspect another hand, hidden claim truth, host deck order, or penalty randomness. A forced challenge is obeyed; otherwise choose a legal play or challenge using a small documented strategy. Use separate randomness for bot decisions and game authority so bot scheduling cannot perturb deck/penalty outcomes.

At most one bot action is scheduled for the current turn/revision. After its short cancellable thinking delay, check session generation, foreground state, phase, revision, and active player again before submitting through the authority. A stale bot action is discarded and recalculated. No polling loop and no uncancelled timers remain after leaving practice.

Domain guidance currently proposes an explicit round-end phase following challenge resolution and a host `nextRound` command. Preserve that pause so the human can read the reveal and penalty result. The human host can continue while spectating after elimination. The controller must not bypass the round-end phase or implement its own rule progression.

## Focused acceptance tests

- Real authority practice starts, renders only the human hand, accepts a legal human action, schedules a legal bot turn, and reaches round end/results without an alternate rules path.
- Two rapid taps do not produce independent duplicate actions; rejection clears pending state.
- Leave during a delayed join/reconnect/bot turn closes resources and prevents late state resurrection.
- Client interruption followed by accepted resume restores a new snapshot without replaying a stale move; invalid credentials stop automatic retries.
- Host receives concurrent peer actions serially, sends only recipient-specific views, and safely handles a failed peer send without corrupting the authority.
- Background pauses bot and retry scheduling; foreground recalculates from current state; permanent close cancels all work.
- Settings load/save completion ordering cannot overwrite a later user edit; failure retains usable in-memory settings.

Use fake transport and virtual time for controller edge cases. Integration validation must separately use the real selected transport with at least a host and clients. Native device checks remain necessary for platform lifecycle, local-network permissions, and real reconnection behavior; passing in-memory tests is not evidence that those platform constraints were exercised.

## Implemented qualification

The controller baseline, before invited-service rediscovery was added, passed this focused command after the inactive/background separation:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew :composeApp:jvmTest \
  --tests '*PartyDeckControllerTest*' \
  --tests '*ControllerAdversarialFlowTest*' \
  --tests '*LanMultiplayerIntegrationTest*' --console=plain
```

Result: BUILD SUCCESSFUL in 11 seconds; 18 tests across the selected classes. This also compiled the integrated common controller, Compose shell, and game UI for JVM.

- Eight controller tests cover a complete same-authority practice match and ready lobby return, duplicate taps, bot pause/leave cancellation, late host startup, settings load/write ordering, scanner result isolation, initial permission-alert inactivity, actual-background authenticated resume, and a permission prompt outlasting the initial handshake.
- Eight independently authored adversarial tests cover receipt/snapshot ordering, wrong-room and wrong-seat snapshots, stale snapshots, old-loop cleanup, command-timeout authenticated resume without replay, explicit-ended private-card removal, immediate authority presence changes on revocation, and old-session completion isolation.
- Two independently authored tests use real JVM TLS sockets with the production transport factory, CSPRNG-backed services, protocol, and controller. They cover a three-seat invited lobby, ready/start gates, recipient-only hands on the wire, play/challenge/redeal, guest/host leave, port closure, real socket interruption, and authenticated TLS resume with the same hand/turn and a fresh command ID.

Independent source review also confirmed that cancellation cleanup is registered before acquisition and the real callback transport tracks/cleans cancelled native returns. Native permission prompts, iOS suspension timing, platform clipboard/share/scanner presentation, audio, and actual-device lifecycle remain platform qualification items; the JVM evidence does not claim those were exercised on Android or iOS hardware.

The invited-service rediscovery follow-up passed:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew :composeApp:jvmTest \
  --tests '*ClientDiscoveryFlowTest*' --console=plain
```

Result after the permission-denied reconnect correction: BUILD SUCCESSFUL in 11 seconds; eight tests, zero failures/errors/skips. The tests exercise a stale direct address whose exact service resolves later, preserved pin/admission/resume credentials, unrelated service rejection and bounded failure, discovery failure or suspended startup with a working direct invitation, immediate authentication/permission failure without fallback, actual-background cleanup and fresh resume, multiple rapid retries while old native cleanup is delayed, leave during discovery, and address-only invitations without browsing. The added reconnect regression verifies immediate batch/discovery shutdown on permission denial, no further attempts over 60 seconds of virtual time, preserved read-only context, and successful explicit Retry using the original Resume credential and pin. The transport owner independently reviewed the discovery runtime/test diff and found no transport contract concerns. Full combined regression and Android validation remain with the coordinator.

Independent controller review inspected the permission-denied reconnect correction, its regression, and the eight-test XML result, then closed the finding. The review confirmed immediate batch shutdown, retained credentials for explicit Retry, and preservation of the original pin and seat; no further controller changes or focused test runs were requested.
