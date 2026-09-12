extends SceneTree
## Public-event and real Tween behavior only; headless execution is not pixel/audio evidence.

const PlayFeedback = preload("res://presentations/three_d/play_feedback.gd")

var _helper: Node
var _world: Node3D
var _checks: Array[Dictionary] = []
var _failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_helper = PlayFeedback.new()
	root.add_child(_helper)
	_world = Node3D.new()
	root.add_child(_world)
	_world.position = Vector3(0.7, 0, -0.2)
	_check_public_events()
	_check_lifecycle_observation()
	_check_motion()
	# process_frame is emitted BEFORE the tree's Tween pass. Allow that pass
	# to complete before checking removal from get_processed_tweens().
	await process_frame
	await process_frame
	_check(get_processed_tweens().is_empty(), "no Tween survives settled/cancelled feedback")
	_check(not _helper.is_processing(), "helper never enables a frame process loop")
	_helper.queue_free()
	_world.queue_free()
	await process_frame
	print(JSON.stringify({"result": "passed" if _failures == 0 else "failed",
		"godotVersion": Engine.get_version_info().string, "checks": _checks,
		"limitations": "Headless public-event and real Node/Tween behavior; no rendered pixels, native device or audible output."}))
	quit(0 if _failures == 0 else 1)


func _check_public_events() -> void:
	var opening := _state(_game([5, 5, 5], 0))
	_helper.observe(opening, "10")
	_check(_helper.take_play().is_empty(), "first attach establishes a silent baseline")
	_helper.observe(opening, "11")
	_check(_helper.take_play().is_empty(), "newer revision with identical public game is silent")
	var pending := opening.duplicate(true)
	pending.controls.canSendAction = false
	pending.selectedCardIds = []
	pending.status = "Sending play…"
	_helper.observe(pending, "11")
	_check(_helper.take_play().is_empty(), "local pending input never creates a placement cue")
	var local := _state(_game([3, 5, 5], 1, 0, 2))
	local.handVisible = false
	_helper.observe(local, "12")
	_helper.observe(local, "12")
	_helper.observe(local, "13")
	_check(_helper.take_play() == {"playerId": "seat-1", "cardCount": 2, "revision": "12"},
		"accepted local play survives equal and newer controls-only observations once")
	_check(_helper.take_play().is_empty(), "consuming a placement cannot replay it")
	_helper.observe(local, "12")
	_check(_helper.take_play().is_empty(), "older observation cannot replay placement")
	_helper.observe(_state(_game([3, 4, 5], 2, 1, 1)), "14")
	_check(_helper.take_play() == {"playerId": "seat-2", "cardCount": 1, "revision": "14"},
		"accepted remote play uses only the public actor and count")
	_helper.observe(_state(_game([3, 4, 4], 0, 2, 1)), "15")
	_helper.observe(_state(_game([1, 4, 4], 1, 0, 2)), "16")
	_check(_helper.take_play() == {"playerId": "seat-1", "cardCount": 2, "revision": "16"},
		"coalesced turns retain the latest play even when claimant/count repeat")
	var retained := JSON.stringify(_helper._previous)
	_check(not retained.contains("yourHand") and not retained.contains("private-card-id") \
		and not retained.contains("PRIVATE-RANK-SENTINEL") and not retained.contains("displayName"),
		"observer retains only a small public projection")
	_rebase(opening, "20")
	_helper.observe(_state(_game([4, 4, 5], 2, 1, 1)), "22")
	_check(_helper.take_play().is_empty(), "ambiguous multi-play backfill establishes a silent baseline")
	_helper.observe(_state(_game([4, 4, 4], 0, 2, 1)), "23")
	_check(_helper.take_play().playerId == "seat-3", "an exact play after a backfill baseline remains eligible")
	var redeal := _state(_game([5, 5, 5], 0, -1, 0, 2))
	_helper.observe(redeal, "24")
	_check(_helper.take_play().is_empty(), "a redeal is never mistaken for placement")
	var changed_roster := _state(_game([4, 5, 5, 5], 1, 0, 1, 2))
	_helper.observe(changed_roster, "25")
	_check(_helper.take_play().is_empty(), "roster changes do not synthesize a play")


func _check_lifecycle_observation() -> void:
	var opening := _state(_game([5, 5, 5], 0))
	var played := _state(_game([4, 5, 5], 1, 0, 1))
	_rebase(opening, "30")
	_helper.observe(played, "31")
	var background := played.duplicate(true)
	background.foreground = false
	background.handVisible = false
	_helper.observe(background, "31")
	background.game = _game([4, 4, 5], 2, 1, 1)
	_helper.observe(background, "32")
	var resumed := background.duplicate(true)
	resumed.foreground = true
	_helper.observe(resumed, "32")
	_check(_helper.take_play().is_empty(), "coalesced background/views/resume suppress all old placement cues")
	_helper.observe(_state(_game([4, 4, 4], 0, 2, 1)), "33")
	_check(_helper.take_play().playerId == "seat-3", "a fresh accepted play after resume is eligible")
	_rebase(opening, "40")
	_helper.observe(played, "41")
	var covered := played.duplicate(true)
	covered.handVisible = false
	_helper.observe(covered, "41")
	_check(_helper.take_play().is_empty(), "same-revision manual Cover clears a pending cue")
	_rebase(opening, "50")
	_helper.observe(played, "51")
	var leaving := played.duplicate(true)
	leaving.returnToLobbyPending = true
	_helper.observe(leaving, "51")
	_helper.observe(played, "51")
	_check(_helper.take_play().is_empty(), "return-pending and coalesced cancellation rebase silently")
	var closed := played.duplicate(true)
	closed.closed = true
	_helper.observe(closed, "51")
	_check(_helper.take_play().is_empty(), "close clears public feedback")


func _check_motion() -> void:
	var opening := _state(_game([5, 5, 5], 0))
	var played := _state(_game([2, 5, 5], 1, 0, 3))
	_rebase(opening, "60")
	_helper.observe(played, "61")
	var play: Dictionary = _helper.take_play()
	var cards: Array = []
	var targets: Array[Transform3D] = []
	for index in range(3):
		var card := Node3D.new()
		card.add_to_group(PlayFeedback.PUBLIC_BACK_GROUP)
		_world.add_child(card)
		card.position = Vector3(index * 0.1, 0.08 + index * 0.035, -0.25)
		card.rotation_degrees.y = -8 + index * 8
		cards.append(card)
		targets.append(card.global_transform)
	var origin := _world.to_global(Vector3(0, 0.45, 1.65))
	_check(play.cardCount == cards.size() and _helper.animate_play(cards, origin, false),
		"accepted public placement starts a bounded real Tween")
	var tween: Tween = _helper._tween
	tween.pause()
	var start: Vector3 = cards[0].global_position
	_check(absf(start.z - origin.z) < 0.00001 and not start.is_equal_approx(targets[0].origin),
		"cards start at the acting source in global coordinates")
	tween.custom_step(0.12)
	var middle: Vector3 = cards[0].global_position
	_check(middle.distance_to(targets[0].origin) < start.distance_to(targets[0].origin) \
		and not middle.is_equal_approx(targets[0].origin) and middle.y > targets[0].origin.y,
		"actual Tween advances a lifted intermediate travel pose")
	var first_progress: float = (origin.z - cards[0].global_position.z) / (origin.z - targets[0].origin.z)
	var last_progress: float = (origin.z - cards[2].global_position.z) / (origin.z - targets[2].origin.z)
	_check(first_progress > last_progress, "multiple public cards use a short bounded stagger")
	tween.custom_step(1.0)
	_check(not _helper.is_animating() and _at_targets(cards, targets), "all cards settle at exact authoritative pile transforms")
	_check(_helper._moving.is_empty(), "completed motion retains no card references")
	_check(not _helper.animate_play(cards, origin, true) and _at_targets(cards, targets),
		"Reduce Motion keeps the final pile and creates no travel Tween")
	var untagged := Node3D.new()
	_world.add_child(untagged)
	_check(not _helper.animate_play([untagged], origin, false), "untagged or private targets are excluded")
	_check(not _helper.animate_play([cards[0], cards[1], cards[2], untagged], origin, false),
		"effects never exceed three cards")
	_check(_helper.animate_play(cards, origin, false), "a subsequent bounded animation can start")
	tween = _helper._tween
	tween.pause()
	tween.custom_step(0.10)
	middle = cards[0].global_position
	var background := played.duplicate(true)
	background.foreground = false
	_helper.observe(background, "61")
	_check(tween.is_valid() and cards[0].global_position.is_equal_approx(middle),
		"background observation only latches cancellation without graphics mutations")
	_helper.observe(played, "61")
	_check(_helper.take_play().is_empty(), "coalesced resume has no replay cue")
	tween.custom_step(0.01)
	_check(not _helper.is_animating() and _at_targets(cards, targets),
		"latched lifecycle cancellation settles motion at the next engine step")
	_check(_helper.animate_play(cards, origin, false), "teardown exercise starts a real animation")
	root.remove_child(_helper)
	_check(not _helper.is_animating() and _helper._moving.is_empty() and _at_targets(cards, targets),
		"detaching the owner kills motion and releases all targets")
	root.add_child(_helper)
	_helper.observe(played, "61")
	_check(_helper.take_play().is_empty(), "re-entry establishes a new silent baseline")


func _rebase(state: Dictionary, revision: String) -> void:
	var background := state.duplicate(true)
	background.foreground = false
	_helper.observe(background, revision)
	_helper.observe(state, revision)


func _at_targets(cards: Array, targets: Array[Transform3D]) -> bool:
	for index in range(cards.size()):
		if not cards[index].global_transform.is_equal_approx(targets[index]):
			return false
	return true


func _state(game: Dictionary) -> Dictionary:
	return {"game": game, "foreground": true, "closed": false, "handVisible": true,
		"returnToLobbyPending": false, "reduceMotion": false, "soundEnabled": true,
		"controls": {"canSendAction": true}, "selectedCardIds": [], "status": ""}


func _game(counts: Array, turn: int, claimant: int = -1, count: int = 0, round_number: int = 1) -> Dictionary:
	var players: Array[Dictionary] = []
	for index in range(counts.size()):
		players.append({"id": "seat-%d" % (index + 1), "displayName": "Seat %d" % (index + 1),
			"handCount": counts[index], "penaltyAttempts": 0, "eliminated": false})
	return {"phase": "PLAYING", "roundNumber": round_number, "viewerId": "seat-1",
		"turnPlayerId": "seat-%d" % (turn + 1), "players": players,
		"latestClaim": {"playerId": "seat-%d" % (claimant + 1), "cardCount": count} if claimant >= 0 else null,
		"yourHand": [{"id": "private-card-id", "rank": "PRIVATE-RANK-SENTINEL"}]}


func _check(condition: bool, name: String) -> void:
	_checks.append({"name": name, "passed": condition})
	if not condition:
		_failures += 1
		push_error(name)
