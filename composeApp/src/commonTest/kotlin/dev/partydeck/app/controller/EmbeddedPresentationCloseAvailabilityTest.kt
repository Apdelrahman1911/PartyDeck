package dev.partydeck.app.controller

import dev.partydeck.core.LastLightEngine
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionPhase
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds
import kotlin.time.ExperimentalTime
import kotlin.time.TestTimeSource
import kotlin.time.TimeSource

/** The host contract includes a temporary lack of factories while native cleanup owns the slot. */
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalTime::class)
class EmbeddedPresentationCloseAvailabilityTest {
    @Test
    fun modeSwitchSurvivesTheCloseAvailabilityGapAndRequiresFocusInEitherOrder() = runTest {
        for (mode in closeAvailabilityModes) {
            for (focusOrder in listOf("already focused", "before close", "after close")) {
                for (immediate in listOf(false, true)) {
                    val scope = if (immediate) {
                        CoroutineScope(backgroundScope.coroutineContext + UnconfinedTestDispatcher(testScheduler))
                    } else backgroundScope
                    val fixture = CloseAvailabilityFixture(scope)
                    try {
                        val originalSession = fixture.state.session
                        val old = beginSwitch(fixture, mode, foreground = focusOrder == "already focused")
                        repeat(2) { fixture.coordinator.update() }
                        if (focusOrder == "before close") fixture.setForeground(true)
                        runCurrent()
                        assertEquals(1, fixture.host.openAttempts, "Focus cannot bypass deferred cleanup")

                        old.completeClose(true)
                        runCurrent()
                        if (focusOrder == "after close") {
                            assertEquals(1, fixture.host.openAttempts, "Restored availability cannot grant focus")
                            assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
                            fixture.setForeground(true)
                            runCurrent()
                        }
                        assertEquals(2, fixture.host.openAttempts)
                        val current = fixture.host.ports.last()
                        assertNotEquals(old.launch.presentationId, current.launch.presentationId)
                        assertEquals(mode, fixture.state.presentation.selected)
                        assertEquals(originalSession, fixture.state.session)
                        val initial = LastLightWireCodec.decodeViewPayload(current.launch.initialView)
                        assertEquals(originalSession?.game, initial.game)
                        assertFalse(initial.controls.canSendAction)
                        current.ready()
                        runCurrent()
                        assertEquals(PresentationLifecycle.ACTIVE, fixture.state.presentation.lifecycle)
                        repeat(2) { fixture.coordinator.update() }
                        assertEquals(2, fixture.host.openAttempts)
                    } finally {
                        dispose(fixture)
                    }
                }
            }
        }
    }

    @Test
    fun successfulCloseRevalidatesBothTheAdvertisedModeAndItsFactory() = runTest {
        for (withdrawFactoryOnly in listOf(false, true)) {
            val fixture = CloseAvailabilityFixture(backgroundScope)
            try {
                val old = beginSwitch(fixture, foreground = false)
                if (withdrawFactoryOnly) fixture.host.unavailableFactory = GameplayPresentation.GODOT_3D
                else fixture.host.offered = setOf(GameplayPresentation.GODOT_2D)
                old.completeClose(true)
                runCurrent()
                assertEquals(1, fixture.host.openAttempts)

                fixture.host.offered = closeAvailabilityModes
                fixture.host.unavailableFactory = null
                fixture.host.publishOffered()
                runCurrent()
                fixture.setForeground(true)
                runCurrent()
                assertEquals(1, fixture.host.openAttempts, "An unavailable choice must not revive after close")
                assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
                assertEquals(2, fixture.host.openAttempts, "A fresh explicit choice may use the restored factory")
            } finally {
                dispose(fixture)
            }
        }
    }

    @Test
    fun closeAvailabilityGapDoesNotPreserveAnInvalidatedSelection() = runTest {
        val invalidations: List<Pair<String, (CloseAvailabilityFixture) -> Unit>> = listOf(
            "background" to { it.state = it.state.copy(isBackgrounded = true) },
            "leave" to { it.state = it.state.copy(leaveConfirmationRequested = true) },
            "route" to { it.state = it.state.copy(screen = AppScreen.HOW_TO) },
            "session removed" to { it.state = it.state.copy(session = null) },
            "session generation" to { it.generation++ },
            "session ID" to { it.state = it.state.copy(session = it.state.session?.copy(sessionId = "replacement")) },
            "recipient" to { it.state = it.state.copy(session = it.guestView) },
            "game phase" to { it.state = it.state.copy(session = it.state.session?.copy(phase = SessionPhase.LOBBY, game = null)) },
            "connection" to { it.state = it.state.copy(connection = it.state.connection.copy(status = ConnectionStatus.DISCONNECTED)) },
            "text scale" to { it.state = it.state.copy(presentationTextScale = 2.0) },
            "motion" to { it.state = it.state.copy(systemReduceMotion = true) },
            "owner pause or replacement" to { it.coordinator.setSelectionOwnerActive(false) },
            "Standard selected" to { assertTrue(it.coordinator.select(GameplayPresentation.COMPOSE)) },
        )
        for ((reason, invalidate) in invalidations) {
            val fixture = CloseAvailabilityFixture(backgroundScope)
            try {
                val old = beginSwitch(fixture)
                val before = fixture.state
                val generation = fixture.generation
                invalidate(fixture)
                fixture.coordinator.update()
                fixture.state = before
                fixture.generation = generation
                fixture.coordinator.setSelectionOwnerActive(true)
                old.completeClose(true)
                runCurrent()
                fixture.coordinator.update()
                assertEquals(1, fixture.host.openAttempts, reason)
                assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle, reason)
            } finally {
                dispose(fixture)
            }
        }
    }

    @Test
    fun monotonicDeadlineStillRejectsCloseCompletionBeforeTheTimerRuns() = runTest {
        val clock = TestTimeSource()
        val fixture = CloseAvailabilityFixture(backgroundScope, clock)
        try {
            val old = beginSwitch(fixture)
            clock += 5.seconds
            // No scheduler advance or update: completion itself must check the original deadline.
            old.completeClose(true)
            runCurrent()
            assertEquals(1, fixture.host.openAttempts)
            assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            assertEquals(2, fixture.host.openAttempts)
        } finally {
            dispose(fixture)
        }
    }

    @Test
    fun restoredAvailabilityDoesNotRestartTheSelectionTimeout() = runTest {
        val fixture = CloseAvailabilityFixture(backgroundScope)
        try {
            val old = beginSwitch(fixture, foreground = false)
            advanceTimeBy(2_000)
            old.completeClose(true)
            runCurrent()
            assertEquals(1, fixture.host.openAttempts)
            advanceTimeBy(3_001)
            runCurrent()
            fixture.setForeground(true)
            runCurrent()
            assertEquals(1, fixture.host.openAttempts)
            assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
        } finally {
            dispose(fixture)
        }
    }

    @Test
    fun failedOrTimedOutCloseQuarantinesThePendingModeDespiteLaterAvailability() = runTest {
        for (timedOut in listOf(false, true)) {
            val fixture = CloseAvailabilityFixture(backgroundScope)
            try {
                val old = beginSwitch(fixture)
                if (timedOut) {
                    advanceTimeBy(3_001)
                    runCurrent()
                    old.completeClose(true)
                } else {
                    old.completeClose(false)
                    runCurrent()
                    fixture.host.publishOffered()
                }
                runCurrent()
                fixture.coordinator.update()
                assertEquals(1, fixture.host.openAttempts)
                assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
                assertEquals(PresentationFallbackReason.DELIVERY_FAILED, fixture.state.presentation.fallbackReason)
                assertEquals(setOf(GameplayPresentation.COMPOSE), fixture.state.presentation.available)
                assertFalse(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
                assertEquals(1, fixture.host.openAttempts)
            } finally {
                dispose(fixture)
            }
        }
    }

    private fun TestScope.beginSwitch(
        fixture: CloseAvailabilityFixture,
        target: GameplayPresentation = GameplayPresentation.GODOT_3D,
        foreground: Boolean = true,
    ): CloseAvailabilityPort {
        assertTrue(fixture.coordinator.select(closeAvailabilityModes.single { it != target }))
        val old = fixture.host.ports.single()
        old.ready()
        runCurrent()
        assertEquals(PresentationLifecycle.ACTIVE, fixture.state.presentation.lifecycle)
        old.deferClose = true
        fixture.setForeground(foreground)
        assertTrue(fixture.coordinator.select(target))
        runCurrent()
        assertTrue(old.closeStarted)
        assertEquals(PresentationLifecycle.CLOSING, fixture.state.presentation.lifecycle)
        assertTrue(fixture.host.available.value.isEmpty())
        assertEquals(setOf(GameplayPresentation.COMPOSE), fixture.state.presentation.available)
        assertEquals(1, fixture.host.openAttempts)
        return old
    }

    private fun TestScope.dispose(fixture: CloseAvailabilityFixture) {
        fixture.coordinator.close()
        fixture.host.ports.filter { it.closeStarted }.forEach { it.completeClose(true) }
        runCurrent()
    }
}

private val closeAvailabilityModes = setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)

private class CloseAvailabilityFixture(scope: CoroutineScope, selectionTimeSource: TimeSource = TimeSource.Monotonic) {
    private val hostPeer = SessionPeer("close-host")
    private val guestPeer = SessionPeer("close-guest")
    private var nextToken = 1L
    private val authority = HostAuthority(
        HostSessionConfig("close-availability", "a".repeat(64), "Host", hostPeer), LastLightEngine(Random(2)),
    ) { (nextToken++).toString(16).padStart(64, '0') }.apply {
        handle(guestPeer, ClientMessage.Join(sessionId, "a".repeat(64), "Guest"))
        handle(guestPeer, ClientMessage.Command(sessionId, 1, assertNotNull(viewFor(guestPeer)).revision, ClientIntent.SetReady(true)))
        handle(hostPeer, ClientMessage.Command(sessionId, 1, assertNotNull(viewFor(hostPeer)).revision, ClientIntent.StartGame))
        assertEquals(SessionPhase.GAME, assertNotNull(viewFor(hostPeer)).phase)
    }
    val guestView = assertNotNull(authority.viewFor(guestPeer))
    val host = CloseAvailabilityHost()
    var state = AppUiState(
        screen = AppScreen.SESSION,
        session = assertNotNull(authority.viewFor(hostPeer)),
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.LAN_HOST),
    )
    var generation = 1L
    private var nextPresentation = 1L
    val coordinator = EmbeddedPresentationCoordinator(
        scope, host, { state }, { generation }, { "close-availability-${nextPresentation++}" },
        { presentation, conceal ->
            state = state.copy(presentation = presentation, privacyEpoch = state.privacyEpoch + if (conceal) 1 else 0)
        },
        { false }, {}, selectionTimeSource,
    ).also { it.start() }

    fun setForeground(foreground: Boolean) {
        state = state.copy(isForeground = foreground)
        coordinator.update()
    }
}

/** Models the native availability/close contract; no renderer is implemented. */
private class CloseAvailabilityHost : EmbeddedPresentationHost {
    override val available = MutableStateFlow(closeAvailabilityModes)
    var offered = closeAvailabilityModes
    var unavailableFactory: GameplayPresentation? = null
    val ports = mutableListOf<CloseAvailabilityPort>()
    var openAttempts = 0
        private set
    private var active: CloseAvailabilityPort? = null

    fun publishOffered() { available.value = offered }

    override fun createFactory(presentation: GameplayPresentation, preferences: PresentationPreferences): EmbeddedGameFactory? {
        if (presentation !in available.value || presentation == unavailableFactory) return null
        return object : EmbeddedGameFactory {
            override val engineId = when (presentation) {
                GameplayPresentation.GODOT_2D -> "godot-2d"
                GameplayPresentation.GODOT_3D -> "godot-3d"
                GameplayPresentation.COMPOSE -> error("Compose does not open an engine")
            }
            override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
            override val supportedGames = setOf(GameId("last-light"))
            override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
                openAttempts++
                check(active == null) { "The previous native owner has not released its slot" }
                check(presentation in available.value && presentation != unavailableFactory)
                return CloseAvailabilityPort(launch, this@CloseAvailabilityHost).also {
                    active = it
                    ports += it
                }
            }
        }
    }

    fun beginClose(port: CloseAvailabilityPort) {
        check(active === port)
        available.value = emptySet()
    }

    fun finishClose(port: CloseAvailabilityPort, success: Boolean) {
        check(active === port)
        if (success) active = null
        available.value = if (success) offered else emptySet()
    }
}

private class CloseAvailabilityPort(val launch: EngineLaunch, private val host: CloseAvailabilityHost) : EmbeddedGameSession {
    private val eventQueue = Channel<EngineEvent>(4)
    override val events = eventQueue.receiveAsFlow()
    private val closeResult = CompletableDeferred<Boolean>()
    var deferClose = false
    var closeStarted = false
        private set

    fun ready() {
        check(eventQueue.trySend(EngineEvent(launch.presentationId, ENGINE_BRIDGE_PROTOCOL_VERSION, 0, EngineEventBody.Ready)).isSuccess)
    }

    override suspend fun send(command: EngineCommand) = Unit

    override suspend fun close() {
        closeStarted = true
        host.beginClose(this)
        if (!deferClose) completeClose(true)
        check(closeResult.await()) { "Controlled native cleanup failure" }
    }

    fun completeClose(success: Boolean) {
        check(closeStarted)
        if (closeResult.isCompleted) return
        // Like iOS finishClose, publish slot release and availability before resuming the waiter.
        host.finishClose(this, success)
        closeResult.complete(success)
    }
}
