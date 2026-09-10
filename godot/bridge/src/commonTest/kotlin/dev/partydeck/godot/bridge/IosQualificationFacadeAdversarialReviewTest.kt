package dev.partydeck.godot.bridge

import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineFailure
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Independent native-preparation cases, separate from the owner's full-match tests. */
class IosQualificationFacadeAdversarialReviewTest {
    @Test
    fun onlyCurrentBoundFailureCanTerminateBeforeReady() {
        val id = "ios-review-initialization"
        val facade = reference(id)
        val initialLaunch = facade.launchDocument
        val initialStatus = facade.status()
        val failed = EngineEventBody.Failed(EngineFailure.INITIALIZATION_FAILED)
        val rejectedInputs = listOf(
            "{private-do-not-echo}" to BridgeRejection.INVALID_DOCUMENT,
            event("foreign-ios-presentation", 0, failed) to BridgeRejection.WRONG_PRESENTATION,
            event(id, 0, failed, protocol = 2) to BridgeRejection.UNSUPPORTED_PROTOCOL,
            event(id, 0, EngineEventBody.ExitRequested) to BridgeRejection.NOT_READY,
            intent(id, 0, 0) to BridgeRejection.NOT_READY,
        )
        for ((document, expected) in rejectedInputs) {
            val result = facade.handleRendererEvent(document)
            assertRejected(result, expected)
            assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, result.status.lifecycle)
            assertEquals("0", result.status.revision)
            assertEquals(0, result.status.acceptedRendererEvents)
            assertEquals(initialLaunch, facade.launchDocument)
        }

        // Rejected inputs have not consumed this sequence or authorized a terminal action.
        val terminal = facade.handleRendererEvent(event(id, 0, failed))
        assertEquals(IosQualificationOutcome.RENDERER_FAILED, terminal.outcome)
        assertEquals("INITIALIZATION_FAILED", terminal.reasonCode)
        assertEquals(listOf(LastLightWireCodec.encodeClose(id)), terminal.commands)
        assertEquals(IosQualificationLifecycle.CLOSED, terminal.status.lifecycle)
        assertEquals("0", terminal.status.revision)
        assertEquals(1, terminal.status.acceptedRendererEvents)
        assertEquals(0, terminal.status.acceptedViewerPlays)
        assertEquals(0, terminal.status.acceptedViewerChallenges)
        assertEquals(0, terminal.status.acceptedOpponentActions)
        assertFalse(terminal.status.foreground)
        assertEquals("", facade.launchDocument)
        assertRejected(facade.handleRendererEvent(event(id, 1, EngineEventBody.Ready)), BridgeRejection.CLOSED)
        assertEquals(terminal.commands, facade.close().commands)

        // A previously delivered receipt remains a snapshot for the serialized native owner.
        assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, initialStatus.lifecycle)
        assertEquals(0, initialStatus.acceptedRendererEvents)
        assertTrue(initialStatus.foreground)
    }

    @Test
    fun backgroundBeforeReadyKeepsReadinessForegroundAndRevisionIndependent() {
        val id = "ios-review-background-preparation"
        val facade = reference(id)
        val initial = Json.parseToJsonElement(facade.launchDocument).jsonObject
        val paused = facade.setForeground(false)
        assertEquals(IosQualificationOutcome.FOREGROUND_CHANGED, paused.outcome)
        assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, paused.status.lifecycle)
        assertFalse(paused.status.foreground)
        assertEquals("0", paused.status.revision)

        val refreshed = facade.refreshView()
        val view = Json.parseToJsonElement(refreshed.commands.single()).jsonObject
        assertEquals(initial.getValue("payload"), view.getValue("payload"))
        assertEquals(IosQualificationOutcome.VIEW_REFRESHED, refreshed.outcome)
        assertEquals("1", refreshed.status.revision)
        assertFalse(refreshed.status.foreground)
        assertEquals(0, refreshed.status.acceptedRendererEvents)
        val opponents = facade.advanceOtherPlayers()
        assertEquals(IosQualificationOutcome.NO_CHANGE, opponents.outcome)
        assertTrue(opponents.commands.isEmpty())
        assertEquals(0, opponents.status.acceptedOpponentActions)

        val ready = facade.handleRendererEvent(event(id, 0, EngineEventBody.Ready))
        assertEquals(IosQualificationOutcome.ACCEPTED, ready.outcome)
        assertTrue(ready.commands.isEmpty())
        assertEquals(IosQualificationLifecycle.READY, ready.status.lifecycle)
        assertFalse(ready.status.foreground)
        assertEquals("1", ready.status.revision)
        assertEquals(1, ready.status.acceptedRendererEvents)
        assertRejected(facade.handleRendererEvent(event(id, 1, EngineEventBody.Ready)), BridgeRejection.ALREADY_READY)
        assertRejected(facade.handleRendererEvent(intent(id, 1, 1)), BridgeRejection.NOT_FOREGROUND)
        val resumed = facade.setForeground(true)
        assertTrue(resumed.status.foreground)
        assertEquals(IosQualificationLifecycle.READY, resumed.status.lifecycle)
        assertEquals("1", resumed.status.revision)
        assertEquals(1, resumed.status.acceptedRendererEvents)
        assertRejected(facade.handleRendererEvent(intent(id, 1, 1)), BridgeRejection.REPLAYED_EVENT)
        assertEquals(0, facade.status().acceptedViewerChallenges)
        assertEquals(IosQualificationLifecycle.WAITING_FOR_READY, paused.status.lifecycle)
        assertFalse(paused.status.foreground)
    }

    private fun assertRejected(result: IosQualificationResult, reason: BridgeRejection) {
        assertEquals(IosQualificationOutcome.REJECTED, result.outcome)
        assertEquals(reason.name, result.reasonCode)
        assertTrue(result.commands.isEmpty())
    }

    private fun reference(id: String) = IosQualificationAuthority(
        Random(IOS_QUALIFICATION_REFERENCE_SEED), id, PresentationMode.TWO_D,
        PresentationPreferences(reduceMotion = true, soundEnabled = false, textScale = 1.0),
        IosQualificationRandomness.REFERENCE_SEED_2,
    )

    private fun intent(id: String, sequence: Long, revision: Long) = event(
        id, sequence, EngineEventBody.PlayerIntent(revision, LastLightWireCodec.intentPayload(RendererIntent.Challenge)),
    )

    private fun event(id: String, sequence: Long, body: EngineEventBody, protocol: Int = 1) =
        LastLightWireCodec.encodeEvent(EngineEvent(id, protocol, sequence, body))
}
