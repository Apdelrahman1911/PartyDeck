extends SceneTree
## Desktop boundary regression. Registry doubles do not execute Android JNI.

class JavaRegistry:
	extends RefCounted
	var methods := {&"get_display_scale": true, &"renderer_diagnostics": true}
	var queries: Array[StringName] = []
	func has_java_method(method_name: StringName) -> bool:
		queries.append(method_name)
		return methods.has(method_name)


class OrdinaryBridge:
	extends Object
	signal command_received(document: String)
	signal diagnostics_requested(request_id: String)
	var launch := ""
	var events: Array[Dictionary] = []
	var diagnostics: Array[Dictionary] = []
	var java_queries := 0
	func has_java_method(_method_name: StringName) -> bool:
		java_queries += 1
		return false
	func get_launch_document() -> String:
		return launch
	func get_display_scale() -> float:
		return 1.75
	func renderer_event(document: String) -> void:
		events.append(JSON.parse_string(document))
	func renderer_diagnostics(document: String) -> void:
		diagnostics.append(JSON.parse_string(document))


var _checks: Array[Dictionary] = []
var _failures := 0
var _output := ""
var _fixtures := ""


func _initialize() -> void:
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
	var probe: Node = load("res://scripts/main.gd").new()
	_check(not probe._plugin_has_method("get_display_scale"), "An absent plugin has no optional method")
	probe._plugin = RefCounted.new()
	_check(not probe._plugin_has_method("get_display_scale"), "An ordinary object without the method is rejected")
	var registry := JavaRegistry.new()
	probe._plugin = registry
	for method_name in [&"get_display_scale", &"renderer_diagnostics"]:
		_check(not registry.has_method(method_name), "Registry-only method is absent from Object: " + method_name)
		_check(probe._plugin_has_method(method_name), "Registry-only method is discovered: " + method_name)
	_check(not probe._plugin_has_method("unknown_bridge_method"), "An unregistered Java method is rejected")
	_check(registry.queries == [&"get_display_scale", &"renderer_diagnostics", &"unknown_bridge_method"],
		"Discovery queries the registered Java method names")
	var ordinary := OrdinaryBridge.new()
	probe._plugin = ordinary
	_check(probe._plugin_has_method("get_display_scale"), "An ordinary density method is discovered")
	_check(probe._plugin_has_method("renderer_diagnostics"), "An ordinary diagnostics method is discovered")
	_check(ordinary.java_queries == 0, "Ordinary methods take precedence over the Java registry")
	probe.free()
	ordinary.free()
	for mode in ["2d", "3d"]:
		await _check_lifetime(mode)
		await _check_frame_boundary(mode)
		await _check_before_first_frame(mode, false)
		await _check_before_first_frame(mode, true)
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks,
		"godotVersion": Engine.get_version_info().string,
		"limitations": "Desktop registry doubles and actual renderer scenes. Android JNI invocation and native readiness require the Android runner."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("Native bridge boundary checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _check_lifetime(mode: String) -> void:
	var bridge := OrdinaryBridge.new()
	bridge.launch = FileAccess.get_file_as_string(_fixtures.path_join("launch-%s.json" % mode))
	Engine.register_singleton("PartyDeckBridge", bridge)
	root.size = Vector2i(720, 1120)
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_check(bridge.events.is_empty() and main._presentation == null,
		mode + ": native launch waits for a frame before mounting or emitting Ready")
	await process_frame
	await process_frame
	_check(bridge.events.size() == 1 and bridge.events[0].get("type") == "ready", mode + ": native launch emits exactly Ready")
	_check(main._native_display_scale_valid and is_equal_approx(root.content_scale_factor, 1.75), mode + ": discovered density is applied")
	_check(is_equal_approx(root.get_visible_rect().size.x, 720.0 / 1.75), mode + ": logical viewport uses native density")
	var controller: Node = main.controller
	_check(controller.presentation_state().presentationMode == mode, mode + ": requested presentation is instantiated")
	bridge.diagnostics_requested.emit("17")
	_check(bridge.diagnostics.size() == 1 and bridge.diagnostics[0].requestId == "17", mode + ": diagnostic request reaches the callback")
	if bridge.diagnostics.size() == 1:
		var diagnostic: Dictionary = bridge.diagnostics[0]
		_check(diagnostic.handConcealed and diagnostic.privateFaceCount == 0 and diagnostic.privateLabelCount == 0,
			mode + ": initial diagnostics confirm private bindings are absent")
		_check(diagnostic.coordinateSpace == "root_viewport" and is_equal_approx(diagnostic.viewport.width, 720.0 / 1.75),
			mode + ": diagnostic coordinates use the logical root viewport")
	bridge.diagnostics_requested.emit("1e3")
	_check(bridge.diagnostics.size() == 1, mode + ": invalid diagnostic request IDs are ignored")
	var reveal: BaseButton = get_first_node_in_group("partydeck_action_reveal")
	if _check(reveal != null, mode + ": the local reveal control is attached"):
		reveal.pressed.emit()
	await process_frame
	await process_frame
	bridge.diagnostics_requested.emit("18")
	_check(bridge.diagnostics.size() == 2 and not bridge.diagnostics.back().handConcealed,
		mode + ": read-only diagnostics can observe local reveal")
	var presentation_id: String = controller.presentation_id
	bridge.command_received.emit(JSON.stringify({"protocolVersion": 1, "presentationId": presentation_id,
		"type": "foreground", "isForeground": false}))
	bridge.diagnostics_requested.emit("19")
	if _check(bridge.diagnostics.size() == 3, mode + ": diagnostics remain callable while backgrounded"):
		var concealed: Dictionary = bridge.diagnostics.back()
		_check(not concealed.foreground and concealed.handConcealed and not controller.presentation_state().controls.canSendAction,
			mode + ": background commands synchronously conceal controller state and reject input")
	await process_frame
	await process_frame
	bridge.diagnostics_requested.emit("20")
	_check(bridge.diagnostics.size() == 4 and bridge.diagnostics.back().privateFaceCount == 0 \
		and bridge.diagnostics.back().privateLabelCount == 0,
		mode + ": the next engine frame removes private scene bindings")
	_check(bridge.events.size() == 1, mode + ": local changes and diagnostics emit no authority intent")
	_check(bridge.java_queries == 0, mode + ": ordinary callback dispatch preserves Object precedence")
	bridge.command_received.emit(JSON.stringify({"protocolVersion": 1, "presentationId": presentation_id, "type": "close"}))
	_check(controller.presentation_state().closed, mode + ": native close reaches the controller")
	await process_frame
	await process_frame
	_check(main._presentation == null, mode + ": Close removes the scene while processing is paused")
	root.remove_child(main)
	main.queue_free()
	Engine.unregister_singleton("PartyDeckBridge")
	paused = false
	root.content_scale_factor = 1.0
	await process_frame
	bridge.free()


func _check_frame_boundary(mode: String) -> void:
	# Enter on process_frame so each following await observes one Main iteration.
	# Callback injection models queued delivery; it does not execute Android EGL/JNI.
	await process_frame
	var bridge := OrdinaryBridge.new()
	bridge.launch = FileAccess.get_file_as_string(_fixtures.path_join("launch-%s.json" % mode)) \
		.replace('"canReturnToLobby":false', '"canReturnToLobby":true') \
		.replace('"reduceMotion":false', '"reduceMotion":true')
	Engine.register_singleton("PartyDeckBridge", bridge)
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_check(main._presentation == null and bridge.events.is_empty(), mode + ": off-frame launch does not build a table or release Ready")
	await process_frame
	var table: Node = main._presentation
	if not _check(is_instance_valid(table) and bridge.events.size() == 1 and bridge.events[0].type == "ready",
		mode + ": the first engine frame mounts the table before Ready"):
		await _dispose_main(main, bridge)
		return
	var controller: Node = main.controller
	var card_id: String = controller.presentation_state().game.yourHand[0].id
	var before := _node_ids(table)
	controller.reveal_hand()
	controller.toggle_card(card_id)
	_check(controller.presentation_state().handVisible and controller.presentation_state().selectedCardIds == [card_id],
		mode + ": local controller state changes immediately")
	_check(_node_ids(table) == before and _private_faces(main) == 0,
		mode + ": revealing outside a frame does not mutate scene resources")
	await process_frame
	_check(_private_faces(main) > 0, mode + ": the next engine frame binds the revealed hand")
	before = _node_ids(table)
	main.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	var state: Dictionary = controller.presentation_state()
	_check(not state.foreground and not state.handVisible and state.selectedCardIds.is_empty() and not state.controls.canSendAction,
		mode + ": focus loss immediately closes privacy and input gates")
	_check(not _has_private_ranks(state) and not _has_private_ranks(table._state),
		mode + ": focus loss drops private ranks from controller and table CPU snapshots")
	_check(_node_ids(table) == before and _private_faces(main) > 0,
		mode + ": focus notification defers scene erasure to the engine frame")
	controller.reveal_hand()
	controller.toggle_card(card_id)
	controller.play_selected()
	controller.challenge()
	_check(bridge.events.size() == 1 and controller.presentation_state().selectedCardIds.is_empty(),
		mode + ": stale input callbacks cannot emit an action after focus loss")
	await process_frame
	_check(paused and _private_faces(main) == 0, mode + ": the first background frame erases bindings and pauses the table")
	before = _node_ids(table)
	main.notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	for _index in 32:
		_foreground(main, true)
		controller.reveal_hand()
		controller.toggle_card(card_id)
		_foreground(main, false)
	_foreground(main, true)
	_check(_node_ids(table) == before and _private_faces(main) == 0,
		mode + ": a paused burst never rebuilds scene resources in command callbacks")
	_check(not _has_private_ranks(table._state) and table._state.selectedCardIds.is_empty(),
		mode + ": only the latest concealed CPU snapshot survives a burst")
	await process_frame
	_check(not paused and _private_faces(main) == 0 and bridge.events.size() == 1,
		mode + ": always-processing reconciliation resumes with the latest concealed state")
	before = _node_ids(table)
	table._request_lobby()
	_check(_node_ids(table) == before and main.find_child("LobbyConfirmation", true, false) == null,
		mode + ": lobby input requests graphics without constructing them")
	await process_frame
	_check(main.find_child("LobbyConfirmation", true, false) != null, mode + ": the next frame constructs lobby confirmation")
	var stale_confirm: BaseButton = get_first_node_in_group("partydeck_action_lobby_confirm")
	var stale_reveal: BaseButton = get_first_node_in_group("partydeck_action_reveal")
	var launch: Dictionary = JSON.parse_string(bridge.launch)
	var view := {"protocolVersion": 1, "presentationId": controller.presentation_id, "type": "view",
		"revision": "1", "schemaId": launch.schemaId, "payload": launch.payload}
	_restore_integer_tokens(view)
	_check(main.receive_document(JSON.stringify(view)), mode + ": a new authority view is admitted before rendering")
	if _check(stale_confirm != null and stale_reveal != null, mode + ": prior-view controls exist for the callback check"):
		stale_confirm.pressed.emit()
		stale_reveal.pressed.emit()
	_check(bridge.events.size() == 1 and not controller.presentation_state().handVisible,
		mode + ": old controls cannot act or reveal at a newly received revision before its frame")
	await process_frame
	before = _node_ids(table)
	table._close_lobby_dialog()
	_check(_node_ids(table) == before, mode + ": lobby cancellation defers hierarchy mutation")
	await process_frame
	_check(main.find_child("LobbyConfirmation", true, false) == null, mode + ": the next frame removes lobby confirmation")
	if mode == "3d":
		before = _node_ids(table)
		table._toggle_history()
		_check(_node_ids(table) == before, "3d: history input defers its layout rebuild")
		await process_frame
		_check(_node_ids(table) != before, "3d: history layout changes inside the next frame")
	await _check_audio_loss(main, mode)
	before = _node_ids(table)
	controller.reveal_hand()
	main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": controller.presentation_id, "type": "close"}))
	_check(controller.presentation_state().closed and table._state.game.is_empty(),
		mode + ": Close immediately clears live controller and table CPU data")
	_check(not _foreground(main, true) and _node_ids(table) == before,
		mode + ": Close rejects later commands without off-frame scene destruction")
	await process_frame
	_check(main._presentation == null and _private_faces(main) == 0, mode + ": Close wins over an earlier queued reveal")
	await process_frame
	_check(main._presentation == null and bridge.events.size() == 1, mode + ": later frames cannot recreate a closed table")
	await _dispose_main(main, bridge)


func _check_audio_loss(main: Node, mode: String) -> void:
	var player: AudioStreamPlayer = get_first_node_in_group("partydeck_feedback")
	var silence := AudioStreamWAV.new()
	silence.mix_rate = 8000
	var data := PackedByteArray()
	data.resize(80_000)
	silence.data = data
	player.stream = silence
	player.play()
	_check(player.playing, mode + ": a live playback exists before coalesced focus loss")
	_foreground(main, false)
	_foreground(main, true)
	await process_frame
	_check(not player.playing, mode + ": a brief foreground loss still stops existing playback on the next frame")


func _check_before_first_frame(mode: String, fail_initialization: bool) -> void:
	await process_frame
	var bridge := OrdinaryBridge.new()
	bridge.launch = FileAccess.get_file_as_string(_fixtures.path_join("launch-%s.json" % mode))
	Engine.register_singleton("PartyDeckBridge", bridge)
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	if fail_initialization:
		main._native_display_scale_valid = false
	else:
		main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": main.controller.presentation_id, "type": "close"}))
	await process_frame
	if fail_initialization:
		_check(bridge.events.size() == 1 and bridge.events[0].type == "failed" and main.controller.presentation_state().closed,
			mode + ": failed initialization suppresses the retained Ready event")
	else:
		_check(bridge.events.is_empty() and main._presentation == null,
			mode + ": Close before the first frame prevents both mounting and Ready")
	await _dispose_main(main, bridge)


func _foreground(main: Node, active: bool) -> bool:
	return main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": main.controller.presentation_id,
		"type": "foreground", "isForeground": active}))


func _node_ids(node: Node) -> Array[int]:
	var ids: Array[int] = [node.get_instance_id()]
	for child in node.get_children():
		ids.append_array(_node_ids(child))
	return ids


func _private_faces(main: Node) -> int:
	return int(JSON.parse_string(main.diagnostics_document()).privateFaceCount)


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


func _dispose_main(main: Node, bridge: OrdinaryBridge) -> void:
	root.remove_child(main)
	_check(not _foreground(main, true), "A detached root rejects bridge commands")
	main.queue_free()
	Engine.unregister_singleton("PartyDeckBridge")
	paused = false
	root.content_scale_factor = 1.0
	await process_frame
	bridge.free()


func _check(condition: bool, description: String) -> bool:
	_checks.append({"check": description, "passed": condition})
	if not condition:
		_failures += 1
		push_error(description)
	return condition
