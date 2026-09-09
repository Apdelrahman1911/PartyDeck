package dev.partydeck.core

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class LastLightEngineTest {
    private val engine = LastLightEngine(Random(178))

    @Test
    fun anAllWildClaimIsTruthfulAndPenalizesOnlyTheChallenger() {
        val initial = startingState(listOf(CardRank.WILD, CardRank.WILD, CardRank.WILD))
        val played = playOpeningCards(initial, count = 3)
        val result = challenge(played)
        val outcome = assertNotNull(result.roundOutcome)

        assertTrue(outcome.truthful)
        assertEquals(List(3) { CardRank.WILD }, outcome.revealedCards.map { it.rank })
        assertEquals("player-1", outcome.penalizedPlayerId)
        assertEquals(listOf(0, 1, 0), result.players.map { it.penaltyAttempts })
        assertFalse(outcome.burnedOut)
        assertEquals(GamePhase.ROUND_ENDED, result.phase)
        assertEquals(5, initial.players.first().hand.size)
    }

    @Test
    fun matchingCardsAndWildsAreTruthfulTogether() {
        val initial = startingState(listOf(CardRank.CROWN, CardRank.WILD, CardRank.CROWN))
        val result = challenge(playOpeningCards(initial, count = 3))
        val outcome = assertNotNull(result.roundOutcome)

        assertTrue(outcome.truthful)
        assertEquals("player-1", outcome.penalizedPlayerId)
        assertEquals(1, outcome.penaltyAttempt)
    }

    @Test
    fun oneMismatchingCardMakesTheEntireClaimABluff() {
        val initial = startingState(listOf(CardRank.CROWN, CardRank.WILD, CardRank.MOON))
        val result = challenge(playOpeningCards(initial, count = 3))
        val outcome = assertNotNull(result.roundOutcome)

        assertFalse(outcome.truthful)
        assertEquals("player-0", outcome.penalizedPlayerId)
        assertEquals(listOf(1, 0, 0), result.players.map { it.penaltyAttempts })
        assertEquals(
            listOf(CardRank.CROWN, CardRank.WILD, CardRank.MOON),
            outcome.revealedCards.map { it.rank },
        )
    }

    @Test
    fun acceptingAnEarlierBluffLeavesOnlyTheLatestClaimChallengeable() {
        val initial = startingState(listOf(CardRank.MOON))
        val firstPlay = playOpeningCards(initial, count = 1)
        val secondActor = firstPlay.players[1]
        val truthfulCard = secondActor.hand.first { it.rank == CardRank.CROWN }
        val secondPlay = accepted(
            engine.apply(firstPlay, GameAction.Play(secondActor.identity.id, listOf(truthfulCard.id))),
        )
        val result = challenge(secondPlay)
        val outcome = assertNotNull(result.roundOutcome)

        assertEquals(2, result.discardedCards.size)
        assertEquals(listOf(truthfulCard), outcome.revealedCards)
        assertTrue(outcome.truthful)
        assertEquals("player-2", outcome.penalizedPlayerId)
        assertEquals(0, result.players.first().penaltyAttempts)
    }

    @Test
    fun aSafePenaltyPersistsThroughADealWithANewOpener() {
        val initial = startingState(listOf(CardRank.WILD))
        val ended = challenge(playOpeningCards(initial, count = 1))
        val resumed = accepted(engine.advanceRound(ended))
        val oldIds = allCards(ended).map { it.id }.toSet()

        assertEquals(GamePhase.PLAYING, resumed.phase)
        assertEquals(2, resumed.roundNumber)
        assertEquals("player-1", resumed.openerPlayerId)
        assertEquals("player-1", resumed.turnPlayerId)
        assertEquals(listOf(5, 5, 5), resumed.players.map { it.hand.size })
        assertEquals(listOf(0, 1, 0), resumed.players.map { it.penaltyAttempts })
        assertEquals(ended.roundOutcome, resumed.roundOutcome)
        assertEquals(null, resumed.pendingPlay)
        assertTrue(allCards(resumed).none { it.id in oldIds })
        assertEquals(30, allCards(resumed).map { it.id }.toSet().size)
    }

    @Test
    fun burnoutInATwoPlayerMatchFinishesWithoutAnotherDeal() {
        val initial = startingState(listOf(CardRank.MOON), playerCount = 2, openerBurnoutStep = 1)
        val finished = challenge(playOpeningCards(initial, count = 1))
        val outcome = assertNotNull(finished.roundOutcome)

        assertTrue(outcome.burnedOut)
        assertEquals(GamePhase.FINISHED, finished.phase)
        assertEquals("player-1", finished.winnerId)
        assertEquals(null, finished.turnPlayerId)
        assertTrue(finished.players.first().hand.isEmpty())
        assertEquals(5, finished.discardedCards.size)
        assertEquals(1, outcome.revealedCards.size)
        assertEquals(30, allCards(finished).map { it.id }.toSet().size)
        assertEquals(
            GameDecision.Rejected(GameRejection.GAME_FINISHED),
            engine.advanceRound(finished),
        )
    }

    private fun playOpeningCards(state: GameState, count: Int): GameState {
        val player = state.players.first()
        return accepted(
            engine.apply(state, GameAction.Play(player.identity.id, player.hand.take(count).map { it.id })),
        )
    }

    private fun challenge(state: GameState): GameState = accepted(
        engine.apply(state, GameAction.Challenge(assertNotNull(state.turnPlayerId))),
    )

    private fun accepted(decision: GameDecision): GameState = assertIs<GameDecision.Applied>(decision).state

    private fun allCards(state: GameState): List<Card> =
        state.players.flatMap { it.hand } + state.discardedCards + state.undealtCards

    /** A conserved deck arranged so the opener's first cards have the desired ranks. */
    private fun startingState(
        openingRanks: List<CardRank>,
        playerCount: Int = 3,
        openerBurnoutStep: Int = 6,
    ): GameState {
        val remainingRanks = mutableListOf<CardRank>().apply {
            repeat(9) { add(CardRank.CROWN) }
            repeat(9) { add(CardRank.MOON) }
            repeat(9) { add(CardRank.STAR) }
            repeat(3) { add(CardRank.WILD) }
        }
        for (rank in openingRanks) assertTrue(remainingRanks.remove(rank))
        val deck = List(30) { slot ->
            val openingCard = slot / playerCount
            val rank = if (slot % playerCount == 0 && openingCard < openingRanks.size) {
                openingRanks[openingCard]
            } else {
                remainingRanks.removeAt(0)
            }
            Card("r1-c$slot", rank)
        }
        val players = List(playerCount) { seat ->
            PlayerState(
                identity = PlayerIdentity("player-$seat", "Player ${seat + 1}"),
                hand = deck.take(playerCount * 5).filterIndexed { index, _ -> index % playerCount == seat },
                penaltyAttempts = 0,
                burnoutStep = if (seat == 0) openerBurnoutStep else 6,
                eliminated = false,
            )
        }
        return GameState(
            players = players,
            phase = GamePhase.PLAYING,
            roundNumber = 1,
            tableRank = CardRank.CROWN,
            openerPlayerId = "player-0",
            turnPlayerId = "player-0",
            pendingPlay = null,
            discardedCards = emptyList(),
            undealtCards = deck.drop(playerCount * 5),
            roundOutcome = null,
            winnerId = null,
        )
    }
}
