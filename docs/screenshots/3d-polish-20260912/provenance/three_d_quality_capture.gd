extends SceneTree
## Real-render, native-density evidence. May be passed as an external --script
## against either a source project or exported resources. Uses safe launch views.
## --check-baseline=true records quality failures without treating them as a gate.

var _options := {}
var _main: Node
var _output := ""
var _fixture_path := ""
var _events: Array[Dictionary] = []
var _captures: Array[Dictionary] = []
var _inputs: Array[Dictionary] = []
var _checks := {
	"nativeDensityConfigured": false,
	"requestedWindowSize": false,
	"physicalCaptureSize": true,
	"nativeViewportPixels": true,
	"tableRimContained": true,
	"concealedHandHasNoPrivateNodes": false,
	"ownHandRevealedByInput": false,
	"cardsSelectedByInput": false,
	"noGameplayIntent": false,
}


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-") and "=" in argument:
			var parts := argument.substr(8).split("=", true, 1)
			_options[parts[0]] = parts[1]
	_run.call_deferred()


func _run() -> void:
	_output = str(_options.get("output", ""))
	_fixture_path = str(_options.get("fixture", ""))
	if not _output.is_absolute_path() or not _fixture_path.is_absolute_path():
		_fail("Absolute --check-output and --check-fixture paths are required.")
		return
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		_fail("Could not create capture output.")
		return
	var fixture = JSON.parse_string(FileAccess.get_file_as_string(_fixture_path))
	if not fixture is Dictionary or fixture.get("type") != "launch":
		_fail("Expected a recipient-safe launch fixture.")
		return
	fixture.presentationMode = "3d"
	fixture.preferences.textScale = float(_options.get("text-scale", "1"))
	fixture.preferences.reduceMotion = true
	fixture.preferences.soundEnabled = false
	_restore_integer_tokens(fixture)
	var requested := Vector2i(int(_options.get("width", "1080")), int(_options.get("height", "2340")))
	root.size = requested
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void:
		_events.append(JSON.parse_string(document))
	)
	root.add_child(_main)
	current_scene = _main
	_checks.nativeDensityConfigured = _main._configure_native_display_scale(float(_options.get("density", "3")))
	if not _checks.nativeDensityConfigured or not _main.receive_document(JSON.stringify(fixture)):
		_fail("Native density or launch fixture was rejected.")
		return
	await _settle()
	_checks.requestedWindowSize = root.size == requested
	_checks.concealedHandHasNoPrivateNodes = get_nodes_in_group("partydeck_private_face").is_empty() \
		and get_nodes_in_group("partydeck_private_label").is_empty() \
		and get_nodes_in_group("partydeck_hand_card").is_empty()
	if not await _capture("01-concealed") or not await _click("partydeck_action_reveal"):
		return
	var state: Dictionary = _main.controller.presentation_state()
	_checks.ownHandRevealedByInput = bool(state.handVisible) \
		and get_nodes_in_group("partydeck_private_face").size() == state.game.yourHand.size()
	if not await _capture("02-revealed") or not await _click("partydeck_hand_card", 0):
		return
	var selected_count := 1
	if state.game.yourHand.size() > 1:
		if not await _click("partydeck_hand_card", state.game.yourHand.size() - 1):
			return
		selected_count = 2
	state = _main.controller.presentation_state()
	_checks.cardsSelectedByInput = state.selectedCardIds.size() == selected_count \
		and state.game.yourHand[0].id in state.selectedCardIds \
		and state.game.yourHand.back().id in state.selectedCardIds
	if not await _capture("03-selected"):
		return
	_checks.noGameplayIntent = _events.size() == 1 and _events[0].get("type") == "ready"
	var baseline: bool = _options.get("baseline", "false") == "true"
	for key in _checks:
		if baseline and key in ["nativeViewportPixels", "tableRimContained"]:
			continue
		if not bool(_checks[key]):
			_fail("Quality capture check failed: " + key)
			return
	_write_report("baseline-captured" if baseline else "passed")
	print("3D quality capture complete: ", _output)
	quit(0)


func _capture(label: String) -> bool:
	await _settle()
	RenderingServer.force_draw()
	var captured := root.get_texture().get_image()
	if captured == null or captured.is_empty():
		return _fail("The real root render target is empty.")
	var image_path := _output.path_join(label + ".png")
	if FileAccess.file_exists(image_path):
		return _fail("Refusing to overwrite an original capture: " + image_path)
	if captured.save_png(image_path) != OK:
		return _fail("Could not save the real-render capture.")
	_checks.physicalCaptureSize = _checks.physicalCaptureSize and captured.get_size() == root.size
	var measurements := _measure()
	if measurements.is_empty():
		return false
	_checks.nativeViewportPixels = _checks.nativeViewportPixels and measurements.nativeViewportPixels
	_checks.tableRimContained = _checks.tableRimContained and measurements.tableRimContained
	var record := {"label": label, "image": image_path,
		"imageSize": _vector2(captured.get_size()), "measurements": measurements,
		"diagnostics": JSON.parse_string(_main.diagnostics_document())}
	_captures.append(record)
	_write_json(_output.path_join(label + ".json"), record)
	return true


func _measure() -> Dictionary:
	var table: Node = _main.get("_presentation")
	if table == null:
		_fail("The 3D presentation is missing.")
		return {}
	var stage: Control = table.get("_stage")
	var viewport: SubViewport = table.get("_viewport")
	var camera: Camera3D = table.get("_camera")
	var world: Node3D = table.get("_world")
	if stage == null or viewport == null or camera == null or world == null:
		_fail("The real 3D stage, viewport, camera, or world is missing.")
		return {}
	var rim: MeshInstance3D
	for child in world.get_children():
		if child is MeshInstance3D and child.mesh is CylinderMesh:
			if rim == null or child.mesh.top_radius > rim.mesh.top_radius:
				rim = child
	if rim == null:
		_fail("No table rim mesh is available for projection measurement.")
		return {}
	var vertices := rim.mesh.get_faces()
	if vertices.is_empty():
		_fail("The table rim mesh has no rendered triangles.")
		return {}
	# Camera unprojection uses SubViewport pixels, not the logical Control size.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Camera3D.xml
	var rim_pixels := Rect2(camera.unproject_position(rim.to_global(vertices[0])), Vector2.ZERO)
	for vertex in vertices:
		rim_pixels = rim_pixels.expand(camera.unproject_position(rim.to_global(vertex)))
	var viewport_size := Vector2(viewport.size)
	var viewport_to_stage := stage.size / viewport_size
	var rim_stage := Rect2(rim_pixels.position * viewport_to_stage, rim_pixels.size * viewport_to_stage)
	# Viewport final transform includes the native Window density. The CanvasItem
	# transform alone ends in logical viewport coordinates.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Viewport.xml
	var stage_to_logical := stage.get_global_transform_with_canvas()
	var stage_to_physical := root.get_final_transform() * stage_to_logical
	var physical_scale := Vector2(stage_to_physical.x.length(), stage_to_physical.y.length())
	var physical_size := stage.size * physical_scale
	var pixel_error := (viewport_size - physical_size).abs()
	var native_pixels := pixel_error.x <= 1.01 and pixel_error.y <= 1.01
	var contained := rim_pixels.position.x >= -0.5 and rim_pixels.position.y >= -0.5 \
		and rim_pixels.end.x <= viewport_size.x + 0.5 and rim_pixels.end.y <= viewport_size.y + 0.5
	var margins := [rim_stage.position.x, rim_stage.position.y,
		stage.size.x - rim_stage.end.x, stage.size.y - rim_stage.end.y]
	return {
		"rootPhysicalSize": _vector2(root.size),
		"rootVisibleRect": _rect(root.get_visible_rect()),
		"rootStretchTransform": _transform(root.get_stretch_transform()),
		"rootFinalTransform": _transform(root.get_final_transform()),
		"contentScaleFactor": root.content_scale_factor,
		"stageLogicalRect": _rect(stage_to_logical * Rect2(Vector2.ZERO, stage.size)),
		"stagePhysicalRect": _rect(stage_to_physical * Rect2(Vector2.ZERO, stage.size)),
		"stagePhysicalScale": _vector2(physical_scale),
		"stageExpectedPhysicalSize": _vector2(physical_size),
		"subViewportSize": _vector2(viewport.size),
		"subViewportMsaa3D": viewport.msaa_3d,
		"renderTargetToStagePhysicalRatio": _vector2(viewport_size / physical_size),
		"nativePixelRoundingError": _vector2(pixel_error),
		"nativeViewportPixels": native_pixels,
		"cameraProjection": camera.projection,
		"cameraKeepAspect": camera.keep_aspect,
		"cameraSize": camera.size,
		"rimVertexCount": vertices.size(),
		"rimMeshRadius": rim.mesh.top_radius,
		"rimProjectedViewportRect": _rect(rim_pixels),
		"rimProjectedStageRect": _rect(rim_stage),
		"rimLogicalMarginsLeftTopRightBottom": margins,
		"rimSuggestedSideMargin": maxf(8, stage.size.x * 0.04),
		"tableRimContained": contained,
	}


func _click(group: String, index: int = -1) -> bool:
	var target: Button
	for node in get_nodes_in_group(group):
		if node is Button and node.is_visible_in_tree() and not node.disabled \
			and (index < 0 or int(node.get_meta("card_index", -1)) == index):
			target = node
			break
	if target == null:
		return _fail("No enabled input target: " + group)
	var ancestor := target.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(target)
		ancestor = ancestor.get_parent()
	await _settle()
	var logical := target.get_global_transform_with_canvas() * (target.size * 0.5)
	if not root.get_visible_rect().has_point(logical):
		return _fail("Input target center is outside the logical viewport: " + group)
	# Input.parse_input_event enters through Window's native-coordinate input path.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/scene/main/window.cpp
	var physical := root.get_final_transform() * logical
	var motion := InputEventMouseMotion.new()
	motion.position = physical
	motion.global_position = physical
	Input.parse_input_event(motion)
	await process_frame
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = physical
		event.global_position = physical
		event.button_index = MOUSE_BUTTON_LEFT
		event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		event.pressed = pressed
		Input.parse_input_event(event)
		await process_frame
	await _settle()
	_inputs.append({"group": group, "cardIndex": index,
		"logicalPoint": _vector2(logical), "physicalPoint": _vector2(physical)})
	return true


func _write_report(result: String, error: String = "") -> void:
	_write_json(_output.path_join("report.json"), {
		"result": result, "kind": "3d-native-density-real-render-capture",
		"godotVersion": Engine.get_version_info().string, "fixture": _fixture_path,
		"baseline": _options.get("baseline", "false") == "true",
		"checks": _checks, "captures": _captures, "inputs": _inputs, "error": error,
		"limitations": "Recipient-safe renderer fixture with real GL frames and mouse input. No device GPU, native accessibility, multiplayer, or authority-accepted play is claimed.",
	})


func _write_json(path: String, value: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(value, "\t") + "\n")


func _fail(reason: String) -> bool:
	if _output.is_absolute_path() and DirAccess.dir_exists_absolute(_output):
		_write_report("failed", reason)
	push_error(reason)
	quit(1)
	return false


func _settle() -> void:
	await process_frame
	await process_frame
	await create_timer(0.15).timeout


func _vector2(value: Vector2) -> Array:
	return [value.x, value.y]


func _rect(value: Rect2) -> Array:
	return [value.position.x, value.position.y, value.size.x, value.size.y]


func _transform(value: Transform2D) -> Array:
	return [value.x.x, value.x.y, value.y.x, value.y.y, value.origin.x, value.origin.y]


func _restore_integer_tokens(value: Variant) -> void:
	# The wire rejects floating point count/revision tokens after fixture re-encoding.
	if value is Dictionary:
		for key in value:
			if value[key] is float and value[key] == floor(value[key]):
				value[key] = int(value[key])
			else:
				_restore_integer_tokens(value[key])
	elif value is Array:
		for child in value:
			_restore_integer_tokens(child)
