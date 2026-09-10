package dev.partydeck.app.controller

import dev.partydeck.core.LastLightEngine
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionDispatch
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.WireDecodeResult
import dev.partydeck.transport.ConnectionState
import dev.partydeck.transport.DiscoveredHost
import dev.partydeck.transport.DiscoveryState
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanHost
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
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

/** Independent submission review: actual authority decisions over explicitly ordered delivery. */
@OptIn(ExperimentalCoroutinesApi::class)
class PinnedRevisionSeamReviewTest {
    @Test
    fun queuedHostRequestKeepsCapturedRevisionAcrossReturnAndAutomaticReadiness() = runTest {
        val runtime = AuthoritySessionRuntime(backgroundScope, RevisionReviewServices(), object : LanTransportFactory {
            override fun create(): LanTransport = error("Practice must not acquire a transport")
        }, "Host", practice = true)
        try {
            runtime.start()
            runCurrent()
            val playing = assertNotNull(runtime.state.value.view)
            assertEquals(SessionPhase.GAME, playing.phase)

            // Both enqueue before the authority actor resumes. Return also readies practice guests.
            val returned = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.ReturnToLobby, playing.revision)
            }
            val staleStart = async(start = CoroutineStart.UNDISPATCHED) {
                runtime.send(ClientIntent.StartGame, playing.revision)
            }
            runCurrent()
            assertTrue(returned.await().accepted)
            val rejected = staleStart.await()
            assertEquals(SessionError.STALE_REVISION, rejected.error)
            val lobby = assertNotNull(runtime.state.value.view)
            assertEquals(SessionPhase.LOBBY, lobby.phase, "A queued stale request restarted the game")
            assertNull(lobby.game)
            assertTrue(lobby.revision > playing.revision)
            assertTrue(lobby.controls.canStartGame, "Trusted practice readiness changed with the public seam")

            val fresh = async { runtime.send(ClientIntent.StartGame, lobby.revision) }
            runCurrent()
            assertTrue(fresh.await().accepted)
            assertEquals(SessionPhase.GAME, runtime.state.value.view?.phase)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun clientTransmitsCapturedRevisionAfterANewerAuthoritySnapshotHasArrived() = runTest {
        val transport = RevisionReviewTransport()
        val runtime = ClientSessionRuntime(backgroundScope, transport, transport.invitation, "Guest")
        try {
            runtime.start()
            runCurrent()
            val shown = assertNotNull(runtime.state.value.view)
            transport.addAnotherSeat()
            runCurrent()
            val newer = assertNotNull(runtime.state.value.view)
            assertTrue(newer.revision > shown.revision)

            val request = async { runtime.send(ClientIntent.SetReady(true), shown.revision) }
            runCurrent()
            assertEquals(shown.revision, transport.commands.single().expectedRevision)
            val receipt = request.await()
            assertEquals(SessionError.STALE_REVISION, receipt.error)
            assertEquals(newer.revision, receipt.revision)
            assertEquals(newer, runtime.state.value.view, "The stale request changed a recipient projection")
            assertFalse(assertNotNull(runtime.state.value.view).players.single { it.id == shown.selfPlayerId }.isReady)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }

    @Test
    fun actualReceiptNeedsItsSnapshotAndAReplayedReceiptCannotReleaseTheNextRequest() = runTest {
        val transport = RevisionReviewTransport()
        val runtime = ClientSessionRuntime(backgroundScope, transport, transport.invitation, "Guest")
        try {
            runtime.start()
            runCurrent()
            transport.holdCommands = true
            val before = assertNotNull(runtime.state.value.view)
            val first = async { runtime.send(ClientIntent.SetReady(true), before.revision) }
            runCurrent()
            val firstCommand = transport.commands.single()
            val actualFirst = transport.apply(firstCommand)
            val firstReceipt = actualFirst.filterIsInstance<ServerMessage.Receipt>().single()
            val firstSnapshot = actualFirst.filterIsInstance<ServerMessage.Snapshot>().single()
            assertTrue(firstReceipt.receipt.accepted)
            transport.deliver(firstReceipt)
            runCurrent()
            assertFalse(first.isCompleted, "Receipt released pending before its authority snapshot")
            assertEquals(before, runtime.state.value.view)

            val extra = runCatching { runtime.send(ClientIntent.SetReady(false), before.revision) }.exceptionOrNull()
            assertEquals(UiProblemCode.ACTION_REJECTED, assertIs<RuntimeFailure>(extra).code)
            assertEquals(1, transport.commands.size, "Pending rejection still emitted a network command")
            transport.deliver(firstSnapshot)
            runCurrent()
            assertEquals(firstReceipt.receipt, first.await())

            val second = async { runtime.send(ClientIntent.SetReady(false), firstSnapshot.view.revision) }
            runCurrent()
            val secondCommand = transport.commands.last()
            assertEquals(firstCommand.commandId + 1, secondCommand.commandId)
            assertEquals(firstSnapshot.view.revision, secondCommand.expectedRevision)
            val actualSecond = transport.apply(secondCommand)
            val secondReceipt = actualSecond.filterIsInstance<ServerMessage.Receipt>().single()
            val secondSnapshot = actualSecond.filterIsInstance<ServerMessage.Snapshot>().single()
            transport.deliver(secondSnapshot)
            transport.deliver(firstReceipt)
            runCurrent()
            assertFalse(second.isCompleted, "A prior command receipt acknowledged the next request")
            transport.deliver(secondReceipt)
            runCurrent()
            assertEquals(secondReceipt.receipt, second.await())
            assertEquals(secondSnapshot.view, runtime.state.value.view)
        } finally {
            runtime.close()
            runtime.awaitClosed()
        }
    }
}

/** All snapshots and receipts originate in HostAuthority; only their delivery order is controlled. */
private class RevisionReviewTransport : LanTransportFactory, LanTransport {
    private val room = "pinned-revision-review"
    private val admission = "a".repeat(64)
    private val hostPeer = SessionPeer("review-host")
    private val clientPeer = SessionPeer("review-client")
    private var token = 1L
    private val authority = HostAuthority(
        HostSessionConfig(room, admission, "Host", hostPeer), LastLightEngine(Random(2)),
    ) { (token++).toString(16).padStart(64, '0') }
    private val frames = Channel<ByteArray>(32)
    private val sent = mutableListOf<ClientMessage>()
    private var closed = false
    val invitation = LanInvitation(room, admission, LanEndpoint("192.0.2.7", 42424), "b".repeat(64))
    val commands: List<ClientMessage.Command> get() = sent.filterIsInstance<ClientMessage.Command>()
    var holdCommands = false
    override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
    override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)

    private val connection = object : LanConnection {
        override val id = clientPeer.connectionId
        override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        override val incoming = frames.receiveAsFlow()
        override suspend fun send(bytes: ByteArray) {
            val message = assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(bytes)).value
            sent += message
            if (message !is ClientMessage.Command || !holdCommands) {
                deliver(authority.handle(clientPeer, message))
            }
        }
        override suspend fun close() {
            if (closed) return
            closed = true
            state.value = ConnectionState.Closed
            frames.close()
        }
    }

    fun addAnotherSeat() {
        deliver(authority.handle(SessionPeer("another-peer"), ClientMessage.Join(room, admission, "Other")))
    }

    fun apply(command: ClientMessage.Command): List<ServerMessage> =
        authority.handle(clientPeer, command).deliveries.filter { it.connectionId == clientPeer.connectionId }.map { it.message }

    fun deliver(message: ServerMessage) {
        check(frames.trySend(SessionCodec.encodeServer(message)).isSuccess)
    }

    private fun deliver(dispatch: SessionDispatch) {
        dispatch.deliveries.filter { it.connectionId == clientPeer.connectionId }.forEach { deliver(it.message) }
    }

    override fun create(): LanTransport = this
    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
    override suspend fun host(displayName: String): LanHost = error("Client transport cannot host")
    override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection = connection
    override suspend fun close() = connection.close()
}

private class RevisionReviewServices : PlatformServices {
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
    private var token = 1L
    // Deterministic sources belong only to this isolated test service.
    override fun gameRandom(): Random = Random(2)
    override fun secureToken(): String = (token++).toString(16).padStart(64, '0')
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = Unit
}
