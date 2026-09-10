package dev.partydeck.godot.bridge

import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameRejection
import dev.partydeck.core.GameView
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import kotlin.random.Random

data class QualificationStep(
    val decision: BridgeDecision,
    val documents: List<String> = emptyList(),
    val authorityRejection: GameRejection? = null,
)

/**
 * A real core-authority round trip for isolated renderer qualification, not multiplayer.
 * Native code serializes calls and owns delivery/lifecycle. Live callers inject CSPRNG-backed
 * Random; reproducible fixture/test callers may deliberately inject a documented seed.
 */
class QualificationAuthorityDriver(
    random: Random,
    val presentationId: String,
    roster: List<PlayerIdentity> = listOf(
        PlayerIdentity("seat-1", "Ari"), PlayerIdentity("seat-2", "Moxie"),
        PlayerIdentity("seat-3", "Pip"), PlayerIdentity("seat-4", "Orbit"),
    ),
    viewerId: String? = null,
) {
    private val engine = LastLightEngine(random)
    private var state = engine.start(roster)
    // Choosing the actual random opener makes the first qualification input actionable;
    // it does not change the authority's chosen opener, cards, outcomes, or rules.
    val viewerId: String = viewerId ?: checkNotNull(state.turnPlayerId)
    private val adapter = LastLightBridgeAdapter(presentationId, 0, view, controls())
    private var ended = false
    private var foreground = true

    init { require(state.players.any { it.identity.id == this.viewerId }) { "Unknown qualification recipient." } }

    val revision: Long get() = adapter.revision
    val view: GameView get() = engine.viewFor(state, viewerId)

    fun launchDocument(
        mode: PresentationMode,
        preferences: PresentationPreferences = PresentationPreferences(),
    ): String = LastLightWireCodec.encodeLaunch(adapter.launch, mode, preferences)

    fun handleEvent(document: String): QualificationStep {
        val decision = adapter.accept(document)
        if (decision is BridgeDecision.Rejected) return QualificationStep(decision)
        return when (val input = (decision as BridgeDecision.Accepted).input) {
            is BridgeInput.Action -> apply(decision, engine.apply(state, input.action))
            BridgeInput.AdvanceRound -> apply(decision, engine.advanceRound(state))
            BridgeInput.ReturnToLobby, BridgeInput.ExitRequested, is BridgeInput.Failed -> {
                ended = true
                adapter.close()
                QualificationStep(decision)
            }
            BridgeInput.Ready -> QualificationStep(decision)
        }
    }

    /** Test-opponent policy reads only its own projection; it contains no rule implementation. */
    fun advanceOtherPlayers(maxActions: Int = 32): List<QualificationStep> {
        require(maxActions in 1..128)
        if (ended || !foreground) return emptyList()
        val steps = mutableListOf<QualificationStep>()
        repeat(maxActions) {
            if (state.phase != GamePhase.PLAYING || state.turnPlayerId == viewerId) return steps.toList()
            val actor = checkNotNull(state.turnPlayerId)
            val actorView = engine.viewFor(state, actor)
            val action = when {
                actorView.availableActions.canChallenge -> GameAction.Challenge(actor)
                actorView.availableActions.canPlay -> GameAction.Play(actor, listOf(actorView.yourHand.first().id))
                else -> error("Authority has no available action for its active seat.")
            }
            val decision = BridgeDecision.Accepted(BridgeInput.Action(action))
            steps += apply(decision, engine.apply(state, action))
            check(steps.last().authorityRejection == null) { "A projected opponent action was rejected." }
        }
        check(state.phase != GamePhase.PLAYING || state.turnPlayerId == viewerId) { "Opponent step budget exhausted." }
        return steps.toList()
    }

    fun setForeground(isForeground: Boolean): String {
        val command = adapter.setForeground(isForeground)
        foreground = isForeground
        return LastLightWireCodec.encodeCommand(presentationId, command)
    }

    /** Reconciles a rejected submission without changing domain state or reusing a revision. */
    fun refreshView(): String {
        check(!ended && revision < Long.MAX_VALUE) { "Qualification presentation is closed or exhausted." }
        return LastLightWireCodec.encodeCommand(presentationId, adapter.showView(revision + 1, view, controls()))
    }

    fun close(): String {
        ended = true
        adapter.close()
        return LastLightWireCodec.encodeClose(presentationId)
    }

    private fun controls() = PresentationControls(
        isHost = true,
        canSendAction = true,
        canAdvanceRound = state.phase == GamePhase.ROUND_ENDED,
        // The comparison flow offers return after a winner; generic session controls can
        // permit an earlier return and the adapter preserves that authority decision.
        canReturnToLobby = state.phase == GamePhase.FINISHED,
    )

    private fun apply(decision: BridgeDecision, result: GameDecision): QualificationStep = when (result) {
        is GameDecision.Rejected -> QualificationStep(decision, authorityRejection = result.reason)
        is GameDecision.Applied -> {
            check(revision < Long.MAX_VALUE) { "Qualification revision exhausted." }
            val projected = engine.viewFor(result.state, viewerId)
            state = result.state
            val command = adapter.showView(revision + 1, projected, controls())
            QualificationStep(decision, listOf(LastLightWireCodec.encodeCommand(presentationId, command)))
        }
    }
}
