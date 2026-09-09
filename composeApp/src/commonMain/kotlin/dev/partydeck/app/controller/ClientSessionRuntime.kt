package dev.partydeck.app.controller

import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.CommandReceipt
import dev.partydeck.session.PROTOCOL_VERSION
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionControls
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.session.WireDecodeResult
import dev.partydeck.transport.ConnectionState
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import dev.partydeck.transport.TransportException
import dev.partydeck.transport.TransportFailureCode
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull

/** Retains a seat credential only in memory; reconnect always requests a fresh authoritative view. */
internal class ClientSessionRuntime(
    parentScope: CoroutineScope,
    private val transportFactory: LanTransportFactory,
    private val invitation: LanInvitation,
    private val displayName: String,
) : OwnedSessionRuntime(
    parentScope,
    RuntimeSnapshot(SessionMode.LAN_CLIENT, ConnectionStatus.CONNECTING),
) {
    private var transport: LanTransport? = null
    private var connectionLoop: Job? = null
    private val connectionLoopLifetime = Mutex()
    private var activeLink: Link? = null
    private var credentials: Credentials? = null
    private var pending: PendingCommand? = null
    private var started = false
    private var terminal = false

    init {
        registerCleanup {
            pending?.reply?.cancel()
            pending = null
            credentials = null
            activeLink?.scope?.cancel()
            activeLink = null
            transport?.close()
            transport = null
            mutableState.update { it.copy(view = null) }
        }
    }

    override fun start() {
        if (started || closed) return
        started = true
        launchConnectionLoop()
    }

    override fun retry() {
        if (!closed && !terminal && foregroundActive && state.value.connection != ConnectionStatus.CONNECTED) {
            launchConnectionLoop()
        }
    }

    private fun launchConnectionLoop() {
        connectionLoop?.cancel()
        connectionLoop = scope.launch {
            // A rapid retry may cancel another retry before it runs. Serialize the entire
            // lifetime so every predecessor has finished native cleanup before a new browse.
            connectionLoopLifetime.withLock {
                try {
                    if (transport == null) transport = transportFactory.create()
                    while (!closed && foregroundActive && !terminal) {
                        val link = connectBatch(coroutineContext[Job]) ?: return@launch
                        val failure = link.lost.await()
                        discardLink(link)
                        if (!closed && foregroundActive && !terminal) {
                            mutableState.update { it.copy(connection = ConnectionStatus.RECONNECTING) }
                            report(failure.code, failure.recovery)
                        }
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    val failure = error.toRuntimeFailure()
                    mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
                    report(failure.code, failure.recovery)
                } finally {
                    // A cancelled older loop must never close a replacement loop's connection.
                    val link = activeLink
                    if (link != null && link.owner === coroutineContext[Job]) discardLink(link)
                }
            }
        }
    }

    private suspend fun connectBatch(owner: Job?): Link? = coroutineScope {
        val currentTransport = checkNotNull(transport)
        val discovery = if (invitation.endpoint.serviceName != null) launch {
            try {
                currentTransport.startDiscovery()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Discovery is optional. A reachable, pinned direct invitation still works.
            }
        } else null
        try {
            connectWithRetries(owner)
        } finally {
            if (discovery != null) withContext(NonCancellable) {
                discovery.cancelAndJoin()
                try {
                    currentTransport.stopDiscovery()
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    // An unavailable discovery backend cannot invalidate a successful join.
                }
            }
        }
    }

    private suspend fun connectWithRetries(owner: Job?): Link? {
        val resuming = credentials != null
        var lastFailure = RuntimeFailure(UiProblemCode.CONNECTION_FAILED, RecoveryAction.RETRY_CONNECTION)
        mutableState.update {
            it.copy(
                connection = if (resuming) ConnectionStatus.RECONNECTING else ConnectionStatus.CONNECTING,
                retryAttempt = 0,
            )
        }
        val result = withTimeoutOrNull(if (resuming) 30_000L else 10_000L) batch@ {
            repeat(if (resuming) 5 else 1) { attempt ->
                if (!foregroundActive || closed || terminal) return@batch null
                if (resuming) delay(minOf(500L shl attempt, 4_000L))
                mutableState.update { it.copy(retryAttempt = attempt + 1) }
                try {
                    val link = withTimeoutOrNull(8_000) { openLink(owner) }
                    if (link != null) return@batch link
                    lastFailure = RuntimeFailure(UiProblemCode.CONNECTION_FAILED, RecoveryAction.RETRY_CONNECTION)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    lastFailure = error.toRuntimeFailure()
                    if (lastFailure.code in terminalProblems) {
                        terminal = true
                    }
                }
                activeLink?.let { discardLink(it) }
                // Permission can be restored in settings, but more attempts in this batch
                // cannot restore it. Retain the seat for an explicit Retry afterwards.
                if (terminal || lastFailure.code == UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED) return@batch null
            }
            null
        }
        if (result == null && !closed && foregroundActive) {
            activeLink?.let { discardLink(it) }
            mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
            val code = if (resuming && !terminal && lastFailure.code == UiProblemCode.CONNECTION_FAILED) {
                UiProblemCode.HOST_UNAVAILABLE
            } else lastFailure.code
            report(code, if (terminal && credentials != null) RecoveryAction.RETURN_HOME else lastFailure.recovery)
        }
        return result
    }

    private suspend fun openLink(owner: Job?): Link {
        val connection = connectToInvitedHost()
        if (closed || !currentCoroutineContext().isActive) {
            withContext(NonCancellable) { connection.close() }
            throw CancellationException("The connection attempt was cancelled")
        }
        val linkScope = CoroutineScope(scope.coroutineContext + SupervisorJob(job))
        val link = Link(connection, linkScope, owner)
        activeLink = link
        linkScope.launch {
            try {
                connection.incoming.collect { bytes ->
                    if (activeLink !== link) return@collect
                    when (val decoded = SessionCodec.decodeServer(bytes)) {
                        is WireDecodeResult.Success -> receive(link, decoded.value)
                        is WireDecodeResult.Failure -> failLink(link, RuntimeFailure(
                            if (decoded.error == SessionError.UNSUPPORTED_VERSION) UiProblemCode.VERSION_MISMATCH
                            else UiProblemCode.JOIN_REJECTED,
                            RecoveryAction.EDIT_INVITE,
                        ))
                    }
                }
                failLink(link, RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                failLink(link, error.toRuntimeFailure())
            }
        }
        linkScope.launch {
            connection.state.collect { connectionState ->
                if (connectionState != ConnectionState.Connected) {
                    failLink(link, RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION))
                }
            }
        }
        val currentCredentials = credentials
        val hello = if (currentCredentials == null) {
            ClientMessage.Join(invitation.sessionId, invitation.admissionSecret, displayName)
        } else {
            ClientMessage.Resume(invitation.sessionId, currentCredentials.playerId, currentCredentials.token)
        }
        connection.send(SessionCodec.encodeClient(hello))
        link.welcome.await()
        return link
    }

    private suspend fun connectToInvitedHost(): LanConnection {
        val currentTransport = checkNotNull(transport)
        try {
            return currentTransport.connect(invitation.endpoint, invitation.certificateSha256)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            val serviceName = invitation.endpoint.serviceName ?: throw error
            // Never try another endpoint after a permission, identity, or protocol failure.
            if ((error as? TransportException)?.failure?.code !in rediscoverableFailures) throw error
            // Browsing starts concurrently with the direct attempt. Native discovery may
            // report "started" before resolving the invited host's changed address.
            val discovered = withTimeoutOrNull(5_000) {
                currentTransport.discoveredHosts.first { hosts ->
                    hosts.any { it.serviceName == serviceName }
                }.first { it.serviceName == serviceName }
            } ?: throw error
            return currentTransport.connect(
                discovered.endpoint.copy(serviceName = serviceName),
                invitation.certificateSha256,
            )
        }
    }

    override suspend fun send(intent: ClientIntent): CommandReceipt {
        val link = activeLink
        val seat = credentials
        val view = state.value.view
        if (closed || !foregroundActive || terminal || link == null || seat == null || view == null ||
            state.value.connection != ConnectionStatus.CONNECTED
        ) {
            throw RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION)
        }
        if (pending != null || seat.nextCommandId >= Long.MAX_VALUE) {
            throw RuntimeFailure(UiProblemCode.ACTION_REJECTED)
        }
        val command = ClientMessage.Command(
            invitation.sessionId, seat.nextCommandId++, view.revision, intent,
        )
        val request = PendingCommand(command.commandId, link, CompletableDeferred(job))
        pending = request
        return try {
            withTimeout(12_000) {
                connectionSend(link, command)
                request.reply.await()
            }
        } catch (_: TimeoutCancellationException) {
            currentCoroutineContext().ensureActive()
            val failure = RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION)
            failLink(link, failure)
            throw failure
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            val failure = error.toRuntimeFailure()
            failLink(link, failure)
            throw failure
        } finally {
            if (pending === request) pending = null
        }
    }

    private suspend fun connectionSend(link: Link, command: ClientMessage.Command) {
        link.connection.send(SessionCodec.encodeClient(command))
    }

    override suspend fun leave() {
        pending?.reply?.cancel()
        pending = null
        if (!closed && state.value.connection == ConnectionStatus.CONNECTED) {
            withTimeoutOrNull(1_500) {
                repeat(2) {
                    val receipt = send(ClientIntent.Leave)
                    if (receipt.error != SessionError.STALE_REVISION) return@withTimeoutOrNull
                }
            }
        }
        close()
    }

    override fun setForeground(value: Boolean) {
        if (closed || foregroundActive == value) return
        foregroundActive = value
        if (!value) {
            connectionLoop?.cancel()
            activeLink?.let {
                failLink(it, RuntimeFailure(UiProblemCode.CONNECTION_LOST, RecoveryAction.RETRY_CONNECTION))
            }
            mutableState.update {
                it.copy(connection = if (credentials == null) ConnectionStatus.DISCONNECTED else ConnectionStatus.RECONNECTING)
            }
        } else {
            retry()
        }
    }

    private fun receive(link: Link, message: ServerMessage) {
        if (activeLink !== link || closed || link.failed) return
        if (message.sessionId != invitation.sessionId || message.protocolVersion != PROTOCOL_VERSION) {
            failLink(link, RuntimeFailure(UiProblemCode.VERSION_MISMATCH, RecoveryAction.EDIT_INVITE))
            return
        }
        if (!link.admitted && (message is ServerMessage.Snapshot || message is ServerMessage.Receipt)) {
            failLink(link, RuntimeFailure(UiProblemCode.JOIN_REJECTED, RecoveryAction.EDIT_INVITE))
            return
        }
        when (message) {
            is ServerMessage.Welcome -> {
                if (link.admitted) return
                if ((credentials != null && credentials?.playerId != message.playerId) ||
                    message.view.revision < (state.value.view?.revision ?: -1)
                ) {
                    failLink(link, RuntimeFailure(UiProblemCode.JOIN_REJECTED, RecoveryAction.EDIT_INVITE))
                    return
                }
                link.admitted = true
                credentials = Credentials(message.playerId, message.reconnectToken, message.nextCommandId)
                mutableState.update {
                    it.copy(view = message.view, connection = ConnectionStatus.CONNECTED, retryAttempt = 0, issue = null)
                }
                link.welcome.complete(Unit)
            }
            is ServerMessage.Snapshot -> {
                if (message.view.selfPlayerId != credentials?.playerId) {
                    failLink(link, RuntimeFailure(UiProblemCode.JOIN_REJECTED, RecoveryAction.EDIT_INVITE))
                    return
                }
                acceptSnapshot(message.view)
                completePendingIfCovered()
            }
            is ServerMessage.Receipt -> {
                pending?.takeIf { it.link === link && it.id == message.receipt.commandId }?.let {
                    it.receipt = message.receipt
                    completePendingIfCovered()
                }
            }
            is ServerMessage.AdmissionRejected -> {
                val problem = RuntimeFailure(message.error.toUiProblem(), RecoveryAction.EDIT_INVITE)
                terminal = true
                report(problem.code, if (credentials == null) problem.recovery else RecoveryAction.RETURN_HOME)
                failLink(link, problem)
            }
            is ServerMessage.Ended -> {
                terminal = true
                pending?.receipt?.let { pending?.reply?.complete(it) }
                credentials = null
                mutableState.update {
                    it.copy(
                        connection = ConnectionStatus.DISCONNECTED,
                        view = it.view?.copy(
                            phase = SessionPhase.ENDED,
                            game = null,
                            pausedPlayerIds = emptyList(),
                            controls = SessionControls(),
                        ),
                    )
                }
                report(UiProblemCode.SESSION_ENDED, RecoveryAction.RETURN_HOME)
                failLink(link, RuntimeFailure(UiProblemCode.SESSION_ENDED, RecoveryAction.RETURN_HOME))
            }
        }
    }

    private fun acceptSnapshot(view: SessionView) {
        if (view.sessionId != invitation.sessionId) return
        mutableState.update { current ->
            if (view.revision >= (current.view?.revision ?: -1)) current.copy(view = view) else current
        }
    }

    private fun completePendingIfCovered() {
        val request = pending ?: return
        val receipt = request.receipt ?: return
        if ((state.value.view?.revision ?: -1) >= receipt.revision) request.reply.complete(receipt)
    }

    private fun failLink(link: Link, failure: RuntimeFailure) {
        if (activeLink !== link || link.failed) return
        link.failed = true
        link.welcome.completeExceptionally(failure)
        link.lost.complete(failure)
        pending?.takeIf { it.link === link }?.reply?.completeExceptionally(failure)
        if (failure.code in terminalProblems) {
            terminal = true
            report(failure.code, if (credentials == null) failure.recovery else RecoveryAction.RETURN_HOME)
        }
        if (state.value.connection == ConnectionStatus.CONNECTED) {
            mutableState.update { it.copy(connection = ConnectionStatus.DISCONNECTED) }
        }
    }

    private suspend fun discardLink(link: Link) {
        if (activeLink === link) activeLink = null
        link.scope.cancel()
        withContext(NonCancellable) { link.connection.close() }
    }

    private class Credentials(val playerId: String, val token: String, var nextCommandId: Long) {
        override fun toString(): String = "Credentials(<redacted>)"
    }

    private class PendingCommand(
        val id: Long,
        val link: Link,
        val reply: CompletableDeferred<CommandReceipt>,
        var receipt: CommandReceipt? = null,
    )

    private class Link(val connection: LanConnection, val scope: CoroutineScope, val owner: Job?) {
        var admitted = false
        var failed = false
        val welcome = CompletableDeferred<Unit>()
        val lost = CompletableDeferred<RuntimeFailure>()
    }

    private companion object {
        val rediscoverableFailures = setOf(
            TransportFailureCode.UNAVAILABLE,
            TransportFailureCode.TIMED_OUT,
            TransportFailureCode.IO_ERROR,
        )
        val terminalProblems = setOf(
            UiProblemCode.VERSION_MISMATCH,
            UiProblemCode.JOIN_REJECTED,
            UiProblemCode.SESSION_ENDED,
            UiProblemCode.SESSION_FULL,
            UiProblemCode.INVALID_NAME,
        )
    }
}
