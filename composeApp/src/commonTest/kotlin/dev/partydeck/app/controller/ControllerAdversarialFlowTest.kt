package dev.partydeck.app.controller

import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GameRejection
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.CommandReceipt
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionControls
import dev.partydeck.session.SessionEndReason
import dev.partydeck.session.SessionError
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
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
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

/** Delivery-order tests use real codecs and safe domain views, with controllable transport timing. */
@OptIn(ExperimentalCoroutinesApi::class)
class ControllerAdversarialFlowTest {
    @Test
    fun receiptsCannotReleasePendingControlsBeforeTheirSnapshotIsVisible() = runTest {
        val client = connectClient()
        try {
            val before = assertNotNull(client.runtime.state.value.view)
            val selected = assertNotNull(before.game).yourHand.first().id
            val request = async { runCatching { client.runtime.send(ClientIntent.PlayCards(listOf(selected))) } }
            runCurrent()
            val command = client.first.commands().single()
            assertEquals(before.revision, command.expectedRevision)
            val expectedReceipt = CommandReceipt(command.commandId, before.revision + 1)
            client.first.server(ServerMessage.Receipt(ROOM, expectedReceipt))
            runCurrent()
            assertFalse(request.isCompleted, "An acknowledgement released controls before the changed hand arrived")
            assertEquals(before, client.runtime.state.value.view)
            val blocked = runCatching { client.runtime.send(ClientIntent.Challenge) }.exceptionOrNull()
            assertEquals(UiProblemCode.ACTION_REJECTED, assertIs<RuntimeFailure>(blocked).code)
            assertEquals(1, client.first.commands().size)

            client.first.server(ServerMessage.Snapshot(ROOM, before.copy(revision = before.revision - 1)))
            runCurrent()
            assertFalse(request.isCompleted)
            assertEquals(before, client.runtime.state.value.view)
            val after = client.fixture.afterOwnPlay(before.revision + 1)
            client.first.server(ServerMessage.Snapshot(ROOM, after))
            runCurrent()
            assertEquals(expectedReceipt, request.await().getOrThrow())
            assertEquals(after, client.runtime.state.value.view)

            // A repeated welcome on an admitted link must not rewind the private command counter.
            client.first.server(welcome(after, nextCommandId = command.commandId))
            runCurrent()
            val nextRequest = async { runCatching { client.runtime.send(ClientIntent.Challenge) } }
            runCurrent()
            val next = client.first.commands().last()
            assertEquals(command.commandId + 1, next.commandId)
            assertEquals(after.revision, next.expectedRevision)
            val rejected = CommandReceipt(next.commandId, after.revision, SessionError.ILLEGAL_GAME_ACTION, GameRejection.NOT_YOUR_TURN)
            client.first.server(ServerMessage.Receipt(ROOM, rejected))
            runCurrent()
            assertEquals(rejected, nextRequest.await().getOrThrow())
        } finally {
            client.runtime.close()
            client.runtime.awaitClosed()
        }
    }

    @Test
    fun aSnapshotBeforeItsReceiptDoesNotAcknowledgeAnUnrelatedOrUnconfirmedCommand() = runTest {
        val client = connectClient()
        try {
            val before = assertNotNull(client.runtime.state.value.view)
            val request = async { runCatching { client.runtime.send(ClientIntent.PlayCards(listOf(assertNotNull(before.game).yourHand.first().id))) } }
            runCurrent()
            val command = client.first.commands().single()
            val after = client.fixture.afterOwnPlay(before.revision + 1)
            client.first.server(ServerMessage.Snapshot(ROOM, after))
            runCurrent()
            assertEquals(after, client.runtime.state.value.view)
            assertFalse(request.isCompleted)
            client.first.server(ServerMessage.Receipt(ROOM, CommandReceipt(command.commandId + 1, after.revision)))
            runCurrent()
            assertFalse(request.isCompleted, "Another command's receipt resolved the pending action")
            val matching = CommandReceipt(command.commandId, after.revision)
            client.first.server(ServerMessage.Receipt(ROOM, matching))
            runCurrent()
            assertEquals(matching, request.await().getOrThrow())
            client.first.server(ServerMessage.Snapshot(ROOM, before))
            runCurrent()
            assertEquals(after, client.runtime.state.value.view, "An older snapshot restored already played cards")
        } finally {
            client.runtime.close()
            client.runtime.awaitClosed()
        }
    }

    @Test
    fun snapshotsForAnotherRoomOrSeatCannotReplaceTheCurrentPrivateHand() = runTest {
        for (wrongRoom in listOf(false, true)) {
            val client = connectClient()
            try {
                val before = assertNotNull(client.runtime.state.value.view)
                val forged = if (wrongRoom) {
                    before.copy(sessionId = "another-room", revision = before.revision + 100)
                } else {
                    client.fixture.view(before.revision + 100, HOST)
                }
                client.first.server(ServerMessage.Snapshot(forged.sessionId, forged))
                // Queue a correct-looking later frame too: a failed link must never revive itself.
                client.first.server(ServerMessage.Snapshot(ROOM, before.copy(revision = before.revision + 101)))
                runCurrent()
                assertEquals(before, client.runtime.state.value.view)
                assertEquals(ConnectionStatus.DISCONNECTED, client.runtime.state.value.connection)
                assertTrue(client.first.closed)
                val expected = if (wrongRoom) UiProblemCode.VERSION_MISMATCH else UiProblemCode.JOIN_REJECTED
                assertEquals(expected, assertNotNull(client.runtime.state.value.issue).code)
                client.runtime.retry()
                advanceTimeBy(31_000)
                runCurrent()
                assertEquals(1, client.transport.connectCalls, "An identity mismatch was retried automatically")
            } finally {
                client.runtime.close()
                client.runtime.awaitClosed()
            }
        }
    }

    @Test
    fun backgroundCancellationClosesTheOldLinkAndResumeNeverReplaysAnUnacknowledgedMove() = runTest {
        val client = connectClient(nextCommandId = 7)
        try {
            val before = assertNotNull(client.runtime.state.value.view)
            val request = async { runCatching { client.runtime.send(ClientIntent.PlayCards(listOf(assertNotNull(before.game).yourHand.first().id))) } }
            runCurrent()
            assertEquals(7L, client.first.commands().single().commandId)
            client.runtime.setForeground(false)
            client.first.server(ServerMessage.Snapshot(ROOM, before.copy(revision = 999)))
            runCurrent()
            assertTrue(client.first.closed, "The timeout child job was mistaken for the connection loop owner")
            assertTrue(request.await().isFailure)
            assertEquals(before, client.runtime.state.value.view)
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(1, client.transport.connectCalls, "A background client kept reconnecting")

            val replacement = FakeConnection("replacement-link")
            client.transport.enqueue(replacement)
            client.runtime.setForeground(true)
            advanceTimeBy(500)
            runCurrent()
            val resume = assertIs<ClientMessage.Resume>(replacement.clientMessages().single())
            assertEquals(SELF, resume.playerId)
            assertEquals(TOKEN, resume.reconnectToken)
            assertEquals(ROOM, resume.sessionId)
            val restored = client.fixture.afterOwnPlay(before.revision + 2)
            replacement.server(welcome(restored, nextCommandId = 8))
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, client.runtime.state.value.connection)
            assertEquals(restored, client.runtime.state.value.view)
            assertEquals(1, replacement.clientMessages().size, "Resume resent the old gameplay intent")
            assertFalse(replacement.closed, "Cleanup from the old loop closed its replacement")

            val nextRequest = async { runCatching { client.runtime.send(ClientIntent.Challenge) } }
            runCurrent()
            val command = replacement.commands().single()
            assertEquals(8L, command.commandId)
            assertEquals(restored.revision, command.expectedRevision)
            val receipt = CommandReceipt(command.commandId, restored.revision, SessionError.ILLEGAL_GAME_ACTION, GameRejection.NOT_YOUR_TURN)
            replacement.server(ServerMessage.Receipt(ROOM, receipt))
            runCurrent()
            assertEquals(receipt, nextRequest.await().getOrThrow())
        } finally {
            client.runtime.close()
            client.runtime.awaitClosed()
        }
    }

    @Test
    fun aMissingAcknowledgementExpiresAndResumeReconcilesItWithoutResendingTheMove() = runTest {
        val client = connectClient()
        try {
            val before = assertNotNull(client.runtime.state.value.view)
            val replacement = FakeConnection("ack-timeout-replacement")
            client.transport.enqueue(replacement)
            val request = async { runCatching { client.runtime.send(ClientIntent.PlayCards(listOf(assertNotNull(before.game).yourHand.first().id))) } }
            runCurrent()
            assertEquals(1, client.first.commands().size)
            assertFalse(request.isCompleted)

            // The 12-second request deadline and first 500ms reconnect delay both elapse.
            advanceTimeBy(13_000)
            runCurrent()
            assertTrue(request.isCompleted, "A missing receipt left the action pending indefinitely")
            assertEquals(UiProblemCode.CONNECTION_LOST, assertIs<RuntimeFailure>(request.await().exceptionOrNull()).code)
            assertTrue(client.first.closed)
            assertIs<ClientMessage.Resume>(replacement.clientMessages().single())
            assertEquals(ConnectionStatus.RECONNECTING, client.runtime.state.value.connection)

            // The host may have applied the move even though its receipt was lost.
            val authoritative = client.fixture.afterOwnPlay(before.revision + 1)
            replacement.server(welcome(authoritative, nextCommandId = 2))
            runCurrent()
            assertEquals(authoritative, client.runtime.state.value.view)
            assertEquals(ConnectionStatus.CONNECTED, client.runtime.state.value.connection)
            assertTrue(replacement.commands().isEmpty(), "A timed-out move was blindly resent after resume")
        } finally {
            client.runtime.close()
            client.runtime.awaitClosed()
        }
    }

    @Test
    fun anExplicitSessionEndPurgesPrivateCardsAndCannotBeUndoneByQueuedSnapshots() = runTest {
        for (acknowledgedLeave in listOf(false, true)) {
            val client = connectClient()
            try {
                val before = assertNotNull(client.runtime.state.value.view)
                val beforeGame = assertNotNull(before.game)
                assertTrue(beforeGame.yourHand.isNotEmpty())
                val intent = if (acknowledgedLeave) ClientIntent.Leave else ClientIntent.PlayCards(listOf(beforeGame.yourHand.first().id))
                val request = async { runCatching { client.runtime.send(intent) } }
                runCurrent()
                val command = client.first.commands().single()
                val receipt = CommandReceipt(command.commandId, before.revision + 1)
                if (acknowledgedLeave) {
                    client.first.server(ServerMessage.Receipt(ROOM, receipt))
                    runCurrent()
                    assertFalse(request.isCompleted)
                }
                val reason = if (acknowledgedLeave) SessionEndReason.LEFT else SessionEndReason.HOST_ENDED
                client.first.server(ServerMessage.Ended(ROOM, reason))
                client.first.server(ServerMessage.Snapshot(ROOM, before.copy(revision = before.revision + 20)))
                runCurrent()
                val result = request.await()
                if (acknowledgedLeave) assertEquals(receipt, result.getOrThrow()) else assertTrue(result.isFailure)
                val ended = assertNotNull(client.runtime.state.value.view)
                assertEquals(SessionPhase.ENDED, ended.phase)
                assertNull(ended.game, "A terminal session retained the private hand and obsolete game actions")
                assertEquals(SessionControls(), ended.controls)
                assertTrue(ended.pausedPlayerIds.isEmpty())
                assertEquals(ConnectionStatus.DISCONNECTED, client.runtime.state.value.connection)
                assertEquals(UiProblemCode.SESSION_ENDED, assertNotNull(client.runtime.state.value.issue).code)
                client.runtime.retry()
                advanceTimeBy(31_000)
                runCurrent()
                assertEquals(ended, client.runtime.state.value.view)
                assertEquals(1, client.transport.connectCalls)
            } finally {
                client.runtime.close()
                client.runtime.awaitClosed()
            }
        }
    }

    @Test
    fun protocolClosingAPeerPausesTheAuthorityBeforeItsBlockedSocketWriterFinishes() = runTest {
        val transport = FakeTransport()
        val runtime = AuthoritySessionRuntime(backgroundScope, TestServices(), factory(transport), "Host", practice = false)
        try {
            runtime.start()
            runCurrent()
            val invitation = LanInvitation.decode(assertNotNull(runtime.state.value.invitation).joinAddress)
            val remote = FakeConnection("admitted-remote")
            transport.host.accept(remote)
            runCurrent()
            remote.client(ClientMessage.Join(invitation.sessionId, invitation.admissionSecret, "Guest"))
            runCurrent()
            val admitted = remote.serverMessages().filterIsInstance<ServerMessage.Welcome>().single()
            remote.client(ClientMessage.Command(invitation.sessionId, 1, admitted.view.revision, ClientIntent.SetReady(true)))
            runCurrent()
            val start = async { runtime.send(ClientIntent.StartGame) }
            runCurrent()
            assertNull(start.await().error)
            assertTrue(assertNotNull(runtime.state.value.view).pausedPlayerIds.isEmpty())

            val blockedWrite = CompletableDeferred<Unit>()
            remote.writeGate = blockedWrite
            remote.client(ClientMessage.Command("wrong-session", 2, assertNotNull(runtime.state.value.view).revision, ClientIntent.Challenge))
            runCurrent()
            assertFalse(remote.closed, "The test must observe authority state while the close response is still flushing")
            assertFalse(blockedWrite.isCompleted)
            val paused = assertNotNull(runtime.state.value.view)
            assertEquals(listOf(admitted.playerId), paused.pausedPlayerIds)
            assertFalse(paused.players.single { it.id == admitted.playerId }.isConnected)
            val pausedGame = assertNotNull(paused.game)
            assertFalse(pausedGame.availableActions.canPlay)
            assertFalse(pausedGame.availableActions.canChallenge)

            blockedWrite.complete(Unit)
            runCurrent()
            assertTrue(remote.closed)
            assertEquals(paused, runtime.state.value.view, "The eventual socket close repeated the presence transition")
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun aFailedLeaveFromAnOldSessionCannotInjectAnErrorOrPrivateHandIntoItsReplacement() = runTest {
        val transport = FakeTransport()
        val oldConnection = FakeConnection("old-controller-session")
        transport.enqueue(oldConnection)
        val controller = PartyDeckController(TestServices(), factory(transport), backgroundScope)
        val oldView = ViewFixture().view(10)
        try {
            controller.navigate(AppScreen.JOIN)
            controller.setJoinAddress(INVITATION.encode())
            controller.join()
            runCurrent()
            assertIs<ClientMessage.Join>(oldConnection.clientMessages().single())
            oldConnection.server(welcome(oldView))
            runCurrent()
            assertEquals(ROOM, assertNotNull(controller.state.value.session).sessionId)
            controller.leaveSession()
            runCurrent()
            assertIs<ClientIntent.Leave>(oldConnection.commands().single().intent)
            assertNull(controller.state.value.session)

            controller.startPractice()
            runCurrent()
            val replacement = assertNotNull(controller.state.value.session)
            assertEquals(SessionMode.PRACTICE, controller.state.value.connection.mode)
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertTrue(replacement.sessionId != ROOM)
            assertNull(controller.state.value.problem)

            oldConnection.server(ServerMessage.Snapshot(ROOM, oldView.copy(revision = oldView.revision + 100)))
            oldConnection.close()
            runCurrent()
            assertEquals(replacement, controller.state.value.session)
            assertEquals(SessionMode.PRACTICE, controller.state.value.connection.mode)
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertNull(controller.state.value.pendingAction)
            assertNull(controller.state.value.problem, "The abandoned session's cleanup overwrote the new session's UI")
        } finally {
            controller.close()
            controller.awaitClosed()
        }
    }

    private fun TestScope.connectClient(nextCommandId: Long = 1): ConnectedClient {
        val transport = FakeTransport()
        val first = FakeConnection("initial-link")
        transport.enqueue(first)
        val runtime = ClientSessionRuntime(backgroundScope, factory(transport), INVITATION, "Guest")
        val fixture = ViewFixture()
        runtime.start()
        runCurrent()
        val join = assertIs<ClientMessage.Join>(first.clientMessages().single())
        assertEquals(ROOM, join.sessionId)
        assertEquals(INVITATION.admissionSecret, join.admissionSecret)
        first.server(welcome(fixture.view(10), nextCommandId))
        runCurrent()
        assertEquals(ConnectionStatus.CONNECTED, runtime.state.value.connection)
        return ConnectedClient(runtime, transport, first, fixture)
    }

    private data class ConnectedClient(
        val runtime: ClientSessionRuntime,
        val transport: FakeTransport,
        val first: FakeConnection,
        val fixture: ViewFixture,
    )

    /** Valid hidden-hand projections are generated by the actual engine; only delivery order is synthetic. */
    private class ViewFixture {
        private val engine = LastLightEngine(Random(41))
        private var state = engine.start(listOf(PlayerIdentity(HOST, "Host"), PlayerIdentity(SELF, "Guest")))

        init {
            if (state.turnPlayerId != SELF) {
                val actor = assertNotNull(state.turnPlayerId)
                val card = engine.viewFor(state, actor).yourHand.first()
                state = assertIs<GameDecision.Applied>(engine.apply(state, GameAction.Play(actor, listOf(card.id)))).state
            }
        }

        fun view(revision: Long, recipient: String = SELF) = SessionView(
            sessionId = ROOM,
            revision = revision,
            selfPlayerId = recipient,
            hostPlayerId = HOST,
            phase = SessionPhase.GAME,
            players = listOf(LobbyPlayer(HOST, "Host", true, true), LobbyPlayer(SELF, "Guest", true, true)),
            game = engine.viewFor(state, recipient),
        )

        fun afterOwnPlay(revision: Long): SessionView {
            val card = engine.viewFor(state, SELF).yourHand.first()
            state = assertIs<GameDecision.Applied>(engine.apply(state, GameAction.Play(SELF, listOf(card.id)))).state
            return view(revision)
        }
    }

    private class FakeConnection(override val id: String) : LanConnection {
        private val inbound = Channel<ByteArray>(Channel.UNLIMITED)
        private val mutableState = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        override val state: StateFlow<ConnectionState> = mutableState
        override val incoming: Flow<ByteArray> = inbound.receiveAsFlow()
        private val written = mutableListOf<ByteArray>()
        var writeGate: CompletableDeferred<Unit>? = null
        var closed = false
            private set

        override suspend fun send(bytes: ByteArray) {
            writeGate?.await()
            check(!closed)
            written += bytes.copyOf()
        }

        override suspend fun close() {
            if (closed) return
            closed = true
            mutableState.value = ConnectionState.Closed
            inbound.close()
        }

        fun server(message: ServerMessage) = inbound.trySend(SessionCodec.encodeServer(message))
        fun client(message: ClientMessage) = inbound.trySend(SessionCodec.encodeClient(message))
        fun clientMessages(): List<ClientMessage> = written.map { assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(it)).value }
        fun commands(): List<ClientMessage.Command> = clientMessages().filterIsInstance<ClientMessage.Command>()
        fun serverMessages(): List<ServerMessage> = written.map { assertIs<WireDecodeResult.Success<ServerMessage>>(SessionCodec.decodeServer(it)).value }
    }

    private class FakeHost : LanHost {
        private val arrivals = Channel<LanConnection>(Channel.UNLIMITED)
        override val info = HostInfo("Host", "test-table", listOf(INVITATION.endpoint), INVITATION.certificateSha256)
        override val incomingConnections: Flow<LanConnection> = arrivals.receiveAsFlow()
        fun accept(connection: LanConnection) { check(arrivals.trySend(connection).isSuccess) }
        override suspend fun close() { arrivals.close() }
    }

    private class FakeTransport : LanTransport {
        private val nextConnections = Channel<FakeConnection>(Channel.UNLIMITED)
        private val allocated = mutableListOf<FakeConnection>()
        val host = FakeHost()
        var connectCalls = 0
            private set
        override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
        override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)

        fun enqueue(connection: FakeConnection) {
            allocated += connection
            check(nextConnections.trySend(connection).isSuccess)
        }

        override suspend fun startDiscovery() = Unit
        override suspend fun stopDiscovery() = Unit
        override suspend fun host(displayName: String): LanHost = host
        override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection {
            assertEquals(INVITATION.endpoint, endpoint)
            assertEquals(INVITATION.certificateSha256, certificateSha256)
            connectCalls++
            return nextConnections.receive()
        }

        override suspend fun close() {
            allocated.forEach { it.close() }
            host.close()
            nextConnections.close()
        }
    }

    private class TestServices : PlatformServices {
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
        override fun scanInvitation(onResult: (String?) -> Unit) { onResult(null) }
        override fun gameRandom(): Random = Random(543)
        override fun secureToken(): String = (++tokenCounter).toString(16).padStart(64, '0')
    }

    private companion object {
        const val ROOM = "controller-adversarial"
        const val HOST = "p0"
        const val SELF = "p1"
        val TOKEN = "b".repeat(64)
        val INVITATION = LanInvitation(ROOM, "a".repeat(64), LanEndpoint("127.0.0.1", 45123), "c".repeat(64))

        fun factory(transport: LanTransport) = object : LanTransportFactory {
            override fun create(): LanTransport = transport
        }

        fun welcome(view: SessionView, nextCommandId: Long = 1) =
            ServerMessage.Welcome(ROOM, SELF, TOKEN, nextCommandId, view)
    }
}
