extends SceneTree
## Actual renderer-scene checks. This does not execute Android JNI or prove a native deadline.

var _checks: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _failures := 0
var _output := ""
var _fixtures := ""
var _initial_render_loop := true


func _initialize() -> void:
	_initial_render_loop = RenderingServer.render_loop_enabled
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-output="):
			_output = argument.trim_prefix("--check-output=")
		elif argument.begins_with("--check-fixtures="):
			_fixtures = argument.trim_prefix("--check-fixtures=")
	_run.call_deferred()


func _run() -> void:
	if not _output.is_absolute_path() or not _fixtures.is_absolute_path():
		push_error("Absolute --check-output and --check-fixtures paths are required.")
		quit(1)
		return
	root.size = Vector2i(390, 844)
	for mode in ["2d", "3d"]:
		await _ordinary_intents(mode)
		await _pending_then_refresh(mode, true)
		await _pending_then_refresh(mode, false)
		for cancellation in ["host_background", "window_background", "close", "failure", "removal"]:
			await _cancel_pending(mode, cancellation)
	RenderingServer.render_loop_enabled = _initial_render_loop
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks,
		"godotVersion": Engine.get_version_info().string,
		"renderingMethod": RenderingServer.get_current_rendering_method(),
		"limitations": "Actual desktop scenes and frame counters; no Android JNI, EGL scheduling deadline or host authority acceptance is simulated."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("Terminal return rendering checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _mount(mode: String, finished: bool = false) -> Node:
	RenderingServer.render_loop_enabled = true
	paused = false
	_events.clear()
	var name := "finished-launch-%s.json" % mode if finished else "launch-%s.json" % mode
	var launch: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(_fixtures.path_join(name)))
	launch.preferences.reduceMotion = true
	launch.preferences.soundEnabled = false
	_restore_integer_tokens(launch)
	var main: Node = load("res://main.tscn").instantiate()
	main.set_meta("test_launch", launch)
	main.bridge_event.connect(func(document: String) -> void:
		var event: Dictionary = JSON.parse_string(document)
		_events.append(event)
		if event.get("type") == "intent" and event.payload.get("type") == "return_to_lobby":
			_check(not RenderingServer.render_loop_enabled,
				mode + ": new draw work is suspended before immediate terminal event delivery")
	)
	root.add_child(main)
	_check(main.receive_document(JSON.stringify(launch)), mode + ": existing strict launch is accepted")
	var before := Engine.get_frames_drawn()
	await process_frame
	await process_frame
	await process_frame
	_check(main._presentation != null and _events.size() == 1 and _events[0].type == "ready",
		mode + ": a fresh lifetime mounts the presentation and emits Ready")
	_check(Engine.get_frames_drawn() > before, mode + ": a fresh lifetime actually draws")
	return main


func _ordinary_intents(mode: String) -> void:
	var main: Node = await _mount(mode)
	var controller: Node = main.controller
	controller.return_to_lobby()
	_check(_events.size() == 1 and RenderingServer.render_loop_enabled,
		mode + ": absent local lobby permission neither emits nor suppresses rendering")
	controller.reveal_hand()
	controller.toggle_card(controller.presentation_state().game.yourHand[0].id)
	controller.play_selected()
	_check(_events.size() == 2 and _events.back().payload.type == "play" \
		and not controller.presentation_state().get("returnToLobbyPending", false) and RenderingServer.render_loop_enabled,
		mode + ": ordinary play retains its existing drawing and event behavior")
	var view := _view(main, controller.revision.to_int() + 1)
	view.payload.game.latestClaim = {"playerId": "seat-2", "cardCount": 1}
	view.payload.game.availableActions.canChallenge = true
	_check(main.receive_document(JSON.stringify(view)), mode + ": a valid challenge projection is accepted")
	controller.challenge()
	_check(_events.size() == 3 and _events.back().payload.type == "challenge" \
		and not controller.presentation_state().get("returnToLobbyPending", false) and RenderingServer.render_loop_enabled,
		mode + ": ordinary challenge retains its existing drawing and event behavior")
	await _dispose(main)


func _pending_then_refresh(mode: String, prior_enabled: bool) -> void:
	var main: Node = await _mount(mode, true)
	var controller: Node = main.controller
	var table: Node = main._presentation
	RenderingServer.render_loop_enabled = prior_enabled
	var nodes := _node_ids(table)
	var frames := Engine.get_frames_drawn()
	var revision: String = controller.revision
	controller.return_to_lobby()
	var state: Dictionary = controller.presentation_state()
	_check(state.get("returnToLobbyPending", false) and not state.closed and not state.handVisible \
		and not state.controls.canSendAction and not state.soundEnabled,
		mode + ": terminal pending is reversible and conceals local input and feedback")
	_check(_events.size() == 2 and _events.back().payload.type == "return_to_lobby" \
		and _events.back().expectedRevision == revision,
		mode + ": lobby intent is delivered synchronously with its existing revision")
	_check(_node_ids(table) == nodes, mode + ": terminal CPU state does not mutate scene resources off-frame")
	controller.return_to_lobby()
	_check(_events.size() == 2, mode + ": duplicate pending return cannot emit another intent")
	await process_frame
	await process_frame
	await process_frame
	_check(Engine.get_frames_drawn() == frames and _node_ids(table) == nodes,
		mode + ": pending return does not draw or rebuild the retained page while logic advances")
	var stale := _view(main, revision.to_int())
	_check(not main.receive_document(JSON.stringify(stale)) and not RenderingServer.render_loop_enabled,
		mode + ": same bridge revision remains rejected and cannot release drawing")
	var wrong := _view(main, revision.to_int() + 1)
	wrong.presentationId = "another-presentation"
	_check(not main.receive_document(JSON.stringify(wrong)) and not RenderingServer.render_loop_enabled,
		mode + ": another presentation cannot release the pending lifetime")
	var refreshed := _view(main, revision.to_int() + 1)
	_check(main.receive_document(JSON.stringify(refreshed)) \
		and not controller.presentation_state().get("returnToLobbyPending", false) \
		and RenderingServer.render_loop_enabled == prior_enabled,
		mode + ": accepted fresh view restores the exact prior rendering setting")
	await process_frame
	await process_frame
	await process_frame
	_check(_node_ids(table) != nodes and (not prior_enabled or Engine.get_frames_drawn() > frames),
		mode + ": a rejected return can reconcile its refreshed page and resume prior drawing")
	await _dispose(main)
	_check(RenderingServer.render_loop_enabled == prior_enabled,
		mode + ": removal preserves an already restored prior rendering setting")


func _cancel_pending(mode: String, cancellation: String) -> void:
	var main: Node = await _mount(mode)
	var controller: Node = main.controller
	var allowed := _view(main, controller.revision.to_int() + 1)
	allowed.payload.controls.canReturnToLobby = true
	_check(main.receive_document(JSON.stringify(allowed)), mode + ": host can grant a live-match return")
	controller.reveal_hand()
	controller.return_to_lobby()
	_check(not controller.presentation_state().handVisible and not _has_private_ranks(main._presentation._state),
		mode + ": pending live-match return erases private CPU ranks before host delivery")
	await process_frame
	match cancellation:
		"host_background":
			_check(_foreground(main, false), mode + ": host background cancels the pending input")
		"window_background":
			main.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
		"close":
			_check(main.receive_document(JSON.stringify({"protocolVersion": 1,
				"presentationId": controller.presentation_id, "type": "close"})), mode + ": Close remains deliverable while drawing is suspended")
		"failure":
			controller.fail("INTERNAL_ERROR")
		"removal":
			root.remove_child(main)
	_check(RenderingServer.render_loop_enabled, mode + ": " + cancellation + " releases the owned drawing suppression")
	if cancellation != "removal":
		_check(not controller.presentation_state().get("returnToLobbyPending", false),
			mode + ": " + cancellation + " clears terminal pending")
		await process_frame
		await process_frame
		if cancellation in ["close", "failure"]:
			_check(controller.presentation_state().closed and main._presentation == null,
				mode + ": terminal cleanup still removes the presentation")
		else:
			controller.return_to_lobby()
			_check(_events.size() == 2, mode + ": backgrounded stale return remains rejected")
			if cancellation == "host_background":
				_foreground(main, true)
			else:
				main.notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
			await process_frame
			await process_frame
			_check(not paused and not controller.presentation_state().handVisible,
				mode + ": foreground recovery resumes with the hand concealed")
	await _dispose(main)


func _view(main: Node, revision: int) -> Dictionary:
	var launch: Dictionary = main.get_meta("test_launch")
	return {"protocolVersion": 1, "presentationId": main.controller.presentation_id, "type": "view",
		"revision": str(revision), "schemaId": launch.schemaId, "payload": launch.payload.duplicate(true)}


func _foreground(main: Node, active: bool) -> bool:
	return main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": main.controller.presentation_id,
		"type": "foreground", "isForeground": active}))


func _node_ids(node: Node) -> Array[int]:
	var ids: Array[int] = [node.get_instance_id()]
	for child in node.get_children():
		ids.append_array(_node_ids(child))
	return ids


func _has_private_ranks(state: Dictionary) -> bool:
	for card in state.game.get("yourHand", []):
		if card.has("rank"):
			return true
	return false


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


func _dispose(main: Node) -> void:
	if main.is_inside_tree():
		root.remove_child(main)
	main.queue_free()
	paused = false
	await process_frame


func _check(condition: bool, description: String) -> bool:
	_checks.append({"check": description, "passed": condition})
	if not condition:
		_failures += 1
		push_error(description)
	return condition
