extends SceneTree
## Independent real-renderer regression for accepted public placement feedback.
## Recipient fixtures are delivered through the actual controller. This is not
## authority, native-host, audible-device, or physical-network qualification.

class ObservedTable:
	extends "res://presentations/three_d/table.gd"
	var sound_calls: Array[String] = []
	var sound_starts: Array[Dictionary] = []
	func _sound(cue: String) -> void:
		sound_calls.append(cue)
		super._sound(cue)
		sound_starts.append({"cue": cue, "playing": _feedback.playing,
			"expectedStream": _feedback.stream == load("res://assets/audio/%s.wav" % cue)})


var _output := ""
var _fixture_path := ""
var _fixture: Dictionary
var _game: Dictionary
var _revision := 0
var _last_view: Dictionary
var _main: Node
var _table: Control
var _viewport: SubViewport
var _checks: Array[Dictionary] = []
var _frames: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _failures := 0
var _pre_draw_mode := -1
var _initial_time_scale := 1.0
var _initial_render_loop := true


func _initialize() -> void:
	_initial_time_scale = Engine.time_scale
	_initial_render_loop = RenderingServer.render_loop_enabled
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-output="):
			_output = argument.trim_prefix("--check-output=")
		elif argument.begins_with("--check-fixture="):
			_fixture_path = argument.trim_prefix("--check-fixture=")
	_run.call_deferred()


func _run() -> void:
	if not _output.is_absolute_path() or not _fixture_path.is_absolute_path():
		push_error("Absolute --check-output and --check-fixture paths are required.")
		quit(1)
		return
	if DisplayServer.get_name() == "headless" or RenderingServer.get_current_rendering_method() != "gl_compatibility":
		push_error("Play-effect checks require an actual display and the compatibility renderer.")
		quit(1)
		return
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(_fixture_path))
	if not parsed is Dictionary or parsed.get("type") != "launch" \
		or parsed.payload.game.phase != "PLAYING" or not parsed.payload.game.availableActions.canPlay \
		or parsed.payload.game.yourHand.size() < 3 or parsed.payload.game.players.size() < 3:
		push_error("Use the recipient-safe launch-3d fixture with a playable own hand and at least three seats.")
		quit(1)
		return
	_fixture = parsed
	_restore_integer_tokens(_fixture)
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		push_error("Could not create play-effect output directory.")
		quit(1)
		return
	root.size = Vector2i(390, 844)
	# Step genuine Tweens and draw genuine frames explicitly so a slow software
	# renderer cannot skip every intermediate pose of this subsecond effect.
	Engine.time_scale = 0.0
	RenderingServer.render_loop_enabled = false
	if await _mount(false, true):
		await _exercise_play_feedback()
		await _dispose()
	if _failures == 0 and await _mount(true, true):
		await _exercise_reduced_motion()
		await _dispose()
	if _failures == 0 and await _mount(false, false):
		await _exercise_muted_play()
		await _dispose()
	Engine.time_scale = _initial_time_scale
	RenderingServer.render_loop_enabled = _initial_render_loop
	paused = false
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks, "frames": _frames,
		"godotVersion": Engine.get_version_info().string, "renderingMethod": RenderingServer.get_current_rendering_method(),
		"limitations": "Actual desktop controller, table, public-card Tweens, audio playback starts and raster buffers. Recipient snapshots are fixtures; authority acceptance, audible-device output, native privacy covers and physical networking require separate execution."}
	var report_file := FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE)
	if report_file == null:
		push_error("Could not write play-effect report.")
		quit(1)
		return
	report_file.store_string(JSON.stringify(report, "\t"))
	report_file.close()
	print("3D play-effect checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _mount(reduce_motion: bool, sound_enabled: bool) -> bool:
	paused = false
	_events.clear()
	var launch := _fixture.duplicate(true)
	launch.presentationMode = "3d"
	launch.preferences.reduceMotion = reduce_motion
	launch.preferences.soundEnabled = sound_enabled
	launch.preferences.textScale = 1.0
	_game = launch.payload.game.duplicate(true)
	_revision = int(launch.revision)
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void: _events.append(JSON.parse_string(document)))
	root.add_child(_main)
	# Preserve the real scene's layout and inherited implementation. The subclass
	# only records calls AFTER invoking its actual audio path; it replaces no cue,
	# animation, renderer, controller or lifecycle behavior.
	_table = load("res://presentations/three_d/table.tscn").instantiate()
	_table.set_script(ObservedTable)
	_table.process_mode = Node.PROCESS_MODE_PAUSABLE
	_main._presentation = _table
	_main._mode = "3d"
	_table.redraw_requested.connect(_main._request_reconcile)
	_main.add_child(_table)
	_table.bind(_main.controller)
	if _main._waiting != null:
		_main._waiting.queue_free()
		_main._waiting = null
	if not _check(_main.receive_document(JSON.stringify(launch)), "strict recipient launch is accepted"):
		return false
	await _settle()
	if not _check(_main._presentation == _table and _scene_current() and _table.get("_play_feedback") != null,
		"actual 3D implementation applies the launch with its play helper"):
		return false
	_viewport = _table._viewport
	RenderingServer.frame_pre_draw.connect(_observe_frame)
	_check(_table.sound_calls.is_empty() and not _table._play_feedback.is_animating(),
		"initial attachment establishes a silent baseline")
	_check(_events.size() == 1 and _events[0].type == "ready", "the mounted implementation emits exactly one Ready")
	_draw("initial table", SubViewport.UPDATE_ONCE)
	_draw("initial idle", SubViewport.UPDATE_DISABLED)
	return true


func _exercise_play_feedback() -> void:
	_main.controller.reveal_hand()
	await _settle()
	_table._toggle_card(_game.yourHand[0].id)
	await _settle()
	await _finish_tweens()
	_table.sound_calls.clear()
	_table.sound_starts.clear()
	_table._play()
	_check(_events.size() == 2 and _events.back().type == "intent" \
		and _events.back().payload.type == "play" and not _table._play_feedback.is_animating(),
		"local intent alone sends one action without inventing an accepted placement")
	if not _send_play(1):
		return
	await _settle()
	_check(_table.sound_calls == ["ui_tap", "card_place"] and _started("card_place"),
		"accepted local play starts card_place once after the queued tap")
	_check(_private_nodes_erased() and _public_backs_only(1),
		"accepted local play immediately replaces private hand bindings with public backs")
	_check(_observer_is_public(), "feedback observer retains no private hand IDs or ranks")
	if not await _exercise_motion("local"):
		return

	_table.sound_calls.clear()
	_table.sound_starts.clear()
	if not _send_play(2):
		return
	# A session/control-only revision can arrive after a play before either draws.
	# It must preserve that unconsumed cue while still deduplicating its own view.
	if not _send_game(_game):
		return
	await _settle()
	_check(_table.sound_calls == ["card_place"] and _started("card_place") and _public_backs_only(2),
		"accepted remote play survives a coalesced identical snapshot and starts one public cue")
	if not await _exercise_motion("remote"):
		return

	_table.sound_calls.clear()
	if not _send_game(_game):
		return
	await _settle()
	var replay := _last_view.duplicate(true)
	var duplicate_rejected: bool = not _main.receive_document(JSON.stringify(replay))
	replay.revision = str(int(replay.revision) - 1)
	var stale_rejected: bool = not _main.receive_document(JSON.stringify(replay))
	await _settle()
	_check(duplicate_rejected and stale_rejected and _table.sound_calls.is_empty() \
		and not _table._play_feedback.is_animating(),
		"unchanged newer views and rejected duplicate/stale revisions never replay placement feedback")

	# Return to the same public claimant/count after a full set of observed turns,
	# with all snapshots coalesced before the next render.
	var previous_claim: Dictionary = _game.latestClaim.duplicate()
	for index in range(_game.players.size()):
		if not _send_play(2 if index == _game.players.size() - 1 else 1):
			return
	await _settle()
	_check(_game.latestClaim == previous_claim and _table.sound_calls == ["card_place"] \
		and _table._play_feedback.is_animating(),
		"repeated claimant/count after observed intervening turns produces one fresh placement")
	await _finish_tweens()

	_table.sound_calls.clear()
	if not _send_play(1):
		return
	await _settle()
	if not _check(_table._play_feedback.is_animating(), "a live accepted placement exists before lifecycle cancellation"):
		return
	_table.sound_calls.clear()
	var nodes_before := _node_ids(_table)
	var poses_before := _back_poses()
	_foreground(false)
	if not _send_play(1):
		return
	_foreground(true)
	_check(nodes_before == _node_ids(_table) and poses_before == _back_poses() and not _contains_private_rank(_table._state),
		"coalesced lifecycle callbacks retain only concealed CPU state and defer graphics changes")
	await _settle()
	_check(not paused and _table.sound_calls.is_empty() and not _table._feedback.playing \
		and not _table._play_feedback.is_animating() and get_processed_tweens().is_empty() and _private_nodes_erased(),
		"background play and immediate resume stop existing feedback without replaying it")
	_draw("resumed covered table", SubViewport.UPDATE_ONCE)
	_draw("resumed idle", SubViewport.UPDATE_DISABLED)

	_main.remove_child(_table)
	_main.add_child(_table)
	_table.bind(_main.controller)
	_main._request_reconcile()
	await _settle()
	_check(_scene_current() and _table.sound_calls.is_empty() and not _table._play_feedback.is_animating(),
		"re-entering the same scene object establishes a silent current baseline")
	# Re-entering reconnects the policy after our observer; reconnect the observer
	# afterwards so it continues to sample the policy's actual draw decision.
	RenderingServer.frame_pre_draw.disconnect(_observe_frame)
	RenderingServer.frame_pre_draw.connect(_observe_frame)
	if not _send_play(1):
		return
	await _settle()
	_check(_table.sound_calls == ["card_place"] and _table._play_feedback.is_animating(),
		"a genuinely new placement still works after resume and scene re-entry")
	var closed: bool = _main.receive_document(JSON.stringify({"protocolVersion": 1,
		"presentationId": _fixture.presentationId, "type": "close"}))
	_check(closed and _table._state.game.is_empty(), "Close clears the current CPU snapshot immediately")
	await _settle()
	_check(not is_instance_valid(_table) and _main._presentation == null and _tweens_inactive() \
		and _private_nodes_erased(), "Close removes live motion, scene resources and private bindings")
	_check(_events.size() == 2, "public snapshots, feedback and lifecycle emit no extra gameplay intents")


func _exercise_motion(label: String) -> bool:
	var tweens := get_processed_tweens()
	if not _check(tweens.size() == 1 and _table._play_feedback.is_animating(), label + ": one finite Tween owns the public flight"):
		return false
	var tween: Tween = tweens[0]
	tween.pause()
	var start_poses := _back_poses()
	var first := _draw(label + " start", SubViewport.UPDATE_ONCE, label + "-01-start.png")
	tween.custom_step(0.14)
	await _settle()
	var middle := _draw(label + " travel", SubViewport.UPDATE_ONCE, label + "-02-travel.png")
	_check(_back_poses() != start_poses and middle != first, label + ": actual public transforms and raster change during flight")
	tween.custom_step(0.45)
	await _settle()
	var last := _draw(label + " settled", SubViewport.UPDATE_ONCE, label + "-03-settled.png")
	_check(last != middle and not _table._play_feedback.is_animating() and get_processed_tweens().is_empty(),
		label + ": placement settles and releases its Tween within 590 ms of stepped time")
	var idle := _draw(label + " final idle", SubViewport.UPDATE_DISABLED)
	_check(last == idle and not _table.is_processing(), label + ": final texture is retained with no continuing table process loop")
	_table._request_target_update()
	_check(_draw(label + " fresh final reference", SubViewport.UPDATE_ONCE) == last,
		label + ": retained final texture matches a fresh render of the final public pose")
	_draw(label + " reference idle", SubViewport.UPDATE_DISABLED)
	return true


func _exercise_reduced_motion() -> void:
	if not _send_play(1):
		return
	await _settle()
	_check(_table.sound_calls == ["card_place"] and _started("card_place") \
		and not _table._play_feedback.is_animating() and get_processed_tweens().is_empty() and _public_backs_only(1),
		"reduced motion applies public backs immediately, creates no Tween and preserves enabled audio")
	var settled := _draw("reduced-motion placement", SubViewport.UPDATE_ONCE)
	_check(_draw("reduced-motion idle", SubViewport.UPDATE_DISABLED) == settled,
		"reduced-motion placement immediately returns to an unchanged idle texture")


func _exercise_muted_play() -> void:
	if not _send_play(1):
		return
	await _settle()
	_check(not _table._feedback.playing and not _started("card_place") and _table._play_feedback.is_animating(),
		"muted placement keeps its public motion without starting sound")
	await _finish_tweens()
	_draw("muted settled placement", SubViewport.UPDATE_ONCE)
	_draw("muted placement idle", SubViewport.UPDATE_DISABLED)


func _send_play(count: int) -> bool:
	# Build a detached recipient fixture for one valid public turn transition.
	# Only this test changes snapshots; the product still relies on its authority.
	var next := _game.duplicate(true)
	var actor: String = next.turnPlayerId
	var actor_index := -1
	for index in range(next.players.size()):
		if next.players[index].id == actor:
			actor_index = index
	if not _check(actor_index >= 0 and int(next.players[actor_index].handCount) >= count,
		"placement fixture has enough cards at the public acting seat"):
		return false
	next.players[actor_index].handCount = int(next.players[actor_index].handCount) - count
	if actor == next.viewerId:
		for _index in range(count):
			next.yourHand.pop_front()
	next.latestClaim = {"playerId": actor, "cardCount": count}
	for offset in range(1, next.players.size()):
		var candidate: Dictionary = next.players[(actor_index + offset) % next.players.size()]
		if not candidate.eliminated and int(candidate.handCount) > 0:
			next.turnPlayerId = candidate.id
			break
	var eligible := 0
	for player in next.players:
		if not player.eliminated and int(player.handCount) > 0:
			eligible += 1
	next.forcedChallenge = eligible == 1
	var local_turn: bool = next.turnPlayerId == next.viewerId
	var can_play: bool = local_turn and not next.forcedChallenge and not next.yourHand.is_empty()
	next.availableActions = {"canPlay": can_play, "canChallenge": local_turn and actor != next.viewerId,
		"maxPlayableCards": mini(3, next.yourHand.size()) if can_play else 0}
	return _send_game(next)


func _send_game(game: Dictionary) -> bool:
	_revision += 1
	_game = game.duplicate(true)
	_last_view = {"protocolVersion": 1, "presentationId": _fixture.presentationId, "type": "view",
		"revision": str(_revision), "schemaId": _fixture.schemaId,
		"payload": {"game": _game.duplicate(true), "controls": _fixture.payload.controls.duplicate(true)}}
	return _check(_main.receive_document(JSON.stringify(_last_view)), "strict controller admits the next recipient snapshot")


func _foreground(active: bool) -> void:
	_check(_main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": _fixture.presentationId,
		"type": "foreground", "isForeground": active})), "strict controller admits lifecycle transition")


func _started(cue: String) -> bool:
	for observation in _table.sound_starts:
		if observation.cue == cue and observation.playing and observation.expectedStream:
			return true
	return false


func _public_backs_only(expected: int) -> bool:
	var backs := get_nodes_in_group("partydeck_play_back")
	if backs.size() != expected:
		return false
	for card in backs:
		if not _table.is_ancestor_of(card) or card.face.is_in_group("partydeck_private_face") \
			or card.face.material_override.albedo_texture != load("res://assets/textures/cards/back.png"):
			return false
	return true


func _observer_is_public() -> bool:
	var stored := JSON.stringify([_table._play_feedback._previous, _table._play_feedback._pending_play])
	for card in _fixture.payload.game.yourHand:
		if card.id in stored:
			return false
	for private_key in ["yourHand", "selectedCardIds", "revealedCards", "rank"]:
		if ('"%s"' % private_key) in stored:
			return false
	return true


func _contains_private_rank(state: Dictionary) -> bool:
	for card in state.get("game", {}).get("yourHand", []):
		if card.has("rank"):
			return true
	return false


func _private_nodes_erased() -> bool:
	return get_nodes_in_group("partydeck_private_face").is_empty() \
		and get_nodes_in_group("partydeck_private_label").is_empty() and get_nodes_in_group("partydeck_hand_card").is_empty()


func _back_poses() -> Array:
	var result: Array = []
	for card in get_nodes_in_group("partydeck_play_back"):
		result.append(card.global_transform)
	return result


func _node_ids(node: Node) -> Array:
	var result: Array = [node.get_instance_id()]
	for child in node.get_children():
		result.append_array(_node_ids(child))
	return result


func _scene_current() -> bool:
	return bool(JSON.parse_string(_main.diagnostics_document()).get("sceneStateApplied", false))


func _observe_frame() -> void:
	if is_instance_valid(_viewport):
		_pre_draw_mode = RenderingServer.viewport_get_update_mode(_viewport.get_viewport_rid())


func _draw(label: String, expected_mode: int, png_name: String = "") -> String:
	_pre_draw_mode = -1
	RenderingServer.render_loop_enabled = true
	RenderingServer.force_draw(false)
	var root_enabled := RenderingServer.render_loop_enabled
	RenderingServer.render_loop_enabled = false
	var after := RenderingServer.viewport_get_update_mode(_viewport.get_viewport_rid())
	_check(root_enabled and _pre_draw_mode == expected_mode and after == RenderingServer.VIEWPORT_UPDATE_DISABLED,
		label + ": actual viewport demand is consumed without changing root drawing")
	var pixels := _viewport.get_texture().get_image()
	if not _check(pixels != null and not pixels.is_empty(), label + ": actual rendered pixels exist"):
		return ""
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(pixels.get_data())
	var fingerprint := hashing.finish().hex_encode()
	if not png_name.is_empty():
		_check(root.get_texture().get_image().save_png(_output.path_join(png_name)) == OK,
			label + ": public motion frame is saved")
	_frames.append({"label": label, "beforeMode": _pre_draw_mode, "afterMode": after,
		"pixelSha256": fingerprint, "png": png_name})
	return fingerprint


func _finish_tweens() -> void:
	for tween in get_processed_tweens():
		tween.custom_step(1.0)
	await _settle()


func _tweens_inactive() -> bool:
	# Close pauses the tree. The pinned engine skips paused entries before its
	# deletion sweep, and get_processed_tweens returns that whole retained list.
	# Require each entry to be killed now; _dispose also requires an empty list
	# after unpausing and completing the sweep.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/scene/main/scene_tree.cpp#L825
	for tween in get_processed_tweens():
		if tween.is_valid() or tween.is_running():
			return false
	return true


func _dispose() -> void:
	if RenderingServer.frame_pre_draw.is_connected(_observe_frame):
		RenderingServer.frame_pre_draw.disconnect(_observe_frame)
	if is_instance_valid(_main):
		if not _main.controller.presentation_state().closed:
			_main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": _fixture.presentationId, "type": "close"}))
		await _settle()
		root.remove_child(_main)
		_main.queue_free()
	_main = null
	_table = null
	_viewport = null
	paused = false
	await _settle()
	_check(get_processed_tweens().is_empty() and _private_nodes_erased(), "teardown leaves no running motion or private bindings")


func _settle() -> void:
	await process_frame
	await process_frame
	await process_frame


func _restore_integer_tokens(value: Variant) -> void:
	if value is Dictionary:
		for key in value:
			if value[key] is float and value[key] == floor(value[key]):
				value[key] = int(value[key])
			else:
				_restore_integer_tokens(value[key])
	elif value is Array:
		for child in value:
			_restore_integer_tokens(child)


func _check(passed: bool, description: String) -> bool:
	_checks.append({"passed": passed, "description": description})
	if not passed:
		_failures += 1
		push_error(description)
	return passed
