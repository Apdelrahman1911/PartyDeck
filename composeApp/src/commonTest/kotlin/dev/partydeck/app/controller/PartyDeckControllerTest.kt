package dev.partydeck.app.controller

import dev.partydeck.core.GamePhase
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
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
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.fail

@OptIn(ExperimentalCoroutinesApi::class)
class PartyDeckControllerTest {
    @Test
    fun practicePlaysACompleteMatchUsingAuthorityAndReturnsToAReadyLobby() = runTest {
        val services = ControllerTestServices()
        val controller = PartyDeckController(services, NoNetworkForPractice(), this)
        try {
            controller.startPractice()
            runCurrent()
            assertEquals(SessionMode.PRACTICE, controller.state.value.connection.mode)
            val initial = assertNotNull(controller.state.value.session)
            assertEquals(4, initial.players.size)
            assertEquals(initial.selfPlayerId, assertNotNull(initial.game).viewerId)
            assertEquals(5, initial.game?.yourHand?.size)

            var finished = false
            for (step in 0 until 600) {
                val session = assertNotNull(controller.state.value.session)
                val game = assertNotNull(session.game)
                assertEquals(session.selfPlayerId, game.viewerId)
                assertTrue(game.yourHand.size <= 5)
                when (game.phase) {
                    GamePhase.FINISHED -> {
                        finished = true
                        break
                    }
                    GamePhase.ROUND_ENDED -> controller.nextRound()
                    GamePhase.PLAYING -> when {
                        game.availableActions.canChallenge -> controller.challenge()
                        game.availableActions.canPlay -> controller.playCards(listOf(game.yourHand.first().id))
                        else -> advanceTimeBy(900)
                    }
                }
                runCurrent()
                assertNull(controller.state.value.problem, "A legal practice flow was rejected at step $step")
            }
            assertTrue(finished, "Practice failed to finish within a bounded number of legal turns")
            assertNotNull(controller.state.value.session?.game?.winnerId)
            controller.returnToLobby()
            runCurrent()
            assertNull(controller.state.value.session?.game)
            assertTrue(controller.state.value.session?.controls?.canStartGame == true)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
        assertTrue(isActive, "Closing a controller cancelled its native owner's scope")
        assertEquals(1, services.feedback.closeCount)
    }

    @Test
    fun aSecondTapCannotSendAnotherPlayWhileTheFirstActionIsPending() = runTest {
        val controller = PartyDeckController(ControllerTestServices(), NoNetworkForPractice(), this)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            val before = assertNotNull(controller.state.value.session)
            val hand = assertNotNull(before.game).yourHand
            controller.playCards(listOf(hand.first().id))
            controller.playCards(listOf(hand.first().id))
            assertEquals(PendingAction.PLAY_CARDS, controller.state.value.pendingAction)
            runCurrent()
            val after = assertNotNull(controller.state.value.session)
            assertEquals(before.revision + 1, after.revision)
            assertEquals(hand.size - 1, after.game?.yourHand?.size)
            assertNull(controller.state.value.pendingAction)
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun backgroundPausesBotsAndLeaveCancelsEveryDelayedTurn() = runTest {
        val controller = PartyDeckController(ControllerTestServices(), NoNetworkForPractice(), this)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            controller.playCards(listOf(assertNotNull(controller.state.value.session?.game).yourHand.first().id))
            runCurrent()
            val revision = assertNotNull(controller.state.value.session).revision
            controller.setForeground(false)
            runCurrent()
            advanceTimeBy(10_000)
            runCurrent()
            assertEquals(revision, controller.state.value.session?.revision)
            assertEquals(1L, controller.state.value.privacyEpoch)
            assertFalse(controller.state.value.isForeground)

            controller.setForeground(true)
            runCurrent()
            advanceTimeBy(900)
            runCurrent()
            assertTrue(assertNotNull(controller.state.value.session).revision > revision)
            assertEquals(1L, controller.state.value.privacyEpoch)
            controller.leaveSession()
            runCurrent()
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(AppScreen.HOME, controller.state.value.screen)
            assertNull(controller.state.value.session)
            assertNull(controller.state.value.invitation)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun aLateHostStartupCannotReplacePracticeAfterLeaving() = runTest {
        val transport = DelayedControllerHostTransport()
        val factory = object : LanTransportFactory {
            override fun create(): LanTransport = transport
        }
        val controller = PartyDeckController(ControllerTestServices(), factory, this)
        try {
            controller.navigate(AppScreen.HOST)
            controller.host()
            runCurrent()
            assertTrue(transport.hostEntered)
            controller.leaveSession()
            controller.startPractice()
            runCurrent()
            val practiceSession = assertNotNull(controller.state.value.session).sessionId
            transport.releaseHost.complete(Unit)
            runCurrent()
            assertTrue(transport.closed)
            assertEquals(SessionMode.PRACTICE, controller.state.value.connection.mode)
            assertEquals(practiceSession, controller.state.value.session?.sessionId)
            assertNull(controller.state.value.problem)
        } finally {
            transport.releaseHost.complete(Unit)
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun delayedPreferenceLoadAndWritesPreserveTheLatestUserChoice() = runTest {
        val load = CompletableDeferred<AppSettings>()
        val saved = mutableListOf<AppSettings>()
        val store = object : SettingsStore {
            override suspend fun load(): AppSettings = load.await()
            override suspend fun save(settings: AppSettings) {
                delay(100)
                saved += settings
            }
        }
        val controller = PartyDeckController(ControllerTestServices(store), NoNetworkForPractice(), this)
        try {
            runCurrent()
            controller.setDisplayName("New name")
            controller.updateSettings(controller.state.value.settings.copy(soundEnabled = false))
            runCurrent()
            controller.updateSettings(controller.state.value.settings.copy(reduceMotion = true))
            load.complete(AppSettings(displayName = "Old name", soundEnabled = true))
            runCurrent()
            assertEquals("New name", controller.state.value.displayName)
            assertFalse(controller.state.value.settings.soundEnabled)
            assertTrue(controller.state.value.settings.reduceMotion)
            val latest = controller.state.value.settings
            controller.close()
            controller.awaitClosed()
            assertEquals(latest, saved.last(), "An older write overwrote the final preference state")
        } finally {
            load.complete(AppSettings())
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun scanResultsFillTheJoinFormWithoutAutoJoiningAndCannotReviveAnAbandonedForm() = runTest {
        val services = ControllerTestServices()
        val controller = PartyDeckController(services, NoNetworkForPractice(), this)
        try {
            val invite = LanInvitation("scan-room", "a".repeat(64), LanEndpoint("192.168.1.2", 42424), "b".repeat(64)).encode()
            controller.navigate(AppScreen.JOIN)
            controller.scanInvitation()
            assertTrue(controller.state.value.isScanningInvitation)
            val abandonedCallback = assertNotNull(services.scanCallback)
            assertTrue(controller.requestBack())
            assertFalse(controller.state.value.isScanningInvitation)
            abandonedCallback(invite)
            runCurrent()
            assertEquals(AppScreen.HOME, controller.state.value.screen)
            assertEquals("", controller.state.value.joinAddress)

            controller.navigate(AppScreen.JOIN)
            controller.scanInvitation()
            assertNotNull(services.scanCallback).invoke(invite)
            runCurrent()
            assertEquals(invite, controller.state.value.joinAddress)
            assertEquals(ConnectionStatus.IDLE, controller.state.value.connection.status)
            assertNull(controller.state.value.session)

            controller.setDisplayName("")
            controller.requestBack()
            controller.startPractice()
            runCurrent()
            assertNotNull(controller.state.value.session)
            assertEquals("Guest", controller.state.value.displayName)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun permissionAlertInactivityPreservesInitialJoinWhileActualBackgroundResumesTheSeat() = runTest {
        val transport = PermissionControllerTransport()
        val controller = PartyDeckController(ControllerTestServices(), object : LanTransportFactory {
            override fun create(): LanTransport = transport
        }, this)
        try {
            val invite = LanInvitation("permission-room", "a".repeat(64), LanEndpoint("192.168.1.2", 42424), "b".repeat(64))
            controller.navigate(AppScreen.JOIN)
            controller.setJoinAddress(invite.encode())
            controller.join()
            runCurrent()
            val initialLink = transport.connections.single()
            assertIs<ClientMessage.Join>(initialLink.messages.single())

            // iOS permission alerts cause inactive, without entering the OS background state.
            controller.setForeground(false)
            advanceTimeBy(1_000)
            runCurrent()
            assertFalse(initialLink.closed, "An inactive permission alert aborted its initial admission")
            assertEquals(1, transport.connections.size)
            val view = SessionView(
                sessionId = invite.sessionId,
                revision = 1,
                selfPlayerId = "p1",
                hostPlayerId = "p0",
                phase = SessionPhase.LOBBY,
                players = listOf(
                    LobbyPlayer("p0", "Host", true, true),
                    LobbyPlayer("p1", "Guest", false, true),
                ),
            )
            initialLink.server(ServerMessage.Welcome(invite.sessionId, "p1", "c".repeat(64), 1, view))
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertFalse(controller.state.value.canSendSessionAction)
            controller.setForeground(true)
            runCurrent()
            assertTrue(controller.state.value.canSendSessionAction)
            assertEquals(1, transport.connections.size)

            controller.setBackgrounded(true)
            runCurrent()
            assertTrue(initialLink.closed)
            controller.setBackgrounded(false)
            controller.setForeground(true)
            advanceTimeBy(500)
            runCurrent()
            val replacement = transport.connections.last()
            assertEquals(2, transport.connections.size)
            assertIs<ClientMessage.Resume>(replacement.messages.single())
            replacement.server(ServerMessage.Welcome(invite.sessionId, "p1", "c".repeat(64), 1, view.copy(revision = 2)))
            runCurrent()
            assertEquals(2L, controller.state.value.session?.revision)
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    private suspend fun TestScope.reachOwnPlay(controller: PartyDeckController) {
        repeat(120) {
            val game = assertNotNull(controller.state.value.session?.game)
            if (game.availableActions.canPlay) return
            if (game.phase == GamePhase.ROUND_ENDED) controller.nextRound() else advanceTimeBy(900)
            runCurrent()
        }
        fail("The human never received a playable practice turn")
    }
}

private class NoNetworkForPractice : LanTransportFactory {
    override fun create(): LanTransport = error("Practice attempted to acquire network resources")
}

private class ControllerTestServices(
    override val settingsStore: SettingsStore = object : SettingsStore {
        override suspend fun load(): AppSettings = AppSettings()
        override suspend fun save(settings: AppSettings) = Unit
    },
) : PlatformServices {
    override val feedback = ControllerTestFeedback()
    override val canScanInvitation = true
    var scanCallback: ((String?) -> Unit)? = null
    private var tokenCounter = 1L
    private var randomCounter = 12L
    override fun gameRandom(): Random = Random(randomCounter++)
    override fun secureToken(): String = (tokenCounter++).toString(16).padStart(64, '0')
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) { scanCallback = onResult }
}

private class ControllerTestFeedback : Feedback {
    var closeCount = 0
    override fun play(cue: FeedbackCue, settings: AppSettings) = Unit
    override fun setForeground(value: Boolean) = Unit
    override fun close() { closeCount++ }
}

private class DelayedControllerHostTransport : LanTransport {
    override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
    override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)
    val releaseHost = CompletableDeferred<Unit>()
    var hostEntered = false
    var closed = false
    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
    override suspend fun host(displayName: String): LanHost {
        hostEntered = true
        withContext(NonCancellable) { releaseHost.await() }
        return object : LanHost {
            override val info = HostInfo(displayName, "late-host", listOf(LanEndpoint("192.168.1.2", 42424)), "b".repeat(64))
            override val incomingConnections: Flow<LanConnection> = emptyFlow()
            override suspend fun close() = Unit
        }
    }
    override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection = error("Host-only test")
    override suspend fun close() { closed = true }
}

private class PermissionControllerTransport : LanTransport {
    override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
    override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)
    val connections = mutableListOf<PermissionControllerConnection>()
    override suspend fun startDiscovery() = Unit
    override suspend fun stopDiscovery() = Unit
    override suspend fun host(displayName: String): LanHost = error("Client-only test")
    override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection =
        PermissionControllerConnection("permission-${connections.size}").also(connections::add)
    override suspend fun close() { connections.forEach { it.close() } }
}

private class PermissionControllerConnection(override val id: String) : LanConnection {
    override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
    private val frames = Channel<ByteArray>(16)
    override val incoming = frames.receiveAsFlow()
    val messages = mutableListOf<ClientMessage>()
    var closed = false
    override suspend fun send(bytes: ByteArray) {
        when (val decoded = SessionCodec.decodeClient(bytes)) {
            is WireDecodeResult.Success -> messages += decoded.value
            is WireDecodeResult.Failure -> error("Malformed client test message")
        }
    }
    suspend fun server(message: ServerMessage) { frames.send(SessionCodec.encodeServer(message)) }
    override suspend fun close() {
        if (closed) return
        closed = true
        state.value = ConnectionState.Closed
        frames.close()
    }
}
