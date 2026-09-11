package dev.partydeck.app

import androidx.compose.ui.geometry.Size
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.EmbeddedPresentationHost
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.PresentationFallbackReason
import dev.partydeck.app.controller.PresentationLifecycle
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.core.GamePhase
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.test.TestCoroutineScheduler
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

/** Real controller and Skiko dialog behavior; the host models deferred close without a renderer. */
@OptIn(ExperimentalTestApi::class)
class PresentationLeaveConfirmationTest {
    @Test
    fun nativeLeaveKeepsItsGuardsAndCreatesOneDialogOnlyAfterClose() {
        for (mode in leaveNativeModes) for (deferred in listOf(false, true)) {
            runSkikoComposeUiTest(size = Size(402f, 874f), testTimeout = 45.seconds) {
                val fixture = runOnUiThread { LeaveConfirmationFixture(deferred) }
                try {
                    setContent { PartyDeckApp(fixture.controller) }
                    waitForIdle()
                    runOnUiThread { fixture.startPracticeAtHumanTurn() }
                    waitForIdle()
                    val baselineRoots = onAllNodes(isRoot(), useUnmergedTree = true).fetchSemanticsNodes().size
                    val before = runOnUiThread { fixture.controller.state.value }
                    val session = assertNotNull(before.session)
                    val native = runOnUiThread { fixture.enter(mode) }
                    waitForIdle()
                    val activePrivacyEpoch = fixture.controller.state.value.privacyEpoch

                    runOnUiThread {
                        fixture.controller.requestPresentationExit(native.launch.presentationId)
                        fixture.settle()
                        val leaving = fixture.controller.state.value
                        assertTrue(leaving.leaveConfirmationRequested)
                        assertTrue(leaving.privacyEpoch > activePrivacyEpoch)
                        assertEquals(GameplayPresentation.COMPOSE, leaving.presentation.selected)
                        assertTrue(leaving.isForeground)
                        assertFalse(leaving.isBackgrounded)
                        assertNull(leaving.pendingAction)
                        assertTrue(leaving.canSendSessionAction)
                        val game = assertNotNull(leaving.session?.game)
                        assertTrue(game.availableActions.canPlay)
                        // This single-card play is legal absent the Leave guard.
                        fixture.controller.playCards(listOf(game.yourHand.first().id))
                        assertNull(fixture.controller.state.value.pendingAction)
                        assertFalse(fixture.controller.selectPresentation(mode))
                        fixture.settle()
                        assertEquals(session, fixture.controller.state.value.session)
                        assertNull(fixture.controller.state.value.problem)
                        assertEquals(1, fixture.host.sessions.size)
                        assertEquals(1, native.closeCalls)
                    }
                    if (deferred) {
                        assertEquals(PresentationLifecycle.CLOSING, fixture.controller.state.value.presentation.lifecycle)
                        onNodeWithTag("leave-confirm").assertDoesNotExist()
                        onNodeWithTag("leave-cancel").assertDoesNotExist()
                        assertEquals(
                            baselineRoots,
                            onAllNodes(isRoot(), useUnmergedTree = true).fetchSemanticsNodes().size,
                            "A pending native close must not create even an empty dialog layer",
                        )
                        runOnUiThread { native.completeClose(true); fixture.settle() }
                    }
                    assertEquals(PresentationLifecycle.COMPOSE, fixture.controller.state.value.presentation.lifecycle)
                    onAllNodesWithTag("leave-confirm").assertCountEquals(1)
                    onNodeWithTag("leave-confirm").assertIsDisplayed().assertIsEnabled()
                    onNodeWithTag("leave-cancel").assertIsDisplayed().assertIsEnabled()
                    assertEquals(
                        baselineRoots + 1,
                        onAllNodes(isRoot(), useUnmergedTree = true).fetchSemanticsNodes().size,
                    )
                    onNodeWithTag("leave-cancel").performClick()
                    waitForIdle()
                    assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                    assertEquals(session, fixture.controller.state.value.session)
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                    onNodeWithTag("game-card-0").assertDoesNotExist()
                    onNodeWithTag("game-reveal-hand").assertExists()
                    assertEquals(baselineRoots, onAllNodes(isRoot(), useUnmergedTree = true).fetchSemanticsNodes().size)
                    runOnUiThread { fixture.enter(mode) }
                    assertEquals(2, fixture.host.sessions.size, "Cancel must preserve a session that can re-enter native play")
                } finally {
                    runOnUiThread { fixture.close() }
                }
            }
        }
    }

    @Test
    fun nativeStandardReturnStaysDialogFreeAndSharedBackStillConfirmsImmediately() =
        runSkikoComposeUiTest(size = Size(402f, 874f), testTimeout = 45.seconds) {
            val fixture = runOnUiThread { LeaveConfirmationFixture(deferred = true) }
            try {
                setContent { PartyDeckApp(fixture.controller) }
                waitForIdle()
                runOnUiThread { fixture.startPracticeAtHumanTurn() }
                val native = runOnUiThread { fixture.enter(GameplayPresentation.GODOT_2D) }
                runOnUiThread { fixture.controller.useComposePresentation(); fixture.settle() }
                assertEquals(PresentationLifecycle.CLOSING, fixture.controller.state.value.presentation.lifecycle)
                assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                onNodeWithTag("leave-confirm").assertDoesNotExist()
                runOnUiThread { native.completeClose(true); fixture.settle() }
                assertEquals(PresentationLifecycle.COMPOSE, fixture.controller.state.value.presentation.lifecycle)
                onNodeWithTag("leave-confirm").assertDoesNotExist()

                onNodeWithTag("navigation-back").assertIsDisplayed().performClick()
                assertTrue(fixture.controller.state.value.leaveConfirmationRequested)
                onNodeWithTag("leave-confirm").assertIsDisplayed().assertIsEnabled().performClick()
                waitForIdle()
                assertEquals(AppScreen.HOME, fixture.controller.state.value.screen)
                assertNull(fixture.controller.state.value.session)
                assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                onNodeWithTag("leave-confirm").assertDoesNotExist()
                onNodeWithTag("home-practice").assertExists()
                assertEquals(1, fixture.host.sessions.size)
            } finally {
                runOnUiThread { fixture.close() }
            }
        }

    @Test
    fun clearedIntentCannotReturnAfterReplacementNavigationOrOwnerClose() {
        for (departure in listOf("replacement", "settings", "owner-close")) {
            runSkikoComposeUiTest(size = Size(402f, 874f), testTimeout = 45.seconds) {
                val fixture = runOnUiThread { LeaveConfirmationFixture(deferred = true) }
                try {
                    setContent { PartyDeckApp(fixture.controller) }
                    waitForIdle()
                    runOnUiThread { fixture.startPracticeAtHumanTurn() }
                    val oldSession = assertNotNull(fixture.controller.state.value.session)
                    val native = runOnUiThread { fixture.enter(GameplayPresentation.GODOT_2D) }
                    runOnUiThread {
                        fixture.controller.requestPresentationExit(native.launch.presentationId)
                        fixture.settle()
                    }
                    assertTrue(fixture.controller.state.value.leaveConfirmationRequested)
                    assertEquals(PresentationLifecycle.CLOSING, fixture.controller.state.value.presentation.lifecycle)
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                    val expected = runOnUiThread {
                        if (departure == "owner-close") {
                            fixture.controller.close()
                        } else {
                            fixture.controller.leaveSession()
                            if (departure == "replacement") {
                                fixture.startPracticeAtHumanTurn()
                                assertNotEquals(oldSession.sessionId, fixture.controller.state.value.session?.sessionId)
                            } else {
                                fixture.controller.navigate(AppScreen.SETTINGS)
                                assertEquals(AppScreen.SETTINGS, fixture.controller.state.value.screen)
                            }
                        }
                        fixture.settle()
                        assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                        fixture.controller.state.value
                    }
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                    runOnUiThread {
                        native.completeClose(true)
                        fixture.settle()
                        // An old callback cannot revive the cleared intent in a newer context.
                        fixture.controller.requestPresentationExit(native.launch.presentationId)
                        fixture.settle()
                    }
                    waitForIdle()
                    assertEquals(expected.screen, fixture.controller.state.value.screen)
                    assertEquals(expected.session, fixture.controller.state.value.session)
                    assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                    onNodeWithTag("leave-cancel").assertDoesNotExist()
                    assertEquals(1, fixture.host.sessions.size)
                } finally {
                    runOnUiThread { fixture.close() }
                }
            }
        }
    }

    @Test
    fun failedOrTimedOutCloseKeepsTheExistingFallbackAndLeaveIntent() {
        for (timeout in listOf(false, true)) {
            runSkikoComposeUiTest(size = Size(402f, 874f), testTimeout = 45.seconds) {
                val fixture = runOnUiThread { LeaveConfirmationFixture(deferred = true) }
                try {
                    setContent { PartyDeckApp(fixture.controller) }
                    waitForIdle()
                    runOnUiThread { fixture.startPracticeAtHumanTurn() }
                    val session = fixture.controller.state.value.session
                    val native = runOnUiThread { fixture.enter(GameplayPresentation.GODOT_3D) }
                    runOnUiThread {
                        fixture.controller.requestPresentationExit(native.launch.presentationId)
                        fixture.settle()
                    }
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                    runOnUiThread {
                        if (timeout) fixture.advanceCloseDeadline() else native.completeClose(false)
                        fixture.settle()
                    }
                    val failed = fixture.controller.state.value
                    assertEquals(PresentationLifecycle.COMPOSE, failed.presentation.lifecycle)
                    assertEquals(PresentationFallbackReason.DELIVERY_FAILED, failed.presentation.fallbackReason)
                    assertEquals(setOf(GameplayPresentation.COMPOSE), failed.presentation.available)
                    assertTrue(failed.leaveConfirmationRequested)
                    assertEquals(session, failed.session)
                    // This preserves shared fallback behavior; it does not prove failed UIKit detachment.
                    onNodeWithTag("leave-confirm").assertIsDisplayed().assertIsEnabled()
                    onNodeWithTag("leave-cancel").performClick()
                    waitForIdle()
                    runOnUiThread { native.completeClose(true); fixture.settle() }
                    assertFalse(fixture.controller.state.value.leaveConfirmationRequested)
                    assertEquals(session, fixture.controller.state.value.session)
                    runOnUiThread { assertFalse(fixture.controller.selectPresentation(GameplayPresentation.GODOT_2D)) }
                    onNodeWithTag("leave-confirm").assertDoesNotExist()
                } finally {
                    runOnUiThread { fixture.close() }
                }
            }
        }
    }
}

private val leaveNativeModes = setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)

@OptIn(ExperimentalCoroutinesApi::class)
private class LeaveConfirmationFixture(deferred: Boolean) {
    // Controller deadlines and practice bots use this clock, independently of Compose frame time.
    private val scheduler = TestCoroutineScheduler()
    private val owner = CoroutineScope(SupervisorJob() + UnconfinedTestDispatcher(scheduler))
    val host = LeaveCloseHost(deferred)
    val controller = PartyDeckController(
        LeaveTestServices(),
        object : LanTransportFactory {
            override fun create(): LanTransport = error("Practice must not create a network transport")
        },
        owner,
        host,
    )

    fun settle() { scheduler.runCurrent() }

    fun startPracticeAtHumanTurn() {
        controller.startPractice()
        settle()
        repeat(120) {
            val game = assertNotNull(controller.state.value.session?.game)
            if (game.availableActions.canPlay) {
                assertNull(controller.state.value.pendingAction)
                return
            }
            if (game.phase == GamePhase.ROUND_ENDED) controller.nextRound()
            else scheduler.advanceTimeBy(900)
            settle()
        }
        error("Practice never offered a human turn")
    }

    fun enter(mode: GameplayPresentation): LeaveCloseSession {
        assertTrue(controller.selectPresentation(mode))
        settle()
        val native = host.sessions.last()
        native.ready()
        settle()
        assertEquals(PresentationLifecycle.ACTIVE, controller.state.value.presentation.lifecycle)
        return native
    }

    fun advanceCloseDeadline() { scheduler.advanceTimeBy(3_001); settle() }

    fun close() {
        controller.close()
        settle()
        host.sessions.filter { it.closeCalls > 0 }.forEach { it.completeClose(true) }
        settle()
        owner.cancel()
        settle()
    }
}

/** Only the host's availability/completion contract is simulated; no Godot renderer is implemented. */
private class LeaveCloseHost(private val deferred: Boolean) : EmbeddedPresentationHost {
    override val available = MutableStateFlow(leaveNativeModes)
    val sessions = mutableListOf<LeaveCloseSession>()
    private var active: LeaveCloseSession? = null

    override fun createFactory(presentation: GameplayPresentation, preferences: PresentationPreferences): EmbeddedGameFactory? {
        if (presentation !in available.value) return null
        return object : EmbeddedGameFactory {
            override val engineId = when (presentation) {
                GameplayPresentation.GODOT_2D -> "godot-2d"
                GameplayPresentation.GODOT_3D -> "godot-3d"
                GameplayPresentation.COMPOSE -> error("Standard does not open an engine")
            }
            override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
            override val supportedGames = setOf(PartyDeckGames.lastLight.id)
            override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
                check(active == null)
                check(presentation in available.value)
                return LeaveCloseSession(launch, deferred, this@LeaveCloseHost).also {
                    active = it
                    sessions += it
                }
            }
        }
    }

    fun beginClose(session: LeaveCloseSession) {
        check(active === session)
        available.value = emptySet()
    }

    fun finishClose(session: LeaveCloseSession, success: Boolean) {
        check(active === session)
        if (success) active = null
        available.value = if (success) leaveNativeModes else emptySet()
    }
}

private class LeaveCloseSession(
    val launch: EngineLaunch,
    private val deferred: Boolean,
    private val host: LeaveCloseHost,
) : EmbeddedGameSession {
    private val incoming = Channel<EngineEvent>(4)
    override val events = incoming.receiveAsFlow()
    private val closeResult = CompletableDeferred<Boolean>()
    var closeCalls = 0
        private set

    fun ready() {
        check(incoming.trySend(EngineEvent(
            launch.presentationId, ENGINE_BRIDGE_PROTOCOL_VERSION, 0, EngineEventBody.Ready,
        )).isSuccess)
    }

    override suspend fun send(command: EngineCommand) = Unit

    override suspend fun close() {
        closeCalls++
        check(closeCalls == 1)
        host.beginClose(this)
        try {
            if (!deferred) completeClose(true)
            check(closeResult.await()) { "Controlled native cleanup failure" }
        } finally {
            incoming.close()
        }
    }

    fun completeClose(success: Boolean) {
        check(closeCalls > 0)
        if (closeResult.isCompleted) return
        // Match the native contract: publish release before a close waiter can resume.
        host.finishClose(this, success)
        closeResult.complete(success)
    }
}

private class LeaveTestServices : PlatformServices {
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
    private var token = 0L
    override fun secureToken() = (++token).toString(16).padStart(16, '0').repeat(4)
    override fun gameRandom(): Random = Random(12)
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
}
