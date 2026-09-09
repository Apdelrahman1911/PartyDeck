package dev.partydeck.app.controller

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
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanHost
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import dev.partydeck.transport.TransportException
import dev.partydeck.transport.TransportFailure
import dev.partydeck.transport.TransportFailureCode
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
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
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class ClientDiscoveryFlowTest {
    @Test
    fun delayedExactServiceRepairsAStaleAddressWithoutChangingPinOrAdmission() = runTest {
        val transport = DiscoveryTransport().apply {
            onConnect = { request ->
                if (request.endpoint == INVITATION.endpoint) {
                    delay(4_000) // Android's direct TCP attempt can fail before NSD resolves.
                    throw transportFailure(TransportFailureCode.IO_ERROR)
                }
                DiscoveryConnection("rediscovered")
            }
        }
        val controller = controller(transport)
        try {
            runCurrent()
            assertEquals(0, transport.createCount, "Home started acquiring LAN resources")
            controller.navigate(AppScreen.JOIN)
            controller.setJoinAddress(INVITATION.encode())
            runCurrent()
            assertEquals(0, transport.startCount, "Editing an invitation started browsing")
            controller.join()
            runCurrent()
            assertEquals(1, transport.startCount)
            assertTrue(transport.browsing)
            transport.discoveredHosts.value = listOf(OTHER_HOST)
            advanceTimeBy(4_000)
            runCurrent()
            assertEquals(1, transport.requests.size, "The client used another table's service")

            advanceTimeBy(500)
            transport.discoveredHosts.value = listOf(OTHER_HOST, MOVED_HOST)
            runCurrent()
            assertEquals(
                listOf(INVITATION.endpoint, MOVED_HOST.endpoint.copy(serviceName = SERVICE)),
                transport.requests.map { it.endpoint },
            )
            assertTrue(transport.requests.all { it.pin == INVITATION.certificateSha256 })
            val connection = transport.connections.single()
            val join = assertIs<ClientMessage.Join>(connection.messages.single())
            assertEquals(INVITATION.sessionId, join.sessionId)
            assertEquals(INVITATION.admissionSecret, join.admissionSecret)
            assertTrue(transport.browsing, "Browsing stopped before authenticated admission")

            connection.server(welcome())
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertEquals(1, transport.stopCount)
            assertFalse(transport.browsing)
            assertTrue(transport.discoveredHosts.value.isEmpty())
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(1, transport.startCount, "Connected play kept browsing")
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun workingDirectInvitationDoesNotWaitForUnavailableOrSuspendedDiscovery() = runTest {
        for (fails in listOf(true, false)) {
            var startupExited = false
            val transport = DiscoveryTransport().apply {
                onStart = {
                    try {
                        if (fails) throw transportFailure(TransportFailureCode.UNAVAILABLE)
                        awaitCancellation()
                    } finally {
                        startupExited = true
                    }
                }
            }
            val controller = controller(transport)
            try {
                val startedAt = testScheduler.currentTime
                controller.joinInvitation()
                runCurrent()
                assertEquals(1, transport.startCount)
                val connection = transport.connections.single()
                connection.server(welcome())
                runCurrent()
                assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
                assertEquals(startedAt, testScheduler.currentTime, "Discovery delayed a reachable direct host")
                assertTrue(startupExited, "The suspended discovery startup was not cancelled")
                assertEquals(1, transport.stopCount)
                assertFalse(transport.browsing)
                assertFalse(connection.closed)
                assertNull(controller.state.value.problem)
            } finally {
                controller.close()
                controller.awaitClosed()
            }
        }
    }

    @Test
    fun permissionAndIdentityFailuresNeverTryADiscoveredEndpoint() = runTest {
        for (failure in listOf(TransportFailureCode.AUTHENTICATION_FAILED, TransportFailureCode.PERMISSION_DENIED)) {
            val transport = DiscoveryTransport().apply {
                onConnect = {
                    delay(100)
                    throw transportFailure(failure)
                }
            }
            val controller = controller(transport)
            try {
                controller.joinInvitation()
                runCurrent()
                transport.discoveredHosts.value = listOf(MOVED_HOST)
                advanceTimeBy(100)
                runCurrent()
                val expected = if (failure == TransportFailureCode.AUTHENTICATION_FAILED) {
                    UiProblemCode.JOIN_REJECTED
                } else UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED
                assertEquals(expected, controller.state.value.problem?.code)
                assertEquals(ConnectionStatus.DISCONNECTED, controller.state.value.connection.status)
                if (failure == TransportFailureCode.AUTHENTICATION_FAILED) controller.retryConnection()
                advanceTimeBy(30_000)
                runCurrent()
                assertEquals(1, transport.requests.size, "A permission or identity failure tried another endpoint")
                assertEquals(1, transport.stopCount)
                assertFalse(transport.browsing)
            } finally {
                controller.close()
                controller.awaitClosed()
            }
        }
    }

    @Test
    fun permissionDenialDuringResumeStopsTheBatchButExplicitRetryRetainsTheSeat() = runTest {
        val transport = DiscoveryTransport()
        val controller = controller(transport)
        try {
            controller.joinInvitation()
            runCurrent()
            val first = transport.connections.single()
            first.server(welcome())
            runCurrent()
            val admittedView = controller.state.value.session

            transport.onConnect = { throw transportFailure(TransportFailureCode.PERMISSION_DENIED) }
            first.interrupt()
            runCurrent()
            transport.discoveredHosts.value = listOf(MOVED_HOST)
            advanceTimeBy(500)
            runCurrent()
            assertEquals(ConnectionStatus.DISCONNECTED, controller.state.value.connection.status)
            assertEquals(UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED, controller.state.value.problem?.code)
            assertEquals(RecoveryAction.RETRY_CONNECTION, controller.state.value.problem?.recovery)
            assertEquals(admittedView, controller.state.value.session)
            assertFalse(controller.state.value.canSendSessionAction)
            assertFalse(transport.browsing)
            assertEquals(2, transport.stopCount)
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(2, transport.requests.size, "Permission denial continued the automatic reconnect batch")
            assertEquals(2, transport.startCount)

            transport.onConnect = { DiscoveryConnection("permission-restored") }
            controller.retryConnection()
            runCurrent()
            assertTrue(transport.browsing)
            advanceTimeBy(500)
            runCurrent()
            val replacement = transport.connections.last()
            assertEquals(2, transport.connections.size)
            val resume = assertIs<ClientMessage.Resume>(replacement.messages.single())
            assertEquals(INVITATION.sessionId, resume.sessionId)
            assertEquals(SELF, resume.playerId)
            assertEquals(TOKEN, resume.reconnectToken)
            assertTrue(transport.requests.all { it.pin == INVITATION.certificateSha256 })
            replacement.server(welcome(revision = 2))
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertEquals(2L, controller.state.value.session?.revision)
            assertFalse(transport.browsing)
            assertEquals(3, transport.stopCount)
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun anUnrelatedServiceCannotExtendTheBoundedJoinOrSupplyAnEndpoint() = runTest {
        val transport = DiscoveryTransport().apply {
            onConnect = { throw transportFailure(TransportFailureCode.IO_ERROR) }
        }
        val controller = controller(transport)
        try {
            controller.joinInvitation()
            runCurrent()
            transport.discoveredHosts.value = listOf(OTHER_HOST)
            advanceTimeBy(8_100)
            runCurrent()
            assertEquals(listOf(INVITATION.endpoint), transport.requests.map { it.endpoint })
            assertEquals(ConnectionStatus.DISCONNECTED, controller.state.value.connection.status)
            assertEquals(UiProblemCode.CONNECTION_FAILED, controller.state.value.problem?.code)
            assertEquals(1, transport.stopCount)
            assertFalse(transport.browsing)
            transport.discoveredHosts.value = listOf(MOVED_HOST)
            advanceTimeBy(30_000)
            runCurrent()
            assertEquals(1, transport.requests.size, "A late discovery result revived an exhausted join")
        } finally {
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun backgroundStopsRediscoveryAndReturnResumesOnlyTheOriginalSeat() = runTest {
        val transport = DiscoveryTransport()
        val controller = controller(transport)
        try {
            controller.joinInvitation()
            runCurrent()
            val first = transport.connections.single()
            controller.setForeground(false) // A permission sheet makes iOS inactive, not backgrounded.
            runCurrent()
            assertTrue(transport.browsing)
            assertFalse(first.closed)
            first.server(welcome())
            runCurrent()
            assertFalse(transport.browsing)
            controller.setForeground(true)

            first.interrupt()
            runCurrent()
            assertEquals(2, transport.startCount)
            assertTrue(transport.browsing)
            controller.setBackgrounded(true)
            runCurrent()
            assertFalse(transport.browsing)
            assertEquals(2, transport.stopCount)
            assertTrue(first.closed)
            advanceTimeBy(60_000)
            runCurrent()
            assertEquals(2, transport.startCount, "A background client restarted browsing")
            assertEquals(1, transport.requests.size)

            transport.onConnect = { request ->
                if (request.endpoint == INVITATION.endpoint) throw transportFailure(TransportFailureCode.IO_ERROR)
                DiscoveryConnection("resumed-at-new-address")
            }
            controller.setBackgrounded(false)
            controller.setForeground(true)
            runCurrent()
            assertEquals(3, transport.startCount)
            advanceTimeBy(500)
            runCurrent()
            transport.discoveredHosts.value = listOf(MOVED_HOST)
            runCurrent()
            val replacement = transport.connections.last()
            assertEquals(2, transport.connections.size)
            val resume = assertIs<ClientMessage.Resume>(replacement.messages.single())
            assertEquals(INVITATION.sessionId, resume.sessionId)
            assertEquals(SELF, resume.playerId)
            assertEquals(TOKEN, resume.reconnectToken)
            assertTrue(transport.requests.all { it.pin == INVITATION.certificateSha256 })
            replacement.server(welcome(revision = 2))
            runCurrent()
            assertEquals(2L, controller.state.value.session?.revision)
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertEquals(3, transport.stopCount)
            assertFalse(transport.browsing)
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun rapidRetriesWaitForEarlierDiscoveryCleanupBeforeStartingAgain() = runTest {
        val releaseStop = CompletableDeferred<Unit>()
        val transport = DiscoveryTransport().apply {
            onConnect = { request ->
                if (request.number == 1) awaitCancellation()
                DiscoveryConnection("after-retries")
            }
            onStop = { if (stopCount == 1) releaseStop.await() }
        }
        val controller = controller(transport)
        try {
            controller.joinInvitation()
            runCurrent()
            controller.retryConnection()
            runCurrent()
            assertEquals(1, transport.stopCount)
            controller.retryConnection()
            controller.retryConnection()
            runCurrent()
            assertEquals(1, transport.startCount, "A new browse overlapped its predecessor's native cleanup")
            assertEquals(1, transport.requests.size)

            releaseStop.complete(Unit)
            runCurrent()
            assertEquals(2, transport.startCount)
            assertEquals(2, transport.requests.size)
            assertTrue(transport.browsing)
            val replacement = transport.connections.single()
            replacement.server(welcome())
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertFalse(replacement.closed, "Old loop cleanup closed the replacement connection")
            assertEquals(2, transport.stopCount)
            assertFalse(transport.browsing)
        } finally {
            releaseStop.complete(Unit)
            controller.close()
            controller.awaitClosed()
        }
    }

    @Test
    fun leavingDuringDiscoveryClosesItAndAddressOnlyInvitationsNeverBrowse() = runTest {
        val transport = DiscoveryTransport().apply {
            onStart = { awaitCancellation() }
            onConnect = { awaitCancellation() }
        }
        val controller = controller(transport)
        try {
            controller.joinInvitation()
            runCurrent()
            assertTrue(transport.browsing)
            controller.leaveSession()
            runCurrent()
            assertTrue(transport.closed)
            assertFalse(transport.browsing)
            assertEquals(1, transport.stopCount)
            transport.discoveredHosts.value = listOf(MOVED_HOST)
            advanceTimeBy(30_000)
            runCurrent()
            assertEquals(AppScreen.HOME, controller.state.value.screen)
            assertEquals(1, transport.requests.size)
            assertNull(controller.state.value.session)
        } finally {
            controller.close()
            controller.awaitClosed()
        }

        val addressOnly = INVITATION.copy(endpoint = INVITATION.endpoint.copy(serviceName = null))
        val directTransport = DiscoveryTransport()
        val directController = controller(directTransport)
        try {
            directController.joinInvitation(addressOnly)
            runCurrent()
            directTransport.connections.single().server(welcome())
            runCurrent()
            assertEquals(ConnectionStatus.CONNECTED, directController.state.value.connection.status)
            assertEquals(0, directTransport.startCount)
            assertEquals(0, directTransport.stopCount)
        } finally {
            directController.close()
            directController.awaitClosed()
        }
    }

    private fun TestScope.controller(transport: DiscoveryTransport) = PartyDeckController(
        DiscoveryTestServices(), transport, this,
    )

    private fun PartyDeckController.joinInvitation(invitation: LanInvitation = INVITATION) {
        navigate(AppScreen.JOIN)
        setJoinAddress(invitation.encode())
        join()
    }

    private fun welcome(revision: Long = 1): ServerMessage.Welcome = ServerMessage.Welcome(
        INVITATION.sessionId, SELF, TOKEN, 1,
        SessionView(
            sessionId = INVITATION.sessionId,
            revision = revision,
            selfPlayerId = SELF,
            hostPlayerId = "host",
            phase = SessionPhase.LOBBY,
            players = listOf(
                LobbyPlayer("host", "Host", true, true),
                LobbyPlayer(SELF, "Guest", false, true),
            ),
        ),
    )

    private companion object {
        const val SERVICE = "partydeck-invited-table"
        const val SELF = "guest"
        val TOKEN = "c".repeat(64)
        val INVITATION = LanInvitation(
            "discovery-room", "a".repeat(64), LanEndpoint("192.168.1.2", 42424, SERVICE), "b".repeat(64),
        )
        val MOVED_HOST = DiscoveredHost(SERVICE, "Host", LanEndpoint("192.168.1.3", 43434))
        val OTHER_HOST = DiscoveredHost(
            "partydeck-other-table", "Host", LanEndpoint("192.168.1.4", 42424, "partydeck-other-table"),
        )
    }
}

private class DiscoveryTransport : LanTransport, LanTransportFactory {
    override val discoveredHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
    override val discoveryState = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)
    var onStart: suspend DiscoveryTransport.() -> Unit = {}
    var onStop: suspend DiscoveryTransport.() -> Unit = {}
    var onConnect: suspend (ConnectRequest) -> DiscoveryConnection = { DiscoveryConnection("direct-${it.number}") }
    val requests = mutableListOf<ConnectRequest>()
    val connections = mutableListOf<DiscoveryConnection>()
    var createCount = 0
    var startCount = 0
    var stopCount = 0
    var browsing = false
    var closed = false

    override fun create(): LanTransport {
        createCount++
        return this
    }

    override suspend fun startDiscovery() {
        startCount++
        browsing = true
        discoveredHosts.value = emptyList()
        discoveryState.value = DiscoveryState.Searching
        onStart()
    }

    override suspend fun stopDiscovery() {
        stopCount++
        onStop()
        browsing = false
        discoveredHosts.value = emptyList()
        discoveryState.value = DiscoveryState.Idle
    }

    override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection {
        val request = ConnectRequest(requests.size + 1, endpoint, certificateSha256)
        requests += request
        return onConnect(request).also(connections::add)
    }

    override suspend fun host(displayName: String): LanHost = error("Client discovery test")

    override suspend fun close() {
        closed = true
        browsing = false
        discoveredHosts.value = emptyList()
        discoveryState.value = DiscoveryState.Idle
        connections.forEach { it.close() }
    }

    data class ConnectRequest(val number: Int, val endpoint: LanEndpoint, val pin: String)
}

private class DiscoveryConnection(override val id: String) : LanConnection {
    override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
    private val frames = Channel<ByteArray>(16)
    override val incoming = frames.receiveAsFlow()
    val messages = mutableListOf<ClientMessage>()
    var closed = false

    override suspend fun send(bytes: ByteArray) {
        messages += assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(bytes)).value
    }

    suspend fun server(message: ServerMessage) { frames.send(SessionCodec.encodeServer(message)) }

    fun interrupt() {
        state.value = ConnectionState.Failed(TransportFailure(TransportFailureCode.IO_ERROR, "Interrupted test connection"))
        frames.close()
    }

    override suspend fun close() {
        closed = true
        state.value = ConnectionState.Closed
        frames.close()
    }
}

private class DiscoveryTestServices : PlatformServices {
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
    override fun gameRandom(): Random = error("LAN guest has no authority random source")
    override fun secureToken(): String = error("LAN guest has no authority token source")
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = Unit
}

private fun transportFailure(code: TransportFailureCode) = TransportException(TransportFailure(code, "Discovery test failure"))
