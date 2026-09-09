package dev.partydeck.app.controller

import dev.partydeck.core.GamePhase
import dev.partydeck.core.LastLightEngine
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.CommandReceipt
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionDispatch
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.session.WireDecodeResult
import dev.partydeck.transport.ConnectionState
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanHost
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.random.Random

/** One serialized authority serves both real LAN peers and in-memory practice seats. */
internal class AuthoritySessionRuntime(
    parentScope: CoroutineScope,
    private val services: PlatformServices,
    private val transportFactory: LanTransportFactory,
    private val displayName: String,
    private val practice: Boolean,
    private val botDelayMillis: Long = 850,
) : OwnedSessionRuntime(
    parentScope,
    RuntimeSnapshot(
        mode = if (practice) SessionMode.PRACTICE else SessionMode.LAN_HOST,
        connection = ConnectionStatus.STARTING_HOST,
    ),
) {
    private val events = Channel<AuthorityEvent>(64)
    private val localHost = LocalSeat(SessionPeer("local-host"))
    private val localSeats = linkedMapOf(localHost.peer.connectionId to localHost)
    private val remotePeers = mutableMapOf<String, RemotePeer>()
    private val retiringWriters = mutableSetOf<Job>()
    private var transport: LanTransport? = null
    private var listener: LanHost? = null
    private var authority: HostAuthority? = null
    private var bot: PracticeBot? = null
    private var botJob: Job? = null
    private var initializing = true
    private var started = false

    init {
        registerCleanup {
            botJob?.cancel()
            events.cancel()
            remotePeers.values.toList().forEach { peer ->
                peer.outgoing.close()
                peer.reader?.cancel()
                peer.timeout?.cancel()
                peer.stateWatcher?.cancel()
            }
            transport?.close()
            remotePeers.clear()
            localSeats.clear()
            localHost.view = null
            mutableState.update { it.copy(view = null, invitation = null) }
            authority = null
            listener = null
            transport = null
        }
    }

    override fun start() {
        if (started || closed) return
        started = true
        scope.launch {
            try {
                initialize()
                for (event in events) {
                    handle(event)
                    scheduleBot()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                val problem = failure.toRuntimeFailure()
                mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
                report(problem.code, if (state.value.view == null) problem.recovery else RecoveryAction.RETURN_HOME)
                // Startup failure must release listeners before the user retries.
                withContext(NonCancellable) { transport?.close() }
            }
        }
    }

    private suspend fun initialize() {
        val sessionId = services.secureToken().take(32)
        val admission = services.secureToken()
        if (!practice) {
            transport = transportFactory.create()
            val acquiredHost = checkNotNull(transport).host(displayName)
            if (closed || !job.isActive) {
                withContext(NonCancellable) { acquiredHost.close() }
                throw CancellationException("The session was closed during hosting")
            }
            listener = acquiredHost
            val info = checkNotNull(listener).info
            val endpoint = info.endpoints.firstOrNull()
                ?: throw RuntimeFailure(UiProblemCode.HOST_UNAVAILABLE, RecoveryAction.RETRY_CONNECTION)
            val invitation = LanInvitation(sessionId, admission, endpoint, info.certificateSha256)
            mutableState.update {
                it.copy(invitation = HostInvitation(
                    joinAddress = invitation.encode(),
                    displayAddress = endpoint.host.ifBlank { endpoint.serviceName ?: info.serviceName },
                ))
            }
        }
        authority = HostAuthority(
            HostSessionConfig(sessionId, admission, displayName, localHost.peer),
            LastLightEngine(services.gameRandom()),
            services::secureToken,
        )
        dispatch(checkNotNull(authority).initialDispatch())
        if (practice) {
            bot = PracticeBot(Random(services.gameRandom().nextLong()))
            listOf("Moxie", "Pip", "Orbit").forEachIndexed { index, name ->
                val seat = LocalSeat(SessionPeer("practice-bot-$index"))
                localSeats[seat.peer.connectionId] = seat
                dispatch(checkNotNull(authority).handle(seat.peer, ClientMessage.Join(sessionId, admission, name)))
            }
            readyPracticeSeats()
            localCommand(localHost, ClientIntent.StartGame)
        }
        initializing = false
        publishHostView()
        mutableState.update { it.copy(connection = ConnectionStatus.CONNECTED, issue = null) }
        scheduleBot()

        listener?.let { host ->
            scope.launch {
                try {
                    host.incomingConnections.collect { events.send(AuthorityEvent.Connected(it)) }
                    if (!closed) events.send(AuthorityEvent.ListenerLost)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    if (!closed) events.send(AuthorityEvent.ListenerLost)
                }
            }
        }
    }

    override suspend fun send(intent: ClientIntent): CommandReceipt {
        if (closed || state.value.connection != ConnectionStatus.CONNECTED) {
            throw RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION)
        }
        val reply = CompletableDeferred<CommandReceipt>(job)
        events.send(AuthorityEvent.LocalCommand(intent, reply))
        return reply.await()
    }

    override suspend fun leave() {
        if (closed) return
        if (state.value.connection == ConnectionStatus.CONNECTED) {
            withTimeoutOrNull(1_500) {
                send(ClientIntent.EndSession)
                retiringWriters.toList().forEach { it.join() }
            }
        }
        close()
    }

    override fun setForeground(value: Boolean) {
        if (!closed) scope.launch { events.send(AuthorityEvent.Foreground(value)) }
    }

    override fun retry() {
        report(UiProblemCode.HOST_UNAVAILABLE, RecoveryAction.RETURN_HOME)
    }

    private suspend fun handle(event: AuthorityEvent) {
        val current = checkNotNull(authority)
        when (event) {
            is AuthorityEvent.LocalCommand -> {
                try {
                    val receipt = localCommand(localHost, event.intent)
                    if (practice && event.intent == ClientIntent.ReturnToLobby && receipt.accepted) {
                        readyPracticeSeats()
                    }
                    event.reply.complete(receipt)
                } catch (failure: Exception) {
                    event.reply.completeExceptionally(failure)
                    throw failure
                }
            }
            is AuthorityEvent.Connected -> addRemotePeer(event.connection)
            is AuthorityEvent.Message -> {
                if (remotePeers.containsKey(event.connectionId)) {
                    dispatch(current.handle(SessionPeer(event.connectionId), event.message))
                }
            }
            is AuthorityEvent.Disconnected -> {
                closeRemotePeer(event.connectionId, flush = false)
                dispatch(current.disconnect(SessionPeer(event.connectionId)))
            }
            is AuthorityEvent.Malformed -> {
                val peer = remotePeers[event.connectionId] ?: return
                peer.outgoing.trySend(SessionCodec.encodeServer(
                    ServerMessage.AdmissionRejected(current.sessionId, event.error),
                ))
                closeRemotePeer(event.connectionId, flush = true)
                dispatch(current.disconnect(SessionPeer(event.connectionId)))
            }
            is AuthorityEvent.AdmissionExpired -> {
                if (remotePeers[event.connectionId]?.admitted == false) {
                    closeRemotePeer(event.connectionId, flush = false)
                    dispatch(current.disconnect(SessionPeer(event.connectionId)))
                }
            }
            is AuthorityEvent.Foreground -> {
                foregroundActive = event.value
                if (!foregroundActive) botJob?.cancel()
            }
            is AuthorityEvent.BotTurn -> {
                val view = localHost.view ?: return
                if (!foregroundActive || view.revision != event.revision) return
                val seat = localSeats[event.connectionId] ?: return
                val game = seat.view?.game ?: return
                bot?.choose(game)?.let { localCommand(seat, it) }
            }
            AuthorityEvent.ListenerLost -> {
                dispatch(current.disconnect(localHost.peer))
                mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
                report(UiProblemCode.HOST_UNAVAILABLE, RecoveryAction.RETURN_HOME)
            }
        }
    }

    private fun localCommand(seat: LocalSeat, intent: ClientIntent): CommandReceipt {
        val current = checkNotNull(authority)
        val view = checkNotNull(seat.view)
        val commandId = seat.nextCommandId++
        val result = current.handle(seat.peer, ClientMessage.Command(
            current.sessionId, commandId, view.revision, intent,
        ))
        dispatch(result)
        return result.deliveries.asSequence()
            .filter { it.connectionId == seat.peer.connectionId }
            .mapNotNull { (it.message as? ServerMessage.Receipt)?.receipt }
            .firstOrNull { it.commandId == commandId }
            ?: throw RuntimeFailure(UiProblemCode.ACTION_REJECTED)
    }

    private fun readyPracticeSeats() {
        localSeats.values.filter { it !== localHost }.forEach { seat ->
            if (seat.view?.players?.firstOrNull { it.id == seat.view?.selfPlayerId }?.isReady == false) {
                localCommand(seat, ClientIntent.SetReady(true))
            }
        }
    }

    /** Only this event owner calls authority methods, including slow-peer disconnection effects. */
    private fun dispatch(first: SessionDispatch) {
        val queue = ArrayDeque<SessionDispatch>()
        queue.add(first)
        while (queue.isNotEmpty()) {
            val current = queue.removeFirst()
            val failedPeers = mutableSetOf<String>()
            current.deliveries.forEach { delivery ->
                val local = localSeats[delivery.connectionId]
                if (local != null) {
                    receiveLocal(local, delivery.message)
                } else {
                    remotePeers[delivery.connectionId]?.let { remote ->
                        if (delivery.message is ServerMessage.Welcome) {
                            remote.admitted = true
                            remote.timeout?.cancel()
                        }
                        if (!remote.outgoing.trySend(SessionCodec.encodeServer(delivery.message)).isSuccess) {
                            failedPeers += delivery.connectionId
                        }
                    }
                }
            }
            current.closeConnections.forEach {
                closeRemotePeer(it, flush = true)
                // Revocation affects authority immediately, independently of a slow socket flush.
                queue.add(checkNotNull(authority).disconnect(SessionPeer(it)))
            }
            failedPeers.forEach { id ->
                closeRemotePeer(id, flush = false)
                queue.add(checkNotNull(authority).disconnect(SessionPeer(id)))
            }
        }
        if (!initializing) publishHostView()
    }

    private fun receiveLocal(seat: LocalSeat, message: ServerMessage) {
        when (message) {
            is ServerMessage.Welcome -> {
                seat.view = message.view
                seat.nextCommandId = message.nextCommandId
            }
            is ServerMessage.Snapshot -> {
                if (message.view.revision >= (seat.view?.revision ?: -1)) seat.view = message.view
            }
            is ServerMessage.Ended -> if (seat === localHost) {
                mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
            }
            is ServerMessage.AdmissionRejected -> if (seat === localHost) {
                report(message.error.toUiProblem(), RecoveryAction.RETURN_HOME)
            }
            is ServerMessage.Receipt -> Unit
        }
    }

    private fun publishHostView() {
        mutableState.update { it.copy(view = localHost.view) }
    }

    private fun scheduleBot() {
        botJob?.cancel()
        botJob = null
        if (!practice || initializing || !foregroundActive || closed) return
        val view = localHost.view ?: return
        val game = view.game ?: return
        if (view.phase != SessionPhase.GAME || game.phase != GamePhase.PLAYING) return
        val seat = localSeats.values.firstOrNull {
            it !== localHost && it.view?.selfPlayerId == game.turnPlayerId
        } ?: return
        botJob = scope.launch {
            delay(botDelayMillis)
            events.send(AuthorityEvent.BotTurn(seat.peer.connectionId, view.revision))
        }
    }

    private fun addRemotePeer(connection: LanConnection) {
        if (connection.id in localSeats || connection.id in remotePeers || remotePeers.size >= 8) {
            scope.launch { connection.close() }
            return
        }
        val peer = RemotePeer(connection)
        remotePeers[connection.id] = peer
        peer.writer = scope.launch {
            try {
                for (bytes in peer.outgoing) withTimeout(2_000) { connection.send(bytes) }
            } catch (_: TimeoutCancellationException) {
                // A stalled peer loses its connection; authority updates occur in the event loop.
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Transport failure has the same bounded disconnection path as stream completion.
            } finally {
                withContext(NonCancellable) { connection.close() }
                if (job.isActive) events.send(AuthorityEvent.Disconnected(connection.id))
            }
        }
        peer.reader = scope.launch {
            try {
                connection.incoming.collect { bytes ->
                    when (val decoded = SessionCodec.decodeClient(bytes)) {
                        is WireDecodeResult.Success -> events.send(AuthorityEvent.Message(connection.id, decoded.value))
                        is WireDecodeResult.Failure -> events.send(AuthorityEvent.Malformed(connection.id, decoded.error))
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // The actor records presence; no raw peer payload or exception is logged.
            } finally {
                if (job.isActive) events.send(AuthorityEvent.Disconnected(connection.id))
            }
        }
        peer.stateWatcher = scope.launch {
            connection.state.collect {
                if (it != ConnectionState.Connected) events.send(AuthorityEvent.Disconnected(connection.id))
            }
        }
        peer.timeout = scope.launch {
            delay(10_000)
            events.send(AuthorityEvent.AdmissionExpired(connection.id))
        }
    }

    private fun closeRemotePeer(connectionId: String, flush: Boolean) {
        val peer = remotePeers.remove(connectionId) ?: return
        peer.reader?.cancel()
        peer.stateWatcher?.cancel()
        peer.timeout?.cancel()
        peer.outgoing.close()
        peer.writer?.let { writer ->
            if (!flush) writer.cancel()
            retiringWriters += writer
            writer.invokeOnCompletion { retiringWriters.remove(writer) }
        }
    }

    private class LocalSeat(val peer: SessionPeer) {
        var nextCommandId = 1L
        var view: SessionView? = null
    }

    private class RemotePeer(val connection: LanConnection) {
        val outgoing = Channel<ByteArray>(16)
        var admitted = false
        var reader: Job? = null
        var writer: Job? = null
        var stateWatcher: Job? = null
        var timeout: Job? = null
    }

    private sealed interface AuthorityEvent {
        data class LocalCommand(val intent: ClientIntent, val reply: CompletableDeferred<CommandReceipt>) : AuthorityEvent
        data class Connected(val connection: LanConnection) : AuthorityEvent
        data class Message(val connectionId: String, val message: ClientMessage) : AuthorityEvent
        data class Disconnected(val connectionId: String) : AuthorityEvent
        data class Malformed(val connectionId: String, val error: SessionError) : AuthorityEvent
        data class AdmissionExpired(val connectionId: String) : AuthorityEvent
        data class Foreground(val value: Boolean) : AuthorityEvent
        data class BotTurn(val connectionId: String, val revision: Long) : AuthorityEvent
        data object ListenerLost : AuthorityEvent
    }
}
