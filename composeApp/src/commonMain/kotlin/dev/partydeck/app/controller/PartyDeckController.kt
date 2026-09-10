package dev.partydeck.app.controller

import dev.partydeck.core.CardId
import dev.partydeck.core.GamePhase
import dev.partydeck.core.LastLightRules
import dev.partydeck.core.PlayerId
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.SessionView
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * One UI-owner controller. Call actions on the owner's UI dispatcher; observe state from anywhere.
 * The native owner retains this instance across temporary lifecycle changes and calls [close] when
 * permanently disposed. Its supplied scope is never cancelled by this controller.
 */
class PartyDeckController(
    private val services: PlatformServices,
    private val transportFactory: LanTransportFactory,
    parentScope: CoroutineScope,
    presentationHost: EmbeddedPresentationHost = EmbeddedPresentationHost.None,
) {
    private val job = SupervisorJob(parentScope.coroutineContext[Job])
    private val scope = CoroutineScope(parentScope.coroutineContext + job)
    private val mutableState = MutableStateFlow(AppUiState(canScanInvitation = services.canScanInvitation))
    val state: StateFlow<AppUiState> = mutableState.asStateFlow()

    private val preferenceWrites = Channel<PreferenceWrite>(Channel.CONFLATED)
    private var preferenceRevision = 0L
    private var displayNameEdited = false
    private var savedPreferenceRevision = 0L
    private var latestPreferences = AppSettings()
    private var preferenceWriter: Job? = null
    private var runtime: SessionRuntime? = null
    private var runtimeCollector: Job? = null
    private var commandJob: Job? = null
    private var commandReservation: Any? = null
    private var feedbackJob: Job? = null
    private var sessionGeneration = 0L
    private var qualificationObservation: SessionQualificationObservation? = null
    private var scanRequest = 0L
    private var occurrence = 0L
    private var overlayReturn = AppScreen.HOME
    private var closed = false
    private var feedbackClosed = false
    private val presentations = EmbeddedPresentationCoordinator(
        scope = scope,
        host = presentationHost,
        currentState = { state.value },
        sessionGeneration = { sessionGeneration },
        newPresentationId = services::secureToken,
        publish = { presentation, conceal ->
            qualificationObservation?.presentationChanged(presentation)
            mutableState.update {
                it.copy(presentation = presentation, privacyEpoch = if (conceal) it.privacyEpoch + 1 else it.privacyEpoch)
            }
        },
        submit = ::submitPresentation,
        requestExit = { requestBack() },
    )

    init {
        presentations.start()
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                withContext(NonCancellable) {
                    closed = true
                    presentations.close()
                    clearSessionState()
                    closeFeedback()
                    preferenceWriter?.join()
                    if (preferenceRevision > savedPreferenceRevision) {
                        try {
                            services.settingsStore.save(latestPreferences)
                            savedPreferenceRevision = preferenceRevision
                        } catch (_: Exception) {
                            showProblem(UiProblemCode.SETTINGS_UNAVAILABLE)
                        }
                    }
                }
            }
        }
        scope.launch {
            try {
                val loaded = services.settingsStore.load()
                if (preferenceRevision == 0L && !closed) {
                    val name = normalizedName(loaded.displayName) ?: "Guest"
                    val settings = loaded.copy(displayName = name)
                    latestPreferences = settings
                    mutableState.update {
                        it.copy(displayName = if (displayNameEdited) it.displayName else name, settings = settings)
                    }
                    presentations.update()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                showProblem(UiProblemCode.SETTINGS_UNAVAILABLE)
            }
        }
        preferenceWriter = scope.launch {
            for (write in preferenceWrites) {
                try {
                    services.settingsStore.save(write.settings)
                    savedPreferenceRevision = write.revision
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    showProblem(UiProblemCode.SETTINGS_UNAVAILABLE)
                }
            }
        }
    }

    /** Internal, opt-in read-only telemetry; installation never starts or replaces a runtime. */
    internal fun enableSessionQualificationObservation(): Boolean {
        if (closed || runtime != null || state.value.session != null) return false
        if (qualificationObservation == null) qualificationObservation = SessionQualificationObservation()
        return true
    }

    internal fun sessionQualificationSnapshot(): String? = qualificationObservation?.snapshot(
        state.value, sessionGeneration, presentations.currentProjectionCounters(),
    )

    fun navigate(screen: AppScreen) {
        if (closed || screen == state.value.screen) return
        if (screen == AppScreen.SESSION && state.value.session == null) return
        val current = state.value
        if (current.session != null && screen in setOf(AppScreen.HOME, AppScreen.HOST, AppScreen.JOIN)) {
            mutableState.update { it.copy(leaveConfirmationRequested = true) }
            presentations.update()
            return
        }
        if (screen == AppScreen.SETTINGS || screen == AppScreen.HOW_TO) {
            if (current.screen != AppScreen.SETTINGS && current.screen != AppScreen.HOW_TO) {
                overlayReturn = current.screen
            }
        } else if (screen == AppScreen.HOME && current.session == null && runtime != null) {
            abandonRuntime()
        }
        mutableState.update { it.copy(screen = screen, problem = null, notice = null) }
        presentations.update()
    }

    /** False only at Home, allowing the native owner to perform its normal Back behavior. */
    fun requestBack(): Boolean {
        if (closed) return false
        return when (state.value.screen) {
            AppScreen.HOME -> false
            AppScreen.SESSION -> {
                mutableState.update { it.copy(leaveConfirmationRequested = true) }
                presentations.update()
                true
            }
            AppScreen.SETTINGS, AppScreen.HOW_TO -> {
                val destination = if (state.value.session != null) AppScreen.SESSION else {
                    overlayReturn.takeUnless { it == AppScreen.SESSION } ?: AppScreen.HOME
                }
                mutableState.update { it.copy(screen = destination, problem = null) }
                presentations.update()
                true
            }
            AppScreen.HOST, AppScreen.JOIN -> {
                abandonRuntime()
                mutableState.update { it.copy(screen = AppScreen.HOME, problem = null) }
                true
            }
        }
    }

    fun dismissLeaveConfirmation() {
        mutableState.update { it.copy(leaveConfirmationRequested = false) }
        presentations.update()
    }

    fun selectPresentation(presentation: GameplayPresentation): Boolean =
        !closed && presentations.select(presentation)

    fun useComposePresentation() { selectPresentation(GameplayPresentation.COMPOSE) }

    fun requestPresentationExit(presentationId: String) {
        if (!closed) presentations.exit(presentationId)
    }

    /** Apply each new native privacy generation after its foreground/background facts. */
    fun refreshPresentationLifecycle(presentationId: String) {
        if (!closed && presentations.owns(presentationId)) presentations.update()
    }

    /** Platform font scale is bounded by the existing renderer preferences schema. */
    fun setPresentationTextScale(value: Double) {
        if (closed || !value.isFinite()) return
        val scale = value.coerceIn(1.0, 2.0)
        if (state.value.presentationTextScale == scale) return
        mutableState.update { it.copy(presentationTextScale = scale) }
        presentations.update()
    }

    fun setDisplayName(value: String) {
        if (closed) return
        displayNameEdited = true
        mutableState.update { it.copy(displayName = value.take(128), problem = null) }
        normalizedName(value)?.let { name -> persistSettings(state.value.settings.copy(displayName = name)) }
    }

    fun setJoinAddress(value: String) {
        if (!closed) mutableState.update { it.copy(joinAddress = value.take(2_049), problem = null) }
    }

    fun updateSettings(settings: AppSettings) {
        if (closed) return
        val name = normalizedName(state.value.displayName) ?: state.value.settings.displayName
        persistSettings(settings.copy(displayName = name))
    }

    private fun persistSettings(settings: AppSettings) {
        preferenceRevision++
        latestPreferences = settings
        mutableState.update { it.copy(settings = settings) }
        presentations.update()
        preferenceWrites.trySend(PreferenceWrite(preferenceRevision, settings))
    }

    fun host() = startAuthority(practice = false)

    fun startPractice() = startAuthority(practice = true)

    private fun startAuthority(practice: Boolean) {
        if (!canStartSession()) return
        if (practice && normalizedName(state.value.displayName) == null) {
            mutableState.update { it.copy(displayName = normalizedName(it.settings.displayName) ?: "Guest") }
        }
        val name = validDisplayName() ?: return
        attachRuntime(
            AuthoritySessionRuntime(scope, services, transportFactory, name, practice),
            PendingAction.HOST,
        )
        if (practice) mutableState.update { it.copy(screen = AppScreen.SESSION) }
    }

    fun join() {
        if (!canStartSession()) return
        val name = validDisplayName() ?: return
        val invitation = try {
            LanInvitation.decode(state.value.joinAddress)
        } catch (_: IllegalArgumentException) {
            showProblem(UiProblemCode.INVALID_INVITE, RecoveryAction.EDIT_INVITE)
            return
        }
        attachRuntime(ClientSessionRuntime(scope, transportFactory, invitation, name), PendingAction.JOIN)
    }

    private fun canStartSession(): Boolean {
        if (closed || state.value.session != null) return false
        return state.value.pendingAction == null && state.value.connection.status !in setOf(
            ConnectionStatus.STARTING_HOST,
            ConnectionStatus.CONNECTING,
            ConnectionStatus.RECONNECTING,
        )
    }

    private fun validDisplayName(): String? {
        val name = normalizedName(state.value.displayName)
        if (name == null) showProblem(UiProblemCode.INVALID_NAME)
        else {
            mutableState.update { it.copy(displayName = name) }
            persistSettings(state.value.settings.copy(displayName = name))
        }
        return name
    }

    private fun attachRuntime(next: SessionRuntime, action: PendingAction) {
        abandonRuntime()
        runtime = next
        val generation = sessionGeneration
        var seenIssue = 0L
        mutableState.update {
            it.copy(pendingAction = action, problem = null, notice = null, leaveConfirmationRequested = false)
        }
        runtimeCollector = scope.launch(start = CoroutineStart.UNDISPATCHED) {
            next.state.collect { snapshot ->
                if (closed || generation != sessionGeneration) return@collect
                val previous = state.value
                val newIssue = snapshot.issue?.takeIf { it.occurrence != seenIssue }
                if (newIssue != null) seenIssue = newIssue.occurrence
                val active = snapshot.connection == ConnectionStatus.CONNECTED
                val completedStart = previous.pendingAction in setOf(PendingAction.HOST, PendingAction.JOIN) &&
                    (active || snapshot.connection == ConnectionStatus.DISCONNECTED)
                val problem = when {
                    newIssue != null -> UiProblem(++occurrence, newIssue.code, newIssue.recovery)
                    active && previous.connection.status != ConnectionStatus.CONNECTED &&
                        previous.problem?.code in connectionProblems -> null
                    else -> previous.problem
                }
                mutableState.update {
                    it.copy(
                        screen = if (snapshot.view != null && it.screen !in setOf(AppScreen.SETTINGS, AppScreen.HOW_TO)) {
                            AppScreen.SESSION
                        } else it.screen,
                        session = snapshot.view,
                        invitation = snapshot.invitation,
                        connection = ConnectionUiState(snapshot.connection, snapshot.mode, snapshot.retryAttempt),
                        pendingAction = if (completedStart || snapshot.connection != ConnectionStatus.CONNECTED &&
                            snapshot.connection != ConnectionStatus.STARTING_HOST &&
                            snapshot.connection != ConnectionStatus.CONNECTING
                        ) null else it.pendingAction,
                        problem = problem,
                    )
                }
                presentations.update()
                if (active && previous.connection.status == ConnectionStatus.CONNECTED) {
                    playSessionFeedback(previous.session, snapshot.view, generation)
                }
            }
        }
        updateRuntimeActivity()
        next.start()
    }

    fun setReady(value: Boolean) { submit(PendingAction.READY, ClientIntent.SetReady(value)) }
    fun startGame() { submit(PendingAction.START_GAME, ClientIntent.StartGame) }
    fun playCards(cardIds: List<CardId>) { submit(PendingAction.PLAY_CARDS, ClientIntent.PlayCards(cardIds.toList())) }
    fun challenge() { submit(PendingAction.CHALLENGE, ClientIntent.Challenge) }
    fun nextRound() { submit(PendingAction.NEXT_ROUND, ClientIntent.AdvanceRound) }
    fun returnToLobby() { submit(PendingAction.RETURN_TO_LOBBY, ClientIntent.ReturnToLobby) }
    fun kickPlayer(playerId: PlayerId) { submit(PendingAction.KICK_PLAYER, ClientIntent.KickPlayer(playerId)) }

    private fun submitPresentation(submission: PresentationSubmission): Boolean {
        val session = state.value.session ?: return false
        if (!presentations.owns(submission.presentationId) || submission.sessionGeneration != sessionGeneration ||
            session.sessionId != submission.sessionId || session.selfPlayerId != submission.recipient ||
            session.revision != submission.expectedRevision || state.value.screen != AppScreen.SESSION
        ) return false
        val action = when (submission.intent) {
            is ClientIntent.PlayCards -> PendingAction.PLAY_CARDS
            ClientIntent.Challenge -> PendingAction.CHALLENGE
            ClientIntent.AdvanceRound -> PendingAction.NEXT_ROUND
            ClientIntent.ReturnToLobby -> PendingAction.RETURN_TO_LOBBY
            else -> return false
        }
        return submit(action, submission.intent, submission.expectedRevision)
    }

    private fun submit(action: PendingAction, intent: ClientIntent, expectedRevision: Long? = null): Boolean {
        val currentRuntime = runtime ?: return false
        val before = state.value
        if (closed || !before.canSendSessionAction || before.leaveConfirmationRequested) return false
        val revision = expectedRevision ?: before.session?.revision ?: return false
        val generation = sessionGeneration
        val observedOrigin = qualificationObservation?.origin(before, generation, expectedRevision != null)
        val reservation = Any()
        commandReservation = reservation
        mutableState.update { it.copy(pendingAction = action, problem = null) }
        presentations.update()
        commandJob = scope.launch {
            try {
                val receipt = currentRuntime.send(intent, revision)
                if (generation == sessionGeneration && commandReservation === reservation) {
                    observedOrigin?.let { qualificationObservation?.received(it, action, revision, receipt) }
                    receipt.error?.let { showProblem(it.toUiProblem()) }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (generation == sessionGeneration && commandReservation === reservation && !closed) {
                    val failure = error.toRuntimeFailure()
                    showProblem(failure.code, failure.recovery)
                }
            } finally {
                if (generation == sessionGeneration && commandReservation === reservation && !closed) {
                    commandReservation = null
                    mutableState.update { it.copy(pendingAction = null) }
                    presentations.update()
                }
            }
        }
        return true
    }

    fun retryConnection() {
        if (closed) return
        val current = runtime ?: return
        dismissProblem()
        if (state.value.connection.mode == SessionMode.LAN_HOST && state.value.session == null) {
            abandonRuntime()
            host()
        } else {
            current.retry()
        }
    }

    fun leaveSession() {
        if (closed) return
        val previous = detachRuntime()
        val departingGeneration = sessionGeneration
        clearSessionState()
        if (previous != null) scope.launch {
            try {
                previous.leave()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Leaving is complete locally; report a bounded cleanup failure, never peer text.
                if (!closed && departingGeneration == sessionGeneration) {
                    showProblem(UiProblemCode.CONNECTION_LOST)
                }
            } finally {
                previous.close()
            }
        }
    }

    private fun detachRuntime(): SessionRuntime? {
        sessionGeneration++
        presentations.update()
        scanRequest++
        commandJob?.cancel()
        commandJob = null
        commandReservation = null
        feedbackJob?.cancel()
        feedbackJob = null
        runtimeCollector?.cancel()
        runtimeCollector = null
        return runtime.also { runtime = null }
    }

    private fun abandonRuntime() {
        detachRuntime()?.close()
        mutableState.update {
            it.copy(
                session = null,
                invitation = null,
                connection = ConnectionUiState(),
                pendingAction = null,
                isScanningInvitation = false,
            )
        }
        presentations.update()
    }

    private fun clearSessionState() {
        mutableState.update {
            it.copy(
                screen = AppScreen.HOME,
                session = null,
                invitation = null,
                joinAddress = "",
                connection = ConnectionUiState(),
                pendingAction = null,
                problem = null,
                notice = null,
                leaveConfirmationRequested = false,
                isScanningInvitation = false,
            )
        }
        presentations.update()
    }

    fun setForeground(value: Boolean) {
        if (closed || state.value.isForeground == value) return
        mutableState.update {
            it.copy(isForeground = value, privacyEpoch = if (!value) it.privacyEpoch + 1 else it.privacyEpoch)
        }
        presentations.update()
        if (!value) feedbackJob?.cancel()
        try {
            services.feedback.setForeground(value)
        } catch (_: Exception) {
            showProblem(UiProblemCode.INTERNAL_ERROR)
        }
        updateRuntimeActivity()
        if (value && !state.value.isBackgrounded && state.value.session == null &&
            state.value.connection.mode == SessionMode.LAN_CLIENT &&
            state.value.connection.status == ConnectionStatus.DISCONNECTED &&
            (state.value.problem == null || state.value.problem?.code in connectionProblems)
        ) {
            // The permission alert may outlast the bounded initial handshake attempt.
            dismissProblem()
            runtime?.retry()
        }
    }

    /** Actual OS background is distinct from a permission alert or temporary loss of focus. */
    fun setBackgrounded(value: Boolean) {
        if (closed || state.value.isBackgrounded == value) return
        if (value && state.value.isForeground) setForeground(false)
        mutableState.update { it.copy(isBackgrounded = value) }
        presentations.update()
        updateRuntimeActivity()
    }

    private fun updateRuntimeActivity() {
        val current = runtime ?: return
        val state = state.value
        current.setForeground(
            if (current.state.value.mode == SessionMode.LAN_CLIENT) !state.isBackgrounded
            else state.isForeground && !state.isBackgrounded,
        )
    }

    fun setSystemReduceMotion(value: Boolean) {
        if (!closed) {
            mutableState.update { it.copy(systemReduceMotion = value) }
            presentations.update()
        }
    }

    fun copyInvitation() {
        val invitation = state.value.invitation ?: return
        try {
            services.copyText(invitation.joinAddress)
            if (!services.showsCopyConfirmation) {
                val notice = UiNotice(++occurrence, UiNoticeCode.INVITATION_COPIED)
                mutableState.update { it.copy(notice = notice) }
            }
        } catch (_: Exception) {
            showProblem(UiProblemCode.COPY_UNAVAILABLE)
        }
    }

    fun shareInvitation() {
        val invitation = state.value.invitation ?: return
        try {
            services.shareText(invitation.joinAddress)
        } catch (_: Exception) {
            showProblem(UiProblemCode.SHARING_UNAVAILABLE)
        }
    }

    fun scanInvitation() {
        if (closed || !state.value.canScanInvitation || state.value.isScanningInvitation) return
        val generation = sessionGeneration
        val request = ++scanRequest
        mutableState.update { it.copy(isScanningInvitation = true, problem = null) }
        try {
            services.scanInvitation { result ->
                scope.launch {
                    if (closed || generation != sessionGeneration || request != scanRequest ||
                        !state.value.isScanningInvitation
                    ) return@launch
                    mutableState.update { it.copy(isScanningInvitation = false) }
                    if (result == null || state.value.screen != AppScreen.JOIN) return@launch
                    try {
                        LanInvitation.decode(result)
                        setJoinAddress(result.trim())
                    } catch (_: IllegalArgumentException) {
                        showProblem(UiProblemCode.INVALID_INVITE, RecoveryAction.EDIT_INVITE)
                    }
                }
            }
        } catch (_: Exception) {
            mutableState.update { it.copy(isScanningInvitation = false) }
            showProblem(UiProblemCode.SCANNING_UNAVAILABLE)
        }
    }

    fun dismissProblem() {
        mutableState.update { it.copy(problem = null) }
    }

    fun dismissNotice() {
        mutableState.update { it.copy(notice = null) }
    }

    private fun showProblem(code: UiProblemCode, recovery: RecoveryAction = RecoveryAction.DISMISS) {
        val problem = UiProblem(++occurrence, code, recovery)
        mutableState.update { it.copy(problem = problem) }
    }

    private fun playSessionFeedback(previous: SessionView?, current: SessionView?, generation: Long) {
        val session = current ?: return
        if (!state.value.isForeground || previous?.sessionId != session.sessionId) return
        val before = previous.game ?: return
        val game = session.game ?: return
        val outcome = game.roundOutcome
        if (outcome != null && outcome != before.roundOutcome) {
            feedbackJob?.cancel()
            playFeedback(FeedbackCue.CHALLENGE)
            feedbackJob = scope.launch {
                delay(260)
                if (generation == sessionGeneration && state.value.isForeground) {
                    playFeedback(when {
                        game.phase == GamePhase.FINISHED && game.winnerId == session.selfPlayerId -> FeedbackCue.WIN
                        outcome.burnedOut -> FeedbackCue.LIGHT_OUT
                        else -> FeedbackCue.ROUND_END
                    })
                }
            }
        } else if (game.latestClaim != null && game.latestClaim != before.latestClaim) {
            playFeedback(FeedbackCue.CARD_PLAY)
        }
    }

    private fun playFeedback(cue: FeedbackCue) {
        if (closed || !state.value.isForeground) return
        try {
            services.feedback.play(cue, state.value.settings)
        } catch (_: Exception) {
            showProblem(UiProblemCode.INTERNAL_ERROR)
        }
    }

    private fun closeFeedback() {
        if (feedbackClosed) return
        feedbackClosed = true
        try {
            services.feedback.close()
        } catch (_: Exception) {
            showProblem(UiProblemCode.INTERNAL_ERROR)
        }
    }

    fun close() {
        if (closed) return
        closed = true
        presentations.close()
        detachRuntime()?.close()
        clearSessionState()
        closeFeedback()
        preferenceWrites.close()
        scope.cancel()
    }

    /** Useful for desktop shutdown and deterministic tests; ordinary native disposal calls close. */
    suspend fun awaitClosed() = job.join()

    private data class PreferenceWrite(val revision: Long, val settings: AppSettings)

    private companion object {
        fun normalizedName(raw: String): String? {
            val name = raw.trim()
            return name.takeIf {
                raw.length <= 128 && it.isNotEmpty() && it.length <= LastLightRules.MAX_DISPLAY_NAME_LENGTH &&
                    it.none(Char::isISOControl)
            }
        }

        val connectionProblems = setOf(
            UiProblemCode.CONNECTION_FAILED,
            UiProblemCode.CONNECTION_LOST,
            UiProblemCode.HOST_UNAVAILABLE,
            UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED,
        )
    }
}
