package dev.partydeck.games

sealed interface EngineEventDecision {
    data class Accepted(val body: EngineEventBody) : EngineEventDecision
    data class Rejected(val reason: EngineEventRejection) : EngineEventDecision
}

enum class EngineEventRejection {
    CLOSED,
    WRONG_PRESENTATION,
    UNSUPPORTED_PROTOCOL,
    REPLAYED_EVENT,
    NOT_READY,
    ALREADY_READY,
}

/**
 * Small guard for a future platform event stream, not an engine implementation.
 * The owning shell calls accept/close on one serialized dispatcher. A new gate and
 * presentation identifier are required on every entry; events after exit cannot act
 * on a later game. Domain/session code still validates intent contents and revisions.
 */
class EngineEventGate(private val launch: EngineLaunch) {
    private var ready = false
    private var closed = false
    private var lastSequence = -1L

    fun accept(event: EngineEvent): EngineEventDecision {
        if (closed) return rejected(EngineEventRejection.CLOSED)
        if (event.presentationId != launch.presentationId) return rejected(EngineEventRejection.WRONG_PRESENTATION)
        if (event.protocolVersion != launch.protocolVersion) return rejected(EngineEventRejection.UNSUPPORTED_PROTOCOL)
        if (event.sequence < 0 || event.sequence <= lastSequence) return rejected(EngineEventRejection.REPLAYED_EVENT)

        when (event.body) {
            EngineEventBody.Ready -> {
                if (ready) return rejected(EngineEventRejection.ALREADY_READY)
                ready = true
            }
            is EngineEventBody.PlayerIntent -> {
                if (!ready) return rejected(EngineEventRejection.NOT_READY)
            }
            EngineEventBody.ExitRequested -> {
                if (!ready) return rejected(EngineEventRejection.NOT_READY)
                closed = true
            }
            is EngineEventBody.Failed -> closed = true
        }
        lastSequence = event.sequence
        return EngineEventDecision.Accepted(event.body)
    }

    fun close() {
        closed = true
    }

    private fun rejected(reason: EngineEventRejection) = EngineEventDecision.Rejected(reason)
}
