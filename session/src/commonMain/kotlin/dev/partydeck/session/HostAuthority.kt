package dev.partydeck.session

import dev.partydeck.core.AvailableActions
import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameRejection
import dev.partydeck.core.GameState
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.LastLightRules
import dev.partydeck.core.PlayerId
import dev.partydeck.core.PlayerIdentity

/**
 * Owns one in-memory table. Every call, including disconnect and resume, must run on the same
 * controller-owned serial execution gate. Only this object receives authoritative game state.
 *
 * [secureToken] must return 32 fresh CSPRNG bytes encoded as 64 lowercase hexadecimal characters.
 * It must be independent of the game engine's random source. Deterministic sources are for tests.
 */
class HostAuthority(
    config: HostSessionConfig,
    private val engine: LastLightEngine,
    private val secureToken: () -> String,
) {
    val sessionId: String = config.sessionId
    val hostPlayerId: PlayerId = "p0"

    private var admissionSecret: String? = config.admissionSecret
    private val replayCacheSize = config.replayCacheSize
    private val seats = linkedMapOf<PlayerId, Seat>()
    private val connections = mutableMapOf<String, PlayerId>()
    private var phase = SessionPhase.LOBBY
    private var revision = 0L
    private var nextPlayerNumber = 1L
    private var game: GameState? = null

    init {
        require(sessionId.isNotBlank() && sessionId.length <= MAX_ID_LENGTH)
        require(isCredential(config.admissionSecret)) { "Invalid admission credential format" }
        require(config.hostPeer.connectionId.isNotBlank())
        require(replayCacheSize in 1..MAX_REPLAY_CACHE_SIZE)
        val hostName = normalizeDisplayName(config.hostDisplayName)
        require(hostName != null) { "Invalid host display name" }
        val host = Seat(hostPlayerId, hostName, newCredential(), config.hostPeer.connectionId, true)
        seats[host.id] = host
        connections[config.hostPeer.connectionId] = host.id
    }

    /** Idempotent welcome for the in-process host. Calling it does not change session state. */
    fun initialDispatch(): SessionDispatch {
        val host = seats[hostPlayerId] ?: return SessionDispatch()
        return SessionDispatch(listOf(welcome(host)))
    }

    fun handle(peer: SessionPeer, message: ClientMessage): SessionDispatch {
        if (message.protocolVersion != PROTOCOL_VERSION) {
            return admissionRejected(peer, SessionError.UNSUPPORTED_VERSION)
        }
        if (message.sessionId != sessionId) return admissionRejected(peer, SessionError.WRONG_SESSION)
        if (phase == SessionPhase.ENDED) return admissionRejected(peer, SessionError.SESSION_CLOSED)
        if (peer.connectionId.isBlank() || !isBoundedClientMessage(message)) {
            return admissionRejected(peer, SessionError.MALFORMED_MESSAGE)
        }
        return when (message) {
            is ClientMessage.Join -> join(peer, message)
            is ClientMessage.Resume -> resume(peer, message)
            is ClientMessage.Command -> command(peer, message)
        }
    }

    /** A late disconnect from a replaced channel has no effect on its replacement. */
    fun disconnect(peer: SessionPeer): SessionDispatch {
        val seat = seatFor(peer) ?: return SessionDispatch()
        if (seat.id == hostPlayerId) return terminateFromDisconnect()
        connections.remove(peer.connectionId)
        seat.connectionId = null
        seat.isReady = false
        advanceRevision()
        return SessionDispatch(snapshotDeliveries())
    }

    fun viewFor(peer: SessionPeer): SessionView? = seatFor(peer)?.let(::viewForSeat)

    private fun join(peer: SessionPeer, message: ClientMessage.Join): SessionDispatch {
        if (!credentialMatches(admissionSecret, message.admissionSecret)) {
            return admissionRejected(peer, SessionError.INVALID_CREDENTIALS)
        }
        seatFor(peer)?.let { return SessionDispatch(listOf(welcome(it))) }
        if (phase != SessionPhase.LOBBY) return admissionRejected(peer, SessionError.WRONG_PHASE)
        val name = normalizeDisplayName(message.displayName)
            ?: return admissionRejected(peer, SessionError.INVALID_NAME)
        if (seats.size >= LastLightRules.MAX_PLAYERS) return admissionRejected(peer, SessionError.LOBBY_FULL)
        if (nextPlayerNumber == Long.MAX_VALUE || revision == Long.MAX_VALUE) {
            return admissionRejected(peer, SessionError.SESSION_EXHAUSTED)
        }
        val seat = Seat("p${nextPlayerNumber++}", name, newCredential(), peer.connectionId, false)
        seats[seat.id] = seat
        connections[peer.connectionId] = seat.id
        resetGuestReadiness()
        advanceRevision()
        return SessionDispatch(listOf(welcome(seat)) + snapshotDeliveries(except = peer.connectionId))
    }

    private fun resume(peer: SessionPeer, message: ClientMessage.Resume): SessionDispatch {
        val seat = seats[message.playerId]
        if (seat == null || !credentialMatches(seat.reconnectToken, message.reconnectToken)) {
            return admissionRejected(peer, SessionError.INVALID_CREDENTIALS)
        }
        // The host is local authority, not a remotely replaceable seat.
        if (seat.id == hostPlayerId && seat.connectionId != peer.connectionId) {
            return admissionRejected(peer, SessionError.INVALID_CREDENTIALS)
        }
        val existingSeat = seatFor(peer)
        if (existingSeat != null) {
            return if (existingSeat.id == seat.id) SessionDispatch(listOf(welcome(seat)))
            else admissionRejected(peer, SessionError.ALREADY_ADMITTED)
        }
        if (revision == Long.MAX_VALUE) return admissionRejected(peer, SessionError.SESSION_EXHAUSTED)
        val oldConnection = seat.connectionId
        oldConnection?.let(connections::remove)
        seat.connectionId = peer.connectionId
        if (phase == SessionPhase.LOBBY && seat.id != hostPlayerId) seat.isReady = false
        connections[peer.connectionId] = seat.id
        advanceRevision()
        return SessionDispatch(
            deliveries = listOf(welcome(seat)) + snapshotDeliveries(except = peer.connectionId),
            closeConnections = listOfNotNull(oldConnection),
        )
    }

    private fun command(peer: SessionPeer, message: ClientMessage.Command): SessionDispatch {
        val seat = seatFor(peer) ?: return admissionRejected(peer, SessionError.NOT_ADMITTED)
        if (message.commandId <= 0L || message.commandId == Long.MAX_VALUE) {
            return reply(seat, CommandReceipt(message.commandId, revision, SessionError.INVALID_COMMAND_ID))
        }
        seat.receipts[message.commandId]?.let { cached ->
            val receipt = if (cached.command == message) cached.receipt
            else CommandReceipt(message.commandId, revision, SessionError.COMMAND_ID_CONFLICT)
            return reply(seat, receipt)
        }
        if (message.commandId <= seat.highWaterMark) {
            return reply(seat, CommandReceipt(message.commandId, revision, SessionError.COMMAND_TOO_OLD))
        }
        val effect = when {
            revision == Long.MAX_VALUE -> Effect(error = SessionError.SESSION_EXHAUSTED)
            message.expectedRevision != revision -> Effect(error = SessionError.STALE_REVISION)
            else -> applyIntent(seat, message.intent)
        }
        if (effect.changed) advanceRevision()
        val receipt = CommandReceipt(message.commandId, revision, effect.error, effect.gameError)
        seat.highWaterMark = message.commandId
        // Freeze collection input: callers can reuse or clear their selection list after sending.
        val retained = when (val intent = message.intent) {
            is ClientIntent.PlayCards -> message.copy(intent = intent.copy(cardIds = intent.cardIds.toList()))
            else -> message
        }
        seat.receipts[message.commandId] = CachedCommand(retained, receipt)
        if (seat.receipts.size > replayCacheSize) seat.receipts.remove(seat.receipts.keys.first())

        if (!effect.changed) return reply(seat, receipt)
        val deliveries = mutableListOf(Delivery(peer.connectionId, ServerMessage.Receipt(sessionId, receipt)))
        deliveries += snapshotDeliveries()
        deliveries += effect.closedPeers.map { (id, reason) ->
            Delivery(id, ServerMessage.Ended(sessionId, reason))
        }
        return SessionDispatch(deliveries, effect.closedPeers.keys.toList())
    }

    private fun applyIntent(actor: Seat, intent: ClientIntent): Effect = when (intent) {
        is ClientIntent.SetReady -> when {
            phase != SessionPhase.LOBBY -> Effect(error = SessionError.WRONG_PHASE)
            actor.id == hostPlayerId && !intent.ready -> Effect(error = SessionError.HOST_ALWAYS_READY)
            actor.isReady == intent.ready -> Effect()
            else -> { actor.isReady = intent.ready; Effect(changed = true) }
        }
        ClientIntent.StartGame -> hostOnly(actor) {
            startError()?.let { return@hostOnly Effect(error = it) }
            game = engine.start(seats.values.map { PlayerIdentity(it.id, it.displayName) })
            phase = SessionPhase.GAME
            Effect(changed = true)
        }
        is ClientIntent.PlayCards -> gameAction(GameAction.Play(actor.id, intent.cardIds))
        ClientIntent.Challenge -> gameAction(GameAction.Challenge(actor.id))
        ClientIntent.AdvanceRound -> hostOnly(actor) {
            val currentGame = game ?: return@hostOnly Effect(error = SessionError.WRONG_PHASE)
            if (pausedPlayerIds().isNotEmpty()) return@hostOnly Effect(error = SessionError.PLAYERS_DISCONNECTED)
            applyGameDecision(engine.advanceRound(currentGame))
        }
        ClientIntent.ReturnToLobby -> hostOnly(actor) {
            if (phase != SessionPhase.GAME) return@hostOnly Effect(error = SessionError.WRONG_PHASE)
            game = null
            phase = SessionPhase.LOBBY
            seats.values.filter { it.hasLeft }.map { it.id }.forEach(seats::remove)
            resetGuestReadiness()
            Effect(changed = true)
        }
        is ClientIntent.KickPlayer -> hostOnly(actor) {
            if (phase != SessionPhase.LOBBY) return@hostOnly Effect(error = SessionError.WRONG_PHASE)
            if (intent.playerId == hostPlayerId) return@hostOnly Effect(error = SessionError.CANNOT_REMOVE_HOST)
            val target = seats[intent.playerId] ?: return@hostOnly Effect(error = SessionError.UNKNOWN_PLAYER)
            val connection = target.connectionId
            removeSeat(target)
            resetGuestReadiness()
            Effect(changed = true, closedPeers = connection?.let { mapOf(it to SessionEndReason.REMOVED) }.orEmpty())
        }
        ClientIntent.Leave -> {
            if (actor.id == hostPlayerId) endEffect(SessionEndReason.HOST_ENDED)
            else {
                val connection = checkNotNull(actor.connectionId)
                if (phase == SessionPhase.LOBBY) {
                    removeSeat(actor)
                    resetGuestReadiness()
                } else {
                    connections.remove(connection)
                    actor.connectionId = null
                    actor.reconnectToken = null
                    actor.isReady = false
                    actor.hasLeft = true
                    actor.receipts.clear()
                }
                Effect(changed = true, closedPeers = mapOf(connection to SessionEndReason.LEFT))
            }
        }
        ClientIntent.EndSession -> hostOnly(actor) { endEffect(SessionEndReason.HOST_ENDED) }
    }

    private fun gameAction(action: GameAction): Effect {
        val currentGame = game ?: return Effect(error = SessionError.WRONG_PHASE)
        if (pausedPlayerIds().isNotEmpty()) return Effect(error = SessionError.PLAYERS_DISCONNECTED)
        return applyGameDecision(engine.apply(currentGame, action))
    }

    private fun applyGameDecision(decision: GameDecision): Effect = when (decision) {
        is GameDecision.Applied -> { game = decision.state; Effect(changed = true) }
        is GameDecision.Rejected -> Effect(error = SessionError.ILLEGAL_GAME_ACTION, gameError = decision.reason)
    }

    private inline fun hostOnly(actor: Seat, operation: () -> Effect): Effect =
        if (actor.id != hostPlayerId) Effect(error = SessionError.NOT_HOST) else operation()

    private fun startError(): SessionError? = when {
        phase != SessionPhase.LOBBY -> SessionError.WRONG_PHASE
        seats.size < LastLightRules.MIN_PLAYERS -> SessionError.NOT_ENOUGH_PLAYERS
        seats.values.any { it.connectionId == null } -> SessionError.PLAYERS_DISCONNECTED
        seats.values.any { !it.isReady } -> SessionError.PLAYERS_NOT_READY
        else -> null
    }

    private fun pausedPlayerIds(): List<PlayerId> {
        val currentGame = game ?: return emptyList()
        if (currentGame.phase == GamePhase.FINISHED) return emptyList()
        return currentGame.players.filter { !it.eliminated && seats[it.identity.id]?.connectionId == null }
            .map { it.identity.id }
    }

    private fun viewForSeat(seat: Seat): SessionView {
        val paused = pausedPlayerIds()
        val gameView = game?.let { state ->
            val view = engine.viewFor(state, seat.id)
            if (paused.isEmpty()) view else view.copy(availableActions = AvailableActions())
        }
        return SessionView(
            sessionId = sessionId,
            revision = revision,
            selfPlayerId = seat.id,
            hostPlayerId = hostPlayerId,
            phase = phase,
            players = seats.values.map { LobbyPlayer(it.id, it.displayName, it.isReady, it.connectionId != null) },
            game = gameView,
            pausedPlayerIds = paused,
            controls = SessionControls(
                canStartGame = seat.id == hostPlayerId && startError() == null,
                canAdvanceRound = seat.id == hostPlayerId && game?.phase == GamePhase.ROUND_ENDED && paused.isEmpty(),
                canReturnToLobby = seat.id == hostPlayerId && phase == SessionPhase.GAME,
            ),
        )
    }

    private fun welcome(seat: Seat): Delivery = Delivery(
        checkNotNull(seat.connectionId),
        ServerMessage.Welcome(
            sessionId, seat.id, checkNotNull(seat.reconnectToken), seat.highWaterMark + 1L, viewForSeat(seat),
        ),
    )

    private fun reply(seat: Seat, receipt: CommandReceipt): SessionDispatch {
        val connection = checkNotNull(seat.connectionId)
        return SessionDispatch(listOf(
            Delivery(connection, ServerMessage.Receipt(sessionId, receipt)),
            Delivery(connection, ServerMessage.Snapshot(sessionId, viewForSeat(seat))),
        ))
    }

    private fun snapshotDeliveries(except: String? = null): List<Delivery> = seats.values.mapNotNull { seat ->
        seat.connectionId?.takeUnless { it == except }?.let { connection ->
            Delivery(connection, ServerMessage.Snapshot(sessionId, viewForSeat(seat)))
        }
    }

    private fun admissionRejected(peer: SessionPeer, error: SessionError) = SessionDispatch(
        listOf(Delivery(peer.connectionId, ServerMessage.AdmissionRejected(sessionId, error))),
        listOf(peer.connectionId),
    )

    private fun seatFor(peer: SessionPeer): Seat? = connections[peer.connectionId]?.let(seats::get)

    private fun resetGuestReadiness() {
        seats.values.forEach { it.isReady = it.id == hostPlayerId }
    }

    private fun removeSeat(seat: Seat) {
        seat.connectionId?.let(connections::remove)
        seat.connectionId = null
        seat.reconnectToken = null
        seat.receipts.clear()
        seats.remove(seat.id)
    }

    private fun endEffect(reason: SessionEndReason): Effect {
        val closed = connections.keys.associateWith { reason }
        seats.values.forEach { it.reconnectToken = null; it.receipts.clear() }
        seats.clear()
        connections.clear()
        admissionSecret = null
        game = null
        phase = SessionPhase.ENDED
        return Effect(changed = true, closedPeers = closed)
    }

    private fun terminateFromDisconnect(): SessionDispatch {
        val effect = endEffect(SessionEndReason.HOST_DISCONNECTED)
        advanceRevision()
        return SessionDispatch(
            effect.closedPeers.map { (id, reason) -> Delivery(id, ServerMessage.Ended(sessionId, reason)) },
            effect.closedPeers.keys.toList(),
        )
    }

    private fun advanceRevision() {
        check(revision < Long.MAX_VALUE) { "Session revision exhausted" }
        revision++
    }

    private fun newCredential(): String {
        repeat(8) {
            val candidate = secureToken()
            require(isCredential(candidate)) { "Secure token source returned an invalid credential" }
            if (candidate != admissionSecret && seats.values.none { it.reconnectToken == candidate }) return candidate
        }
        error("Secure token source did not provide a unique credential")
    }

    private class Seat(
        val id: PlayerId,
        val displayName: String,
        var reconnectToken: String?,
        var connectionId: String?,
        var isReady: Boolean,
        var hasLeft: Boolean = false,
        var highWaterMark: Long = 0L,
        val receipts: LinkedHashMap<Long, CachedCommand> = linkedMapOf(),
    )

    private data class CachedCommand(val command: ClientMessage.Command, val receipt: CommandReceipt)

    private data class Effect(
        val error: SessionError? = null,
        val gameError: GameRejection? = null,
        val changed: Boolean = false,
        val closedPeers: Map<String, SessionEndReason> = emptyMap(),
    )

    private companion object {
        const val MAX_REPLAY_CACHE_SIZE = 256
    }
}
