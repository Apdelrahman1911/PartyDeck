package dev.partydeck.godot.bridge

import dev.partydeck.core.GamePhase
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineFailure
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class IosQualificationFacadeTest {
    @Test
    fun bothModesDelegateEveryFullMatchCommandToIndependentRealDrivers() {
        for (mode in PresentationMode.entries) {
            val id = "ios-reference-${mode.wireName}"
            val facade = reference(id, mode)
            val direct = QualificationAuthorityDriver(Random(IOS_QUALIFICATION_REFERENCE_SEED), id)
            assertEquals(direct.launchDocument(mode, preferences), facade.launchDocument)
            assertEquals(IosQualificationRandomness.REFERENCE_SEED_2, facade.randomness)
            assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, facade.status().lifecycle)
            val ready = event(id, 0, EngineEventBody.Ready)
            assertEquals(direct.handleEvent(ready).documents, facade.handleRendererEvent(ready).commands)
            var sequence = 0L
            var operations = 0
            var opponentActions = 0
            while (direct.view.phase != GamePhase.FINISHED) {
                assertTrue(++operations <= 300, "Reference authority did not finish")
                val view = direct.view
                if (view.phase == GamePhase.PLAYING && view.turnPlayerId != direct.viewerId) {
                    val expected = direct.advanceOtherPlayers()
                    val actual = facade.advanceOtherPlayers()
                    assertTrue(expected.isNotEmpty())
                    assertTrue(expected.all { it.authorityRejection == null })
                    opponentActions += expected.size
                    assertEquals(IosQualificationOutcome.ACCEPTED, actual.outcome)
                    assertEquals(expected.flatMap { it.documents }, actual.commands)
                    assertEquals(opponentActions, actual.status.acceptedOpponentActions)
                } else {
                    val requested = when {
                        view.phase == GamePhase.ROUND_ENDED -> RendererIntent.AdvanceRound
                        view.availableActions.canChallenge -> RendererIntent.Challenge
                        view.availableActions.canPlay -> RendererIntent.Play(listOf(view.yourHand.first().id))
                        else -> error("Authority exposed no projected action")
                    }
                    val document = intent(direct, ++sequence, requested)
                    val expected = direct.handleEvent(document)
                    val actual = facade.handleRendererEvent(document)
                    assertIs<BridgeDecision.Accepted>(expected.decision)
                    assertEquals(null, expected.authorityRejection)
                    assertEquals(IosQualificationOutcome.ACCEPTED, actual.outcome)
                    assertEquals("", actual.reasonCode)
                    assertEquals(expected.documents, actual.commands)
                }
                assertEquals(direct.revision.toString(), facade.status().revision)
                assertEquals(direct.view.phase.name, facade.status().phase.name)
                assertEquals(direct.view.roundNumber, facade.status().roundNumber)
            }
            val finished = facade.status()
            assertEquals(IosQualificationPhase.FINISHED, finished.phase)
            assertEquals(IosQualificationLifecycle.READY, finished.lifecycle)
            assertEquals(direct.view.winnerId, finished.winnerId)
            assertEquals(14, finished.roundNumber)
            assertEquals(2, finished.acceptedViewerPlays)
            assertEquals(2, finished.acceptedViewerChallenges)
            assertEquals(13, finished.roundsAdvanced)
            assertEquals(18, finished.acceptedRendererEvents)
            val lobby = intent(direct, ++sequence, RendererIntent.ReturnToLobby)
            assertEquals(BridgeDecision.Accepted(BridgeInput.ReturnToLobby), direct.handleEvent(lobby).decision)
            val returned = facade.handleRendererEvent(lobby)
            assertEquals(IosQualificationOutcome.RETURN_TO_LOBBY, returned.outcome)
            assertEquals(listOf(direct.close()), returned.commands)
            assertEquals(IosQualificationLifecycle.CLOSED, returned.status.lifecycle)
            assertEquals("", facade.launchDocument)
        }
    }

    @Test
    fun malformedReplayedStaleAndBackgroundInputRemainDriverRejectionsUntilExplicitRefresh() {
        val direct = QualificationAuthorityDriver(Random(IOS_QUALIFICATION_REFERENCE_SEED), "ios-rejections")
        val facade = reference(direct.presentationId)
        val ready = event(direct.presentationId, 0, EngineEventBody.Ready)
        direct.handleEvent(ready)
        facade.handleRendererEvent(ready)
        assertRejectedByBoth(direct, facade, "not JSON", BridgeRejection.INVALID_DOCUMENT)
        assertEquals(listOf(direct.setForeground(false)), facade.setForeground(false).commands)
        assertFalse(facade.status().foreground)
        val play = RendererIntent.Play(listOf(direct.view.yourHand.first().id))
        assertRejectedByBoth(direct, facade, intent(direct, 1, play), BridgeRejection.NOT_FOREGROUND)
        assertTrue(direct.advanceOtherPlayers().isEmpty())
        val backgroundAdvance = facade.advanceOtherPlayers()
        assertEquals(IosQualificationOutcome.NO_CHANGE, backgroundAdvance.outcome)
        assertTrue(backgroundAdvance.commands.isEmpty())
        assertEquals("0", backgroundAdvance.status.revision)
        assertEquals(listOf(direct.setForeground(true)), facade.setForeground(true).commands)
        val refreshed = facade.refreshView()
        assertEquals(IosQualificationOutcome.VIEW_REFRESHED, refreshed.outcome)
        assertEquals(listOf(direct.refreshView()), refreshed.commands)
        assertEquals("1", refreshed.status.revision)
        val stale = event(direct.presentationId, 2, EngineEventBody.PlayerIntent(
            0, LastLightWireCodec.intentPayload(play),
        ))
        assertRejectedByBoth(direct, facade, stale, BridgeRejection.STALE_REVISION)
        assertRejectedByBoth(direct, facade, stale, BridgeRejection.REPLAYED_EVENT)
        val current = intent(direct, 3, play)
        val expected = direct.handleEvent(current)
        val actual = facade.handleRendererEvent(current)
        assertEquals(IosQualificationOutcome.ACCEPTED, actual.outcome)
        assertEquals(expected.documents, actual.commands)
        assertEquals(1, actual.status.acceptedViewerPlays)
        assertEquals(2, actual.status.acceptedRendererEvents)
    }

    @Test
    fun exitAndRendererFailureReturnTerminalCloseWithoutRetainingLaunchData() {
        val terminalEvents = listOf(
            Triple(EngineEventBody.ExitRequested, IosQualificationOutcome.EXIT_REQUESTED, ""),
            Triple(EngineEventBody.Failed(EngineFailure.RENDERER_LOST), IosQualificationOutcome.RENDERER_FAILED, "RENDERER_LOST"),
        )
        for ((body, outcome, reason) in terminalEvents) {
            val id = "ios-terminal-${outcome.name}"
            val direct = QualificationAuthorityDriver(Random(IOS_QUALIFICATION_REFERENCE_SEED), id)
            val facade = reference(id)
            val ready = event(id, 0, EngineEventBody.Ready)
            direct.handleEvent(ready)
            facade.handleRendererEvent(ready)
            val terminal = event(id, 1, body)
            assertIs<BridgeDecision.Accepted>(direct.handleEvent(terminal).decision)
            val result = facade.handleRendererEvent(terminal)
            assertEquals(outcome, result.outcome)
            assertEquals(reason, result.reasonCode)
            assertEquals(listOf(direct.close()), result.commands)
            assertEquals(IosQualificationLifecycle.CLOSED, result.status.lifecycle)
            assertFalse(result.status.foreground)
            assertEquals(2, result.status.acceptedRendererEvents)
            assertEquals("", facade.launchDocument)
            assertRejectedByBoth(direct, facade, event(id, 2, EngineEventBody.Ready), BridgeRejection.CLOSED)
        }
    }

    @Test
    fun closeIsIdempotentAndAReplacementGetsAnIndependentIdentityAndGate() {
        val facade = reference("ios-old")
        val closed = facade.close()
        assertEquals(IosQualificationOutcome.CLOSED, closed.outcome)
        assertEquals(IosQualificationLifecycle.CLOSED, closed.status.lifecycle)
        assertEquals(closed.commands, facade.close().commands)
        assertEquals("", facade.launchDocument)
        for (result in listOf(facade.refreshView(), facade.advanceOtherPlayers(), facade.setForeground(true))) {
            assertEquals(IosQualificationOutcome.REJECTED, result.outcome)
            assertEquals("CLOSED", result.reasonCode)
            assertTrue(result.commands.isEmpty())
            assertEquals(IosQualificationLifecycle.CLOSED, result.status.lifecycle)
        }
        val replacement = reference("ios-new")
        assertTrue(replacement.launchDocument.contains("\"presentationId\":\"ios-new\""))
        assertEquals("0", replacement.status().revision)
        assertEquals(0, replacement.status().acceptedRendererEvents)
        assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, replacement.status().lifecycle)
        val oldReady = replacement.handleRendererEvent(event("ios-old", 0, EngineEventBody.Ready))
        assertEquals(IosQualificationOutcome.REJECTED, oldReady.outcome)
        assertEquals("WRONG_PRESENTATION", oldReady.reasonCode)
        val ready = replacement.handleRendererEvent(event("ios-new", 0, EngineEventBody.Ready))
        assertEquals(IosQualificationOutcome.ACCEPTED, ready.outcome)
        assertEquals(IosQualificationLifecycle.READY, ready.status.lifecycle)
        assertEquals(1, ready.status.acceptedRendererEvents)
    }

    private fun assertRejectedByBoth(
        direct: QualificationAuthorityDriver,
        facade: IosQualificationAuthority,
        document: String,
        reason: BridgeRejection,
    ) {
        val priorView = direct.view
        val priorStatus = facade.status()
        assertEquals(BridgeDecision.Rejected(reason), direct.handleEvent(document).decision)
        val result = facade.handleRendererEvent(document)
        assertEquals(IosQualificationOutcome.REJECTED, result.outcome)
        assertEquals(reason.name, result.reasonCode)
        assertTrue(result.commands.isEmpty())
        assertEquals(priorView, direct.view)
        assertEquals(priorStatus.revision, result.status.revision)
        assertEquals(priorStatus.acceptedRendererEvents, result.status.acceptedRendererEvents)
        assertEquals(priorStatus.acceptedViewerPlays, result.status.acceptedViewerPlays)
        assertEquals(priorStatus.acceptedViewerChallenges, result.status.acceptedViewerChallenges)
        assertEquals(direct.revision.toString(), result.status.revision)
    }

    private fun reference(id: String, mode: PresentationMode = PresentationMode.TWO_D) = IosQualificationAuthority(
        Random(IOS_QUALIFICATION_REFERENCE_SEED), id, mode, preferences, IosQualificationRandomness.REFERENCE_SEED_2,
    )

    private fun intent(driver: QualificationAuthorityDriver, sequence: Long, intent: RendererIntent) = event(
        driver.presentationId, sequence, EngineEventBody.PlayerIntent(driver.revision, LastLightWireCodec.intentPayload(intent)),
    )

    private fun event(id: String, sequence: Long, body: EngineEventBody) =
        LastLightWireCodec.encodeEvent(EngineEvent(id, 1, sequence, body))

    private val preferences = PresentationPreferences(reduceMotion = true, soundEnabled = false, textScale = 1.0)
}
