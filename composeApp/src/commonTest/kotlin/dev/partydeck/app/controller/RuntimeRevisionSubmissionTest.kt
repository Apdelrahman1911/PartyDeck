package dev.partydeck.app.controller

import dev.partydeck.core.LastLightEngine
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionDispatch
import dev.partydeck.session.SessionEndReason
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.session.WireDecodeResult
import dev.partydeck.transport.ConnectionState
import dev.partydeck.transport.DiscoveredHost
import dev.partydeck.transport.DiscoveryState
import dev.partydeck.transport.HostInfo
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanHost
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RuntimeRevisionSubmissionTest {
    @Test
    fun aQueuedHostActionKeepsItsCapturedRevisionAfterThePreviousActionChangesPhase() = runTest {
        val runtime = practiceRuntime()
        try {
            val lobby = startPracticeInLobby(runtime)
            val start = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.StartGame, lobby.revision)
            }
            val staleReturn = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.ReturnToLobby, lobby.revision)
            }
            assertEquals(lobby, runtime.state.value.view, "Both actions must be queued before authority execution")
            runCurrent()

            assertTrue(start.await().accepted)
            val playing = assertNotNull(runtime.state.value.view)
            assertEquals(SessionPhase.GAME, playing.phase)
            val rejection = staleReturn.await()
            assertEquals(SessionError.STALE_REVISION, rejection.error)
            assertEquals(playing.revision, rejection.revision)
            assertTrue(playing.revision > lobby.revision)

            val freshReturn = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.ReturnToLobby, playing.revision)
            }
            runCurrent()
            assertTrue(freshReturn.await().accepted)
            val restoredLobby = assertNotNull(runtime.state.value.view)
            assertEquals(SessionPhase.LOBBY, restoredLobby.phase)
            assertTrue(restoredLobby.players.all { it.isReady }, "Trusted practice readiness must remain serial")
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun hostTeardownStillEndsTheSessionAfterAnEarlierQueuedCommandAdvancesItsRevision() = runTest {
        val transport = RevisionTransport()
        val runtime = AuthoritySessionRuntime(backgroundScope, RuntimeServices(), transport, "Host", practice = false)
        try {
            runtime.start()
            runCurrent()
            val invitation = LanInvitation.decode(assertNotNull(runtime.state.value.invitation).joinAddress)
            val guest = RevisionConnection("teardown-guest")
            transport.host.accept(guest)
            runCurrent()
            guest.deliver(ClientMessage.Join(invitation.sessionId, invitation.admissionSecret, "Guest"))
            runCurrent()
            val welcome = guest.serverMessages().filterIsInstance<ServerMessage.Welcome>().single()
            guest.deliver(ClientMessage.Command(invitation.sessionId, 1, welcome.view.revision, ClientIntent.SetReady(true)))
            runCurrent()
            val lobby = assertNotNull(runtime.state.value.view)
            val start = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.StartGame, lobby.revision)
            }
            val leave = async(start = CoroutineStart.UNDISPATCHED) { runtime.leave() }
            assertEquals(lobby, runtime.state.value.view)
            runCurrent()

            assertTrue(start.await().accepted)
            leave.await()
            assertTrue(guest.serverMessages().filterIsInstance<ServerMessage.Snapshot>().any { it.view.phase == SessionPhase.GAME })
            val ended = guest.serverMessages().filterIsInstance<ServerMessage.Ended>().single()
            assertEquals(SessionEndReason.HOST_ENDED, ended.reason, "Teardown must flush the authority's end event to guests")
            assertEquals(ConnectionState.Closed, guest.state.value)
            assertNull(runtime.state.value.view)
            assertEquals(ConnectionStatus.DISCONNECTED, runtime.state.value.connection)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun aClientTransmitsTheCapturedRevisionAndKeepsPendingUntilTheReceiptIsCovered() = runTest {
        val fixture = ClientFixture(backgroundScope)
        val runtime = fixture.runtime
        try {
            runtime.start()
            runCurrent()
            val join = assertIs<ClientMessage.Join>(fixture.connection.sent.single())
            fixture.deliver(fixture.authority.handle(fixture.peer, join))
            runCurrent()
            val captured = assertNotNull(runtime.state.value.view)
            assertEquals(ConnectionStatus.CONNECTED, runtime.state.value.connection)

            val releaseSubmission = CompletableDeferred<Unit>()
            val staleRequest = async(start = CoroutineStart.UNDISPATCHED) {
                releaseSubmission.await()
                runtime.send(ClientIntent.SetReady(true), captured.revision)
            }
            // A different peer changes the actual authority while the captured action is suspended.
            fixture.deliver(fixture.authority.handle(
                SessionPeer("another-client"),
                ClientMessage.Join(INVITATION.sessionId, INVITATION.admissionSecret, "Another guest"),
            ))
            runCurrent()
            val newer = assertNotNull(runtime.state.value.view)
            assertTrue(newer.revision > captured.revision)
            releaseSubmission.complete(Unit)
            runCurrent()
            val staleCommand = fixture.connection.commands().single()
            assertEquals(captured.revision, staleCommand.expectedRevision)
            fixture.deliver(fixture.authority.handle(fixture.peer, staleCommand))
            runCurrent()
            assertEquals(SessionError.STALE_REVISION, staleRequest.await().error)
            assertFalse(assertNotNull(runtime.state.value.view).players.single { it.id == newer.selfPlayerId }.isReady)

            val freshRequest = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.SetReady(true), newer.revision)
            }
            runCurrent()
            val freshCommand = fixture.connection.commands().last()
            assertEquals(newer.revision, freshCommand.expectedRevision)
            val messages = fixture.messagesForClient(fixture.authority.handle(fixture.peer, freshCommand))
            val receipt = messages.filterIsInstance<ServerMessage.Receipt>().single()
            val snapshot = messages.filterIsInstance<ServerMessage.Snapshot>().single()
            assertTrue(receipt.receipt.accepted)
            assertTrue(receipt.receipt.revision > newer.revision)
            fixture.connection.deliver(receipt)
            runCurrent()
            assertFalse(freshRequest.isCompleted, "A receipt cannot complete before its authoritative snapshot")
            val duplicate = runCatching { runtime.send(ClientIntent.SetReady(false), newer.revision) }.exceptionOrNull()
            assertEquals(UiProblemCode.ACTION_REJECTED, assertIs<RuntimeFailure>(duplicate).code)
            assertEquals(2, fixture.connection.commands().size, "Pending input must not create another wire command")

            fixture.connection.deliver(ServerMessage.Snapshot(INVITATION.sessionId, captured))
            runCurrent()
            assertFalse(freshRequest.isCompleted)
            assertEquals(newer, runtime.state.value.view)
            fixture.connection.deliver(snapshot)
            runCurrent()
            assertEquals(receipt.receipt, freshRequest.await())
            assertEquals(snapshot.view, runtime.state.value.view)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun clientTeardownRetriesAStaleLeaveUsingTheNewlyCoveredRevision() = runTest {
        val fixture = ClientFixture(backgroundScope)
        val runtime = fixture.runtime
        try {
            runtime.start()
            runCurrent()
            fixture.deliver(fixture.authority.handle(fixture.peer, assertIs<ClientMessage.Join>(fixture.connection.sent.single())))
            runCurrent()
            val before = assertNotNull(runtime.state.value.view)
            val leaving = async(start = CoroutineStart.UNDISPATCHED) { runtime.leave() }
            runCurrent()
            val first = fixture.connection.commands().single()
            assertEquals(before.revision, first.expectedRevision)

            // Withhold another peer's admission snapshot until the authority rejects this leave.
            fixture.authority.handle(
                SessionPeer("leave-race-peer"),
                ClientMessage.Join(INVITATION.sessionId, INVITATION.admissionSecret, "Another guest"),
            )
            val rejected = fixture.messagesForClient(fixture.authority.handle(fixture.peer, first))
            val receipt = rejected.filterIsInstance<ServerMessage.Receipt>().single()
            val snapshot = rejected.filterIsInstance<ServerMessage.Snapshot>().single()
            assertEquals(SessionError.STALE_REVISION, receipt.receipt.error)
            fixture.connection.deliver(receipt)
            runCurrent()
            assertFalse(leaving.isCompleted)
            assertEquals(1, fixture.connection.commands().size)

            fixture.connection.deliver(snapshot)
            runCurrent()
            val retry = fixture.connection.commands().last()
            assertEquals(2, fixture.connection.commands().size)
            assertEquals(ClientIntent.Leave, retry.intent)
            assertEquals(first.commandId + 1, retry.commandId)
            assertEquals(snapshot.view.revision, retry.expectedRevision)
            assertTrue(retry.expectedRevision > first.expectedRevision)
            val accepted = fixture.authority.handle(fixture.peer, retry)
            val ended = fixture.messagesForClient(accepted).filterIsInstance<ServerMessage.Ended>().single()
            assertEquals(SessionEndReason.LEFT, ended.reason)
            fixture.deliver(accepted)
            runCurrent()
            leaving.await()
            assertNull(runtime.state.value.view)
            assertEquals(ConnectionState.Closed, fixture.connection.state.value)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    private fun TestScope.practiceRuntime() = AuthoritySessionRuntime(
        backgroundScope,
        RuntimeServices(),
        object : LanTransportFactory {
            override fun create(): LanTransport = error("Practice must not acquire a LAN transport")
        },
        "Host",
        practice = true,
    )

    private suspend fun TestScope.startPracticeInLobby(runtime: AuthoritySessionRuntime): SessionView {
        runtime.start()
        runCurrent()
        val playing = assertNotNull(runtime.state.value.view)
        assertEquals(SessionPhase.GAME, playing.phase, "Trusted practice startup must still ready seats and start")
        runtime.setForeground(false)
        runCurrent()
        val request = async(start = CoroutineStart.UNDISPATCHED) {
            runtime.send(ClientIntent.ReturnToLobby, playing.revision)
        }
        runCurrent()
        assertTrue(request.await().accepted)
        return assertNotNull(runtime.state.value.view).also {
            assertEquals(SessionPhase.LOBBY, it.phase)
            assertTrue(it.players.all { player -> player.isReady })
        }
    }

    private class ClientFixture(scope: CoroutineScope) {
        private var tokenCounter = 0
        val peer = SessionPeer("revision-client")
        val authority = HostAuthority(
            HostSessionConfig(INVITATION.sessionId, INVITATION.admissionSecret, "Host", SessionPeer("revision-host")),
            LastLightEngine(Random(718)),
            { (++tokenCounter).toString(16).padStart(64, '0') },
        )
        val connection = RevisionConnection(peer.connectionId)
        val runtime = ClientSessionRuntime(scope, RevisionTransport(connection), INVITATION, "Guest")

        fun messagesForClient(dispatch: SessionDispatch): List<ServerMessage> = dispatch.deliveries
            .filter { it.connectionId == peer.connectionId }.map { it.message }

        fun deliver(dispatch: SessionDispatch) = messagesForClient(dispatch).forEach(connection::deliver)
    }

    private class RevisionConnection(override val id: String) : LanConnection {
        private val incomingFrames = Channel<ByteArray>(16)
        private val written = mutableListOf<ByteArray>()
        override val incoming = incomingFrames.receiveAsFlow()
        override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        val sent: List<ClientMessage>
            get() = written.map { assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(it)).value }

        override suspend fun send(bytes: ByteArray) {
            check(state.value == ConnectionState.Connected)
            written += bytes.copyOf()
        }

        fun commands() = sent.filterIsInstance<ClientMessage.Command>()
        fun serverMessages() = written.map { assertIs<WireDecodeResult.Success<ServerMessage>>(SessionCodec.decodeServer(it)).value }

        fun deliver(message: ServerMessage) {
            check(incomingFrames.trySend(SessionCodec.encodeServer(message)).isSuccess)
        }

        fun deliver(message: ClientMessage) {
            check(incomingFrames.trySend(SessionCodec.encodeClient(message)).isSuccess)
        }

        override suspend fun close() {
            state.value = ConnectionState.Closed
            incomingFrames.close()
        }
    }

    private class RevisionHost : LanHost {
        private val arrivals = Channel<LanConnection>(16)
        private val connections = mutableListOf<RevisionConnection>()
        override val info = HostInfo("Host", "revision-table", listOf(INVITATION.endpoint), INVITATION.certificateSha256)
        override val incomingConnections = arrivals.receiveAsFlow()

        fun accept(connection: RevisionConnection) {
            connections += connection
            check(arrivals.trySend(connection).isSuccess)
        }

        override suspend fun close() {
            connections.forEach { it.close() }
            arrivals.close()
        }
    }

    private class RevisionTransport(private val connection: RevisionConnection? = null) : LanTransport, LanTransportFactory {
        val host = RevisionHost()
        override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
        override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)
        override fun create(): LanTransport = this
        override suspend fun startDiscovery() = Unit
        override suspend fun stopDiscovery() = Unit
        override suspend fun host(displayName: String): LanHost = host
        override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection {
            assertEquals(INVITATION.endpoint, endpoint)
            assertEquals(INVITATION.certificateSha256, certificateSha256)
            return checkNotNull(connection)
        }
        override suspend fun close() {
            connection?.close()
            host.close()
        }
    }

    private class RuntimeServices : PlatformServices {
        private var tokenCounter = 0
        override val settingsStore = object : SettingsStore {
            override suspend fun load() = AppSettings()
            override suspend fun save(settings: AppSettings) = Unit
        }
        override val feedback = object : Feedback {
            override fun play(cue: FeedbackCue, settings: AppSettings) = Unit
            override fun setForeground(value: Boolean) = Unit
            override fun close() = Unit
        }
        override val canScanInvitation = false
        override fun copyText(value: String) = Unit
        override fun shareText(value: String) = Unit
        override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
        override fun gameRandom(): Random = Random(547)
        override fun secureToken(): String = (++tokenCounter).toString(16).padStart(64, '0')
    }

    private companion object {
        val INVITATION = LanInvitation(
            "runtime-revision-room", "a".repeat(64), LanEndpoint("127.0.0.1", 42424), "c".repeat(64),
        )
    }
}
