package dev.partydeck.app.controller

import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds
import kotlin.time.ExperimentalTime
import kotlin.time.TestTimeSource
import kotlin.time.TimeSource

/** Exercises the acquisition boundary; the host counts requests and implements no renderer. */
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalTime::class)
class PresentationPickerSelectionTest {
    @Test
    fun eachModeRequiresDisposalAndFocusInEitherOrderAndAcquiresOnlyOnce() = runTest {
        for (mode in pickerModes) {
            for (focusFirst in listOf(false, true)) {
                val fixture = PickerSelectionFixture(backgroundScope)
                try {
                    val original = fixture.state.session
                    fixture.setForeground(false)
                    val choice = assertNotNull(fixture.coordinator.selectFromPicker(mode))
                    repeat(2) { fixture.coordinator.update() }
                    assertTrue(fixture.host.launches.isEmpty())
                    assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)

                    if (focusFirst) fixture.setForeground(true) else choice.commit()
                    repeat(2) { fixture.coordinator.update() }
                    assertTrue(fixture.host.launches.isEmpty(), "Neither focus nor disposal suffices alone")
                    if (focusFirst) choice.commit() else fixture.setForeground(true)

                    assertEquals(mode, fixture.state.presentation.selected)
                    val launch = fixture.host.launches.single()
                    val initial = LastLightWireCodec.decodeViewPayload(launch.initialView)
                    assertEquals(original, fixture.state.session)
                    assertEquals(original?.game, initial.game)
                    assertFalse(initial.controls.canSendAction)
                    assertEquals(1L, fixture.state.privacyEpoch)
                    repeat(2) { choice.commit(); fixture.coordinator.update() }
                    assertEquals(1, fixture.host.launches.size)
                } finally {
                    fixture.coordinator.close()
                    runCurrent()
                }
            }
        }
    }

    @Test
    fun removalCancelsBeforeCommitAndWhileCommittedChoiceWaitsForFocus() = runTest {
        for (commitFirst in listOf(false, true)) {
            val fixture = PickerSelectionFixture(backgroundScope)
            try {
                fixture.setForeground(false)
                val choice = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_2D))
                if (commitFirst) choice.commit()
                choice.cancel()
                fixture.setForeground(true)
                choice.commit()
                fixture.coordinator.update()
                assertTrue(fixture.host.launches.isEmpty())
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun obsoletePickerCannotCommitOrCancelItsReplacement() = runTest {
        val fixture = PickerSelectionFixture(backgroundScope)
        try {
            val old = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_2D))
            val current = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_3D))
            old.commit()
            old.cancel()
            fixture.coordinator.update()
            assertTrue(fixture.host.launches.isEmpty())
            current.commit()
            assertEquals(GameplayPresentation.GODOT_3D, fixture.state.presentation.selected)
            assertEquals(1, fixture.host.launches.size)
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun contextInvalidationCannotReviveWhenDisposalArrivesAfterStateIsRestored() = runTest {
        val invalidations: List<Pair<String, (PickerSelectionFixture) -> Unit>> = listOf(
            "background while modal is unfocused" to { it.state = it.state.copy(isBackgrounded = true) },
            "leave" to { it.state = it.state.copy(leaveConfirmationRequested = true) },
            "route" to { it.state = it.state.copy(screen = AppScreen.HOW_TO) },
            "session removed" to { it.state = it.state.copy(session = null) },
            "session generation" to { it.generation++ },
            "session ID" to { it.state = it.state.copy(session = it.state.session?.copy(sessionId = "replacement")) },
            "recipient" to { it.state = it.state.copy(session = it.otherRecipientView) },
            "game phase" to { it.state = it.state.copy(session = it.state.session?.copy(phase = SessionPhase.LOBBY, game = null)) },
            "connection" to { it.state = it.state.copy(connection = it.state.connection.copy(status = ConnectionStatus.DISCONNECTED)) },
            "text scale" to { it.state = it.state.copy(presentationTextScale = 2.0) },
            "motion" to { it.state = it.state.copy(systemReduceMotion = true) },
            "owner" to { it.coordinator.setSelectionOwnerActive(false) },
            "availability" to { it.host.available.value = emptySet() },
            "factory" to { it.host.unavailableFactory = GameplayPresentation.GODOT_2D },
            "Standard selected" to { assertTrue(it.coordinator.select(GameplayPresentation.COMPOSE)) },
        )
        for ((reason, invalidate) in invalidations) {
            val fixture = PickerSelectionFixture(backgroundScope)
            try {
                fixture.setForeground(false)
                val before = fixture.state
                val generation = fixture.generation
                val choice = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_2D))
                invalidate(fixture)
                fixture.coordinator.update()
                fixture.state = before
                fixture.generation = generation
                fixture.host.available.value = pickerModes
                fixture.host.unavailableFactory = null
                fixture.coordinator.setSelectionOwnerActive(true)
                fixture.setForeground(true)
                choice.commit()
                runCurrent()
                assertTrue(fixture.host.launches.isEmpty(), reason)
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun disposalDoesNotRestartTheOriginalDeadlineOrTimer() = runTest {
        for (timerRuns in listOf(false, true)) {
            val clock = TestTimeSource()
            val fixture = PickerSelectionFixture(backgroundScope, clock)
            try {
                fixture.setForeground(false)
                val choice = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_2D))
                clock += 2.seconds
                if (timerRuns) advanceTimeBy(2_000)
                choice.commit()
                assertTrue(fixture.host.launches.isEmpty())
                if (timerRuns) {
                    advanceTimeBy(3_001)
                    runCurrent()
                } else {
                    clock += 3.seconds // Check the monotonic deadline before an overdue timer runs.
                }
                fixture.setForeground(true)
                choice.commit()
                assertTrue(fixture.host.launches.isEmpty())
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun disposalAfterDeadlineCannotAcquireEvenWhenAlreadyFocused() = runTest {
        val clock = TestTimeSource()
        val fixture = PickerSelectionFixture(backgroundScope, clock)
        try {
            val choice = assertNotNull(fixture.coordinator.selectFromPicker(GameplayPresentation.GODOT_2D))
            clock += 5.seconds
            choice.commit()
            assertTrue(fixture.host.launches.isEmpty())
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }
}

private val pickerModes = setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)

private class PickerSelectionFixture(scope: CoroutineScope, clock: TimeSource = TimeSource.Monotonic) {
    private val players = listOf(PlayerIdentity("host", "Host"), PlayerIdentity("guest", "Guest"))
    private val engine = LastLightEngine(Random(2))
    private val game = engine.start(players)
    private val viewer = assertNotNull(game.turnPlayerId)
    private val session = SessionView(
        sessionId = "picker-selection", revision = 0, selfPlayerId = viewer, hostPlayerId = viewer,
        phase = SessionPhase.GAME,
        players = players.map { LobbyPlayer(it.id, it.displayName, isReady = true, isConnected = true) },
        game = engine.viewFor(game, viewer),
    )
    val otherRecipientView = players.single { it.id != viewer }.id.let {
        session.copy(selfPlayerId = it, game = engine.viewFor(game, it))
    }
    val host = PickerSelectionHost()
    var state = AppUiState(
        screen = AppScreen.SESSION, session = session,
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.PRACTICE),
    )
    var generation = 1L
    private var nextPresentation = 1L
    val coordinator = EmbeddedPresentationCoordinator(
        scope, host, { state }, { generation }, { "picker-selection-${nextPresentation++}" },
        { presentation, conceal ->
            state = state.copy(presentation = presentation, privacyEpoch = state.privacyEpoch + if (conceal) 1 else 0)
        }, { false }, {}, clock,
    ).also { it.start() }

    fun setForeground(value: Boolean) {
        state = state.copy(isForeground = value)
        coordinator.update()
    }
}

private class PickerSelectionHost : EmbeddedPresentationHost {
    override val available = MutableStateFlow(pickerModes)
    var unavailableFactory: GameplayPresentation? = null
    val launches = mutableListOf<EngineLaunch>()

    override fun createFactory(presentation: GameplayPresentation, preferences: PresentationPreferences): EmbeddedGameFactory? {
        if (presentation !in available.value || presentation == unavailableFactory) return null
        return object : EmbeddedGameFactory {
            override val engineId = when (presentation) {
                GameplayPresentation.GODOT_2D -> "godot-2d"
                GameplayPresentation.GODOT_3D -> "godot-3d"
                GameplayPresentation.COMPOSE -> error("Compose does not acquire a native surface")
            }
            override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
            override val supportedGames = setOf(GameId("last-light"))
            override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
                launches += launch
                awaitCancellation()
            }
        }
    }
}
