package dev.partydeck.app.controller

import dev.partydeck.core.CardRank
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameView
import dev.partydeck.session.ClientIntent
import kotlin.random.Random

/** A practice opponent receives exactly the same private projection as a remote player. */
internal class PracticeBot(private val random: Random) {
    fun choose(view: GameView): ClientIntent? {
        if (view.phase != GamePhase.PLAYING || view.viewerId != view.turnPlayerId) return null
        val actions = view.availableActions
        if (view.forcedChallenge) return if (actions.canChallenge) ClientIntent.Challenge else null

        val matches = view.yourHand.filter { it.rank == view.tableRank || it.rank == CardRank.WILD }
        val claimCount = view.latestClaim?.cardCount ?: 0
        // Bigger claims and holding matching cards make a challenge more attractive.
        val suspicion = (0.18 + claimCount * 0.09 + matches.size * 0.05).coerceAtMost(0.65)
        if (actions.canChallenge && (!actions.canPlay || random.nextDouble() < suspicion)) {
            return ClientIntent.Challenge
        }
        if (!actions.canPlay || actions.maxPlayableCards < 1 || view.yourHand.isEmpty()) return null

        val candidates = if (matches.isNotEmpty() && random.nextDouble() < 0.72) matches else view.yourHand
        val count = random.nextInt(1, minOf(candidates.size, actions.maxPlayableCards) + 1)
        return ClientIntent.PlayCards(candidates.shuffled(random).take(count).map { it.id })
    }
}
