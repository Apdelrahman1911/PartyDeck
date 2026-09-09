package dev.partydeck.core

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Independent rule-contract tests: legal histories, conserved cards, and hostile actions. */
class LastLightAdversarialTest {
    @Test
    fun completeMatchesPreserveCardsPrivacyAndFiniteProgressForEveryTableSize() {
        for (playerCount in 2..6) {
            for (seed in 0 until 24) {
                for (delayChallenges in listOf(false, true)) {
                    val random = ObservedRandom(seed * 31 + playerCount)
                    val engine = LastLightEngine(random)
                    val policy = Random(seed * 997 + playerCount)
                    val roster = roster(playerCount)
                    var state = engine.start(roster)
                    var roundCards = physicalCards(state).map { it.id }.toSet()
                    var challengeCount = 0
                    var playsThisRound = 0
                    var actions = 0
                    val context = "players=$playerCount seed=$seed delayed=$delayChallenges"

                    while (state.phase != GamePhase.FINISHED) {
                        assertStateAndViews(engine, state, roster, roundCards, context)
                        val before = snapshot(state)
                        val entropyBefore = random.draws
                        if (state.phase == GamePhase.ROUND_ENDED) {
                            val oldIds = roundCards
                            val oldOpener = roster.indexOfFirst { it.id == state.openerPlayerId }
                            val expectedOpener = (1 until roster.size)
                                .map { roster[(oldOpener + it) % roster.size].id }
                                .first { id -> state.players.single { it.identity.id == id }.eliminated.not() }
                            val next = applied(engine.advanceRound(state), context)
                            assertEquals(before, state, "Advancing mutated a previous state: $context")
                            assertEquals(before.roundNumber + 1, next.roundNumber, context)
                            assertEquals(expectedOpener, next.openerPlayerId, context)
                            assertEquals(next.openerPlayerId, next.turnPlayerId, context)
                            assertEquals(before.roundOutcome, next.roundOutcome, context)
                            assertEquals(before.players.map { it.penaltyAttempts }, next.players.map { it.penaltyAttempts }, context)
                            assertEquals(before.players.map { it.burnoutStep }, next.players.map { it.burnoutStep }, context)
                            assertTrue(random.draws > entropyBefore, "A redeal must use fresh entropy: $context")
                            state = next
                            roundCards = physicalCards(state).map { it.id }.toSet()
                            assertTrue(oldIds.intersect(roundCards).isEmpty(), "Old card IDs returned: $context")
                            playsThisRound = 0
                            continue
                        }

                        val actorId = assertNotNull(state.turnPlayerId, context)
                        val view = engine.viewFor(state, actorId)
                        val shouldChallenge = view.forcedChallenge ||
                            (!delayChallenges && view.availableActions.canChallenge && policy.nextInt(3) == 0)
                        val action = if (shouldChallenge) {
                            GameAction.Challenge(actorId)
                        } else {
                            val amount = policy.nextInt(1, view.availableActions.maxPlayableCards + 1)
                            GameAction.Play(actorId, view.yourHand.shuffled(policy).take(amount).map { it.id })
                        }
                        val next = applied(engine.apply(state, action), context)
                        assertEquals(before, state, "A transition mutated its input: $context")
                        assertEquals(entropyBefore, random.draws, "Playing/challenging consumed entropy: $context")
                        assertEquals(before.players.map { it.burnoutStep }, next.players.map { it.burnoutStep }, context)

                        when (action) {
                            is GameAction.Play -> {
                                playsThisRound++
                                val survivors = before.players.count { !it.eliminated }
                                assertTrue(playsThisRound <= survivors * 5 - 1, "Round exceeded its finite play bound: $context")
                                assertEquals(before.players.sumOf { it.hand.size } - action.cardIds.size, next.players.sumOf { it.hand.size }, context)
                                assertEquals(before.players.map { it.penaltyAttempts }, next.players.map { it.penaltyAttempts }, context)
                            }
                            is GameAction.Challenge -> {
                                challengeCount++
                                val claim = assertNotNull(before.pendingPlay, context)
                                val truthful = claim.cards.none { it.rank != CardRank.WILD && it.rank != before.tableRank }
                                val loser = if (truthful) actorId else claim.playerId
                                val outcome = assertNotNull(next.roundOutcome, context)
                                assertEquals(claim.cards, outcome.revealedCards, context)
                                assertEquals(truthful, outcome.truthful, context)
                                assertEquals(loser, outcome.penalizedPlayerId, context)
                                assertEquals(actorId, outcome.challengerId, context)
                                assertEquals(claim.playerId, outcome.claimantId, context)
                                assertEquals(1, next.players.sumOf { it.penaltyAttempts } - before.players.sumOf { it.penaltyAttempts }, context)
                                for (player in next.players) {
                                    val old = before.players.single { it.identity.id == player.identity.id }
                                    assertEquals(old.penaltyAttempts + if (player.identity.id == loser) 1 else 0, player.penaltyAttempts, context)
                                }
                                assertTrue(challengeCount <= 6 * playerCount - 1, "Match exceeded its penalty bound: $context")
                            }
                        }
                        state = next
                        actions++
                        assertTrue(actions <= (6 * playerCount - 1) * 5 * playerCount, "Match stopped progressing: $context")
                    }

                    assertStateAndViews(engine, state, roster, roundCards, context)
                    assertTrue(challengeCount in 1..(6 * playerCount - 1), context)
                    val winner = state.players.single { !it.eliminated }
                    assertEquals(winner.identity.id, state.winnerId, context)
                    rejectWithoutChanges(engine, random, state, GameAction.Challenge(winner.identity.id), GameRejection.GAME_FINISHED)
                    val entropyBefore = random.draws
                    assertEquals(GameDecision.Rejected(GameRejection.GAME_FINISHED), engine.advanceRound(state), context)
                    assertEquals(entropyBefore, random.draws, context)
                }
            }
        }
    }

    @Test
    fun malformedRostersFailBeforeAnyRandomOutcomeIsChosen() {
        val invalidRosters = listOf(
            emptyList(),
            roster(1),
            roster(7),
            listOf(PlayerIdentity("same", "Ada"), PlayerIdentity("same", "Bo")),
            listOf(PlayerIdentity(" ", "Ada"), PlayerIdentity("bo", "Bo")),
            listOf(PlayerIdentity("a".repeat(65), "Ada"), PlayerIdentity("bo", "Bo")),
            listOf(PlayerIdentity("ada\n", "Ada"), PlayerIdentity("bo", "Bo")),
            listOf(PlayerIdentity("ada", "\t"), PlayerIdentity("bo", "Bo")),
            listOf(PlayerIdentity("ada", "A".repeat(25)), PlayerIdentity("bo", "Bo")),
            listOf(PlayerIdentity("ada", "Ada\u007f"), PlayerIdentity("bo", "Bo")),
        )
        for (players in invalidRosters) {
            val random = ObservedRandom(71)
            assertFailsWith<IllegalArgumentException> { LastLightEngine(random).start(players) }
            assertEquals(0, random.draws, "An invalid roster consumed game entropy")
        }
    }

    @Test
    fun invalidTurnsAndSelectionsAreAtomicAndLeaveTheRandomStreamUntouched() {
        val random = ObservedRandom(44)
        val engine = LastLightEngine(random)
        val state = engine.start(roster(3))
        val actor = state.players.single { it.identity.id == state.turnPlayerId }
        val opponent = state.players.first { it.identity.id != state.turnPlayerId }
        val cases = listOf(
            GameAction.Challenge("missing") to GameRejection.UNKNOWN_PLAYER,
            GameAction.Challenge(opponent.identity.id) to GameRejection.NOT_YOUR_TURN,
            GameAction.Challenge(actor.identity.id) to GameRejection.NO_CLAIM,
            GameAction.Play(actor.identity.id, emptyList()) to GameRejection.INVALID_CARD_COUNT,
            GameAction.Play(actor.identity.id, actor.hand.take(4).map { it.id }) to GameRejection.INVALID_CARD_COUNT,
            GameAction.Play(actor.identity.id, listOf(actor.hand.first().id, actor.hand.first().id)) to GameRejection.DUPLICATE_CARD,
            GameAction.Play(actor.identity.id, listOf(opponent.hand.first().id)) to GameRejection.CARD_NOT_IN_HAND,
            GameAction.Play(actor.identity.id, listOf(actor.hand.first().id, "missing-card")) to GameRejection.CARD_NOT_IN_HAND,
            GameAction.Play(opponent.identity.id, opponent.hand.take(1).map { it.id }) to GameRejection.NOT_YOUR_TURN,
        )
        for ((action, error) in cases) rejectWithoutChanges(engine, random, state, action, error)

        val entropyBefore = random.draws
        assertEquals(GameDecision.Rejected(GameRejection.ROUND_NOT_ENDED), engine.advanceRound(state))
        assertEquals(entropyBefore, random.draws)
        val played = applied(engine.apply(state, GameAction.Play(actor.identity.id, actor.hand.take(1).map { it.id })))
        val ended = applied(engine.apply(played, GameAction.Challenge(assertNotNull(played.turnPlayerId))))
        assertEquals(GamePhase.ROUND_ENDED, ended.phase)
        rejectWithoutChanges(engine, random, ended, GameAction.Challenge(actor.identity.id), GameRejection.ROUND_NOT_PLAYING)
        rejectWithoutChanges(engine, random, ended, GameAction.Play(actor.identity.id, actor.hand.take(1).map { it.id }), GameRejection.ROUND_NOT_PLAYING)

        val next = applied(engine.advanceRound(ended))
        rejectWithoutChanges(engine, random, next, GameAction.Play(assertNotNull(next.turnPlayerId), listOf(actor.hand.first().id)), GameRejection.CARD_NOT_IN_HAND)
    }

    @Test
    fun emptyHandClaimsRemainChallengeableAndTheFinalHolderCannotPlay() {
        for (playerCount in 2..6) {
            val random = ObservedRandom(81 + playerCount)
            val engine = LastLightEngine(random)
            val roster = roster(playerCount)
            var state = engine.start(roster)
            val cardIds = physicalCards(state).map { it.id }.toSet()
            var plays = 0
            while (!engine.viewFor(state, state.turnPlayerId).forcedChallenge) {
                val actor = assertNotNull(state.turnPlayerId)
                val hand = engine.viewFor(state, actor).yourHand
                state = applied(engine.apply(state, GameAction.Play(actor, hand.take(3).map { it.id })))
                plays++
                assertTrue(plays <= 5 * playerCount - 1)
                assertStateAndViews(engine, state, roster, cardIds, "forced challenge at $playerCount players")
            }
            val claimant = assertNotNull(state.pendingPlay).playerId
            val finalHolder = assertNotNull(state.turnPlayerId)
            assertTrue(state.players.single { it.identity.id == claimant }.hand.isEmpty())
            assertTrue(claimant != finalHolder)
            val view = engine.viewFor(state, finalHolder)
            assertFalse(view.availableActions.canPlay)
            assertTrue(view.availableActions.canChallenge)
            rejectWithoutChanges(engine, random, state, GameAction.Play(finalHolder, view.yourHand.take(1).map { it.id }), GameRejection.MUST_CHALLENGE)
            rejectWithoutChanges(engine, random, state, GameAction.Challenge(claimant), GameRejection.NOT_YOUR_TURN)
            val ended = applied(engine.apply(state, GameAction.Challenge(finalHolder)))
            assertEquals(claimant, assertNotNull(ended.roundOutcome).claimantId)
            assertEquals(finalHolder, ended.roundOutcome.challengerId)
            assertStateAndViews(engine, ended, roster, cardIds, "resolved empty-hand claim")
        }
    }

    @Test
    fun eliminatingTheOpenerRetiresUnplayedCardsWithoutRevealingThem() {
        val random = ObservedRandom(211)
        val engine = LastLightEngine(random)
        var state = engine.start(roster(4))
        state = state.copy(players = state.players.map { it.copy(burnoutStep = 1) })
        val opener = state.players.single { it.identity.id == state.openerPlayerId }
        val card = opener.hand.first { it.rank != CardRank.WILD }
        val differentRank = listOf(CardRank.CROWN, CardRank.MOON, CardRank.STAR).first { it != card.rank }
        state = state.copy(tableRank = differentRank)
        val unplayed = opener.hand.filter { it.id != card.id }
        val allIds = physicalCards(state).map { it.id }.toSet()
        val played = applied(engine.apply(state, GameAction.Play(opener.identity.id, listOf(card.id))))
        val ended = applied(engine.apply(played, GameAction.Challenge(assertNotNull(played.turnPlayerId))))
        assertTrue(ended.players.single { it.identity.id == opener.identity.id }.eliminated)
        assertTrue(ended.players.single { it.identity.id == opener.identity.id }.hand.isEmpty())
        assertTrue(ended.discardedCards.containsAll(unplayed))
        assertEquals(listOf(card), assertNotNull(ended.roundOutcome).revealedCards)
        assertEquals(allIds, physicalCards(ended).map { it.id }.toSet())
        assertEquals(30, physicalCards(ended).size)
        for (recipient in roster(4)) {
            assertEquals(listOf(card), assertNotNull(engine.viewFor(ended, recipient.id).roundOutcome).revealedCards)
        }

        val next = applied(engine.advanceRound(ended))
        val openerIndex = ended.players.indexOfFirst { it.identity.id == opener.identity.id }
        assertEquals(ended.players[(openerIndex + 1) % 4].identity.id, next.openerPlayerId)
        rejectWithoutChanges(engine, random, next, GameAction.Challenge(opener.identity.id), GameRejection.PLAYER_ELIMINATED)
    }

    @Test
    fun aBurnedOutNonemptyChallengerLosesOnlyTheirSeatAndKeepsTheirOtherCardsHidden() {
        val engine = LastLightEngine(Random(413))
        var state = engine.start(roster(3))
        state = state.copy(players = state.players.map { it.copy(burnoutStep = 1) })
        val actor = state.players.single { it.identity.id == state.turnPlayerId }
        val card = actor.hand.first { it.rank != CardRank.WILD }
        state = state.copy(tableRank = card.rank)
        val played = applied(engine.apply(state, GameAction.Play(actor.identity.id, listOf(card.id))))
        val challengerId = assertNotNull(played.turnPlayerId)
        val hiddenHand = played.players.single { it.identity.id == challengerId }.hand
        assertEquals(5, hiddenHand.size)
        val ended = applied(engine.apply(played, GameAction.Challenge(challengerId)))
        assertEquals(challengerId, assertNotNull(ended.roundOutcome).penalizedPlayerId)
        assertTrue(ended.roundOutcome.burnedOut)
        assertTrue(ended.discardedCards.containsAll(hiddenHand))
        assertEquals(listOf(card), ended.roundOutcome.revealedCards)
        assertStateAndViews(engine, ended, roster(3), physicalCards(state).map { it.id }.toSet(), "nonempty challenger elimination")
        assertTrue(engine.viewFor(ended, challengerId).yourHand.isEmpty())
    }

    @Test
    fun callerCollectionsAndRecipientViewsCannotRewriteAcceptedAuthorityStates() {
        val engine = LastLightEngine(Random(719))
        val suppliedRoster = roster(3).toMutableList()
        val initial = engine.start(suppliedRoster)
        val before = snapshot(initial)
        suppliedRoster.clear()
        val actor = assertNotNull(initial.turnPlayerId)
        val selected = engine.viewFor(initial, actor).yourHand.take(2).map { it.id }.toMutableList()
        val selectedIds = selected.toList()
        val played = applied(engine.apply(initial, GameAction.Play(actor, selected)))
        val accepted = snapshot(played)
        val savedView = engine.viewFor(played, actor)
        selected.clear()
        selected.add("replaced-by-caller")
        assertEquals(before, initial)
        assertEquals(selectedIds, assertNotNull(played.pendingPlay).cards.map { it.id })

        attemptClear(played.players)
        attemptClear(played.discardedCards)
        attemptClear(played.undealtCards)
        attemptClear(assertNotNull(played.pendingPlay).cards)
        for (player in played.players) attemptClear(player.hand)
        attemptClear(savedView.yourHand)
        attemptClear(savedView.players)
        assertEquals(accepted, played)
        assertEquals(savedView, engine.viewFor(played, actor))

        val ended = applied(engine.apply(played, GameAction.Challenge(assertNotNull(played.turnPlayerId))))
        val endedBefore = snapshot(ended)
        val outcomeView = engine.viewFor(ended, null)
        attemptClear(assertNotNull(outcomeView.roundOutcome).revealedCards)
        assertEquals(endedBefore, ended)
        assertEquals(outcomeView, engine.viewFor(ended, null))
        assertEquals(accepted, played)
    }

    @Test
    fun rejectedNoiseAndRepeatedViewsDoNotChangeLaterShufflesOrMatchResults() {
        for (seed in 0 until 8) {
            val noisyRandom = ObservedRandom(seed)
            val cleanRandom = ObservedRandom(seed)
            val noisyEngine = LastLightEngine(noisyRandom)
            val cleanEngine = LastLightEngine(cleanRandom)
            var noisy = noisyEngine.start(roster(4))
            var clean = cleanEngine.start(roster(4))
            var actions = 0
            while (noisy.phase != GamePhase.FINISHED) {
                assertEquals(clean, noisy)
                for (recipient in listOf(null, "missing", *roster(4).map { it.id }.toTypedArray())) {
                    noisyEngine.viewFor(noisy, recipient)
                }
                val before = noisyRandom.draws
                if (noisy.phase == GamePhase.ROUND_ENDED) {
                    assertIs<GameDecision.Rejected>(noisyEngine.apply(noisy, GameAction.Challenge("missing")))
                    assertEquals(before, noisyRandom.draws)
                    noisy = applied(noisyEngine.advanceRound(noisy))
                    clean = applied(cleanEngine.advanceRound(clean))
                } else {
                    assertIs<GameDecision.Rejected>(noisyEngine.advanceRound(noisy))
                    assertIs<GameDecision.Rejected>(noisyEngine.apply(noisy, GameAction.Play("missing", listOf("missing-card"))))
                    val actor = assertNotNull(noisy.turnPlayerId)
                    val view = noisyEngine.viewFor(noisy, actor)
                    val action = if (view.availableActions.canChallenge && (actions % 3 == 0 || view.forcedChallenge)) {
                        GameAction.Challenge(actor)
                    } else {
                        GameAction.Play(actor, view.yourHand.take(view.availableActions.maxPlayableCards).map { it.id })
                    }
                    noisy = applied(noisyEngine.apply(noisy, action))
                    clean = applied(cleanEngine.apply(clean, action))
                    assertEquals(before, noisyRandom.draws)
                }
                assertEquals(cleanRandom.draws, noisyRandom.draws)
                actions++
                assertTrue(actions <= 500)
            }
            assertEquals(clean, noisy)
        }
    }

    private fun assertStateAndViews(
        engine: LastLightEngine,
        state: GameState,
        roster: List<PlayerIdentity>,
        roundIds: Set<String>,
        context: String,
    ) {
        assertEquals(roster, state.players.map { it.identity }, context)
        val allCards = physicalCards(state)
        assertEquals(30, allCards.size, context)
        assertEquals(30, allCards.map { it.id }.toSet().size, "A card was duplicated: $context")
        assertEquals(roundIds, allCards.map { it.id }.toSet(), "A card was lost/replaced: $context")
        assertEquals(mapOf(CardRank.CROWN to 9, CardRank.MOON to 9, CardRank.STAR to 9, CardRank.WILD to 3), allCards.groupingBy { it.rank }.eachCount(), context)
        assertTrue(state.tableRank != CardRank.WILD, context)
        for (player in state.players) {
            assertTrue(player.burnoutStep in 1..6, context)
            assertTrue(player.penaltyAttempts in 0..6, context)
            assertEquals(player.penaltyAttempts == player.burnoutStep, player.eliminated, context)
            if (player.eliminated) assertTrue(player.hand.isEmpty(), context)
            else assertTrue(player.penaltyAttempts < player.burnoutStep, context)
            assertTrue(player.hand.size <= 5, context)
        }
        val survivors = state.players.filterNot { it.eliminated }
        val holders = survivors.filter { it.hand.isNotEmpty() }
        val active = state.phase == GamePhase.PLAYING
        if (active) {
            assertTrue(survivors.size >= 2, context)
            assertTrue(holders.isNotEmpty(), "All hands emptied during play: $context")
            assertTrue(holders.any { it.identity.id == state.turnPlayerId }, context)
            assertNull(state.winnerId, context)
            val claim = state.pendingPlay
            if (claim != null) {
                assertTrue(claim.playerId != state.turnPlayerId, "A player faced their own claim: $context")
                assertTrue(survivors.any { it.identity.id == claim.playerId }, context)
                assertTrue(claim.cards.size in 1..3, context)
                assertTrue(state.discardedCards.containsAll(claim.cards), context)
            } else {
                assertTrue(survivors.all { it.hand.size == 5 }, context)
                assertTrue(state.discardedCards.isEmpty(), context)
            }
            if (holders.size == 1) assertNotNull(claim, context)
            if (state.roundOutcome != null) assertTrue(state.roundOutcome.roundNumber < state.roundNumber, context)
        } else {
            assertNull(state.turnPlayerId, context)
            assertNull(state.pendingPlay, context)
            assertEquals(state.roundNumber, assertNotNull(state.roundOutcome, context).roundNumber, context)
            if (state.phase == GamePhase.FINISHED) {
                assertEquals(1, survivors.size, context)
                assertEquals(survivors.single().identity.id, state.winnerId, context)
            } else {
                assertTrue(survivors.size >= 2, context)
                assertNull(state.winnerId, context)
            }
        }

        for (recipient in listOf(null, "missing", *roster.map { it.id }.toTypedArray())) {
            val view = engine.viewFor(state, recipient)
            val owner = state.players.singleOrNull { it.identity.id == recipient }
            assertEquals(owner?.identity?.id, view.viewerId, context)
            assertEquals(if (owner != null && !owner.eliminated) owner.hand else emptyList(), view.yourHand, context)
            assertEquals(state.phase, view.phase, context)
            assertEquals(state.roundNumber, view.roundNumber, context)
            assertEquals(state.tableRank, view.tableRank, context)
            assertEquals(state.turnPlayerId, view.turnPlayerId, context)
            assertEquals(state.winnerId, view.winnerId, context)
            assertEquals(state.roundOutcome, view.roundOutcome, context)
            assertEquals(state.pendingPlay?.let { PublicClaim(it.playerId, it.cards.size) }, view.latestClaim, context)
            assertEquals(state.players.map { PlayerView(it.identity.id, it.identity.displayName, it.hand.size, it.penaltyAttempts, it.eliminated) }, view.players, context)
            val isActor = active && owner != null && !owner.eliminated && owner.identity.id == state.turnPlayerId
            val canPlay = isActor && holders.size >= 2
            val canChallenge = isActor && state.pendingPlay != null
            assertEquals(active && holders.size == 1, view.forcedChallenge, context)
            assertEquals(canPlay, view.availableActions.canPlay, context)
            assertEquals(canChallenge, view.availableActions.canChallenge, context)
            assertEquals(if (canPlay) minOf(3, assertNotNull(owner).hand.size) else 0, view.availableActions.maxPlayableCards, context)
            if (isActor) assertTrue(canPlay || canChallenge, "Current player has no legal action: $context")
        }
    }

    private fun rejectWithoutChanges(
        engine: LastLightEngine,
        random: ObservedRandom,
        state: GameState,
        action: GameAction,
        error: GameRejection,
    ) {
        val before = snapshot(state)
        val draws = random.draws
        assertEquals(GameDecision.Rejected(error), engine.apply(state, action))
        assertEquals(before, state, "A rejected action mutated authority state")
        assertEquals(draws, random.draws, "A rejected action consumed randomness")
    }

    private fun snapshot(state: GameState): GameState = state.copy(
        players = state.players.map { it.copy(hand = it.hand.toList()) },
        pendingPlay = state.pendingPlay?.let { it.copy(cards = it.cards.toList()) },
        discardedCards = state.discardedCards.toList(),
        undealtCards = state.undealtCards.toList(),
        roundOutcome = state.roundOutcome?.let { it.copy(revealedCards = it.revealedCards.toList()) },
    )

    private fun physicalCards(state: GameState): List<Card> =
        state.players.flatMap { it.hand } + state.discardedCards + state.undealtCards

    private fun roster(size: Int): List<PlayerIdentity> = List(size) { PlayerIdentity("player-$it", "Player ${it + 1}") }

    private fun applied(decision: GameDecision, context: String = ""): GameState =
        assertIs<GameDecision.Applied>(decision, context).state

    private fun <T> attemptClear(values: List<T>) {
        val mutable = values as? MutableList<T> ?: return
        runCatching { mutable.clear() }
    }

    private class ObservedRandom(seed: Int) : Random() {
        private val delegate = Random(seed)
        var draws = 0
            private set

        override fun nextBits(bitCount: Int): Int {
            draws++
            return delegate.nextBits(bitCount)
        }
    }
}
