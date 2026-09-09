package dev.partydeck.core

import kotlinx.serialization.Serializable

typealias PlayerId = String
typealias CardId = String

@Serializable
enum class CardRank {
    CROWN,
    MOON,
    STAR,
    WILD,
}

@Serializable
enum class GamePhase {
    PLAYING,
    ROUND_ENDED,
    FINISHED,
}

@Serializable
data class PlayerIdentity(
    val id: PlayerId,
    val displayName: String,
)

@Serializable
data class Card(
    val id: CardId,
    val rank: CardRank,
)

/** Public seat information. Fuse burnout steps and other hands never appear here. */
@Serializable
data class PlayerView(
    val id: PlayerId,
    val displayName: String,
    val handCount: Int,
    val penaltyAttempts: Int,
    val eliminated: Boolean,
)

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
@Serializable
data class PublicClaim(
    val playerId: PlayerId,
    val cardCount: Int,
)

/** Actions available to this view's recipient, rather than to any other player. */
@Serializable
data class AvailableActions(
    val canPlay: Boolean = false,
    val canChallenge: Boolean = false,
    val maxPlayableCards: Int = 0,
)

/** Public proof and outcome of one resolved challenge. */
@Serializable
data class RoundOutcome(
    val roundNumber: Int,
    val tableRank: CardRank,
    val claimantId: PlayerId,
    val challengerId: PlayerId,
    val revealedCards: List<Card>,
    val truthful: Boolean,
    val penalizedPlayerId: PlayerId,
    val penaltyAttempt: Int,
    val burnedOut: Boolean,
)

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
@Serializable
data class GameView(
    val viewerId: PlayerId?,
    val phase: GamePhase,
    val roundNumber: Int,
    val tableRank: CardRank,
    val players: List<PlayerView>,
    val yourHand: List<Card>,
    val turnPlayerId: PlayerId?,
    val latestClaim: PublicClaim?,
    val forcedChallenge: Boolean,
    val availableActions: AvailableActions,
    val roundOutcome: RoundOutcome?,
    val winnerId: PlayerId?,
)
