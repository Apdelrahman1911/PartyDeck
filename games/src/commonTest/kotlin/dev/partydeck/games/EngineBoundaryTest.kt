package dev.partydeck.games

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class EngineBoundaryTest {
    private val payload = EnginePayload("test-view-v1", "{}")
    private val launch = EngineLaunch(GameId("test-game"), "presentation-1", payload, 0)

    @Test
    fun payloadLimitCountsUtf8BytesAndRejectsOversizedDocuments() {
        EnginePayload("test-view-v1", "a".repeat(MAX_ENGINE_PAYLOAD_BYTES))
        EnginePayload("test-view-v1", "é".repeat(MAX_ENGINE_PAYLOAD_BYTES / 2))
        assertFailsWith<IllegalArgumentException> {
            EnginePayload("test-view-v1", "a".repeat(MAX_ENGINE_PAYLOAD_BYTES + 1))
        }
        assertFailsWith<IllegalArgumentException> {
            EnginePayload("test-view-v1", "é".repeat(MAX_ENGINE_PAYLOAD_BYTES / 2 + 1))
        }
    }

    @Test
    fun wrongPresentationAndProtocolCannotAdvanceTheEventStream() {
        assertFailsWith<IllegalArgumentException> { launch.copy(protocolVersion = 2) }
        val gate = EngineEventGate(launch)
        assertRejected(EngineEventRejection.WRONG_PRESENTATION, gate.accept(event(0).copy(presentationId = "old")))
        assertRejected(EngineEventRejection.UNSUPPORTED_PROTOCOL, gate.accept(event(0).copy(protocolVersion = 2)))
        assertIs<EngineEventDecision.Accepted>(gate.accept(event(0)))
    }

    @Test
    fun intentsRequireReadinessAndReplaysCannotRepeatActions() {
        val gate = EngineEventGate(launch)
        val intent = EngineEventBody.PlayerIntent(0, payload)
        assertRejected(EngineEventRejection.NOT_READY, gate.accept(event(0, intent)))
        assertIs<EngineEventDecision.Accepted>(gate.accept(event(0)))
        assertRejected(EngineEventRejection.ALREADY_READY, gate.accept(event(1)))
        assertIs<EngineEventDecision.Accepted>(gate.accept(event(1, intent)))
        assertRejected(EngineEventRejection.REPLAYED_EVENT, gate.accept(event(1, intent)))
        assertRejected(EngineEventRejection.REPLAYED_EVENT, gate.accept(event(0, intent)))
        assertRejected(EngineEventRejection.REPLAYED_EVENT, gate.accept(event(-1, intent)))
    }

    @Test
    fun closedOrFailedPresentationsCannotEmitFurtherActions() {
        val gate = EngineEventGate(launch)
        assertIs<EngineEventDecision.Accepted>(gate.accept(event(0)))
        assertIs<EngineEventDecision.Accepted>(gate.accept(event(1, EngineEventBody.ExitRequested)))
        assertRejected(EngineEventRejection.CLOSED, gate.accept(event(2, EngineEventBody.PlayerIntent(0, payload))))

        val failed = EngineEventGate(launch)
        assertIs<EngineEventDecision.Accepted>(failed.accept(event(0, EngineEventBody.Failed(EngineFailure.INITIALIZATION_FAILED))))
        assertRejected(EngineEventRejection.CLOSED, failed.accept(event(1)))

        val cancelled = EngineEventGate(launch)
        cancelled.close()
        cancelled.close()
        assertRejected(EngineEventRejection.CLOSED, cancelled.accept(event(0)))
    }

    private fun event(sequence: Long, body: EngineEventBody = EngineEventBody.Ready) = EngineEvent(
        presentationId = launch.presentationId,
        protocolVersion = launch.protocolVersion,
        sequence = sequence,
        body = body,
    )

    private fun assertRejected(reason: EngineEventRejection, decision: EngineEventDecision) {
        assertEquals(EngineEventDecision.Rejected(reason), decision)
    }
}
