package dev.partydeck.app.controller

import dev.partydeck.session.CommandReceipt

/** Optional observation only. Never stores a hand, invite, command, or exported session identity. */
internal class SessionQualificationObservation {
    private var lastPresentationId: String? = null // Used only to assign a local ordinal; never serialized.
    private var ordinal = 0L
    private var receiptSerial = 0L
    private var lastReceipt = "null"
    private var exhausted = false

    fun presentationChanged(value: GameplayPresentationState) {
        val id = value.presentationId ?: return
        if (id == lastPresentationId) return
        if (ordinal == Long.MAX_VALUE) { exhausted = true; return }
        ordinal++
        lastPresentationId = id
    }

    data class Origin(val generation: Long, val ordinal: Long, val mode: GameplayPresentation)

    fun origin(state: AppUiState, generation: Long, fromRenderer: Boolean): Origin? {
        if (!state.isPractice || exhausted) return null
        presentationChanged(state.presentation)
        return Origin(generation, if (fromRenderer) ordinal else 0L,
            if (fromRenderer) state.presentation.selected else GameplayPresentation.COMPOSE)
    }

    fun received(origin: Origin, action: PendingAction, expectedRevision: Long, receipt: CommandReceipt) {
        if (receiptSerial == Long.MAX_VALUE) { exhausted = true; return }
        receiptSerial++
        // Every quoted variable below is an enum name. No exception/peer text or intent payload is used.
        lastReceipt = """{"serial":"$receiptSerial","sessionGeneration":"${origin.generation}","presentationOrdinal":"${origin.ordinal}","mode":"${origin.mode.name}","action":"${action.name}","expectedRevision":"$expectedRevision","revision":"${receipt.revision}","accepted":${receipt.accepted},"error":${receipt.error?.let { "\"${it.name}\"" } ?: "null"}}"""
    }

    fun snapshot(state: AppUiState, generation: Long, projection: Pair<Long, Long>?): String {
        // This route is restricted to practice. A host/join path exposes no session details.
        if (state.session != null && !state.isPractice) return """{"supported":false}"""
        presentationChanged(state.presentation)
        val session = state.session
        val game = session?.game
        val actions = game?.availableActions
        fun quoted(value: Enum<*>?) = value?.let { "\"${it.name}\"" } ?: "null"
        fun counter(value: Long?) = value?.let { "\"$it\"" } ?: "null"
        return """{"supported":true,"exhausted":$exhausted,"sessionGeneration":"$generation","sessionPresent":${session != null},"practice":${state.isPractice},"screen":"${state.screen.name}","sessionRevision":${counter(session?.revision)},"phase":${quoted(game?.phase)},"round":${game?.roundNumber ?: 0},"ownTurn":${game != null && game.viewerId != null && game.turnPlayerId == game.viewerId},"handCount":${game?.yourHand?.size ?: 0},"canSendAction":${state.canSendSessionAction},"canPlay":${actions?.canPlay == true},"canChallenge":${actions?.canChallenge == true},"canAdvanceRound":${session?.controls?.canAdvanceRound == true},"pending":${quoted(state.pendingAction)},"problem":${quoted(state.problem?.code)},"privacyEpoch":"${state.privacyEpoch}","leaveConfirmation":${state.leaveConfirmationRequested},"foreground":${state.isForeground},"backgrounded":${state.isBackgrounded},"mode":"${state.presentation.selected.name}","lifecycle":"${state.presentation.lifecycle.name}","fallbackReason":${quoted(state.presentation.fallbackReason)},"presentationOrdinal":"${if (state.presentation.presentationId != null) ordinal else 0L}","projectedRendererRevision":${counter(projection?.first)},"projectedSessionRevision":${counter(projection?.second)},"lastViewerReceipt":$lastReceipt}"""
    }
}
