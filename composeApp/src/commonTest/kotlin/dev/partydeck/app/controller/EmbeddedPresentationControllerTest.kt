@file:OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package dev.partydeck.app.controller

import dev.partydeck.core.GamePhase
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.godot.bridge.RendererIntent
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.Channel
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
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.fail

class EmbeddedPresentationControllerTest {
    @Test
    fun pickerChoiceWaitsForTheControllersActualForegroundPublicationInBothModes() = runTest {
        for (choice in listOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)) {
            val host = TestPresentationHost()
            val controller = controller(host)
            try {
                controller.startPractice()
                runCurrent()
                reachOwnPlay(controller)
                val before = controller.state.value.session
                controller.setForeground(false)
                assertFalse(controller.state.value.isBackgrounded)
                assertTrue(controller.selectPresentation(choice))
                runCurrent()
                assertTrue(host.opened.isEmpty())
                assertEquals(before, controller.state.value.session)
                val concealedEpoch = controller.state.value.privacyEpoch

                controller.setForeground(true)
                val native = host.opened.single()
                assertTrue(controller.state.value.privacyEpoch > concealedEpoch)
                assertEquals(before?.game, LastLightWireCodec.decodeViewPayload(native.launch.initialView).game)
                assertFalse(LastLightWireCodec.decodeViewPayload(native.launch.initialView).controls.canSendAction)
                assertTrue(native.commands.isEmpty())
                controller.setForeground(true)
                runCurrent()
                assertEquals(1, host.opened.size)
                assertEquals(choice, controller.state.value.presentation.selected)
            } finally {
                controller.close()
                runCurrent()
                controller.awaitClosed()
            }
        }
    }

    @Test
    fun ownerDepartureWhileAlreadyUnfocusedCancelsTheChoiceBeforeReturning() = runTest {
        val host = TestPresentationHost()
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.setForeground(false)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            controller.setPresentationSelectionOwnerActive(false)
            assertFalse(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            controller.setPresentationSelectionOwnerActive(true)
            controller.setForeground(true)
            runCurrent()
            assertTrue(host.opened.isEmpty())
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            assertEquals(1, host.opened.size)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun bothModesSubmitToPracticeAuthorityOnceAndReturnToTheSameConcealedSession() = runTest {
        for (choice in listOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)) {
            val host = TestPresentationHost()
            val controller = controller(host)
            try {
                controller.startPractice()
                runCurrent()
                reachOwnPlay(controller)
                val before = assertNotNull(controller.state.value.session)
                val hand = assertNotNull(before.game).yourHand
                assertTrue(controller.selectPresentation(choice))
                val native = host.opened.single()
                assertFalse(native.preferences.soundEnabled, "The shell already owns transition audio")
                val initial = LastLightWireCodec.decodeViewPayload(native.launch.initialView)
                assertEquals(before.selfPlayerId, initial.game.viewerId)
                assertEquals(hand, initial.game.yourHand)
                assertFalse(initial.controls.canSendAction)
                assertTrue(native.commands.isEmpty())

                native.ready()
                runCurrent()
                val view = native.latestView()
                assertTrue(view.revision > native.launch.initialRevision)
                native.intent(RendererIntent.Play(listOf(hand.first().id)), view.revision)
                native.intent(RendererIntent.Play(listOf(hand.first().id)), view.revision)
                runCurrent()
                val after = assertNotNull(controller.state.value.session)
                assertEquals(before.revision + 1, after.revision, "Two queued taps must produce one authority command")
                assertEquals(hand.size - 1, assertNotNull(after.game).yourHand.size)
                assertNull(controller.state.value.pendingAction)
                assertTrue(native.commands.filterIsInstance<EngineCommand.ShowView>().any {
                    !LastLightWireCodec.decodeViewPayload(it.payload).controls.canSendAction
                })

                val privacy = controller.state.value.privacyEpoch
                controller.useComposePresentation()
                assertTrue(controller.state.value.privacyEpoch > privacy)
                assertNull(controller.state.value.presentation.presentationId)
                runCurrent()
                assertEquals(GameplayPresentation.COMPOSE, controller.state.value.presentation.selected)
                assertEquals(PresentationLifecycle.COMPOSE, controller.state.value.presentation.lifecycle)
                assertEquals(after, controller.state.value.session)
                assertEquals(1, native.closeCalls)
                assertFalse(controller.state.value.leaveConfirmationRequested)
            } finally {
                controller.close()
                runCurrent()
                controller.awaitClosed()
            }
        }
    }

    @Test
    fun readyReceivesTheNewestBufferedViewAndForegroundWithoutAnyEarlierCommands() = runTest {
        val host = TestPresentationHost()
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            val native = host.opened.single()
            val card = assertNotNull(controller.state.value.session?.game).yourHand.first().id
            controller.playCards(listOf(card))
            runCurrent()
            controller.setForeground(false)
            controller.setForeground(true)
            assertTrue(native.commands.isEmpty(), "Nothing may acknowledge native Ready before the common gate")
            native.ready()
            runCurrent()
            assertTrue(native.commands.first() is EngineCommand.ShowView)
            assertEquals(controller.state.value.session?.game, LastLightWireCodec.decodeViewPayload(native.latestView().payload).game)
            assertEquals(EngineCommand.SetForeground(true), native.commands.last())
            assertEquals(PresentationLifecycle.ACTIVE, controller.state.value.presentation.lifecycle)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun queuedInputFromBeforeRapidForegroundLossAndRegainCannotMutateAuthority() = runTest {
        val host = TestPresentationHost()
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            controller.selectPresentation(GameplayPresentation.GODOT_3D)
            val native = host.opened.single()
            native.ready()
            runCurrent()
            val before = assertNotNull(controller.state.value.session)
            val oldRevision = native.latestView().revision
            native.intent(RendererIntent.Play(listOf(assertNotNull(before.game).yourHand.first().id)), oldRevision)
            controller.setForeground(false)
            controller.setForeground(true)
            runCurrent()
            assertEquals(before, controller.state.value.session)
            assertTrue(native.latestView().revision >= oldRevision + 2)
            assertEquals(listOf(false, true), native.commands.filterIsInstance<EngineCommand.SetForeground>().takeLast(2).map { it.isForeground })
            assertNull(controller.state.value.pendingAction)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun rulesAndChangedRendererPreferencesReturnToComposeWithoutReplacingTheSession() = runTest {
        val host = TestPresentationHost()
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val first = host.opened.single()
            first.ready()
            runCurrent()
            val sessionId = controller.state.value.session?.sessionId
            controller.navigate(AppScreen.HOW_TO)
            runCurrent()
            assertEquals(1, first.closeCalls)
            assertEquals(AppScreen.HOW_TO, controller.state.value.screen)
            assertEquals(sessionId, controller.state.value.session?.sessionId)
            controller.requestBack()
            assertEquals(GameplayPresentation.COMPOSE, controller.state.value.presentation.selected)
            controller.selectPresentation(GameplayPresentation.GODOT_3D)
            val second = host.opened.last()
            second.ready()
            runCurrent()
            controller.updateSettings(controller.state.value.settings.copy(soundEnabled = false, hapticsEnabled = false))
            runCurrent()
            assertEquals(0, second.closeCalls, "Shell-owned audio settings need no renderer restart")
            controller.setSystemReduceMotion(true)
            runCurrent()
            assertEquals(1, second.closeCalls)
            assertEquals(PresentationFallbackReason.PREFERENCES_CHANGED, controller.state.value.presentation.fallbackReason)
            assertEquals(sessionId, controller.state.value.session?.sessionId)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun switchingModesWaitsForCloseAndDoesNotOpenASecondNativeEngine() = runTest {
        val closeGate = CompletableDeferred<Unit>()
        val host = TestPresentationHost(nextCloseGate = closeGate)
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val first = host.opened.single()
            first.ready()
            runCurrent()
            val session = controller.state.value.session
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            runCurrent()
            assertEquals(PresentationLifecycle.CLOSING, controller.state.value.presentation.lifecycle)
            assertEquals(1, host.opened.size)
            closeGate.complete(Unit)
            runCurrent()
            val second = host.opened.last()
            assertEquals(2, host.opened.size)
            assertEquals(1, first.closeCalls)
            assertNotEquals(first.launch.presentationId, second.launch.presentationId)
            assertEquals(GameplayPresentation.GODOT_3D, controller.state.value.presentation.selected)
            assertEquals(session, controller.state.value.session)
        } finally {
            closeGate.complete(Unit)
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun aCloseTimeoutDisablesFurtherNativeOpensWhileTheSessionContinues() = runTest {
        val host = TestPresentationHost(nextCloseGate = CompletableDeferred())
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val sessionId = controller.state.value.session?.sessionId
            controller.selectPresentation(GameplayPresentation.GODOT_3D)
            advanceTimeBy(3_001)
            runCurrent()
            assertEquals(setOf(GameplayPresentation.COMPOSE), controller.state.value.presentation.available)
            assertEquals(PresentationLifecycle.COMPOSE, controller.state.value.presentation.lifecycle)
            assertEquals(PresentationFallbackReason.DELIVERY_FAILED, controller.state.value.presentation.fallbackReason)
            assertFalse(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            assertEquals(1, host.opened.size)
            assertEquals(sessionId, controller.state.value.session?.sessionId)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun unavailableFactoriesNeverStartAndMissingReadyFallsBackToTheLiveTable() = runTest {
        val host = TestPresentationHost(unsupportedThreeD = true)
        val controller = controller(host)
        try {
            assertEquals(setOf(GameplayPresentation.COMPOSE, GameplayPresentation.GODOT_2D), controller.state.value.presentation.available)
            assertTrue(host.opened.isEmpty())
            assertFalse(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            controller.startPractice()
            runCurrent()
            assertTrue(host.opened.isEmpty(), "Starting practice keeps Compose as the default")
            assertFalse(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val sessionId = controller.state.value.session?.sessionId
            advanceTimeBy(10_001)
            runCurrent()
            assertEquals(PresentationLifecycle.COMPOSE, controller.state.value.presentation.lifecycle)
            assertEquals(PresentationFallbackReason.INITIALIZATION_FAILED, controller.state.value.presentation.fallbackReason)
            assertEquals(sessionId, controller.state.value.session?.sessionId)
            assertEquals(1, host.opened.single().closeCalls)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun boundedDeliveryBacklogFallsBackWithoutEndingTheSession() = runTest {
        val host = TestPresentationHost(nextDeliveryGate = CompletableDeferred())
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val native = host.opened.single()
            native.ready()
            runCurrent()
            val sessionId = controller.state.value.session?.sessionId
            repeat(10) {
                controller.setForeground(false)
                controller.setForeground(true)
            }
            runCurrent()
            assertEquals(GameplayPresentation.COMPOSE, controller.state.value.presentation.selected)
            assertEquals(PresentationFallbackReason.DELIVERY_FAILED, controller.state.value.presentation.fallbackReason)
            assertEquals(1, native.closeCalls)
            assertEquals(sessionId, controller.state.value.session?.sessionId)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun commandsRetainTheirNativeLifecycleGenerationAcrossAStalledSend() = runTest {
        val delivery = CompletableDeferred<Unit>()
        val host = TestPresentationHost(nextDeliveryGate = delivery)
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val native = host.opened.single()
            native.ready()
            runCurrent() // First view is in send; its foreground grant is still in the common queue.
            assertEquals(1, native.attemptedCommands.size)
            native.lifecycleGeneration = 2
            controller.setForeground(false)
            native.lifecycleGeneration = 3
            controller.setForeground(true)
            delivery.complete(Unit)
            runCurrent()
            val grants = native.attemptedCommands.filter { it.first is EngineCommand.SetForeground }
                .map { (command, generation) -> (command as EngineCommand.SetForeground).isForeground to generation }
            assertEquals(listOf(true to 1L, false to 2L, true to 3L), grants)
            assertEquals(3L, native.attemptedCommands.last { it.first is EngineCommand.ShowView }.second)
            assertEquals(EngineCommand.SetForeground(true), native.commands.last())
            assertEquals(2, native.commands.size, "Only the current native generation applies its view and foreground grant")
        } finally {
            delivery.complete(Unit)
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun aStalledSendTimesOutClosesNativeAndKeepsTheSamePrivateHand() = runTest {
        val host = TestPresentationHost(nextDeliveryGate = CompletableDeferred())
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            reachOwnPlay(controller)
            val session = controller.state.value.session
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val native = host.opened.single()
            native.ready()
            runCurrent()
            advanceTimeBy(4_999)
            runCurrent()
            assertEquals(PresentationLifecycle.ACTIVE, controller.state.value.presentation.lifecycle)
            advanceTimeBy(2)
            runCurrent()
            assertEquals(PresentationLifecycle.COMPOSE, controller.state.value.presentation.lifecycle)
            assertEquals(PresentationFallbackReason.DELIVERY_FAILED, controller.state.value.presentation.fallbackReason)
            assertEquals(1, native.closeCalls)
            assertEquals(session, controller.state.value.session)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun aNewNativePrivacyGenerationRefreshesAnUnchangedForegroundOnce() = runTest {
        val host = TestPresentationHost()
        val controller = controller(host)
        try {
            controller.startPractice()
            runCurrent()
            controller.selectPresentation(GameplayPresentation.GODOT_2D)
            val native = host.opened.single()
            native.ready()
            runCurrent()
            val oldRevision = native.latestView().revision
            val oldCount = native.commands.size
            native.lifecycleGeneration = 2
            controller.refreshPresentationLifecycle("obsolete-presentation")
            runCurrent()
            assertEquals(oldCount, native.commands.size)
            controller.refreshPresentationLifecycle(native.launch.presentationId)
            runCurrent()
            assertEquals(oldCount + 2, native.commands.size)
            assertTrue(native.latestView().revision > oldRevision)
            assertEquals(EngineCommand.SetForeground(true), native.commands.last())
            assertEquals(2L, native.attemptedCommands.last().second)
            controller.refreshPresentationLifecycle(native.launch.presentationId)
            runCurrent()
            assertEquals(oldCount + 2, native.commands.size, "Repeated facts do not enqueue another grant")
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    private fun TestScope.controller(host: TestPresentationHost): PartyDeckController = PartyDeckController(
        PresentationTestServices(),
        object : LanTransportFactory {
            override fun create(): LanTransport = error("Practice must not create a network transport")
        },
        backgroundScope,
        host,
    )

    private fun TestScope.reachOwnPlay(controller: PartyDeckController) {
        repeat(120) {
            val game = assertNotNull(controller.state.value.session?.game)
            if (game.availableActions.canPlay) return
            if (game.phase == GamePhase.ROUND_ENDED) controller.nextRound() else advanceTimeBy(900)
            runCurrent()
        }
        fail("Practice never offered a human turn")
    }

    private class TestPresentationHost(
        val unsupportedThreeD: Boolean = false,
        var nextCloseGate: CompletableDeferred<Unit>? = null,
        var nextDeliveryGate: CompletableDeferred<Unit>? = null,
    ) : EmbeddedPresentationHost {
        override val available = MutableStateFlow(setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D))
        val opened = mutableListOf<TestNativeSession>()

        override fun createFactory(presentation: GameplayPresentation, preferences: PresentationPreferences): EmbeddedGameFactory =
            object : EmbeddedGameFactory {
                override val engineId = if (presentation == GameplayPresentation.GODOT_2D) "godot-2d" else "godot-3d"
                override val protocolVersion = if (unsupportedThreeD && presentation == GameplayPresentation.GODOT_3D) 2 else 1
                override val supportedGames = setOf(GameId("last-light"))
                override suspend fun open(launch: EngineLaunch): EmbeddedGameSession =
                    TestNativeSession(launch, preferences, nextCloseGate, nextDeliveryGate).also {
                        nextCloseGate = null
                        nextDeliveryGate = null
                        opened += it
                    }
            }
    }

    private class TestNativeSession(
        val launch: EngineLaunch,
        val preferences: PresentationPreferences,
        val closeGate: CompletableDeferred<Unit>?,
        val deliveryGate: CompletableDeferred<Unit>?,
    ) : LifecycleBoundEmbeddedGameSession {
        private val incoming = Channel<EngineEvent>(32)
        override val events = incoming.receiveAsFlow()
        val commands = mutableListOf<EngineCommand>()
        val attemptedCommands = mutableListOf<Pair<EngineCommand, Long>>()
        override var lifecycleGeneration = 1L
        var closeCalls = 0
        private var sequence = 0L

        fun ready() = emit(EngineEventBody.Ready)
        fun intent(intent: RendererIntent, revision: Long) = emit(EngineEventBody.PlayerIntent(revision, LastLightWireCodec.intentPayload(intent)))
        private fun emit(body: EngineEventBody) {
            assertTrue(incoming.trySend(EngineEvent(launch.presentationId, launch.protocolVersion, sequence++, body)).isSuccess)
        }
        fun latestView(): EngineCommand.ShowView = commands.filterIsInstance<EngineCommand.ShowView>().last()
        override suspend fun send(command: EngineCommand) {
            send(command, lifecycleGeneration)
        }
        override suspend fun send(command: EngineCommand, lifecycleGeneration: Long) {
            attemptedCommands += command to lifecycleGeneration
            deliveryGate?.await()
            if (lifecycleGeneration == this.lifecycleGeneration) commands += command
        }
        override suspend fun close() {
            closeCalls++
            closeGate?.await()
            incoming.close()
        }
    }

    private class PresentationTestServices : PlatformServices {
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
        override fun secureToken(): String = (token++).toString(16).padStart(64, '0')
        override fun gameRandom(): Random = Random(12)
        override fun copyText(value: String) = Unit
        override fun shareText(value: String) = Unit
        override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
    }
}
