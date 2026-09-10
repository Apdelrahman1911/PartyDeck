package dev.partydeck.godot.bridge

import dev.partydeck.core.GameAction
import dev.partydeck.core.GamePhase
import kotlin.random.Random

/** A reference is explicit and repeatable; a live iOS session uses Security.framework. */
enum class IosQualificationRandomness { REFERENCE_SEED_2, SECURE }

enum class IosQualificationLifecycle { WAITING_FOR_READY, READY, CLOSED }

/** A direct label for the existing authority phase, with no Swift dependency on domain types. */
enum class IosQualificationPhase { PLAYING, ROUND_ENDED, FINISHED }

enum class IosQualificationOutcome {
    ACCEPTED, REJECTED, AUTHORITY_REJECTED, NO_CHANGE, FOREGROUND_CHANGED, VIEW_REFRESHED,
    RETURN_TO_LOBBY, EXIT_REQUESTED, RENDERER_FAILED, CLOSED,
}

/** Coarse receipt data only. Never used to decide a move or reconstruct a game view. */
class IosQualificationStatus internal constructor(
    val lifecycle: IosQualificationLifecycle,
    val phase: IosQualificationPhase,
    val revision: String,
    val roundNumber: Int,
    val winnerId: String,
    val foreground: Boolean,
    val acceptedRendererEvents: Int,
    val acceptedViewerPlays: Int,
    val acceptedViewerChallenges: Int,
    val roundsAdvanced: Int,
    val acceptedOpponentActions: Int,
)

/**
 * [reasonCode] is empty on success, or the exact existing bridge/domain/failure enum name.
 * [outcome] identifies which kind of reason it is. Commands are safe native wire documents.
 */
class IosQualificationResult internal constructor(
    val outcome: IosQualificationOutcome,
    commands: List<String>,
    val reasonCode: String,
    val status: IosQualificationStatus,
) {
    val commands: List<String> = commands.toList()
}

/**
 * Swift-friendly ownership of a real qualification driver, without exposing its domain types.
 * The native host serializes calls, bounds/delivers queues, and discards this facade on close.
 * Re-entry creates a new facade and presentation ID. This is not a network/session authority.
 */
class IosQualificationAuthority internal constructor(
    random: Random,
    presentationId: String,
    mode: PresentationMode,
    preferences: PresentationPreferences,
    val randomness: IosQualificationRandomness,
) {
    private val driver = QualificationAuthorityDriver(random, presentationId)
    private var initialLaunchDocument = driver.launchDocument(mode, preferences)
    private var lifecycle = IosQualificationLifecycle.WAITING_FOR_READY
    private var foreground = true
    private var acceptedRendererEvents = 0
    private var acceptedViewerPlays = 0
    private var acceptedViewerChallenges = 0
    private var roundsAdvanced = 0
    private var acceptedOpponentActions = 0

    /** Initial safe launch, supplied once to native preparation. Empty after terminal close. */
    val launchDocument: String get() = initialLaunchDocument

    fun status(): IosQualificationStatus {
        val view = driver.view
        return IosQualificationStatus(
            lifecycle = lifecycle,
            phase = when (view.phase) {
                GamePhase.PLAYING -> IosQualificationPhase.PLAYING
                GamePhase.ROUND_ENDED -> IosQualificationPhase.ROUND_ENDED
                GamePhase.FINISHED -> IosQualificationPhase.FINISHED
            },
            revision = driver.revision.toString(),
            roundNumber = view.roundNumber,
            winnerId = view.winnerId.orEmpty(),
            foreground = foreground,
            acceptedRendererEvents = acceptedRendererEvents,
            acceptedViewerPlays = acceptedViewerPlays,
            acceptedViewerChallenges = acceptedViewerChallenges,
            roundsAdvanced = roundsAdvanced,
            acceptedOpponentActions = acceptedOpponentActions,
        )
    }

    /** Ordinary malformed/stale/replayed/paused input returns REJECTED, without a refresh. */
    @Throws(Exception::class)
    fun handleRendererEvent(document: String): IosQualificationResult {
        val step = driver.handleEvent(document)
        val decision = step.decision
        if (decision is BridgeDecision.Rejected) return rejected(decision.reason)
        acceptedRendererEvents++
        if (step.authorityRejection != null) {
            return result(IosQualificationOutcome.AUTHORITY_REJECTED, step.documents, step.authorityRejection.name)
        }
        return when (val input = (decision as BridgeDecision.Accepted).input) {
            BridgeInput.Ready -> {
                lifecycle = IosQualificationLifecycle.READY
                result(IosQualificationOutcome.ACCEPTED, step.documents)
            }
            is BridgeInput.Action -> {
                when (input.action) {
                    is GameAction.Play -> acceptedViewerPlays++
                    is GameAction.Challenge -> acceptedViewerChallenges++
                }
                result(IosQualificationOutcome.ACCEPTED, step.documents)
            }
            BridgeInput.AdvanceRound -> {
                roundsAdvanced++
                result(IosQualificationOutcome.ACCEPTED, step.documents)
            }
            BridgeInput.ReturnToLobby -> terminal(IosQualificationOutcome.RETURN_TO_LOBBY)
            BridgeInput.ExitRequested -> terminal(IosQualificationOutcome.EXIT_REQUESTED)
            is BridgeInput.Failed -> terminal(IosQualificationOutcome.RENDERER_FAILED, input.reason.name)
        }
    }

    /** Existing bounded safe-view opponent policy; no game strategy or rules live here. */
    @Throws(Exception::class)
    fun advanceOtherPlayers(): IosQualificationResult {
        if (lifecycle == IosQualificationLifecycle.CLOSED) return rejected(BridgeRejection.CLOSED)
        val steps = driver.advanceOtherPlayers()
        val commands = mutableListOf<String>()
        for (step in steps) {
            val decision = step.decision
            if (decision is BridgeDecision.Rejected) {
                return result(IosQualificationOutcome.REJECTED, commands, decision.reason.name)
            }
            commands += step.documents
            if (step.authorityRejection != null) {
                return result(IosQualificationOutcome.AUTHORITY_REJECTED, commands, step.authorityRejection.name)
            }
            if ((decision as BridgeDecision.Accepted).input is BridgeInput.Action) acceptedOpponentActions++
        }
        return result(if (steps.isEmpty()) IosQualificationOutcome.NO_CHANGE else IosQualificationOutcome.ACCEPTED, commands)
    }

    /** Reconcile pending UI only when the native owner chooses to do so after a rejection. */
    @Throws(Exception::class)
    fun refreshView(): IosQualificationResult {
        if (lifecycle == IosQualificationLifecycle.CLOSED) return rejected(BridgeRejection.CLOSED)
        return result(IosQualificationOutcome.VIEW_REFRESHED, listOf(driver.refreshView()))
    }

    @Throws(Exception::class)
    fun setForeground(isForeground: Boolean): IosQualificationResult {
        if (lifecycle == IosQualificationLifecycle.CLOSED) return rejected(BridgeRejection.CLOSED)
        val command = driver.setForeground(isForeground)
        foreground = isForeground
        return result(IosQualificationOutcome.FOREGROUND_CHANGED, listOf(command))
    }

    /** Terminal and idempotent; returned close documents may safely be delivered again. */
    @Throws(Exception::class)
    fun close(): IosQualificationResult = terminal(IosQualificationOutcome.CLOSED)

    private fun terminal(outcome: IosQualificationOutcome, reasonCode: String = ""): IosQualificationResult {
        val command = driver.close()
        lifecycle = IosQualificationLifecycle.CLOSED
        foreground = false
        initialLaunchDocument = ""
        return result(outcome, listOf(command), reasonCode)
    }

    private fun rejected(reason: BridgeRejection) = result(IosQualificationOutcome.REJECTED, reasonCode = reason.name)

    private fun result(
        outcome: IosQualificationOutcome,
        commands: List<String> = emptyList(),
        reasonCode: String = "",
    ) = IosQualificationResult(outcome, commands, reasonCode, status())
}

internal const val IOS_QUALIFICATION_REFERENCE_SEED = 2
