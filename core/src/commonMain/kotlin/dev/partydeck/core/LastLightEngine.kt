package dev.partydeck.core

import kotlin.random.Random

/**
 * Host-authoritative Last Light rules. The caller serializes operations and supplies randomness.
 * Live matches use a platform-CSPRNG-backed [random]; deterministic sources are useful for tests.
 * Screens, clients, and bots receive [viewFor] results, never [GameState].
 */
class LastLightEngine(private val random: Random) {

    /** Starts a match. Invalid rosters fail before consuming any random values. */
    fun start(players: List<PlayerIdentity>): GameState {
        val roster = players.immutableSnapshot()
        validateRoster(roster)
        val seats = roster.map { identity ->
            PlayerState(
                identity = identity,
                hand = emptyList(),
                penaltyAttempts = 0,
                burnoutStep = random.nextInt(LastLightRules.FUSE_LIGHTS) + 1,
                eliminated = false,
            )
        }.immutableSnapshot()
        val opener = seats[random.nextInt(seats.size)].identity.id
        return dealRound(seats, roundNumber = 1, openerPlayerId = opener, previousOutcome = null)
    }

    /** Validates and applies one player action. No action consumes randomness. */
    fun apply(state: GameState, action: GameAction): GameDecision {
        if (state.phase == GamePhase.FINISHED) return reject(GameRejection.GAME_FINISHED)
        if (state.phase != GamePhase.PLAYING) return reject(GameRejection.ROUND_NOT_PLAYING)
        val actor = state.players.firstOrNull { it.identity.id == action.playerId }
            ?: return reject(GameRejection.UNKNOWN_PLAYER)
        if (actor.eliminated) return reject(GameRejection.PLAYER_ELIMINATED)
        if (state.turnPlayerId != actor.identity.id) return reject(GameRejection.NOT_YOUR_TURN)

        return when (action) {
            is GameAction.Play -> play(state, actor, action.cardIds)
            is GameAction.Challenge -> challenge(state, actor)
        }
    }

    /** Host permission and request replay checks belong to the session, including for an eliminated host. */
    fun advanceRound(state: GameState): GameDecision {
        if (state.phase == GamePhase.FINISHED) return reject(GameRejection.GAME_FINISHED)
        if (state.phase != GamePhase.ROUND_ENDED) return reject(GameRejection.ROUND_NOT_ENDED)
        val opener = nextSeatAfter(state.players, state.openerPlayerId) { !it.eliminated }
        return GameDecision.Applied(
            dealRound(
                players = state.players,
                roundNumber = state.roundNumber + 1,
                openerPlayerId = opener.identity.id,
                previousOutcome = state.roundOutcome,
            ),
        )
    }

    /** Produces a detached, recipient-specific view without revealing authority-only information. */
    fun viewFor(state: GameState, viewerId: PlayerId?): GameView {
        val viewer = state.players.firstOrNull { it.identity.id == viewerId }
        val playing = state.phase == GamePhase.PLAYING
        val forcedChallenge = playing && nonemptySurvivors(state.players) == 1
        val isActor = playing && viewer != null && !viewer.eliminated &&
            viewer.identity.id == state.turnPlayerId
        val canPlay = isActor && !forcedChallenge && viewer.hand.isNotEmpty()
        val canChallenge = isActor && state.pendingPlay != null &&
            state.pendingPlay.playerId != viewer.identity.id

        return GameView(
            viewerId = viewer?.identity?.id,
            phase = state.phase,
            roundNumber = state.roundNumber,
            tableRank = state.tableRank,
            players = state.players.map {
                PlayerView(
                    id = it.identity.id,
                    displayName = it.identity.displayName,
                    handCount = it.hand.size,
                    penaltyAttempts = it.penaltyAttempts,
                    eliminated = it.eliminated,
                )
            }.immutableSnapshot(),
            yourHand = if (viewer != null && !viewer.eliminated) viewer.hand.immutableSnapshot() else emptyList(),
            turnPlayerId = state.turnPlayerId,
            latestClaim = state.pendingPlay?.let { PublicClaim(it.playerId, it.cards.size) },
            forcedChallenge = forcedChallenge,
            availableActions = AvailableActions(
                canPlay = canPlay,
                canChallenge = canChallenge,
                maxPlayableCards = if (canPlay) minOf(viewer.hand.size, LastLightRules.MAX_PLAY_CARDS) else 0,
            ),
            roundOutcome = state.roundOutcome?.let {
                it.copy(revealedCards = it.revealedCards.immutableSnapshot())
            },
            winnerId = state.winnerId,
        )
    }

    private fun play(state: GameState, actor: PlayerState, selectedIds: List<CardId>): GameDecision {
        if (nonemptySurvivors(state.players) < 2) return reject(GameRejection.MUST_CHALLENGE)
        if (selectedIds.size !in 1..LastLightRules.MAX_PLAY_CARDS) {
            return reject(GameRejection.INVALID_CARD_COUNT)
        }
        val selection = selectedIds.immutableSnapshot()
        val distinctIds = selection.toSet()
        if (distinctIds.size != selection.size) return reject(GameRejection.DUPLICATE_CARD)
        if (distinctIds.any { id -> actor.hand.none { it.id == id } }) {
            return reject(GameRejection.CARD_NOT_IN_HAND)
        }

        val cards = selection.map { id -> actor.hand.first { it.id == id } }.immutableSnapshot()
        val players = state.players.map { player ->
            if (player.identity.id == actor.identity.id) {
                player.copy(hand = player.hand.filterNot { it.id in distinctIds }.immutableSnapshot())
            } else {
                player
            }
        }.immutableSnapshot()
        val nextActor = nextSeatAfter(players, actor.identity.id) { !it.eliminated && it.hand.isNotEmpty() }
        return GameDecision.Applied(
            state.copy(
                players = players,
                turnPlayerId = nextActor.identity.id,
                pendingPlay = PendingPlay(actor.identity.id, cards),
                discardedCards = (state.discardedCards + cards).immutableSnapshot(),
            ),
        )
    }

    private fun challenge(state: GameState, challenger: PlayerState): GameDecision {
        val claim = state.pendingPlay ?: return reject(GameRejection.NO_CLAIM)
        if (claim.playerId == challenger.identity.id) return reject(GameRejection.CANNOT_CHALLENGE_SELF)
        val truthful = claim.cards.all { it.rank == state.tableRank || it.rank == CardRank.WILD }
        val penalizedId = if (truthful) challenger.identity.id else claim.playerId
        val penalized = state.players.first { it.identity.id == penalizedId }
        val penaltyAttempt = penalized.penaltyAttempts + 1
        val burnedOut = penaltyAttempt == penalized.burnoutStep
        val players = state.players.map { player ->
            if (player.identity.id == penalizedId) {
                player.copy(
                    hand = if (burnedOut) emptyList() else player.hand,
                    penaltyAttempts = penaltyAttempt,
                    eliminated = burnedOut,
                )
            } else {
                player
            }
        }.immutableSnapshot()
        val survivors = players.filterNot { it.eliminated }
        val winner = survivors.singleOrNull()?.identity?.id
        val outcome = RoundOutcome(
            roundNumber = state.roundNumber,
            tableRank = state.tableRank,
            claimantId = claim.playerId,
            challengerId = challenger.identity.id,
            revealedCards = claim.cards.immutableSnapshot(),
            truthful = truthful,
            penalizedPlayerId = penalizedId,
            penaltyAttempt = penaltyAttempt,
            burnedOut = burnedOut,
        )
        return GameDecision.Applied(
            state.copy(
                players = players,
                phase = if (winner != null) GamePhase.FINISHED else GamePhase.ROUND_ENDED,
                turnPlayerId = null,
                pendingPlay = null,
                discardedCards = if (burnedOut) {
                    (state.discardedCards + penalized.hand).immutableSnapshot()
                } else {
                    state.discardedCards
                },
                roundOutcome = outcome,
                winnerId = winner,
            ),
        )
    }

    private fun dealRound(
        players: List<PlayerState>,
        roundNumber: Int,
        openerPlayerId: PlayerId,
        previousOutcome: RoundOutcome?,
    ): GameState {
        val tableRank = TABLE_RANKS[random.nextInt(TABLE_RANKS.size)]
        val deck = shuffledDeck(roundNumber)
        val openingIndex = players.indexOfFirst { it.identity.id == openerPlayerId }
        val dealingOrder = players.indices.map { (openingIndex + it) % players.size }
            .filterNot { players[it].eliminated }
        val hands = List(players.size) { mutableListOf<Card>() }
        var nextCard = 0
        repeat(LastLightRules.HAND_SIZE) {
            for (seat in dealingOrder) hands[seat].add(deck[nextCard++])
        }
        val dealtPlayers = players.mapIndexed { index, player ->
            player.copy(hand = hands[index].immutableSnapshot())
        }.immutableSnapshot()

        return GameState(
            players = dealtPlayers,
            phase = GamePhase.PLAYING,
            roundNumber = roundNumber,
            tableRank = tableRank,
            openerPlayerId = openerPlayerId,
            turnPlayerId = openerPlayerId,
            pendingPlay = null,
            discardedCards = emptyList(),
            undealtCards = deck.drop(nextCard).immutableSnapshot(),
            roundOutcome = previousOutcome,
            winnerId = null,
        )
    }

    private fun shuffledDeck(roundNumber: Int): List<Card> {
        val ranks = mutableListOf<CardRank>()
        for (rank in TABLE_RANKS) repeat(LastLightRules.COPIES_PER_RANK) { ranks.add(rank) }
        repeat(LastLightRules.WILD_CARDS) { ranks.add(CardRank.WILD) }
        // Fisher–Yates with bounded draws. IDs are assigned afterwards, so they do not encode ranks.
        for (last in ranks.lastIndex downTo 1) {
            val swapWith = random.nextInt(last + 1)
            val previous = ranks[last]
            ranks[last] = ranks[swapWith]
            ranks[swapWith] = previous
        }
        return ranks.mapIndexed { index, rank -> Card(id = "r$roundNumber-c$index", rank = rank) }
            .immutableSnapshot()
    }

    private fun validateRoster(players: List<PlayerIdentity>) {
        require(players.size in LastLightRules.MIN_PLAYERS..LastLightRules.MAX_PLAYERS) {
            "Last Light requires two to six players."
        }
        require(players.map { it.id }.toSet().size == players.size) { "Player IDs must be unique." }
        for (player in players) {
            require(
                player.id.isNotBlank() && player.id.length <= LastLightRules.MAX_PLAYER_ID_LENGTH &&
                    !player.id.hasAsciiControls(),
            ) { "Player IDs must be nonblank, at most 64 characters, and contain no control characters." }
            require(
                player.displayName.isNotBlank() &&
                    player.displayName.length <= LastLightRules.MAX_DISPLAY_NAME_LENGTH &&
                    !player.displayName.hasAsciiControls(),
            ) { "Display names must be nonblank, at most 24 characters, and contain no control characters." }
        }
    }

    private fun String.hasAsciiControls(): Boolean = any { it.code < 32 || it.code == 127 }

    private fun nonemptySurvivors(players: List<PlayerState>): Int =
        players.count { !it.eliminated && it.hand.isNotEmpty() }

    private fun nextSeatAfter(
        players: List<PlayerState>,
        playerId: PlayerId,
        eligible: (PlayerState) -> Boolean,
    ): PlayerState {
        val previousIndex = players.indexOfFirst { it.identity.id == playerId }
        for (offset in 1 until players.size) {
            val player = players[(previousIndex + offset) % players.size]
            if (eligible(player)) return player
        }
        error("A valid active round must have another eligible player.")
    }

    private fun reject(reason: GameRejection): GameDecision = GameDecision.Rejected(reason)

    private companion object {
        val TABLE_RANKS = listOf(CardRank.CROWN, CardRank.MOON, CardRank.STAR)
    }
}
