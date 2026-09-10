extends SceneTree
## Real compatibility-renderer checks. No native host or latency result is simulated.

var _output := ""
var _fixture_path := ""
var _fixture: Dictionary
var _main: Node
var _table: Control
var _viewport: SubViewport
var _checks: Array[Dictionary] = []
var _frames: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _failures := 0
var _pre_draw_mode := -1
var _pre_draw_count := 0
var _skip_next_viewport_draw := false
var _initial_render_loop := true
var _initial_time_scale := 1.0


func _initialize() -> void:
	_initial_render_loop = RenderingServer.render_loop_enabled
	_initial_time_scale = Engine.time_scale
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
		push_error("Run with an actual display and the compatibility renderer; a dummy renderer is not evidence.")
		quit(1)
		return
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(_fixture_path))
	if not parsed is Dictionary or parsed.get("type") != "launch" \
		or parsed.payload.game.phase != "PLAYING" or parsed.payload.game.yourHand.is_empty() \
		or not parsed.payload.game.availableActions.canPlay:
		push_error("Use a recipient-safe PLAYING launch with a playable own hand.")
		quit(1)
		return
	_fixture = parsed
	root.size = Vector2i(390, 844)
	# Control exactly which root frames draw; the real scene and its Tweens still process.
	RenderingServer.render_loop_enabled = false
	if await _mount(false):
		await _exercise_redraws()
		await _dispose()
	if _failures == 0 and await _mount(true):
		await _exercise_reduced_motion()
		await _dispose()
	Engine.time_scale = _initial_time_scale
	RenderingServer.render_loop_enabled = _initial_render_loop
	paused = false
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks, "frames": _frames,
		"godotVersion": Engine.get_version_info().string, "renderingMethod": RenderingServer.get_current_rendering_method(),
		"fixture": _fixture_path, "pngFilesWritten": 0,
		"limitations": "Actual desktop scene, input, Tween, viewport modes and pixel buffers. Native privacy-cover presentation and Retained timing require native execution."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("3D redraw checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _mount(reduce_motion: bool) -> bool:
	paused = false
	_events.clear()
	var launch := _fixture.duplicate(true)
	launch.presentationMode = "3d"
	launch.preferences.reduceMotion = reduce_motion
	launch.preferences.soundEnabled = false
	launch.preferences.textScale = 1.0
	_restore_integer_tokens(launch)
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void: _events.append(JSON.parse_string(document)))
	root.add_child(_main)
	if not _check(_main.receive_document(JSON.stringify(launch)), "strict launch is accepted"):
		return false
	await _settle_layout()
	_table = _main._presentation
	if not _check(is_instance_valid(_table), "the actual 3D scene is mounted"):
		return false
	_viewport = _table._viewport
	RenderingServer.frame_pre_draw.connect(_observe_pre_draw)
	# Object::emit_signalp and get_signal_connection_list traverse the same slot map.
	# Verify this observer runs after the policy, instead of assuming connection order.
	var policy_index := -1
	var observer_index := -1
	var connections := RenderingServer.frame_pre_draw.get_connections()
	for index in range(connections.size()):
		if connections[index].callable == Callable(_table, "_prepare_viewport_frame"):
			policy_index = index
		if connections[index].callable == Callable(self, "_observe_pre_draw"):
			observer_index = index
	if not _check(policy_index >= 0 and observer_index > policy_index, "mode observer follows the table policy before each real draw"):
		return false
	_check(_events.size() == 1 and _events[0].type == "ready", "mount emits exactly one Ready")
	_check(_scene_current(), "mounted scene has applied current state")
	return true


func _exercise_redraws() -> void:
	var concealed := _draw("first concealed frame", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check(_private_nodes_erased(), "the first frame contains no private card nodes")
	for index in range(3):
		_check(_draw("concealed idle %d" % index, RenderingServer.VIEWPORT_UPDATE_DISABLED) == concealed,
			"unchanged concealed texture is retained")
	var root_before := _pixels_sha256(root.get_texture().get_image())
	var probe := ColorRect.new()
	probe.color = Color.MAGENTA
	probe.size = Vector2(16, 16)
	probe.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(probe)
	await _settle_layout()
	_check(_draw("root canvas changes", RenderingServer.VIEWPORT_UPDATE_DISABLED) == concealed,
		"root canvas changes do not rerasterize an unchanged 3D scene")
	_check(_pixels_sha256(root.get_texture().get_image()) != root_before,
		"the root really composites a new canvas frame while 3D remains idle")
	probe.queue_free()
	await _settle_layout()
	_draw("root canvas probe removed", RenderingServer.VIEWPORT_UPDATE_DISABLED)

	# Covered cards have no hit bindings. Their real transforms must still invalidate.
	var covered_card: Node3D = _table._cards.get_child(0)
	covered_card.position.z -= 0.25
	await _settle_layout()
	var moved_back := _draw("covered card moved", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check(moved_back != concealed, "moving a covered card changes the real texture")
	_draw("covered card idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	covered_card.position.z += 0.25
	await _settle_layout()
	_draw("covered card restored", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("covered card restored idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)

	# Force the real renderer to skip an armed request after preparation, leaving the
	# node's usable size unchanged. The pending request must survive that skipped draw.
	_table._camera.position.x += 0.1
	await _settle_layout()
	_skip_next_viewport_draw = true
	_draw("renderer skips armed viewport", RenderingServer.VIEWPORT_UPDATE_ONCE, false, RenderingServer.VIEWPORT_UPDATE_ONCE)
	RenderingServer.viewport_set_size(_viewport.get_viewport_rid(), _viewport.size.x, _viewport.size.y, _viewport.view_count)
	_draw("skipped request retries", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("retried request becomes idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)

	if not await _click("partydeck_action_reveal"):
		return
	var revealed := _draw("revealed state", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check(revealed != concealed and get_nodes_in_group("partydeck_private_face").size() == _fixture.payload.game.yourHand.size(),
		"Reveal paints the complete own hand")
	_check_targets("revealed")
	var revealed_root := _pixels_sha256(root.get_texture().get_image())
	await _settle_layout()
	_draw("revealed idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	_check(_pixels_sha256(root.get_texture().get_image()) == revealed_root,
		"the first revealed root frame already contains the final overlay layout")
	# Freeze elapsed time only while clicking. Step the actual card-created Tween so
	# slow rasterization cannot skip all intermediate poses during this behavior test.
	Engine.time_scale = 0.0
	if not await _click("partydeck_hand_card", 0):
		Engine.time_scale = _initial_time_scale
		return
	var tweens := get_processed_tweens()
	if not _check(tweens.size() == 1, "real selection creates exactly one card lift Tween"):
		Engine.time_scale = _initial_time_scale
		return
	var lift: Tween = tweens[0]
	lift.pause()
	Engine.time_scale = _initial_time_scale
	var selected_start := _draw("selection initial pose", RenderingServer.VIEWPORT_UPDATE_ONCE)
	var selected_card: Node3D = _table._card_bindings[0].card
	_check(is_equal_approx(selected_card.position.y, 0.36), "selection starts at its original card pose")
	var selected_root := _pixels_sha256(root.get_texture().get_image())
	await _settle_layout()
	_draw("selection initial pose idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	_check(_pixels_sha256(root.get_texture().get_image()) == selected_root,
		"the first selected root frame already contains the final overlay layout")
	var selected_finish := ""
	for delta in [0.04, 0.04, 0.07]:
		lift.custom_step(delta)
		await _settle_layout()
		selected_finish = _draw("actual lift pose %.5f" % selected_card.position.y, RenderingServer.VIEWPORT_UPDATE_ONCE)
		_check_targets("animated")
	_check(is_equal_approx(selected_card.position.y, 0.54), "the actual Tween reaches its final lift pose")
	_check(selected_finish != selected_start, "the selection motion changes the actual rasterized texture")
	_check(_draw("final lift idle", RenderingServer.VIEWPORT_UPDATE_DISABLED) == selected_finish,
		"the final animation pose remains in the idle texture")
	_table._request_target_update()
	_check(_draw("forced final pose reference", RenderingServer.VIEWPORT_UPDATE_ONCE) == selected_finish,
		"the retained final animation texture matches a fresh render of the final pose")
	_draw("reference returns to idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)

	root.size = Vector2i(844, 390)
	await _settle_layout()
	_draw("landscape resize", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check_targets("resized")
	_draw("landscape idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	root.size = Vector2i(390, 844)
	await _settle_layout()
	# Resizing rebuilds selected cards and their genuine Tweens. Finish these before
	# checking stable resize behavior, then separately exercise unusable target sizes.
	for tween in get_processed_tweens():
		tween.custom_step(0.2)
	await _settle_layout()
	_draw("portrait resize", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check_targets("portrait restored")
	var before_zero := _draw("portrait idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	var usable_size := _viewport.size
	_table._viewport_container.stretch = false
	for unusable in [Vector2i.ZERO, Vector2i.ONE]:
		_viewport.size = unusable
		_draw("unusable target %s" % unusable, RenderingServer.VIEWPORT_UPDATE_DISABLED, false)
	_viewport.size = usable_size
	_table._viewport_container.stretch = true
	await _settle_layout()
	_check(_draw("same-size texture recovery", RenderingServer.VIEWPORT_UPDATE_ONCE) == before_zero,
		"recovering the same usable size redraws the discarded texture")
	_draw("recovered target idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)

	_table._viewport_container.hide()
	_draw("hidden unchanged container", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	_table._viewport_container.show()
	_check(_viewport.render_target_update_mode == SubViewport.UPDATE_ALWAYS, "real container visibility re-enables ALWAYS before the policy")
	_draw("shown unchanged container", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	if not await _click("partydeck_action_hide"):
		return
	var covered := _draw("explicit hand cover", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check(_private_nodes_erased() and _main.controller.presentation_state().selectedCardIds.is_empty(),
		"Cover removes private faces, labels, targets and selection")
	_check(covered != selected_finish, "Cover replaces the real revealed texture")
	_draw("covered idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	if not await _click("partydeck_action_reveal"):
		return
	_draw("revealed before pause", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("revealed before pause idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	var foreground := {"protocolVersion": 1, "presentationId": _fixture.presentationId, "type": "foreground", "isForeground": false}
	_check(_main.receive_document(JSON.stringify(foreground)), "foreground loss is accepted")
	_check(not _main.controller.presentation_state().handVisible and not _main.controller.presentation_state().controls.canSendAction,
		"foreground loss immediately conceals controller state and rejects input")
	await _settle_layout()
	_check(paused and _scene_current() and _private_nodes_erased(), "paused scene applies the concealed state")
	_draw("paused concealment frame", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("paused concealed idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	foreground.isForeground = true
	_check(_main.receive_document(JSON.stringify(foreground)), "resume is accepted")
	await _settle_layout()
	_draw("resumed concealed frame", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("resumed concealed idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	_check(not paused and _private_nodes_erased() and _scene_current(), "resume keeps the current hand covered")
	_check(_events.size() == 1 and _events[0].type == "ready", "local reveal, selection, cover and lifecycle send no gameplay intent")


func _exercise_reduced_motion() -> void:
	_draw("reduced-motion first frame", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("reduced-motion initial idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	if not await _click("partydeck_action_reveal"):
		return
	_draw("reduced-motion reveal", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_draw("reduced-motion revealed idle", RenderingServer.VIEWPORT_UPDATE_DISABLED)
	if not await _click("partydeck_hand_card", 0):
		return
	_draw("reduced-motion selected frame", RenderingServer.VIEWPORT_UPDATE_ONCE)
	_check(is_equal_approx(_table._card_bindings[0].card.position.y, 0.54) and get_processed_tweens().is_empty(),
		"reduced motion paints the final selected pose immediately without a Tween")
	_check_targets("reduced motion")
	for index in range(3):
		_draw("reduced-motion selected idle %d" % index, RenderingServer.VIEWPORT_UPDATE_DISABLED)


func _observe_pre_draw() -> void:
	if not is_instance_valid(_viewport):
		return
	_pre_draw_count += 1
	_pre_draw_mode = RenderingServer.viewport_get_update_mode(_viewport.get_viewport_rid())
	if _skip_next_viewport_draw:
		_skip_next_viewport_draw = false
		RenderingServer.viewport_set_size(_viewport.get_viewport_rid(), 0, 0, _viewport.view_count)


func _draw(label: String, expected_before: int, read_texture: bool = true,
	expected_after: int = RenderingServer.VIEWPORT_UPDATE_DISABLED) -> String:
	var before_count := _pre_draw_count
	_pre_draw_mode = -1
	# No awaits occur while automatic drawing is enabled. Verify the table leaves
	# root drawing enabled during every real frame, then resume manual scheduling.
	RenderingServer.render_loop_enabled = true
	RenderingServer.force_draw(false)
	_check(RenderingServer.render_loop_enabled, label + ": root drawing remains enabled")
	RenderingServer.render_loop_enabled = false
	var after_mode := RenderingServer.viewport_get_update_mode(_viewport.get_viewport_rid())
	_check(_pre_draw_count == before_count + 1 and _pre_draw_mode == expected_before,
		label + ": actual server mode before drawing matches demand")
	_check(after_mode == expected_after, label + ": actual server mode after drawing matches consumption")
	var pixels := ""
	if read_texture:
		var texture_image := _viewport.get_texture().get_image()
		_check(texture_image != null and not texture_image.is_empty(), label + ": actual viewport texture exists")
		if texture_image != null and not texture_image.is_empty():
			pixels = _pixels_sha256(texture_image)
	_frames.append({"label": label, "beforeMode": _pre_draw_mode, "afterMode": after_mode,
		"width": _viewport.size.x, "height": _viewport.size.y, "pixelSha256": pixels})
	return pixels


func _click(group: String, card_index: int = -1) -> bool:
	var target: Button
	for node in get_nodes_in_group(group):
		if node is Button and node.is_visible_in_tree() and not node.disabled \
			and (card_index < 0 or int(node.get_meta("card_index", -1)) == card_index):
			target = node
			break
	if not _check(target != null, "enabled real input target exists: " + group):
		return false
	var ancestor := target.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(target)
		ancestor = ancestor.get_parent()
	await _settle_layout()
	var point := target.get_global_transform_with_canvas() * (target.size * 0.5)
	if not _check(root.get_visible_rect().has_point(point), "real input target is inside the root: " + group):
		return false
	ancestor = target.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer and not _check(ancestor.get_global_rect().has_point(point), "real input target is inside its scroll clip"):
			return false
		ancestor = ancestor.get_parent()
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	await process_frame
	for pressed in [true, false]:
		var button := InputEventMouseButton.new()
		button.position = point
		button.global_position = point
		button.button_index = MOUSE_BUTTON_LEFT
		button.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		button.pressed = pressed
		Input.parse_input_event(button)
		await process_frame
	await _settle_layout()
	return _check(_scene_current(), "real input reconciles current scene state: " + group)


func _check_targets(label: String) -> void:
	var count := 0
	for binding in _table._card_bindings:
		if binding.target == null:
			continue
		count += 1
		var points: Array[Vector3] = binding.card.corners()
		var bounds := Rect2(_table._camera.unproject_position(points[0]), Vector2.ZERO)
		for point in points:
			bounds = bounds.expand(_table._camera.unproject_position(point))
		_check(binding.target.get_rect().has_point(bounds.get_center()) and binding.target.size.x >= 48 and binding.target.size.y >= 48,
			label + ": card hit target follows its actual projected pose and keeps the input floor")
	_check(count == _fixture.payload.game.yourHand.size(), label + ": every own card retains an input target")


func _dispose() -> void:
	Engine.time_scale = _initial_time_scale
	var table_id := _table.get_instance_id()
	_check(_main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": _fixture.presentationId, "type": "close"})),
		"Close is accepted")
	await _settle_layout()
	_check(not is_instance_valid(_table) and _main._presentation == null and _private_nodes_erased(), "Close removes the actual scene and private nodes")
	var old_callbacks := 0
	for connection in RenderingServer.frame_pre_draw.get_connections():
		if connection.callable.get_object_id() == table_id:
			old_callbacks += 1
	_check(old_callbacks == 0, "teardown disconnects the table's draw callback")
	_check(not _scene_current(), "terminal teardown does not claim a current applied scene")
	RenderingServer.frame_pre_draw.disconnect(_observe_pre_draw)
	RenderingServer.force_draw(false)
	root.remove_child(_main)
	_main.queue_free()
	_main = null
	_table = null
	_viewport = null
	paused = false
	await _settle_layout()
	_check(get_processed_tweens().is_empty(), "teardown leaves no card Tweens")


func _scene_current() -> bool:
	return bool(JSON.parse_string(_main.diagnostics_document()).get("sceneStateApplied", false))


func _private_nodes_erased() -> bool:
	return get_nodes_in_group("partydeck_private_face").is_empty() \
		and get_nodes_in_group("partydeck_private_label").is_empty() and get_nodes_in_group("partydeck_hand_card").is_empty()


func _pixels_sha256(pixels: Image) -> String:
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(pixels.get_data())
	return hashing.finish().hex_encode()


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


func _settle_layout() -> void:
	await process_frame
	await process_frame
	await process_frame


func _check(passed: bool, description: String) -> bool:
	_checks.append({"passed": passed, "description": description})
	if not passed:
		_failures += 1
		push_error(description)
	return passed
