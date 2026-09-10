extends RefCounted

## Structural/privacy validation of the version-one recipient view, never a second rule engine.
const RANKS := ["CROWN", "MOON", "STAR", "WILD"]
const TABLE_RANKS := ["CROWN", "MOON", "STAR"]
const LONG_MAX := "9223372036854775807"


static func fields(value: Variant, names: Array) -> bool:
	if not value is Dictionary or value.size() != names.size():
		return false
	for name in names:
		if not value.has(name):
			return false
	return true


static func counter(value: Variant) -> bool:
	if not value is String or value.is_empty() or value.length() > 19:
		return false
	if value.length() > 1 and value.begins_with("0"):
		return false
	for index in range(value.length()):
		var code: int = value.unicode_at(index)
		if code < 48 or code > 57:
			return false
	return value.length() < 19 or value <= LONG_MAX


static func integer(value: Variant, minimum: int, maximum: int) -> bool:
	return (value is int or value is float) and is_finite(value) \
		and value >= minimum and value <= maximum and value == floor(value)


static func text(value: Variant, limit: int) -> bool:
	if not value is String or value.strip_edges().is_empty():
		return false
	var utf16_length := 0
	for index in range(value.length()):
		var code: int = value.unicode_at(index)
		if code < 32 or code == 127:
			return false
		utf16_length += 2 if code > 0xFFFF else 1
	return utf16_length <= limit


static func preferences(value: Variant) -> bool:
	return fields(value, ["reduceMotion", "soundEnabled", "textScale"]) \
		and value.reduceMotion is bool and value.soundEnabled is bool \
		and (value.textScale is int or value.textScale is float) \
		and is_finite(value.textScale) and value.textScale >= 1 and value.textScale <= 2


static func payload(value: Variant) -> bool:
	if not fields(value, ["game", "controls"]):
		return false
	if not fields(value.controls, ["isHost", "canSendAction", "canAdvanceRound", "canReturnToLobby"]):
		return false
	for flag in value.controls.values():
		if not flag is bool:
			return false
	if not game(value.game):
		return false
	return (not value.controls.isHost or value.game.viewerId != null) \
		and (not value.controls.canAdvanceRound or (value.controls.isHost and value.game.phase == "ROUND_ENDED")) \
		and (not value.controls.canReturnToLobby or value.controls.isHost)


static func game(value: Variant) -> bool:
	if not fields(value, ["viewerId", "phase", "roundNumber", "tableRank", "players", "yourHand",
		"turnPlayerId", "latestClaim", "forcedChallenge", "availableActions", "roundOutcome", "winnerId"]):
		return false
	if value.phase not in ["PLAYING", "ROUND_ENDED", "FINISHED"] \
		or not integer(value.roundNumber, 1, 2_147_483_647) or value.tableRank not in TABLE_RANKS:
		return false
	if not value.players is Array or value.players.size() < 2 or value.players.size() > 6:
		return false
	var players := {}
	for player in value.players:
		if not fields(player, ["id", "displayName", "handCount", "penaltyAttempts", "eliminated"]):
			return false
		if not text(player.id, 64) or not text(player.displayName, 24) or players.has(player.id) \
			or not integer(player.handCount, 0, 5) or not integer(player.penaltyAttempts, 0, 6) \
			or not player.eliminated is bool:
			return false
		if player.eliminated and player.handCount != 0:
			return false
		players[player.id] = player
	for id_value in [value.viewerId, value.turnPlayerId, value.winnerId]:
		if id_value != null and (not id_value is String or not players.has(id_value)):
			return false
	if not cards(value.yourHand, 0, 5):
		return false
	if value.viewerId == null:
		if not value.yourHand.is_empty():
			return false
	elif players[value.viewerId].eliminated:
		if not value.yourHand.is_empty():
			return false
	elif value.yourHand.size() != int(players[value.viewerId].handCount):
		return false
	if not value.forcedChallenge is bool or not fields(value.availableActions,
		["canPlay", "canChallenge", "maxPlayableCards"]):
		return false
	var actions: Dictionary = value.availableActions
	if not actions.canPlay is bool or not actions.canChallenge is bool \
		or not integer(actions.maxPlayableCards, 0, 3):
		return false
	if value.latestClaim != null:
		if not fields(value.latestClaim, ["playerId", "cardCount"]) \
			or not value.latestClaim.playerId is String or not players.has(value.latestClaim.playerId) \
			or not integer(value.latestClaim.cardCount, 1, 3):
			return false
	if value.roundOutcome != null:
		if not outcome(value.roundOutcome, players, int(value.roundNumber)):
			return false
		if value.phase != "PLAYING" and value.roundOutcome.roundNumber != value.roundNumber:
			return false
	var survivors: Array = value.players.filter(func(player): return not player.eliminated)
	if value.phase == "PLAYING":
		if value.turnPlayerId == null or players[value.turnPlayerId].eliminated \
			or players[value.turnPlayerId].handCount == 0 or value.winnerId != null:
			return false
	else:
		if value.turnPlayerId != null or value.latestClaim != null or value.forcedChallenge or value.roundOutcome == null:
			return false
	if value.phase == "FINISHED":
		if survivors.size() != 1 or value.winnerId != survivors[0].id:
			return false
	elif value.winnerId != null:
		return false
	if value.forcedChallenge and survivors.filter(func(player): return player.handCount > 0).size() != 1:
		return false
	var actor: bool = value.phase == "PLAYING" and value.viewerId != null \
		and not players[value.viewerId].eliminated and value.viewerId == value.turnPlayerId
	if actions.canPlay:
		if not actor or value.forcedChallenge or value.yourHand.is_empty() \
			or actions.maxPlayableCards < 1 or actions.maxPlayableCards > mini(3, value.yourHand.size()):
			return false
	elif actions.maxPlayableCards != 0:
		return false
	if actions.canChallenge and (not actor or value.latestClaim == null or value.latestClaim.playerId == value.viewerId):
		return false
	return true


static func cards(value: Variant, minimum: int, maximum: int) -> bool:
	if not value is Array or value.size() < minimum or value.size() > maximum:
		return false
	var ids := {}
	for card in value:
		if not fields(card, ["id", "rank"]) or not text(card.id, 64) \
			or card.rank not in RANKS or ids.has(card.id):
			return false
		ids[card.id] = true
	return true


static func outcome(value: Variant, players: Dictionary, current_round: int) -> bool:
	if not fields(value, ["roundNumber", "tableRank", "claimantId", "challengerId", "revealedCards",
		"truthful", "penalizedPlayerId", "penaltyAttempt", "burnedOut"]):
		return false
	if not integer(value.roundNumber, 1, current_round) or value.tableRank not in TABLE_RANKS \
		or not cards(value.revealedCards, 1, 3) or not value.truthful is bool \
		or not value.burnedOut is bool or not integer(value.penaltyAttempt, 1, 6):
		return false
	for key in ["claimantId", "challengerId", "penalizedPlayerId"]:
		if not value[key] is String or not players.has(value[key]):
			return false
	return value.claimantId != value.challengerId
