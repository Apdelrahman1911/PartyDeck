extends SceneTree
## Focused 2D layout/privacy check. Run from source, outside exported renderer resources.
## Input is a recipient-safe launch fixture. This does not simulate or accept game actions.

var _options := {}
var _main: Node
var _output := ""
var _observations: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _gesture_log: Array[Dictionary] = []

func _initialize() -> void:
	Input.emulate_touch_from_mouse = true
	ProjectSettings.set_setting("input_devices/pointing/emulate_touch_from_mouse", true)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-") and "=" in argument:
			var parts := argument.substr(8).split("=", true, 1)
			_options[parts[0]] = parts[1]
	_run.call_deferred()

func _run() -> void:
	_output = str(_options.get("output", ""))
	var fixture_path := str(_options.get("fixture", ""))
	if not _output.is_absolute_path() or not fixture_path.is_absolute_path():
		_fail("An absolute --check-output and --check-fixture are required.")
		return
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		_fail("Could not create evidence output.")
		return
	var fixture = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	if not fixture is Dictionary or fixture.get("type") != "launch":
		_fail("Expected a recipient-safe launch document.")
		return
	fixture.presentationMode = "2d"
	fixture.preferences.textScale = float(_options.get("text-scale", "1"))
	fixture.preferences.reduceMotion = true
	fixture.preferences.soundEnabled = false
	_restore_integer_tokens(fixture)
	root.size = Vector2i(int(_options.get("width", "1280")), int(_options.get("height", "800")))
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void:
		_events.append(JSON.parse_string(document))
	)
	root.add_child(_main)
	current_scene = _main
	if not _main.receive_document(JSON.stringify(fixture)):
		_fail("The shared controller rejected the fixture.")
		return
	await _settle()
	await _capture("01-concealed")
	if not _private_nodes_erased():
		_fail("The concealed scene still contains private card nodes.")
		return
	var state: Dictionary = _main.controller.presentation_state()
	var proof := _main.find_child("PublicReveal", true, false)
	if state.game.get("phase") == "PLAYING":
		if proof.visible or proof.get_child_count() != 0:
			_fail("An unresolved round exposes previous-round proof as current.")
			return
	elif not proof.visible or proof.get_child_count() != state.game.roundOutcome.revealedCards.size():
		_fail("The public resolved-card proof is incomplete.")
		return
	if state.game.get("phase") == "PLAYING" and not state.game.get("yourHand", []).is_empty():
		if not await _click("partydeck_action_reveal"):
			return
		if get_nodes_in_group("partydeck_private_face").size() != state.game.yourHand.size():
			_fail("The revealed scene does not contain every own-hand card.")
			return
		if not await _check_hand_drag():
			return
		if bool(state.game.availableActions.canPlay):
			if not await _click("partydeck_hand_card", 0):
				return
			if state.game.yourHand[0].id not in _main.controller.presentation_state().selectedCardIds:
				_fail("The first real card click did not select its card.")
				return
			if state.game.yourHand.size() > 1:
				if not await _click("partydeck_hand_card", state.game.yourHand.size() - 1):
					return
				if state.game.yourHand.back().id not in _main.controller.presentation_state().selectedCardIds:
					_fail("The last real card click did not select its card.")
					return
		await _capture("02-revealed-selected")
		if not await _click("partydeck_action_hide"):
			return
		if not _private_nodes_erased() or not _main.controller.presentation_state().selectedCardIds.is_empty():
			_fail("Cover did not erase private nodes and selection.")
			return
		await _capture("03-covered-again")
		if not await _click("partydeck_action_reveal"):
			return
		var foreground := {"protocolVersion": 1, "presentationId": fixture.presentationId,
			"type": "foreground", "isForeground": false}
		if not _main.receive_document(JSON.stringify(foreground)) or not _private_nodes_erased():
			_fail("Foreground loss did not immediately erase private card nodes.")
			return
		foreground.isForeground = true
		_main.receive_document(JSON.stringify(foreground))
		await _settle()
		await _capture("04-resumed-covered")
	if _events.size() != 1 or _events[0].get("type") != "ready":
		_fail("Reveal/select/cover/foreground emitted a gameplay event.")
		return
	if _options.get("lobby", "false") == "true":
		if not state.controls.canReturnToLobby or state.game.phase == "FINISHED":
			_fail("Lobby confirmation check requires a live match with native host permission.")
			return
		if not await _click("partydeck_action_lobby"):
			return
		if _events.size() != 1 or _main.find_child("LobbyConfirmation", true, false) == null or not _private_nodes_erased():
			_fail("Opening confirmation emitted an action or kept private hand nodes.")
			return
		await _capture("05-lobby-confirmation")
		if not await _click("partydeck_action_lobby_cancel"):
			return
		if _events.size() != 1 or _main.find_child("LobbyConfirmation", true, false) != null:
			_fail("Cancelling confirmation dispatched an action or left the dialog open.")
			return
		if not await _click("partydeck_action_lobby") or not await _click("partydeck_action_lobby_confirm"):
			return
		if _events.size() != 2 or _events.back().get("type") != "intent" or _events.back().payload.get("type") != "return_to_lobby":
			_fail("Confirmed lobby input did not emit exactly one intended request.")
			return
		if _main.controller.presentation_state().controls.canSendAction:
			_fail("A pending request did not disable repeated actions.")
			return
	var closed := {"protocolVersion": 1, "presentationId": fixture.presentationId, "type": "close"}
	_main.receive_document(JSON.stringify(closed))
	if not _private_nodes_erased():
		_fail("Close retained private card nodes.")
		return
	var report := {"result": "passed", "kind": "2d-scene-layout-and-privacy", "fixture": fixture_path,
		"godotVersion": Engine.get_version_info().string,
		"width": root.size.x, "height": root.size.y, "textScale": fixture.preferences.textScale,
		"observations": _observations,
		"limitations": "Static safe view only. No authority-accepted action or native accessibility is claimed."}
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("2D scene layout/privacy check passed: ", _output)
	quit(0)

func _click(group: String, index: int = -1) -> bool:
	var target: Button
	for node in get_nodes_in_group(group):
		if node is Button and node.is_visible_in_tree() and not node.disabled \
			and (index < 0 or int(node.get_meta("card_index", -1)) == index):
			target = node
			break
	if target == null:
		_fail("No enabled button for " + group)
		return false
	var ancestor := target.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(target)
		ancestor = ancestor.get_parent()
	await _settle()
	var point := target.get_global_transform_with_canvas() * (target.size * 0.5)
	if not root.get_visible_rect().has_point(point):
		_fail("Button center is outside the viewport: " + group)
		return false
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	await process_frame
	var down := InputEventMouseButton.new()
	down.position = point
	down.global_position = point
	down.button_index = MOUSE_BUTTON_LEFT
	down.button_mask = MOUSE_BUTTON_MASK_LEFT
	down.pressed = true
	Input.parse_input_event(down)
	await process_frame
	var up := InputEventMouseButton.new()
	up.position = point
	up.global_position = point
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	Input.parse_input_event(up)
	await _settle()
	_observations.append({"input": group, "cardIndex": index, "x": point.x, "y": point.y})
	return true

func _capture(label: String) -> void:
	await _settle()
	# Static tables stop redrawing in low-processor mode; request one actual fresh frame.
	RenderingServer.force_draw()
	var captured := root.get_texture().get_image()
	var output_path := _output.path_join(label + ".png")
	if captured.save_png(output_path) != OK:
		_fail("Could not write scene capture.")
		return
	var diagnostics = JSON.parse_string(_main.diagnostics_document())
	_observations.append({"capture": output_path, "diagnostics": diagnostics})
	FileAccess.open(_output.path_join(label + ".json"), FileAccess.WRITE).store_string(JSON.stringify(diagnostics, "\t"))

func _private_nodes_erased() -> bool:
	return get_nodes_in_group("partydeck_private_face").is_empty() \
		and get_nodes_in_group("partydeck_private_label").is_empty() \
		and get_nodes_in_group("partydeck_hand_card").is_empty()

func _restore_integer_tokens(value: Variant) -> void:
	# Godot parses all JSON numbers as floats. Preserve this fixture's integer fields
	# when re-encoding launch preferences; the strict wire correctly rejects 1.0 counts.
	if value is Dictionary:
		for key in value:
			if value[key] is float and value[key] == floor(value[key]):
				value[key] = int(value[key])
			else:
				_restore_integer_tokens(value[key])
	elif value is Array:
		for child in value:
			_restore_integer_tokens(child)

func _settle() -> void:
	await process_frame
	await process_frame
	await create_timer(0.15).timeout

func _fail(reason: String) -> void:
	push_error(reason)
	quit(1)

func _check_hand_drag() -> bool:
	var scroll: ScrollContainer = _main.find_child("HandScroll", true, false)
	scroll.gui_input.connect(func(event: InputEvent) -> void:
		_gesture_log.append({"target": "HandScroll", "event": event.as_text(), "scroll": scroll.scroll_horizontal})
	)
	for card in get_nodes_in_group("partydeck_hand_card"):
		card.gui_input.connect(func(event: InputEvent) -> void:
			_gesture_log.append({"target": "HandCard", "event": event.as_text(), "scroll": scroll.scroll_horizontal})
		)
	var before := scroll.scroll_horizontal
	var rect := scroll.get_global_rect()
	var start := rect.position + Vector2(rect.size.x * 0.80, rect.size.y * 0.45)
	var setup := {"rect": str(rect), "start": str(start), "rootVisibleRect": str(root.get_visible_rect()), "before": before, "touchscreenReported": DisplayServer.is_touchscreen_available(), "emulateTouch": Input.emulate_touch_from_mouse, "emulateMouse": Input.emulate_mouse_from_touch, "selectedBefore": _main.controller.presentation_state().selectedCardIds.size(), "max": scroll.get_h_scroll_bar().max_value, "page": scroll.get_h_scroll_bar().page}
	var hover := InputEventMouseMotion.new()
	hover.position = start
	hover.global_position = start
	Input.parse_input_event(hover)
	await process_frame
	var down := InputEventMouseButton.new()
	down.position = start
	down.global_position = start
	down.button_index = MOUSE_BUTTON_LEFT
	down.button_mask = MOUSE_BUTTON_MASK_LEFT
	down.pressed = true
	Input.parse_input_event(down)
	await process_frame
	for step in range(1, 7):
		var motion := InputEventMouseMotion.new()
		motion.position = start + Vector2(-30 * step, 0)
		motion.global_position = motion.position
		motion.relative = Vector2(-30, 0)
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		Input.parse_input_event(motion)
		await process_frame
	var up := InputEventMouseButton.new()
	up.position = start + Vector2(-180, 0)
	up.global_position = up.position
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	Input.parse_input_event(up)
	await _settle()
	var after := scroll.scroll_horizontal
	setup["after"] = after
	setup["selectedAfter"] = _main.controller.presentation_state().selectedCardIds.size()
	setup["events"] = _gesture_log
	FileAccess.open(_output.path_join("gesture-diagnostics.json"), FileAccess.WRITE).store_string(JSON.stringify(setup, "\t"))
	print(JSON.stringify(setup))
	if after <= before or not _main.controller.presentation_state().selectedCardIds.is_empty():
		_fail("Emulated touch drag did not scroll cleanly without selecting a card.")
		return false
	_observations.append({"input": "emulated-touch-horizontal-drag", "before": before, "after": after, "selectedCount": 0, "touchscreenReported": DisplayServer.is_touchscreen_available()})
	return true
