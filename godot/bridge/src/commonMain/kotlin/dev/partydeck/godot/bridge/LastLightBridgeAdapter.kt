package dev.partydeck.godot.bridge

import dev.partydeck.core.GameAction
import dev.partydeck.core.GameView
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineEventDecision
import dev.partydeck.games.EngineEventGate
import dev.partydeck.games.EngineEventRejection
import dev.partydeck.games.EngineFailure
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId

sealed interface BridgeInput {
    data object Ready : BridgeInput
    data class Action(val action: GameAction) : BridgeInput
    data object AdvanceRound : BridgeInput
    data object ReturnToLobby : BridgeInput
    data object ExitRequested : BridgeInput
    data class Failed(val reason: EngineFailure) : BridgeInput
}

sealed interface BridgeDecision {
    data class Accepted(val input: BridgeInput) : BridgeDecision
    data class Rejected(val reason: BridgeRejection) : BridgeDecision
}

enum class BridgeRejection {
    INVALID_DOCUMENT, CLOSED, WRONG_PRESENTATION, UNSUPPORTED_PROTOCOL,
    REPLAYED_EVENT, NOT_READY, ALREADY_READY, STALE_REVISION,
    NOT_FOREGROUND, ACTION_UNAVAILABLE, INVALID_SELECTION,
}

/**
 * One serialized native owner, one presentation, one fixed recipient. Returned actions still
 * require acceptance by the real core/session authority. This class never owns GameState.
 */
class LastLightBridgeAdapter(
    val presentationId: String,
    initialRevision: Long,
    initialView: GameView,
    controls: PresentationControls,
) {
    val launch = EngineLaunch(
        GameId("last-light"), presentationId,
        LastLightWireCodec.viewPayload(initialView, controls), initialRevision,
    )
    private val gate = EngineEventGate(launch)
    private val recipient = initialView.viewerId
    private var snapshot = LastLightWireCodec.decodeViewPayload(launch.initialView)
    private var foreground = true
    private var closed = false
    var revision: Long = initialRevision
        private set

    fun accept(document: String): BridgeDecision {
        if (closed) return rejected(BridgeRejection.CLOSED)
        val event = try { LastLightWireCodec.decodeEvent(document) } catch (_: IllegalArgumentException) {
            return rejected(BridgeRejection.INVALID_DOCUMENT)
        }
        return when (val decision = gate.accept(event)) {
            is EngineEventDecision.Rejected -> rejected(decision.reason.toBridgeRejection())
            is EngineEventDecision.Accepted -> when (val body = decision.body) {
                EngineEventBody.Ready -> accepted(BridgeInput.Ready)
                is EngineEventBody.PlayerIntent -> acceptIntent(body)
                EngineEventBody.ExitRequested -> {
                    closed = true
                    accepted(BridgeInput.ExitRequested)
                }
                is EngineEventBody.Failed -> {
                    closed = true
                    accepted(BridgeInput.Failed(body.reason))
                }
            }
        }
    }

    fun showView(newRevision: Long, view: GameView, controls: PresentationControls): EngineCommand.ShowView {
        check(!closed) { "Presentation is closed." }
        require(newRevision > revision) { "A view revision must strictly increase." }
        require(view.viewerId == recipient) { "A presentation cannot change its recipient." }
        val payload = LastLightWireCodec.viewPayload(view, controls)
        val command = EngineCommand.ShowView(newRevision, payload)
        // Verify the complete native envelope before accepting the new view/revision.
        LastLightWireCodec.encodeCommand(presentationId, command)
        snapshot = LastLightWireCodec.decodeViewPayload(payload)
        revision = newRevision
        return command
    }

    fun setForeground(isForeground: Boolean): EngineCommand.SetForeground {
        check(!closed) { "Presentation is closed." }
        foreground = isForeground
        return EngineCommand.SetForeground(isForeground)
    }

    fun close() {
        if (closed) return
        closed = true
        gate.close()
    }

    private fun acceptIntent(body: EngineEventBody.PlayerIntent): BridgeDecision {
        if (body.expectedRevision != revision) return rejected(BridgeRejection.STALE_REVISION)
        if (!foreground) return rejected(BridgeRejection.NOT_FOREGROUND)
        if (!snapshot.controls.canSendAction) return rejected(BridgeRejection.ACTION_UNAVAILABLE)
        val view = snapshot.game
        return when (val intent = LastLightWireCodec.decodeIntentPayload(body.payload)) {
            is RendererIntent.Play -> {
                if (recipient == null || !view.availableActions.canPlay) return rejected(BridgeRejection.ACTION_UNAVAILABLE)
                if (intent.cardIds.size > view.availableActions.maxPlayableCards || intent.cardIds.any { id -> view.yourHand.none { it.id == id } }) {
                    return rejected(BridgeRejection.INVALID_SELECTION)
                }
                accepted(BridgeInput.Action(GameAction.Play(recipient, intent.cardIds.toList())))
            }
            RendererIntent.Challenge -> {
                if (recipient == null || !view.availableActions.canChallenge) return rejected(BridgeRejection.ACTION_UNAVAILABLE)
                accepted(BridgeInput.Action(GameAction.Challenge(recipient)))
            }
            RendererIntent.AdvanceRound -> if (snapshot.controls.isHost && snapshot.controls.canAdvanceRound) {
                accepted(BridgeInput.AdvanceRound)
            } else rejected(BridgeRejection.ACTION_UNAVAILABLE)
            RendererIntent.ReturnToLobby -> if (snapshot.controls.isHost && snapshot.controls.canReturnToLobby) {
                accepted(BridgeInput.ReturnToLobby)
            } else rejected(BridgeRejection.ACTION_UNAVAILABLE)
        }
    }

    private fun accepted(input: BridgeInput) = BridgeDecision.Accepted(input)
    private fun rejected(reason: BridgeRejection) = BridgeDecision.Rejected(reason)
}

private fun EngineEventRejection.toBridgeRejection(): BridgeRejection = when (this) {
    EngineEventRejection.CLOSED -> BridgeRejection.CLOSED
    EngineEventRejection.WRONG_PRESENTATION -> BridgeRejection.WRONG_PRESENTATION
    EngineEventRejection.UNSUPPORTED_PROTOCOL -> BridgeRejection.UNSUPPORTED_PROTOCOL
    EngineEventRejection.REPLAYED_EVENT -> BridgeRejection.REPLAYED_EVENT
    EngineEventRejection.NOT_READY -> BridgeRejection.NOT_READY
    EngineEventRejection.ALREADY_READY -> BridgeRejection.ALREADY_READY
}
