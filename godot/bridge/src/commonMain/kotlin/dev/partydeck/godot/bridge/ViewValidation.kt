package dev.partydeck.godot.bridge

import dev.partydeck.core.Card
import dev.partydeck.core.CardRank
import dev.partydeck.core.GamePhase
import dev.partydeck.core.LastLightRules

/** Shape/reference validation only; challenge results and game rules remain in core/session. */
internal fun validateSnapshot(snapshot: PresentationSnapshot) {
    val view = snapshot.game
    val players = view.players
    wireRequire(players.size in LastLightRules.MIN_PLAYERS..LastLightRules.MAX_PLAYERS, "Invalid seat count.")
    wireRequire(players.map { it.id }.distinct().size == players.size, "Duplicate player identifier.")
    players.forEach {
        validateText(it.id, LastLightRules.MAX_PLAYER_ID_LENGTH, "player identifier")
        validateText(it.displayName, LastLightRules.MAX_DISPLAY_NAME_LENGTH, "display name")
        wireRequire(it.handCount in 0..LastLightRules.HAND_SIZE && it.penaltyAttempts in 0..LastLightRules.FUSE_LIGHTS, "Invalid public seat count.")
        wireRequire(!it.eliminated || it.handCount == 0, "An eliminated seat cannot have a hand.")
    }
    wireRequire(view.roundNumber >= 1 && view.tableRank != CardRank.WILD, "Invalid round metadata.")
    val ids = players.map { it.id }.toSet()
    val viewer = view.viewerId?.let { id ->
        players.singleOrNull { it.id == id } ?: throw BridgeFormatException("Unknown view recipient.")
    }
    wireRequire(view.yourHand.size <= LastLightRules.HAND_SIZE, "Private hand exceeds its limit.")
    validateCards(view.yourHand)
    if (viewer == null || viewer.eliminated) {
        wireRequire(view.yourHand.isEmpty(), "An unknown or eliminated recipient cannot receive a hand.")
    } else {
        wireRequire(view.yourHand.size == viewer.handCount, "Recipient hand does not match its public count.")
    }
    val turn = view.turnPlayerId?.let { id ->
        players.singleOrNull { it.id == id } ?: throw BridgeFormatException("Unknown turn seat.")
    }
    if (view.phase == GamePhase.PLAYING) {
        wireRequire(turn != null && !turn.eliminated && turn.handCount > 0 && view.winnerId == null, "Invalid playing turn.")
    } else {
        wireRequire(turn == null && view.latestClaim == null && !view.forcedChallenge, "Inactive round has active-turn data.")
        wireRequire(view.roundOutcome != null, "A round result must include public proof.")
    }
    if (view.phase == GamePhase.FINISHED) {
        wireRequire(view.winnerId in ids && players.singleOrNull { !it.eliminated }?.id == view.winnerId, "Invalid public winner.")
    } else wireRequire(view.winnerId == null, "Unfinished match has a winner.")

    val claim = view.latestClaim
    claim?.let {
        wireRequire(it.playerId in ids && it.cardCount in 1..LastLightRules.MAX_PLAY_CARDS, "Invalid public claim.")
    }
    wireRequire(!view.forcedChallenge || (view.phase == GamePhase.PLAYING && players.count { !it.eliminated && it.handCount > 0 } == 1), "Invalid forced-challenge flag.")
    val isActor = view.phase == GamePhase.PLAYING && viewer != null && !viewer.eliminated && viewer.id == view.turnPlayerId
    val actions = view.availableActions
    if (actions.canPlay) {
        wireRequire(isActor && !view.forcedChallenge && view.yourHand.isNotEmpty(), "Play is unavailable to this recipient.")
        wireRequire(actions.maxPlayableCards in 1..minOf(LastLightRules.MAX_PLAY_CARDS, view.yourHand.size), "Invalid maximum selection count.")
    } else wireRequire(actions.maxPlayableCards == 0, "Disabled play has a nonzero selection limit.")
    if (actions.canChallenge) {
        wireRequire(isActor && claim != null && claim.playerId != view.viewerId, "Challenge is unavailable to this recipient.")
    }
    // False action flags are valid even on this recipient's turn: a session may be paused.
    view.roundOutcome?.let {
        wireRequire(it.roundNumber in 1..view.roundNumber && it.tableRank != CardRank.WILD, "Invalid public proof round.")
        wireRequire(view.phase == GamePhase.PLAYING || it.roundNumber == view.roundNumber, "Result proof belongs to another round.")
        wireRequire(it.claimantId in ids && it.challengerId in ids && it.claimantId != it.challengerId && it.penalizedPlayerId in ids, "Invalid public proof seats.")
        wireRequire(it.revealedCards.size in 1..LastLightRules.MAX_PLAY_CARDS && it.penaltyAttempt in 1..LastLightRules.FUSE_LIGHTS, "Invalid public proof count.")
        validateCards(it.revealedCards)
    }
    val controls = snapshot.controls
    wireRequire(!controls.isHost || viewer != null, "Host controls require a known recipient.")
    wireRequire(!controls.canAdvanceRound || (controls.isHost && view.phase == GamePhase.ROUND_ENDED), "Invalid advance-round permission.")
    wireRequire(!controls.canReturnToLobby || controls.isHost, "Invalid return-to-lobby permission.")
}

private fun validateCards(cards: List<Card>) {
    wireRequire(cards.map { it.id }.distinct().size == cards.size, "Duplicate card identifier.")
    cards.forEach { validateText(it.id, 64, "card identifier") }
}
