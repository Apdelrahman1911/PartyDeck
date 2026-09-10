package dev.partydeck.app.controller

import dev.partydeck.core.LastLightEngine
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineFailure
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.godot.bridge.RendererIntent
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.CommandReceipt
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds
import kotlin.time.ExperimentalTime
import kotlin.time.TestTimeSource
import kotlin.time.TimeSource

@OptIn(ExperimentalCoroutinesApi::class, ExperimentalTime::class)
class EmbeddedPresentationReviewTest {
    @Test
    fun modalSelectionWaitsForForegroundAndOpensEachModeOnceWithCurrentConcealedControls() = runTest {
        for (mode in listOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)) {
            val fixture = PresentationReviewFixture(backgroundScope)
            try {
                val original = fixture.state.session
                fixture.state = fixture.state.copy(isForeground = false)
                fixture.coordinator.update()
                assertTrue(fixture.coordinator.select(mode))
                runCurrent()
                assertTrue(fixture.host.ports.isEmpty(), "A dismissed-dialog flag must not grant focus")
                assertEquals(GameplayPresentation.COMPOSE, fixture.state.presentation.selected)
                fixture.coordinator.update()
                assertTrue(fixture.host.ports.isEmpty())

                // The same session can publish a newer recipient view during the focus wait.
                fixture.authority.disconnectGuest()
                fixture.changeSession(fixture.authority.view())
                val newest = fixture.state.session
                assertEquals(original?.sessionId, newest?.sessionId)
                assertTrue(fixture.host.ports.isEmpty())
                fixture.state = fixture.state.copy(isForeground = true)
                fixture.coordinator.update()
                val port = fixture.host.ports.single()
                val initial = LastLightWireCodec.decodeViewPayload(port.launch.initialView)
                assertEquals(newest?.game, initial.game)
                assertEquals(newest?.selfPlayerId, initial.game.viewerId)
                assertFalse(initial.controls.canSendAction)
                assertTrue(port.commands.isEmpty())
                assertEquals(mode, fixture.state.presentation.selected)
                repeat(3) { fixture.coordinator.update() }
                assertEquals(1, fixture.host.ports.size)
                assertTrue(fixture.submissions.isEmpty())
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun newestExplicitChoiceSurvivesTheReplacedChoicesTimeout() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        try {
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            advanceTimeBy(3_000)
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            advanceTimeBy(2_001)
            runCurrent()
            assertTrue(fixture.host.ports.isEmpty())
            fixture.state = fixture.state.copy(isForeground = true)
            fixture.coordinator.update()
            assertEquals(1, fixture.host.ports.size)
            assertEquals(GameplayPresentation.GODOT_3D, fixture.state.presentation.selected)
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun selectionExpiryNeverLaunchesAndForegroundUpdatesDoNotRenewIt() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        try {
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            advanceTimeBy(4_000)
            fixture.coordinator.update()
            advanceTimeBy(1_001)
            runCurrent()
            assertTrue(fixture.host.ports.isEmpty())
            fixture.state = fixture.state.copy(isForeground = true)
            fixture.coordinator.update()
            assertTrue(fixture.host.ports.isEmpty(), "An expired choice must not launch on a later return")
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            assertEquals(1, fixture.host.ports.size)
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun monotonicDeadlineRejectsFocusEvenBeforeTheTimeoutCoroutineCanRun() = runTest {
        val clock = TestTimeSource()
        val fixture = PresentationReviewFixture(backgroundScope, clock)
        try {
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            clock += 5.seconds
            // Leave scheduler time unchanged: focus may be dispatched before an overdue timer.
            fixture.state = fixture.state.copy(isForeground = true)
            fixture.coordinator.update()
            assertTrue(fixture.host.ports.isEmpty())
            runCurrent()
            assertTrue(fixture.host.ports.isEmpty())
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun aPendingChoiceCannotSurviveSessionRoutePrivacyPreferenceOrOwnerInvalidation() = runTest {
        val invalidations: List<Pair<String, (PresentationReviewFixture) -> Unit>> = listOf(
            "background" to { it.state = it.state.copy(isBackgrounded = true) },
            "leave" to { it.state = it.state.copy(leaveConfirmationRequested = true) },
            "route" to { it.state = it.state.copy(screen = AppScreen.HOW_TO) },
            "session removed" to { it.state = it.state.copy(session = null) },
            "session generation" to { it.generation++ },
            "session ID" to { it.state = it.state.copy(session = it.state.session?.copy(sessionId = "replacement-session")) },
            "recipient" to { it.state = it.state.copy(session = it.authority.view(it.authority.guests.first())) },
            "game phase" to { it.state = it.state.copy(session = it.state.session?.copy(phase = SessionPhase.LOBBY, game = null)) },
            "connection" to { it.state = it.state.copy(connection = it.state.connection.copy(status = ConnectionStatus.DISCONNECTED)) },
            "text scale" to { it.state = it.state.copy(presentationTextScale = 2.0) },
            "motion" to { it.state = it.state.copy(systemReduceMotion = true) },
            "owner pause or replacement" to { it.coordinator.setSelectionOwnerActive(false) },
            "Standard selected" to { assertTrue(it.coordinator.select(GameplayPresentation.COMPOSE)) },
        )
        for ((reason, invalidate) in invalidations) {
            val fixture = PresentationReviewFixture(backgroundScope)
            try {
                fixture.state = fixture.state.copy(isForeground = false)
                fixture.coordinator.update()
                val before = fixture.state
                val generation = fixture.generation
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D), reason)
                invalidate(fixture)
                fixture.coordinator.update()
                fixture.state = before.copy(isForeground = true)
                fixture.generation = generation
                fixture.coordinator.setSelectionOwnerActive(true)
                fixture.coordinator.update()
                runCurrent()
                assertTrue(fixture.host.ports.isEmpty(), reason)
                assertTrue(fixture.submissions.isEmpty(), reason)
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D), reason)
                assertEquals(1, fixture.host.ports.size, reason)
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun availabilityLossCancelsTheChoiceEvenIfTheModeReturnsBeforeFocus() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        try {
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            fixture.host.available.value = emptySet()
            runCurrent()
            fixture.host.available.value = setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)
            runCurrent()
            fixture.state = fixture.state.copy(isForeground = true)
            fixture.coordinator.update()
            assertTrue(fixture.host.ports.isEmpty())
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            assertEquals(1, fixture.host.ports.size)
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun inactiveOwnerRejectsNewChoicesAndReactivationDoesNotReplayAnOldOne() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        try {
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            fixture.coordinator.setSelectionOwnerActive(false)
            assertFalse(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            fixture.coordinator.setSelectionOwnerActive(true)
            fixture.state = fixture.state.copy(isForeground = true)
            fixture.coordinator.update()
            assertTrue(fixture.host.ports.isEmpty())
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun modeSwitchRequiresBothCloseCompletionAndForegroundInEitherOrder() = runTest {
        for (focusFirst in listOf(false, true)) {
            val fixture = PresentationReviewFixture(backgroundScope)
            val close = CompletableDeferred<Unit>()
            try {
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
                val first = fixture.host.ports.single()
                first.closeBarrier = close
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
                fixture.state = fixture.state.copy(isForeground = false)
                fixture.coordinator.update()
                runCurrent()
                if (focusFirst) {
                    fixture.state = fixture.state.copy(isForeground = true)
                    fixture.coordinator.update()
                    assertEquals(1, fixture.host.ports.size)
                    close.complete(Unit)
                    runCurrent()
                } else {
                    close.complete(Unit)
                    runCurrent()
                    assertEquals(1, fixture.host.ports.size)
                    fixture.state = fixture.state.copy(isForeground = true)
                    fixture.coordinator.update()
                }
                assertTrue(first.closed)
                assertEquals(2, fixture.host.ports.size)
                assertEquals(GameplayPresentation.GODOT_3D, fixture.state.presentation.selected)
                assertEquals(PresentationLifecycle.OPENING, fixture.state.presentation.lifecycle)
            } finally {
                close.complete(Unit)
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun reentrantForegroundPublicationCannotOpenUntilClosePublicationFinishes() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        val close = CompletableDeferred<Unit>()
        try {
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            fixture.host.ports.single().closeBarrier = close
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            fixture.state = fixture.state.copy(isForeground = false)
            fixture.coordinator.update()
            runCurrent()
            var foregroundPublications = 0
            fixture.onPublish = { presentation ->
                if (presentation.lifecycle == PresentationLifecycle.COMPOSE) {
                    foregroundPublications++
                    fixture.state = fixture.state.copy(isForeground = true)
                    fixture.coordinator.update()
                    assertEquals(1, fixture.host.ports.size, "Close publication must retain the old close gate")
                }
            }
            close.complete(Unit)
            runCurrent()
            assertEquals(1, foregroundPublications)
            assertEquals(2, fixture.host.ports.size)
            assertEquals(PresentationLifecycle.OPENING, fixture.state.presentation.lifecycle)
        } finally {
            fixture.onPublish = {}
            close.complete(Unit)
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun bothModesReceiveOnlyTheCurrentRecipientAndTheNewestViewAfterReady() = runTest {
        for (mode in listOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D)) {
            val fixture = PresentationReviewFixture(backgroundScope)
            try {
                val original = fixture.authority.view()
                fixture.state = fixture.state.copy(invitation = HostInvitation(fixture.authority.admissionSecret, "private invite"))
                assertTrue(fixture.coordinator.select(mode))
                val port = fixture.host.ports.single()
                val initial = LastLightWireCodec.decodeViewPayload(port.launch.initialView)
                assertEquals(original.game, initial.game)
                assertFalse(initial.controls.canSendAction, "An unready renderer was authorized to submit")
                assertTrue(initial.controls.isHost)
                assertTrue(initial.controls.canReturnToLobby)
                assertFalse(port.launch.initialView.document.contains(fixture.authority.admissionSecret))
                val otherCards = fixture.authority.guests.flatMap { assertNotNull(fixture.authority.view(it).game).yourHand }.map { it.id }
                assertTrue(initial.game.yourHand.none { it.id in otherCards })
                assertTrue(fixture.host.preferences.all { !it.soundEnabled }, "Renderer audio duplicated shell feedback")

                // Actual disconnect projection disables game actions despite the host owning the turn.
                fixture.authority.disconnectGuest()
                fixture.changeSession(fixture.authority.view())
                runCurrent()
                assertTrue(port.commands.isEmpty(), "A command was sent before Ready was accepted")
                port.ready()
                runCurrent()
                val delivered = port.commands.filterIsInstance<EngineCommand.ShowView>().single()
                val newest = LastLightWireCodec.decodeViewPayload(delivered.payload)
                assertEquals(fixture.state.session?.game, newest.game)
                assertFalse(newest.game.availableActions.canPlay, "Coordinator recomputed paused authority actions")
                assertFalse(newest.game.availableActions.canChallenge)
                assertEquals(EngineCommand.SetForeground(true), port.commands.last())
                assertEquals(PresentationLifecycle.ACTIVE, fixture.state.presentation.lifecycle)
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun recipientRoomGenerationAndMismatchedGameReplacementInvalidateTheOldLifetime() = runTest {
        for (replacement in listOf("recipient", "room", "generation", "mismatched-game")) {
            val fixture = PresentationReviewFixture(backgroundScope)
            try {
                assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
                val old = fixture.host.ports.single()
                old.ready()
                runCurrent()
                val revision = old.latestView().revision
                val previousCommands = old.commands.toList()
                val previousEpoch = fixture.state.privacyEpoch
                val next = when (replacement) {
                    "recipient" -> fixture.authority.view(fixture.authority.guests.first())
                    "room" -> PresentationReviewAuthority("replacement-room").view()
                    "generation" -> fixture.authority.view().also { fixture.generation++ }
                    else -> fixture.authority.view().copy(game = fixture.authority.view(fixture.authority.guests.first()).game)
                }
                fixture.changeSession(next)
                assertFalse(fixture.coordinator.owns(old.launch.presentationId))
                assertTrue(fixture.state.privacyEpoch > previousEpoch)
                old.intent(RendererIntent.ReturnToLobby, revision)
                runCurrent()
                assertTrue(old.closed)
                assertEquals(previousCommands, old.commands, "Replacement private data was delivered to the old native port")
                assertTrue(fixture.submissions.isEmpty())

                if (replacement == "mismatched-game") {
                    assertFalse(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
                    assertEquals(1, fixture.host.ports.size)
                } else {
                    assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
                    val current = fixture.host.ports.last()
                    assertTrue(current.launch.presentationId != old.launch.presentationId)
                    assertEquals(next.game, LastLightWireCodec.decodeViewPayload(current.launch.initialView).game)
                    current.ready()
                    runCurrent()
                    old.event(EngineEventBody.ExitRequested)
                    runCurrent()
                    assertTrue(fixture.coordinator.owns(current.launch.presentationId))
                    assertFalse(current.closed)
                    assertEquals(0, fixture.exitRequests)
                }
            } finally {
                fixture.coordinator.close()
                runCurrent()
            }
        }
    }

    @Test
    fun aLateNativeOpenIsClosedAndAQueuedModeSwitchCannotCrossSessionGeneration() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        val release = CompletableDeferred<Unit>()
        fixture.host.openBarrier = release
        try {
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            val old = fixture.host.ports.single()
            fixture.changeSession(PresentationReviewAuthority("late-open-replacement").view())
            assertFalse(fixture.coordinator.owns(old.launch.presentationId))
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            fixture.generation++
            fixture.coordinator.update()
            release.complete(Unit)
            runCurrent()
            assertTrue(old.closed, "A cancelled open leaked the acquired native session")
            assertTrue(old.commands.isEmpty())
            assertEquals(1, fixture.host.ports.size, "An old queued choice reopened after session replacement")
            assertEquals(PresentationLifecycle.COMPOSE, fixture.state.presentation.lifecycle)
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_3D))
            val current = fixture.host.ports.last()
            assertEquals(fixture.state.session?.game, LastLightWireCodec.decodeViewPayload(current.launch.initialView).game)
        } finally {
            release.complete(Unit)
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun rejectedAndAcceptedLobbyRequestsKeepTheGameUntilTheAuthorityLobbyProjection() = runTest {
        val fixture = PresentationReviewFixture(backgroundScope)
        val receipts = mutableListOf<CommandReceipt>()
        fixture.onSubmission = {
            receipts += fixture.authority.submit(it.intent, expectedRevision = it.expectedRevision)
            true // The shell accepted submission; authority acceptance is a separate receipt.
        }
        try {
            assertTrue(fixture.coordinator.select(GameplayPresentation.GODOT_2D))
            val port = fixture.host.ports.single()
            port.ready()
            runCurrent()
            val capturedSessionRevision = assertNotNull(fixture.state.session).revision
            fixture.authority.disconnectGuest() // The new authority snapshot has not reached the shell yet.
            port.intent(RendererIntent.ReturnToLobby, port.latestView().revision)
            runCurrent()
            assertEquals(capturedSessionRevision, fixture.submissions.single().expectedRevision)
            assertEquals(SessionError.STALE_REVISION, receipts.single().error)
            assertFalse(port.closed)
            assertTrue(fixture.coordinator.owns(port.launch.presentationId))
            assertEquals(SessionPhase.GAME, fixture.state.session?.phase)

            fixture.changeSession(fixture.authority.view())
            runCurrent()
            port.intent(RendererIntent.ReturnToLobby, port.latestView().revision)
            runCurrent()
            assertTrue(receipts.last().accepted)
            assertFalse(port.closed, "A receipt was mistaken for authoritative lobby delivery")
            assertEquals(SessionPhase.GAME, fixture.state.session?.phase)
            fixture.changeSession(fixture.authority.view())
            runCurrent()
            assertEquals(SessionPhase.LOBBY, fixture.state.session?.phase)
            assertTrue(port.closed)
            assertEquals(GameplayPresentation.COMPOSE, fixture.state.presentation.selected)
        } finally {
            fixture.coordinator.close()
            runCurrent()
        }
    }

    @Test
    fun controllerReservesPendingBeforeTheNextEventAndReconcilesStaleOrReplayedInput() = runTest {
        val host = PresentationReviewHost()
        val controller = PartyDeckController(PresentationReviewServices(), PresentationReviewNoNetwork, backgroundScope, host)
        try {
            controller.startPractice()
            runCurrent()
            val before = assertNotNull(controller.state.value.session)
            val game = assertNotNull(before.game)
            val hand = game.yourHand
            assertTrue(game.availableActions.canPlay)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            val port = host.ports.single()
            port.ready()
            runCurrent()
            val renderedRevision = port.latestView().revision
            val beforeCommands = port.commands.size
            val first = port.intent(RendererIntent.Play(listOf(hand.first().id)), renderedRevision)
            port.intent(RendererIntent.Play(listOf(hand[1].id)), renderedRevision)
            runCurrent()
            val after = assertNotNull(controller.state.value.session)
            assertEquals(before.revision + 1, after.revision, "Two queued inputs mutated the game twice")
            assertEquals(hand.size - 1, after.game?.yourHand?.size)
            assertNull(controller.state.value.pendingAction)
            assertNull(controller.state.value.problem)
            assertTrue(port.commands.drop(beforeCommands).filterIsInstance<EngineCommand.ShowView>().any {
                !LastLightWireCodec.decodeViewPayload(it.payload).controls.canSendAction
            }, "A fleeting pending state was never projected to the renderer")

            port.emit(first)
            runCurrent()
            assertEquals(after, controller.state.value.session)
            val previousPresentationRevision = port.latestView().revision
            port.intent(RendererIntent.Play(listOf(hand[1].id)), renderedRevision)
            runCurrent()
            assertEquals(after, controller.state.value.session)
            assertTrue(port.latestView().revision > previousPresentationRevision, "Stale input did not clear native pending through a fresh projection")
            assertNull(controller.state.value.problem)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun aReservedCommandCompletesInComposeWithoutTargetingTheClosedNativeLifetime() = runTest {
        val host = PresentationReviewHost()
        val controller = PartyDeckController(PresentationReviewServices(), PresentationReviewNoNetwork, backgroundScope, host)
        var switched = false
        val watcher = backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
            controller.state.collect {
                if (it.pendingAction == PendingAction.PLAY_CARDS && !switched) {
                    switched = true
                    controller.useComposePresentation()
                }
            }
        }
        try {
            controller.startPractice()
            runCurrent()
            val before = assertNotNull(controller.state.value.session)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            val port = host.ports.single()
            port.ready()
            runCurrent()
            val previousEpoch = controller.state.value.privacyEpoch
            port.intent(RendererIntent.Play(listOf(assertNotNull(before.game).yourHand.first().id)), port.latestView().revision)
            runCurrent()
            assertTrue(switched)
            assertTrue(port.closed)
            assertEquals(before.revision + 1, controller.state.value.session?.revision)
            assertEquals(before.sessionId, controller.state.value.session?.sessionId)
            assertEquals(GameplayPresentation.COMPOSE, controller.state.value.presentation.selected)
            assertTrue(controller.state.value.privacyEpoch > previousEpoch)
            assertNull(controller.state.value.pendingAction)
            assertNull(controller.state.value.problem)
            val closedCommands = port.commands.toList()
            port.event(EngineEventBody.ExitRequested)
            runCurrent()
            assertEquals(closedCommands, port.commands)
            assertFalse(controller.state.value.leaveConfirmationRequested)
        } finally {
            watcher.cancel()
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }

    @Test
    fun nativeExitBeforeReadyAndRendererFailurePreserveTheSessionWithAConcealedFallback() = runTest {
        val host = PresentationReviewHost()
        val controller = PartyDeckController(PresentationReviewServices(), PresentationReviewNoNetwork, backgroundScope, host)
        try {
            controller.startPractice()
            runCurrent()
            val original = assertNotNull(controller.state.value.session)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            val first = host.ports.single()
            val openingEpoch = controller.state.value.privacyEpoch
            controller.requestPresentationExit(first.launch.presentationId)
            runCurrent()
            assertTrue(first.closed)
            assertEquals(original, controller.state.value.session)
            assertTrue(controller.state.value.leaveConfirmationRequested)
            assertTrue(controller.state.value.privacyEpoch > openingEpoch)
            controller.dismissLeaveConfirmation()
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            val second = host.ports.last()
            second.ready()
            runCurrent()
            val activeEpoch = controller.state.value.privacyEpoch
            second.event(EngineEventBody.Failed(EngineFailure.RENDERER_LOST))
            runCurrent()
            assertTrue(second.closed)
            assertEquals(original, controller.state.value.session)
            assertEquals(ConnectionStatus.CONNECTED, controller.state.value.connection.status)
            assertFalse(controller.state.value.leaveConfirmationRequested)
            assertEquals(PresentationFallbackReason.RENDERER_LOST, controller.state.value.presentation.fallbackReason)
            assertTrue(controller.state.value.privacyEpoch > activeEpoch)
        } finally {
            controller.close()
            runCurrent()
            controller.awaitClosed()
        }
    }
}

private class PresentationReviewFixture(scope: CoroutineScope, selectionTimeSource: TimeSource = TimeSource.Monotonic) {
    val authority = PresentationReviewAuthority()
    val host = PresentationReviewHost()
    var state = AppUiState(
        screen = AppScreen.SESSION,
        session = authority.view(),
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.LAN_HOST),
    )
    var generation = 1L
    private var nextPresentation = 1L
    var exitRequests = 0
        private set
    val submissions = mutableListOf<PresentationSubmission>()
    var onSubmission: (PresentationSubmission) -> Boolean = { false }
    var onPublish: (GameplayPresentationState) -> Unit = {}
    val coordinator = EmbeddedPresentationCoordinator(
        scope, host, { state }, { generation }, { "review-presentation-${nextPresentation++}" },
        { presentation, conceal ->
            state = state.copy(presentation = presentation, privacyEpoch = state.privacyEpoch + if (conceal) 1 else 0)
            onPublish(presentation)
        },
        { submissions += it; onSubmission(it) },
        { exitRequests++ },
        selectionTimeSource,
    ).also { it.start() }

    fun changeSession(next: SessionView) {
        state = state.copy(session = next)
        coordinator.update()
    }
}

private object PresentationReviewNoNetwork : LanTransportFactory {
    override fun create(): LanTransport = error("Presentation practice must not create a LAN transport")
}

private class PresentationReviewServices : PlatformServices {
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
    override fun gameRandom(): Random = Random(2)
    override fun secureToken(): String = (token++).toString(16).padStart(64, '0')
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = Unit
}

/** Review fixtures use actual authority projections; the test port only controls native timing. */
private class PresentationReviewAuthority(room: String = "presentation-review-room") {
    val admissionSecret = "e".repeat(64)
    val host = SessionPeer("review-host")
    val guests = (1..3).map { SessionPeer("review-guest-$it") }
    private var token = 1L
    private val nextCommands = mutableMapOf<String, Long>()
    private val authority = HostAuthority(
        HostSessionConfig(room, admissionSecret, "Host", host), LastLightEngine(Random(2)),
    ) { (token++).toString(16).padStart(64, '0') }

    init {
        guests.forEachIndexed { index, peer ->
            authority.handle(peer, ClientMessage.Join(room, admissionSecret, "Guest ${index + 1}"))
        }
        guests.forEach { assertTrue(submit(ClientIntent.SetReady(true), it).accepted) }
        assertTrue(submit(ClientIntent.StartGame).accepted)
    }

    fun view(peer: SessionPeer = host): SessionView = assertNotNull(authority.viewFor(peer))

    fun submit(
        intent: ClientIntent,
        peer: SessionPeer = host,
        expectedRevision: Long = view(peer).revision,
    ): CommandReceipt {
        val commandId = nextCommands.getOrElse(peer.connectionId) { 1L }
        nextCommands[peer.connectionId] = commandId + 1
        return authority.handle(peer, ClientMessage.Command(authority.sessionId, commandId, expectedRevision, intent))
            .deliveries.filter { it.connectionId == peer.connectionId }
            .mapNotNull { (it.message as? ServerMessage.Receipt)?.receipt }.single()
    }

    fun disconnectGuest() {
        authority.disconnect(guests.first())
    }
}

/** No renderer is implemented here; this bounded test port records the common host contract. */
private class PresentationReviewHost : EmbeddedPresentationHost {
    override val available = MutableStateFlow(setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D))
    val preferences = mutableListOf<PresentationPreferences>()
    val ports = mutableListOf<PresentationReviewPort>()
    var openBarrier: CompletableDeferred<Unit>? = null

    override fun createFactory(
        presentation: GameplayPresentation,
        preferences: PresentationPreferences,
    ): EmbeddedGameFactory {
        this.preferences += preferences
        return object : EmbeddedGameFactory {
            override val engineId = when (presentation) {
                GameplayPresentation.GODOT_2D -> "godot-2d"
                GameplayPresentation.GODOT_3D -> "godot-3d"
                GameplayPresentation.COMPOSE -> error("Compose does not open an engine")
            }
            override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
            override val supportedGames = setOf(GameId("last-light"))
            override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
                val port = PresentationReviewPort(launch)
                ports += port
                openBarrier?.let { withContext(NonCancellable) { it.await() } }
                return port
            }
        }
    }
}

private class PresentationReviewPort(val launch: EngineLaunch) : EmbeddedGameSession {
    private val eventQueue = Channel<EngineEvent>(32)
    override val events = eventQueue.receiveAsFlow()
    val commands = mutableListOf<EngineCommand>()
    var closed = false
        private set
    var closeBarrier: CompletableDeferred<Unit>? = null
    var sendBarrier: CompletableDeferred<Unit>? = null
    private var sequence = 0L

    override suspend fun send(command: EngineCommand) {
        check(!closed) { "A command targeted a closed presentation" }
        sendBarrier?.await()
        commands += command
    }

    override suspend fun close() {
        closed = true
        closeBarrier?.await()
    }

    fun ready() = event(EngineEventBody.Ready)

    fun intent(intent: RendererIntent, revision: Long): EngineEvent = event(
        EngineEventBody.PlayerIntent(revision, LastLightWireCodec.intentPayload(intent)),
    )

    fun event(body: EngineEventBody): EngineEvent = EngineEvent(
        launch.presentationId, ENGINE_BRIDGE_PROTOCOL_VERSION, sequence++, body,
    ).also(::emit)

    fun emit(event: EngineEvent) {
        check(eventQueue.trySend(event).isSuccess)
    }

    fun latestView(): EngineCommand.ShowView = commands.filterIsInstance<EngineCommand.ShowView>().last()
}
