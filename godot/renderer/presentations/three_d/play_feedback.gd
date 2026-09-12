extends Node
## Observe every accepted state on the CPU; consume only the latest fresh play.
## Only public seat counts/claim/turn data are retained, never hands or card IDs.
## The table owns sound and the final pile. This helper only moves public backs.
## Godot 4.7.2 API sources:
## https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Tween.xml
## https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Node.xml
## https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Transform3D.xml

const PUBLIC_BACK_GROUP := "partydeck_play_back"
const MAX_CARDS := 3
const TRAVEL_SECONDS := 0.30
const SETTLE_SECONDS := 0.09
const STAGGER_SECONDS := 0.025
const ARC_HEIGHT := 0.28

var _previous: Dictionary = {}
var _revision := -1
var _pending_play: Dictionary = {}
var _active := false
var _hand_visible := false
var _cancel_requested := false
var _tween: Tween
var _moving: Array[Dictionary] = []


func observe(state: Dictionary, revision: String) -> void:
	# store_state can run without a current graphics context. Do not touch nodes,
	# Tweens, materials, audio or RenderingServer from this observation path.
	_active = bool(state.get("foreground", false)) and not bool(state.get("closed", true)) \
		and not bool(state.get("returnToLobbyPending", false))
	var hand_visible: bool = state.get("handVisible", false)
	if not _active:
		_previous.clear()
		_pending_play.clear()
		_revision = -1
		_hand_visible = hand_visible
		_cancel_requested = true
		return
	if bool(state.get("reduceMotion", false)):
		_cancel_requested = true
	var next_revision := revision.to_int()
	if next_revision <= _revision:
		# Authoritative views conceal the hand at a NEW revision. A same-revision
		# Cover action instead cancels feedback without inventing another play.
		if next_revision == _revision and _hand_visible and not hand_visible:
			_pending_play.clear()
			_cancel_requested = true
		_hand_visible = hand_visible
		return
	var current := _public_frame(state.get("game", {}))
	# A controls-only view can follow a play before either one is drawn. Keep
	# that single cue while the public pile still represents the same event.
	if current != _previous:
		_pending_play = _fresh_play(_previous, current, revision)
	_previous = current
	_revision = next_revision
	_hand_visible = hand_visible
	_cancel_requested = true


func take_play() -> Dictionary:
	var play := _pending_play
	_pending_play = {}
	return play


func animate_play(cards: Array, origin: Vector3, reduce_motion: bool) -> bool:
	# The caller has already applied the authoritative view and laid out its
	# face-down pile. State/input never waits for this optional presentation.
	cancel()
	if reduce_motion or not _active or not is_inside_tree() or not origin.is_finite() \
		or cards.is_empty() or cards.size() > MAX_CARDS:
		return false
	for card in cards:
		if not is_instance_valid(card) or not card is Node3D or not card.is_inside_tree() \
			or card.is_queued_for_deletion() or not card.is_in_group(PUBLIC_BACK_GROUP):
			return false
	for index in range(cards.size()):
		var card: Node3D = cards[index]
		var target := card.global_transform
		var start := target
		start.origin = origin + Vector3((index - (cards.size() - 1) / 2.0) * 0.12, index * 0.025, 0)
		start.basis = target.basis.rotated(Vector3.UP, deg_to_rad(-16.0 + index * 6.0))
		_moving.append({"card": card, "start": start, "target": target, "delay": index * STAGGER_SECONDS})
		card.global_transform = start
	var duration := TRAVEL_SECONDS + SETTLE_SECONDS + (cards.size() - 1) * STAGGER_SECONDS
	_tween = create_tween()
	_tween.tween_method(_advance, 0.0, duration, duration)
	_tween.finished.connect(_finish)
	return true


func cancel() -> void:
	if _tween != null and _tween.is_valid():
		_tween.kill()
	_tween = null
	_settle_cards()
	_cancel_requested = false


func is_animating() -> bool:
	return _tween != null and _tween.is_valid()


func _advance(elapsed: float) -> void:
	if _cancel_requested or not _active:
		cancel()
		return
	for moving in _moving:
		var card: Node3D = moving.card
		if not is_instance_valid(card) or not card.is_inside_tree() or card.is_queued_for_deletion():
			cancel()
			return
	for moving in _moving:
		var travel := clampf((elapsed - float(moving.delay)) / TRAVEL_SECONDS, 0.0, 1.0)
		var eased := 1.0 - pow(1.0 - travel, 3.0)
		var start: Transform3D = moving.start
		var target: Transform3D = moving.target
		var pose := start.interpolate_with(target, eased)
		pose.origin.y += sin(PI * travel) * ARC_HEIGHT
		if travel >= 1.0:
			var settle := clampf((elapsed - float(moving.delay) - TRAVEL_SECONDS) / SETTLE_SECONDS, 0.0, 1.0)
			pose.origin.y += sin(PI * settle) * (1.0 - settle) * 0.035
		moving.card.global_transform = pose


func _finish() -> void:
	# A manually stepped completed Tween stays valid until the tree's next
	# Tween pass. Release our finished effect immediately, including when paused.
	cancel()


func _settle_cards() -> void:
	for moving in _moving:
		var card: Node3D = moving.card
		if is_instance_valid(card) and card.is_inside_tree() and not card.is_queued_for_deletion():
			card.global_transform = moving.target
	_moving.clear()


func _exit_tree() -> void:
	cancel()
	_previous.clear()
	_pending_play.clear()
	_revision = -1
	_active = false
	_hand_visible = false


static func _public_frame(game: Dictionary) -> Dictionary:
	if game.is_empty():
		return {}
	var players: Dictionary = {}
	for player in game.get("players", []):
		players[player.id] = {"handCount": int(player.handCount),
			"penaltyAttempts": int(player.penaltyAttempts), "eliminated": bool(player.eliminated)}
	var claim: Dictionary = game.latestClaim if game.get("latestClaim") is Dictionary else {}
	return {"round": int(game.get("roundNumber", 0)), "phase": game.get("phase", ""),
		"viewer": game.get("viewerId"), "turn": game.get("turnPlayerId"), "players": players,
		"claimant": claim.get("playerId", ""), "count": int(claim.get("cardCount", 0))}


static func _fresh_play(previous: Dictionary, current: Dictionary, revision: String) -> Dictionary:
	if previous.is_empty() or current.is_empty() or previous.phase != "PLAYING" or current.phase != "PLAYING" \
		or previous.round != current.round or previous.viewer != current.viewer:
		return {}
	var claimant: String = current.claimant
	var count: int = current.count
	var before: Dictionary = previous.players
	var after: Dictionary = current.players
	if count < 1 or count > MAX_CARDS or claimant.is_empty() or previous.turn != claimant \
		or current.turn == claimant or before.size() != after.size() or not before.has(claimant):
		return {}
	# A play changes exactly the acting seat's public count. Multi-play jumps,
	# redeals, roster changes and result backfill establish a silent new baseline.
	for id_value in before:
		if not after.has(id_value) or before[id_value].eliminated != after[id_value].eliminated \
			or before[id_value].penaltyAttempts != after[id_value].penaltyAttempts:
			return {}
		var removed: int = before[id_value].handCount - after[id_value].handCount
		if removed != (count if id_value == claimant else 0):
			return {}
	return {"playerId": claimant, "cardCount": count, "revision": revision}
