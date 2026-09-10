package dev.partydeck.app.controller

import dev.partydeck.core.GameAction
import dev.partydeck.core.GameView
import dev.partydeck.core.PlayerId
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameRegistry
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineResolution
import dev.partydeck.games.GamePresentation
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.godot.bridge.BridgeDecision
import dev.partydeck.godot.bridge.BridgeInput
import dev.partydeck.godot.bridge.BridgeRejection
import dev.partydeck.godot.bridge.LastLightBridgeAdapter
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationControls
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.TimeMark
import kotlin.time.TimeSource

/** The session revision is captured from the exact projection which accepted the renderer input. */
internal data class PresentationSubmission(
    val presentationId: String,
    val sessionGeneration: Long,
    val sessionId: String,
    val recipient: PlayerId,
    val expectedRevision: Long,
    val intent: ClientIntent,
)

/** One serialized shell owner; native factories never receive this controller or a SessionRuntime. */
internal class EmbeddedPresentationCoordinator(
    private val scope: CoroutineScope,
    private val host: EmbeddedPresentationHost,
    private val currentState: () -> AppUiState,
    private val sessionGeneration: () -> Long,
    private val newPresentationId: () -> String,
    private val publish: (GameplayPresentationState, Boolean) -> Unit,
    private val submit: (PresentationSubmission) -> Boolean,
    private val requestExit: () -> Unit,
    private val selectionTimeSource: TimeSource = TimeSource.Monotonic,
) {
    private var ui = GameplayPresentationState()
    private var active: Presentation? = null
    private var closing: Presentation? = null
    private var pendingOpen: PendingOpen? = null
    private var selectionOwnerActive = true
    private var availabilityJob: Job? = null
    private var advertised: Set<GameplayPresentation>? = null
    private var factoryPreferences: PresentationPreferences? = null
    private var factories = emptyMap<GameplayPresentation, EmbeddedGameFactory>()
    private var nativeCleanupFailed = false
    private var closed = false

    fun start() {
        if (closed || availabilityJob != null) return
        availabilityJob = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            host.available.collect { update() }
        }
    }

    /** Called synchronously after relevant controller changes, including every foreground edge. */
    fun update() {
        if (closed) return
        refreshFactories()
        val state = currentState()
        pendingOpen?.let { if (!pendingIsCurrent(it, state)) cancelPendingSelection() }
        val presentation = active
        if (presentation != null) {
            if (!presentation.binding.matches(state.session, sessionGeneration()) ||
                state.screen != AppScreen.SESSION || state.leaveConfirmationRequested ||
                state.connection.status != ConnectionStatus.CONNECTED
            ) {
                cancelPendingSelection()
                stop(presentation)
                return
            }
            if (presentation.preferences != preferences(state)) {
                cancelPendingSelection()
                stop(presentation, PresentationFallbackReason.PREFERENCES_CHANGED)
                return
            }
            project(presentation)
        }
        openPendingIfReady()
    }

    /** A modal may take focus; pause, departure or owner replacement invalidates its selection. */
    fun setSelectionOwnerActive(value: Boolean) {
        selectionOwnerActive = value
        if (!value) cancelPendingSelection()
    }

    fun select(choice: GameplayPresentation): Boolean {
        if (closed) return false
        cancelPendingSelection()
        if (choice == GameplayPresentation.COMPOSE) {
            active?.let { stop(it) } ?: emit(ui.copy(fallbackReason = null))
            return true
        }
        val state = currentState()
        val session = state.session?.takeIf { it.phase == SessionPhase.GAME && it.game?.viewerId == it.selfPlayerId }
            ?: return false
        if (!selectionAllowed(state)) return false
        if (active?.choice == choice) return true
        refreshFactories(force = true)
        if (choice !in factories) return false
        val pending = PendingOpen(
            choice,
            Binding(sessionGeneration(), session.sessionId, session.selfPlayerId),
            preferences(state),
            selectionTimeSource.markNow() + SELECTION_TIMEOUT_MS.milliseconds,
        )
        pendingOpen = pending
        pending.timeout = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            delay(SELECTION_TIMEOUT_MS)
            // Expiry only cancels this attempt; it never grants focus or renews a later choice.
            if (pendingOpen === pending) cancelPendingSelection()
        }
        if (active != null || closing != null) {
            active?.let { stop(it) }
            return true
        }
        return openPendingIfReady()
    }

    private fun selectionAllowed(state: AppUiState): Boolean =
        !closed && selectionOwnerActive && scope.isActive && state.screen == AppScreen.SESSION &&
            !state.isBackgrounded && !state.leaveConfirmationRequested &&
            state.connection.status == ConnectionStatus.CONNECTED

    private fun pendingIsCurrent(pending: PendingOpen, state: AppUiState): Boolean =
        selectionAllowed(state) && pending.binding.matches(state.session, sessionGeneration()) &&
            pending.preferences == preferences(state) && pending.choice in factories &&
            !pending.deadline.hasPassedNow()

    private fun cancelPendingSelection() {
        val pending = pendingOpen
        pendingOpen = null
        pending?.timeout?.cancel()
    }

    private fun openPendingIfReady(): Boolean {
        val pending = pendingOpen ?: return false
        refreshFactories(force = true)
        if (pendingOpen !== pending) return false
        val state = currentState()
        if (!pendingIsCurrent(pending, state)) {
            cancelPendingSelection()
            return false
        }
        // Both close completion and actual foreground publication may arrive first. Neither a
        // dismissed-dialog flag nor the expiration timer is evidence of current window focus.
        if (active != null || closing != null || !state.isForeground) return true
        val factory = factories[pending.choice] ?: return false
        cancelPendingSelection() // Consume before publishing or entering an undispatched factory.
        val choice = pending.choice
        val binding = pending.binding
        val preference = pending.preferences
        val initial = projection(state, ready = false)
        val adapter = try {
            LastLightBridgeAdapter(newPresentationId(), 0, initial.game, initial.controls).also {
                it.setForeground(false)
            }
        } catch (_: Exception) {
            emit(ui.copy(fallbackReason = PresentationFallbackReason.INITIALIZATION_FAILED))
            return false
        }
        val presentation = Presentation(choice, binding, preference, adapter, initial)
        active = presentation
        emit(ui.copy(
            selected = choice,
            lifecycle = PresentationLifecycle.OPENING,
            presentationId = adapter.presentationId,
            fallbackReason = null,
        ), conceal = true)
        presentation.job = scope.launch(start = CoroutineStart.UNDISPATCHED) { run(presentation, factory) }
        return true
    }

    /** Distinguish the renderer view revision from the authority session revision for observation. */
    fun currentProjectionCounters(): Pair<Long, Long>? = active?.let {
        it.adapter.revision to it.projection.sessionRevision
    }

    fun owns(presentationId: String): Boolean = active?.adapter?.presentationId == presentationId

    /** Native Back may arrive before renderer Ready; it is not assigned a renderer sequence. */
    fun exit(presentationId: String) {
        val presentation = active?.takeIf { it.adapter.presentationId == presentationId } ?: return
        cancelPendingSelection()
        stop(presentation)
        requestExit()
    }

    fun close() {
        if (closed) return
        cancelPendingSelection()
        active?.let { stop(it) }
        closed = true
        availabilityJob?.cancel()
        availabilityJob = null
    }

    private suspend fun run(presentation: Presentation, factory: EmbeddedGameFactory) {
        var native: EmbeddedGameSession? = null
        try {
            coroutineScope {
                val startup = launch {
                    delay(STARTUP_TIMEOUT_MS)
                    if (active === presentation && !presentation.ready) {
                        stop(presentation, PresentationFallbackReason.INITIALIZATION_FAILED)
                    }
                }
                presentation.startup = startup
                try {
                    native = factory.open(presentation.adapter.launch)
                    presentation.native = native
                    if (active !== presentation) return@coroutineScope
                    val session = checkNotNull(native)
                    launch {
                        for (queued in presentation.commands) {
                            try {
                                withTimeout(DELIVERY_TIMEOUT_MS) {
                                    if (session is LifecycleBoundEmbeddedGameSession && queued.lifecycleGeneration != null) {
                                        session.send(queued.command, queued.lifecycleGeneration)
                                    } else session.send(queued.command)
                                }
                            } catch (cancelled: CancellationException) {
                                if (active === presentation && isActive) {
                                    stop(presentation, PresentationFallbackReason.DELIVERY_FAILED)
                                }
                                throw cancelled
                            } catch (_: Exception) {
                                stop(presentation, PresentationFallbackReason.DELIVERY_FAILED)
                                return@launch
                            } finally {
                                presentation.queuedCount--
                                presentation.queuedBytes -= queued.bytes
                            }
                        }
                    }
                    session.events.collect { event ->
                        accept(presentation, event)
                        if (active !== presentation) throw CancellationException("Presentation closed")
                    }
                    if (active === presentation) stop(presentation, PresentationFallbackReason.RENDERER_LOST)
                } finally {
                    startup.cancel()
                    presentation.commands.cancel()
                }
            }
        } catch (cancelled: CancellationException) {
            if (active === presentation) stop(presentation, PresentationFallbackReason.RENDERER_LOST)
            throw cancelled
        } catch (_: Exception) {
            if (active === presentation) stop(presentation, if (presentation.ready) {
                PresentationFallbackReason.RENDERER_LOST
            } else PresentationFallbackReason.INITIALIZATION_FAILED)
        } finally {
            presentation.adapter.close()
            presentation.commands.cancel()
            val released = withContext(NonCancellable) {
                try {
                    withTimeoutOrNull(CLOSE_TIMEOUT_MS) { native?.close(); true } == true
                } catch (_: Exception) {
                    false
                }
            }
            completeClose(presentation, released)
        }
    }

    private fun accept(presentation: Presentation, event: EngineEvent) {
        if (active !== presentation || closed) return
        update()
        if (active !== presentation) return
        val decision = try {
            presentation.adapter.accept(LastLightWireCodec.encodeEvent(event))
        } catch (_: IllegalArgumentException) {
            stop(presentation, PresentationFallbackReason.INVALID_EVENT)
            return
        }
        when (decision) {
            is BridgeDecision.Rejected -> when (decision.reason) {
                BridgeRejection.INVALID_DOCUMENT, BridgeRejection.WRONG_PRESENTATION,
                BridgeRejection.UNSUPPORTED_PROTOCOL -> stop(presentation, PresentationFallbackReason.INVALID_EVENT)
                BridgeRejection.STALE_REVISION, BridgeRejection.NOT_FOREGROUND,
                BridgeRejection.ACTION_UNAVAILABLE, BridgeRejection.INVALID_SELECTION -> {
                    if (event.body is EngineEventBody.PlayerIntent && presentation.ready) project(presentation, force = true)
                }
                else -> Unit
            }
            is BridgeDecision.Accepted -> when (val input = decision.input) {
                BridgeInput.Ready -> {
                    presentation.ready = true
                    presentation.startup?.cancel()
                    emit(ui.copy(lifecycle = PresentationLifecycle.ACTIVE))
                    project(presentation, force = true, sendForeground = true)
                }
                BridgeInput.ExitRequested -> exit(presentation.adapter.presentationId)
                is BridgeInput.Failed -> stop(presentation, if (presentation.ready) {
                    PresentationFallbackReason.RENDERER_LOST
                } else PresentationFallbackReason.INITIALIZATION_FAILED)
                else -> {
                    val intent = when (input) {
                        is BridgeInput.Action -> when (val action = input.action) {
                            is GameAction.Play -> ClientIntent.PlayCards(action.cardIds.toList())
                            is GameAction.Challenge -> ClientIntent.Challenge
                        }
                        BridgeInput.AdvanceRound -> ClientIntent.AdvanceRound
                        BridgeInput.ReturnToLobby -> ClientIntent.ReturnToLobby
                    }
                    val binding = presentation.binding
                    val accepted = submit(PresentationSubmission(
                        presentation.adapter.presentationId, binding.generation, binding.sessionId,
                        binding.recipient, presentation.projection.sessionRevision, intent,
                    ))
                    if (!accepted && active === presentation) project(presentation, force = true)
                }
            }
        }
    }

    private fun project(presentation: Presentation, force: Boolean = false, sendForeground: Boolean = false) {
        if (active !== presentation) return
        val nativeGeneration = (presentation.native as? LifecycleBoundEmbeddedGameSession)?.lifecycleGeneration
        val next = projection(currentState(), presentation.ready, nativeGeneration)
        val previous = presentation.projection
        val foregroundChanged = next.foreground != previous.foreground || next.privacyEpoch != previous.privacyEpoch ||
            next.nativeGeneration != previous.nativeGeneration
        try {
            // Immediate gate change precedes queued delivery, including rapid loss/regain edges.
            val foreground = presentation.adapter.setForeground(presentation.ready && next.foreground)
            if (next != previous || force) {
                if (presentation.adapter.revision == Long.MAX_VALUE) {
                    stop(presentation, PresentationFallbackReason.DELIVERY_FAILED)
                    return
                }
                val command = presentation.adapter.showView(presentation.adapter.revision + 1, next.game, next.controls)
                presentation.projection = next
                if (presentation.ready && !enqueue(presentation, command)) return
            }
            if (presentation.ready && (foregroundChanged || sendForeground)) enqueue(presentation, foreground)
        } catch (_: IllegalArgumentException) {
            stop(presentation, PresentationFallbackReason.INVALID_EVENT)
        }
    }

    private fun enqueue(presentation: Presentation, command: EngineCommand): Boolean {
        if (active !== presentation) return false
        val bytes = LastLightWireCodec.encodeCommand(presentation.adapter.presentationId, command).encodeToByteArray().size
        if (presentation.queuedCount >= MAX_QUEUED_COMMANDS || presentation.queuedBytes + bytes > MAX_QUEUED_BYTES) {
            stop(presentation, PresentationFallbackReason.DELIVERY_FAILED)
            return false
        }
        presentation.queuedCount++
        presentation.queuedBytes += bytes
        val lifecycleGeneration = (presentation.native as? LifecycleBoundEmbeddedGameSession)?.lifecycleGeneration
        if (!presentation.commands.trySend(QueuedCommand(command, bytes, lifecycleGeneration)).isSuccess) {
            presentation.queuedCount--
            presentation.queuedBytes -= bytes
            stop(presentation, PresentationFallbackReason.DELIVERY_FAILED)
            return false
        }
        return true
    }

    private fun stop(presentation: Presentation, reason: PresentationFallbackReason? = null) {
        if (active !== presentation) return
        active = null
        closing = presentation
        presentation.adapter.close()
        presentation.startup?.cancel()
        presentation.commands.cancel()
        emit(ui.copy(
            selected = GameplayPresentation.COMPOSE,
            lifecycle = PresentationLifecycle.CLOSING,
            presentationId = null,
            fallbackReason = reason,
        ), conceal = true)
        presentation.job?.cancel()
    }

    private fun completeClose(presentation: Presentation, released: Boolean) {
        if (closing !== presentation) return
        if (!released) nativeCleanupFailed = true
        if (closed) {
            closing = null
            return
        }
        // Keep the close gate through publication: a native owner may synchronously publish
        // regained foreground from this callback, before the old close has finished publishing.
        refreshFactories(force = true)
        emit(ui.copy(lifecycle = PresentationLifecycle.COMPOSE, fallbackReason = if (released) {
            ui.fallbackReason
        } else PresentationFallbackReason.DELIVERY_FAILED))
        closing = null
        openPendingIfReady()
    }

    private fun refreshFactories(force: Boolean = false) {
        if (closed) return
        val preference = preferences(currentState())
        val offered = if (nativeCleanupFailed) emptySet() else host.available.value.toSet()
        if (!force && advertised == offered && factoryPreferences == preference) return
        advertised = offered
        factoryPreferences = preference
        factories = offered.filter { it != GameplayPresentation.COMPOSE }.mapNotNull { choice ->
            val engineId = when (choice) {
                GameplayPresentation.GODOT_2D -> "godot-2d"
                GameplayPresentation.GODOT_3D -> "godot-3d"
                GameplayPresentation.COMPOSE -> return@mapNotNull null
            }
            try {
                val factory = host.createFactory(choice, preference) ?: return@mapNotNull null
                if (factory.engineId != engineId) return@mapNotNull null
                val descriptor = PartyDeckGames.lastLight.copy(presentation = GamePresentation.Embedded(engineId))
                if (EmbeddedGameRegistry(listOf(factory)).resolve(descriptor) is EngineResolution.Available) choice to factory
                else null
            } catch (_: Exception) {
                null
            }
        }.toMap()
        emit(ui.copy(available = setOf(GameplayPresentation.COMPOSE) + factories.keys))
    }

    private fun preferences(state: AppUiState) = PresentationPreferences(
        reduceMotion = state.effectiveReduceMotion,
        soundEnabled = false,
        textScale = state.presentationTextScale,
    )

    private fun projection(state: AppUiState, ready: Boolean, nativeGeneration: Long? = null): Projection {
        val session = checkNotNull(state.session)
        return Projection(
            sessionRevision = session.revision,
            game = checkNotNull(session.game),
            controls = PresentationControls(
                isHost = session.selfPlayerId == session.hostPlayerId,
                canSendAction = ready && state.canSendSessionAction && state.screen == AppScreen.SESSION && !state.leaveConfirmationRequested,
                canAdvanceRound = session.controls.canAdvanceRound,
                canReturnToLobby = session.controls.canReturnToLobby,
            ),
            foreground = state.isForeground && !state.isBackgrounded,
            privacyEpoch = state.privacyEpoch,
            nativeGeneration = nativeGeneration,
        )
    }

    private fun emit(next: GameplayPresentationState, conceal: Boolean = false) {
        if (ui == next && !conceal) return
        ui = next
        publish(next, conceal)
    }

    private data class Binding(val generation: Long, val sessionId: String, val recipient: PlayerId) {
        fun matches(session: SessionView?, currentGeneration: Long): Boolean =
            generation == currentGeneration && session?.sessionId == sessionId && session.selfPlayerId == recipient &&
                session.phase == SessionPhase.GAME && session.game?.viewerId == recipient
    }

    private class PendingOpen(
        val choice: GameplayPresentation,
        val binding: Binding,
        val preferences: PresentationPreferences,
        val deadline: TimeMark,
    ) {
        var timeout: Job? = null
    }

    private data class Projection(
        val sessionRevision: Long,
        val game: GameView,
        val controls: PresentationControls,
        val foreground: Boolean,
        val privacyEpoch: Long,
        val nativeGeneration: Long?,
    )

    private data class QueuedCommand(val command: EngineCommand, val bytes: Int, val lifecycleGeneration: Long?)

    private class Presentation(
        val choice: GameplayPresentation,
        val binding: Binding,
        val preferences: PresentationPreferences,
        val adapter: LastLightBridgeAdapter,
        var projection: Projection,
    ) {
        var ready = false
        var job: Job? = null
        var startup: Job? = null
        var native: EmbeddedGameSession? = null
        val commands = Channel<QueuedCommand>(MAX_QUEUED_COMMANDS)
        var queuedCount = 0
        var queuedBytes = 0
    }

    private companion object {
        const val SELECTION_TIMEOUT_MS = 5_000L
        const val STARTUP_TIMEOUT_MS = 10_000L
        const val DELIVERY_TIMEOUT_MS = 5_000L
        const val CLOSE_TIMEOUT_MS = 3_000L
        const val MAX_QUEUED_COMMANDS = 16
        const val MAX_QUEUED_BYTES = 262_144
    }
}
