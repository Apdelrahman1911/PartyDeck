extends SceneTree
## Independent geometry and viewport-input review. Image review remains separate.
## Run against production resources with the recipient-safe launch-3d fixture.

const CASES := [
	{"name": "portrait-density-3", "pixels": Vector2i(1080, 2340), "density": 3.0},
	{"name": "landscape-density-3", "pixels": Vector2i(2340, 1080), "density": 3.0},
	{"name": "portrait-fractional", "pixels": Vector2i(720, 1560), "density": 1.75},
	{"name": "portrait-density-1", "pixels": Vector2i(390, 844), "density": 1.0},
	{"name": "landscape-density-1", "pixels": Vector2i(844, 390), "density": 1.0},
	{"name": "tall-density-3", "pixels": Vector2i(1080, 2400), "density": 3.0},
]

var _options := {}
var _checks: Array[Dictionary] = []
var _observations: Array[Dictionary] = []
var _events: Array[Dictionary] = []
var _main: Node
var _case := ""


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--review-") and "=" in argument:
			var parts := argument.substr(9).split("=", true, 1)
			_options[parts[0]] = parts[1]
	_run.call_deferred()


func _check(passed: bool, description: String) -> bool:
	_checks.append({"case": _case, "check": description, "passed": passed})
	return passed


func _run() -> void:
	var fixture_path := str(_options.get("fixture", ""))
	var output := str(_options.get("output", ""))
	if not fixture_path.is_absolute_path() or not output.is_absolute_path():
		push_error("Absolute --review-fixture and --review-output paths are required.")
		quit(1)
		return
	var fixture = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	if not fixture is Dictionary or fixture.get("type") != "launch":
		push_error("Expected a recipient-safe launch document.")
		quit(1)
		return
	fixture.presentationMode = "3d"
	fixture.preferences.reduceMotion = false
	fixture.preferences.soundEnabled = false
	fixture.preferences.textScale = 1.0
	_restore_integer_tokens(fixture)
	for scenario: Dictionary in CASES:
		if _options.has("case") and _options.case != scenario.name:
			continue
		_case = scenario.name
		await _review_case(scenario, fixture)
	var passed := not _checks.is_empty()
	for item: Dictionary in _checks:
		passed = passed and item.passed
	var report := {
		"result": "passed" if passed else "failed",
		"kind": "independent-3d-quality-geometry-and-input-review",
		"engine": Engine.get_version_info().string,
		"checks": _checks,
		"observations": _observations,
		"reviewScriptSha256": _file_sha256(get_script().resource_path),
		"mainPackSha256": _file_sha256(str(_options.get("pack", ""))),
		"sourceSha256": {
			"table": _file_sha256("res://presentations/three_d/table.gd"),
			"card": _file_sha256("res://presentations/three_d/card_3d.gd"),
			"main": _file_sha256("res://scripts/main.gd"),
			"fixture": _file_sha256(fixture_path),
		},
		"limitations": "Geometry and injected viewport mouse input only. No visual approval, physical-device input, authority-accepted gameplay, or GPU performance claim.",
	}
	if DirAccess.make_dir_recursive_absolute(output) != OK:
		push_error("Could not create review output.")
		quit(1)
		return
	var file := FileAccess.open(output.path_join("report.json"), FileAccess.WRITE)
	if file == null:
		push_error("Could not write review report.")
		quit(1)
		return
	file.store_string(JSON.stringify(report, "\t") + "\n")
	print("Independent 3D quality review: ", report.result, " (", _checks.size(), " checks); ", output)
	quit(0 if passed else 1)


func _review_case(scenario: Dictionary, fixture: Dictionary) -> void:
	root.content_scale_factor = 1.0
	root.size = scenario.pixels
	_events.clear()
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void: _events.append(JSON.parse_string(document)))
	root.add_child(_main)
	current_scene = _main
	_check(_main._configure_native_display_scale(scenario.density), "Production density configuration accepted")
	if not _check(_main.receive_document(JSON.stringify(fixture)), "Production controller accepted safe fixture"):
		_cleanup()
		return
	await _settle()
	_check(root.size == scenario.pixels, "Requested physical window dimensions retained")
	_check(root.get_visible_rect().size.is_equal_approx(Vector2(scenario.pixels) / scenario.density), "Logical viewport reflects physical size and density")
	if not _check(is_instance_valid(_main._presentation), "Production presentation instantiated"):
		_cleanup()
		return
	_measure("concealed")
	_check(get_nodes_in_group("partydeck_private_face").is_empty(), "Concealed table contains no private face nodes")
	if not await _click_control("partydeck_action_reveal"):
		_cleanup()
		return
	if not _check(_main.controller.presentation_state().handVisible, "Viewport input revealed the local hand"):
		_cleanup()
		return
	_measure("revealed")
	var count: int = fixture.payload.game.yourHand.size()
	for index: int in [0, count - 1]:
		if not await _click_card_face(index):
			_cleanup()
			return
		_check(fixture.payload.game.yourHand[index].id in _main.controller.presentation_state().selectedCardIds,
			"Input at rendered card %d center selected that card" % index)
	_measure("selected-ends")
	if await _click_card_face(0):
		_check(fixture.payload.game.yourHand[0].id not in _main.controller.presentation_state().selectedCardIds,
			"Input at lifted first-card center deselected that card")
	if await _click_control("partydeck_action_hide"):
		_check(get_nodes_in_group("partydeck_private_face").is_empty()
			and get_nodes_in_group("partydeck_hand_card").is_empty()
			and _main.controller.presentation_state().selectedCardIds.is_empty(), "Cover erased private faces, hit targets and selection")
	_check(_events.size() == 1 and _events[0].get("type") == "ready", "Local reveal and selection emitted no gameplay event")
	_cleanup()
	await process_frame


func _measure(state: String) -> void:
	var table: Control = _main._presentation
	var stage: Control = table._stage
	var container: SubViewportContainer = table._viewport_container
	var viewport: SubViewport = table._viewport
	var camera: Camera3D = table._camera
	# Measure the displayed surface through its actual transform, independent of
	# the production pixel-sizing and overlay-positioning helper functions.
	var physical_transform := root.get_final_transform() * stage.get_global_transform_with_canvas()
	var physical_size := Vector2(physical_transform.x.length() * stage.size.x, physical_transform.y.length() * stage.size.y)
	var rendered_stage: Rect2 = stage.get_global_transform_with_canvas().affine_inverse() \
		* container.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, container.size)
	_check(rendered_stage.is_equal_approx(Rect2(Vector2.ZERO, stage.size)), state + ": displayed viewport covers the logical stage")
	_check(absf(viewport.size.x - physical_size.x) <= 1.01 and absf(viewport.size.y - physical_size.y) <= 1.01,
		state + ": 3D target covers native physical stage within one pixel")
	var table_points := PackedVector2Array()
	var table_meshes := 0
	for node in table._world.get_children():
		if node is MeshInstance3D and node.mesh != null:
			table_meshes += 1
			for vertex: Vector3 in node.mesh.get_faces():
				table_points.append(_project_to_stage(node.to_global(vertex)))
	if not _check(table_meshes >= 3 and not table_points.is_empty(), state + ": measured actual table mesh triangles"):
		return
	var bounds := _bounds(table_points)
	var margin := maxf(8.0, stage.size.x * 0.04)
	_check(bounds.position.x >= margin - 0.01 and stage.size.x - bounds.end.x >= margin - 0.01,
		state + ": complete table rim retains 4 percent or 8 logical pixels at each side")
	_check(bounds.position.y >= -0.01 and bounds.end.y <= stage.size.y + 0.01,
		state + ": complete table depth remains within stage")
	var cards: Array[Dictionary] = []
	var targets: Array[Rect2] = []
	for binding: Dictionary in table._card_bindings:
		var face: MeshInstance3D = binding.card.face
		var face_points := PackedVector2Array()
		for vertex: Vector3 in face.mesh.get_faces():
			face_points.append(_project_to_stage(face.to_global(vertex)))
		var face_bounds := _bounds(face_points)
		_check(Rect2(Vector2.ZERO, stage.size).grow(0.01).encloses(face_bounds), state + ": card face fits inside stage")
		if binding.target == null:
			continue
		var target: Button = binding.target
		var target_transform := stage.get_global_transform_with_canvas().affine_inverse() * target.get_global_transform_with_canvas()
		var target_bounds: Rect2 = target_transform * Rect2(Vector2.ZERO, target.size)
		# Transform size vectors directly: subtracting translated Rect2 endpoints can
		# turn an exact 48-pixel width into 47.9999847 through float cancellation.
		var target_size := Vector2(target_transform.x.length() * target.size.x, target_transform.y.length() * target.size.y)
		_check(target_size.x >= 48.0 and target_size.y >= 48.0, state + ": card hit area retains 48 logical pixel floor")
		_check(target_bounds.has_point(_project_to_stage(face.global_position)), state + ": displayed face center lies within its hit area")
		for previous: Rect2 in targets:
			_check(not target_bounds.intersects(previous), state + ": card hit areas do not overlap")
		targets.append(target_bounds)
		cards.append({"index": target.get_meta("card_index"), "faceBounds": _rect(face_bounds),
			"hitBounds": _rect(target_bounds), "hitSizeInStage": _vector(target_size), "controlSize": _vector(target.size)})
	_observations.append({"case": _case, "state": state, "physicalWindow": _vector(Vector2(root.size)),
		"logicalViewport": _vector(root.get_visible_rect().size), "stage": _vector(stage.size),
		"physicalStage": _vector(physical_size), "subViewport": _vector(Vector2(viewport.size)),
		"msaa": viewport.msaa_3d, "cameraSize": camera.size, "tableBounds": _rect(bounds),
		"sideMargins": [bounds.position.x, stage.size.x - bounds.end.x], "requiredSideMargin": margin, "cards": cards})


func _project_to_stage(point: Vector3) -> Vector2:
	var table: Control = _main._presentation
	var container: SubViewportContainer = table._viewport_container
	var pixel: Vector2 = table._camera.unproject_position(point)
	var surface_point := pixel * container.size / Vector2(table._viewport.size)
	return table._stage.get_global_transform_with_canvas().affine_inverse() * container.get_global_transform_with_canvas() * surface_point


func _click_card_face(index: int) -> bool:
	for binding: Dictionary in _main._presentation._card_bindings:
		if binding.target != null and int(binding.target.get_meta("card_index", -1)) == index:
			await _scroll_into_view(binding.target)
			var point: Vector2 = _main._presentation._stage.get_global_transform_with_canvas() \
				* _project_to_stage(binding.card.face.global_position)
			return await _click_at(point)
	return _check(false, "Card %d has an input binding" % index)


func _click_control(group: String) -> bool:
	for node in get_nodes_in_group(group):
		if node is Button and node.is_visible_in_tree() and not node.disabled:
			await _scroll_into_view(node)
			return await _click_at(node.get_global_transform_with_canvas() * (node.size * 0.5))
	return _check(false, "Enabled control exists: " + group)


func _click_at(logical_point: Vector2) -> bool:
	if not _check(root.get_visible_rect().has_point(logical_point), "Projected input point is inside visible root viewport"):
		return false
	# push_input(false) accepts embedder coordinates and applies the root density
	# conversion before dispatching _gui_input. This is not physical-device input.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Viewport.xml
	var physical_point := root.get_final_transform() * logical_point
	var motion := InputEventMouseMotion.new()
	motion.position = physical_point
	motion.global_position = physical_point
	root.push_input(motion, false)
	await process_frame
	for pressed: bool in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = physical_point
		event.global_position = physical_point
		event.button_index = MOUSE_BUTTON_LEFT
		event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		event.pressed = pressed
		root.push_input(event, false)
		await process_frame
	await _settle()
	return true


func _scroll_into_view(control: Control) -> void:
	var ancestor := control.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(control)
		ancestor = ancestor.get_parent()
	await _settle()


func _settle() -> void:
	await process_frame
	await process_frame
	await create_timer(0.25).timeout
	RenderingServer.force_draw()


func _cleanup() -> void:
	root.remove_child(_main)
	_main.free()
	_main = null
	current_scene = null
	paused = false


func _bounds(points: PackedVector2Array) -> Rect2:
	var bounds := Rect2(points[0], Vector2.ZERO)
	for point: Vector2 in points:
		bounds = bounds.expand(point)
	return bounds


func _vector(value: Vector2) -> Array:
	return [value.x, value.y]


func _rect(value: Rect2) -> Array:
	return [value.position.x, value.position.y, value.size.x, value.size.y]


func _file_sha256(path: String) -> Variant:
	# Exported scripts may be remapped to bytecode; identify that run by PCK hash.
	return FileAccess.get_sha256(path) if not path.is_empty() and FileAccess.file_exists(path) else null


func _restore_integer_tokens(value: Variant) -> void:
	# The strict wire expects integer counts after Godot's JSON float parsing.
	if value is Dictionary:
		for key in value:
			if value[key] is float and value[key] == floorf(value[key]):
				value[key] = int(value[key])
			else:
				_restore_integer_tokens(value[key])
	elif value is Array:
		for child in value:
			_restore_integer_tokens(child)
