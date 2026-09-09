# Application controller research and proposal

Owner: application controller implementation stream. Researched 2026-09-09. This document proposes contracts for the coordinator to freeze after environment smoke verification; the illustrative names below are not claims about APIs already present in the repository.

## Verified foundations

| Source | Verified behavior | Consequence for PartyDeck |
| --- | --- | --- |
| [Kotlin StateFlow API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/-state-flow/) | StateFlow always has a value, never completes normally, conflates equal values using `Any.equals`, and is thread safe. Errors and completion must be represented explicitly. | Publish immutable `AppUiState` through a read-only StateFlow. Connection loss, shutdown, and recoverable errors are explicit state. Do not use a state collector as a guaranteed delivery channel for every animation or acknowledgment. |
| [Kotlin CoroutineScope API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-coroutine-scope/) | An entity-owned scope must be cancelled when its owner is no longer needed. A parent cancellation cancels its children. `SupervisorJob` can isolate sibling failures. | One explicitly owned controller scope, one child job per active session, and cancellation of session jobs on leave or replacement. Preserve cancellation exceptions rather than presenting them as connection errors. |
| [Kotlin Mutex API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.sync/-mutex/) | Coroutine mutual exclusion is available in common code; Mutex is non-reentrant. | Serialize authority transitions. Compute outgoing effects under the lock and perform suspending network sends after releasing it. Do not recursively call authority methods while holding its lock. |
| [Compose Multiplatform lifecycle](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-lifecycle.html) | Compose provides common LifecycleOwner support. iOS background maps to `ON_STOP`; desktop main-dispatcher support requires the Swing coroutine dispatcher when those lifecycle scopes are used. | Shared UI can observe lifecycle, but transport survival is a separate concern. Platform owners explicitly forward foreground changes. A desktop target must provision its dispatcher if adopted. |
| [Compose Multiplatform ViewModel](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-viewmodel.html) | Common ViewModel support exists. Common `viewModel` creation needs an explicit initializer because non-JVM platforms lack the JVM reflection-based creation path. Shared Compose examples collect StateFlow using `collectAsState()`. | A root ViewModel wrapper is viable, but the controller itself can remain a plain common class with injected dependencies. Avoid a controller per screen and avoid reflection-dependent factories. |
| [Android ViewModel overview](https://developer.android.com/topic/libraries/architecture/viewmodel) | A ViewModel remains until its owner is cleared and survives owner configuration changes. SavedStateHandle is a separate process-restoration mechanism. | Retain the controller through Activity recreation. Do not imply that a retained controller, socket, or host authority survives process death. |
| [Apple application lifecycle](https://developer.apple.com/documentation/uikit/managing-your-app-s-life-cycle) | Background apps should minimize work; background scenes eventually suspend and may be disconnected to reclaim resources. Foreground/background and final cleanup are distinct transitions. | No guaranteed background host service. Pause bots and feedback in background, then reconnect or resynchronize clients on return. Temporary background must not permanently close the owner. |
| [Kotlin coroutine testing](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/) | `runTest`, TestScope, and TestCoroutineScheduler allow virtual-time coroutine tests. Work on uninjected production dispatchers does not automatically use virtual time. | Inject scope/dispatcher and bot/reconnect timing so critical flow tests remain fast and deterministic. |

Dependency versions belong to the coordinator's verified toolchain lock. This proposal adds no version pins. Current documentation pages can show differing lifecycle versions, so their examples must not be copied into the build independently.

### Frozen implementation coordination

The coordinator approved public contracts in `composeApp/src/commonMain/kotlin/dev/partydeck/app/controller`. `PlatformServices.kt` and `AppUiState.kt` are now the concrete source of truth; the earlier illustrative fragments in this research document explain the rationale. The public implementation constructor is `PartyDeckController(services: PlatformServices, transportFactory: LanTransportFactory, parentScope: CoroutineScope)`. The controller owns a child supervisor job, leaving cancellation of the supplied owner scope to the platform. The Compose entry point is `dev.partydeck.app.PartyDeckApp(controller)`.

Protocol contracts are in `dev.partydeck.session`; the safe game models are in `dev.partydeck.core`. The transport factory is `dev.partydeck.transport.LanTransportFactory`. Its versioned `LanInvitation` encodes the endpoint, pinned certificate SHA-256, session identifier, and room admission secret. The host's invitation is intentionally shareable, whereas a seat's resume credential is never exposed to UI state.

`PlatformServices.gameRandom(): Random` supplies an adapter whose every output comes from the platform CSPRNG. A secure initial seed for Kotlin's deterministic generator is insufficient for secret deck/fuse outcomes; independent security review corrected the original seed-only proposal before implementation. Separately, `secureToken(): String` must return exactly 32 directly CSPRNG-generated bytes encoded as 64 lowercase hexadecimal characters for admission/resume tokens; deriving these secrets from a seeded Kotlin random generator is prohibited. The native services also supply `copyText(String)` and `shareText(String)` for explicit invitation buttons, because the full pinned invite is too long to expect people to transcribe. Clipboard implementations should use their verified native sensitive-content facilities where available.

The native controller methods include `setForeground`, `setSystemReduceMotion`, and `close`. `requestBack(): Boolean` returns false at Home for native default handling and consumes other Back actions; session Back exposes `leaveConfirmationRequested` in state. Copy feedback is represented by a localizable `UiNotice` rather than an exception message. `FeedbackCue.LIGHT_OUT` distinguishes a burned-out fuse from the safe round-end cue.

## Ownership and dependency direction

`Compose UI -> AppController -> session runtime -> pure SessionAuthority / byte transport`

The controller owns navigation, editable forms, persisted preferences, foreground state, a single active runtime, pending user actions, and presentation of recoverable problems. It never validates game truth or computes penalty outcomes. The session module owns protocol validation, authentication binding, deduplication, roster/session rules, and player-specific snapshots. The game module owns Last Light rules. The transport owns listeners, sockets, framing, connection state, and its own resource cleanup.

Because the session stream proposes a synchronous authority without coroutines, the controller package needs small runtime adapters:

- `HostSessionRuntime`: serialize incoming peer messages through SessionAuthority, publish the host's sanitized snapshot, and deliver each outgoing message only to its bound recipient.
- `ClientSessionRuntime`: handshake, retain private reconnect credentials in memory, consume authoritative snapshots, and send typed intents with request IDs and expected revisions.
- `PracticeSessionRuntime`: register the human and bots through the same authority using in-memory peer bindings; no sockets and no alternate game rules.

The adapters implement one narrow interface used by AppController: observed player-visible session/connection state, typed commands, foreground transition, and close. Avoid exposing raw wire frames or `GameState` to Compose. A host may possess the authority internally, but its UI receives precisely the same sanitized `SessionView` shape as a client.

All session mutations are serialized. A lock must not span network IO. Async completions also carry a monotonically increasing controller session-generation marker; a late join, old collector, or reconnect response cannot revive a session after leave or overwrite a newer session.

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
setForeground(value), close()
```

`navigate` must not route to a nonexistent session or move to host/join while another runtime remains active. `leaveSession` explicitly closes owned work and then resets the session route. Host start and continuation eligibility comes from validated session state; the UI can explain why a control is unavailable without duplicating authority decisions. Future games add feature-specific commands/projections at the session boundary instead of taking over application lifecycle.

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

The Android owner retains the controller through a ViewModel and reattaches feedback to the current window if needed. The proposed iOS owner is a SwiftUI-retained exported Kotlin handle owning the UIViewController and controller. `scenePhase` forwards foreground transitions; permanent disposal calls close. A common Compose root ViewModel is an alternative if the coordinator chooses it, but there must be only one owner and one cleanup path.

`setForeground(false)` pauses practice bot delays, prevents retries from spinning while suspended, and stops feedback. It does not destroy a live controller. Resume recalculates bot eligibility from the newest authority revision and resynchronizes a client connection. Hosting is a foreground activity; if the system suspends or terminates the host, peers see recoverable host loss. There is no initial host migration or promised process-death restoration.

System Reduce Motion is runtime state, supplied by platform observers through `setSystemReduceMotion`; effective motion preference is system request OR user preference. Only the user preference is persisted. Observers and feedback resources are removed/released on final close.

## Host, join, reconnect, and failure behavior

1. Host validates the display name, opens a real transport listener, obtains invitation details, creates SessionAuthority, binds the local host, and publishes a lobby snapshot. Failure closes partially acquired resources and leaves the host form retryable.
2. Join validates the invite through the transport's parser, establishes the connection, completes protocol join, then publishes the initial session snapshot. An abandoned or superseded join cannot publish into a later session.
3. Gameplay always sends an intent, request ID, and expected revision. Actor identity comes from session peer binding, not from an untrusted action payload. The authority provides each player's redacted response.
4. A rejected or stale action surfaces the specific recoverable problem and refreshes state. The controller does not optimistically deal cards or independently advance rounds.
5. On client disconnection, preserve the latest snapshot for context, disable gameplay controls, and attempt a bounded reconnect while foreground. The transport stream proposed 0.5/1/2/4-second backoff with jitter within approximately 30 seconds; these are product policy suggestions for the coordinator to finalize, not platform guarantees.
6. Reconnect proves the private resume credential, replaces the old peer binding, and receives a full fresh snapshot. Do not blindly replay a queued gameplay action. A lost acknowledgment is reconciled using the session's duplicate-request semantics and authoritative state; an unresolved old action must not block the UI forever.
7. Failure after the retry window offers explicit Retry and Leave. A known ended session, invalid credential, or version mismatch cannot be fixed by unlimited retries. Host termination ends the initial architecture's session; starting another lobby is the recovery.

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
