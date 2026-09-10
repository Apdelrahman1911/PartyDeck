extends SceneTree
## Exact proposed native gestures with real input; never sets scene scroll positions.

const FIXTURE := "/tmp/partydeck-native-2d-scroll-investigation/round-four-launch-2d.json"
const AUTHORITY := "/tmp/partydeck-native-2d-scroll-adaptive/AcceptNext.java"
const AUTHORITY_CP := "/root/projects/PartyDeck/godot/qualification/build/modules/comparison/install/partydeck-godot-compare/lib/*"
var _options := {}
var _main: Node
var _scroll: ScrollContainer
var _next: Button
var _output := ""
var _raw: FileAccess
var _events: Array[Dictionary] = []
var _gui_events: Array[Dictionary] = []
var _dragging := false
var _mouse_delta := Vector2.ZERO
var _screen_delta := Vector2.ZERO
var _mouse_count := 0
var _screen_count := 0
var _input_count := 0
var _scale := 1.75
var _setup: Array[Dictionary] = []

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--probe-") and "=" in argument:
			var parts := argument.substr(8).split("=", true, 1)
			_options[parts[0]] = parts[1]
	Input.emulate_mouse_from_touch = true
	Input.emulate_touch_from_mouse = true
	ProjectSettings.set_setting("input_devices/pointing/emulate_touch_from_mouse", true)
	_run.call_deferred()

func _run() -> void:
	_output = str(_options.get("output", ""))
	if not _output.is_absolute_path() or DirAccess.dir_exists_absolute(_output):
		_fail("Fresh absolute --probe-output required")
		return
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		_fail("Cannot create output")
		return
	_raw = FileAccess.open(_output.path_join("bridge-events.jsonl"), FileAccess.WRITE)
	root.size = Vector2i(720, 1204)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	root.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_FRACTIONAL
	root.content_scale_factor = _scale
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(_record_document)
	root.add_child(_main)
	current_scene = _main
	if not _main.receive_document(FileAccess.get_file_as_string(FIXTURE)):
		_fail("Safe authority fixture rejected")
		return
	await _settle(0.3)
	_scroll = _main.find_child("TableScroll", true, false)
	_next = get_first_node_in_group("partydeck_action_next_round")
	_scroll.gui_input.connect(_observe_input)
	var initial := _geometry()
	await _capture("01-initial")
	var case_name := str(_options.get("case", "below"))
	var start := Vector2(359, 969)
	var finish := Vector2(359, 582)
	var duration := 0.885
	var expected_y := 809.0
	if case_name == "above":
		if not await _prepare_y(191.0):
			_fail("Could not prepare exact Next y191 with real touch input")
			return
		await _capture("02-prepared")
		start = Vector2(359, 744)
		finish = Vector2(359, 807)
		duration = 0.350
		expected_y = 191.0
	elif case_name != "below":
		_fail("Unknown probe case")
		return
	var before := _geometry()
	if float(before["nextRect"][1]) != expected_y or _events.size() != 1:
		_fail("Exact initial geometry or sole Ready event mismatch")
		return
	_reset_measurements()
	var held := await _gesture(start, finish, duration)
	await _settle(1.4)
	var after := _geometry()
	await _capture("03-after-release")
	var tap_point := Vector2.ZERO
	var next_requested := false
	var authority_accepted := false
	var authority_output: Array = []
	var authority_exit := -1
	if bool(after["fullyVisible"]):
		tap_point = _next.get_global_rect().get_center() * _scale
		_send_touch(tap_point, true)
		await process_frame
		_send_touch(tap_point, false)
		await _settle(0.15)
		next_requested = _events.size() == 2 and _events.back().get("type") == "intent" and _events.back().get("payload", {}).get("type") == "advance_round"
		if next_requested:
			authority_exit = OS.execute("java", PackedStringArray(["-cp", AUTHORITY_CP, AUTHORITY, _output]), authority_output, true)
			if authority_exit == 0:
				authority_accepted = _main.receive_document(FileAccess.get_file_as_string(_output.path_join("accepted-authority-view.json")))
				await _settle(0.2)
				await _capture("04-after-authority-acceptance")
	FileAccess.open(_output.path_join("authority-output.log"), FileAccess.WRITE).store_string("\n".join(authority_output))
	var report := {
		"kind": "2d-native-geometry-adaptive-scroll-validation", "case": case_name,
		"durationRequestedSeconds": duration, "physicalStart": [start.x, start.y], "physicalEnd": [finish.x, finish.y],
		"androidDisplayStart": [start.x, start.y + 312], "androidDisplayEnd": [finish.x, finish.y + 312],
		"displayScale": _scale, "expectedLogicalDrag": [(finish.x-start.x)/_scale, (finish.y-start.y)/_scale],
		"touchscreenAvailable": DisplayServer.is_touchscreen_available(),
		"initial": initial, "setupStrokes": _setup, "before": before, "held": held, "afterRelease": after,
		"injectedDrags": _input_count, "mouseMotionsAtScroll": _mouse_count, "screenDragsAtScroll": _screen_count,
		"summedMouseRelative": [_mouse_delta.x, _mouse_delta.y], "summedScreenRelative": [_screen_delta.x, _screen_delta.y],
		"tapPhysicalPosition": [tap_point.x, tap_point.y], "nextRequestedByActualTap": next_requested,
		"rawBridgeEvents": "bridge-events.jsonl", "authorityExit": authority_exit,
		"acceptedAuthorityViewAppliedToScene": authority_accepted, "guiEvents": _gui_events,
		"limitations": "Real Godot X11/Mesa rendering and touch input with the exact native logical viewport, density and authority view. Captured raw Next accepted by a fresh real adapter and actual Kotlin authority. This does not reproduce Android OS touch delivery or timing. Renderer source is unchanged."
	}
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t") + "\n")
	print(JSON.stringify({"case": case_name, "before": before, "held": held, "afterRelease": after,
		"injectedDrags": _input_count, "mouseMotions": _mouse_count, "screenDrags": _screen_count,
		"nextRequested": next_requested, "authorityAccepted": authority_accepted}))
	quit(0 if authority_accepted else 1)

func _record_document(document: String) -> void:
	# Preserve integer wire tokens exactly before Godot's JSON parser changes number types.
	_raw.store_line(document)
	_raw.flush()
	_events.append(JSON.parse_string(document))

func _prepare_y(target_y: float) -> bool:
	for index in range(8):
		var error := _next.get_global_rect().position.y - target_y
		if error == 0.0:
			return true
		var logical_distance := clampf(error, -220.0, 220.0)
		var center := Vector2(359, _scroll.get_global_rect().get_center().y * _scale)
		var start := center + Vector2(0, logical_distance * _scale / 2.0)
		var finish := center - Vector2(0, logical_distance * _scale / 2.0)
		var before := _geometry()
		var held := await _gesture(start, finish, maxf(0.35, absf(logical_distance) / 220.0), 0.25,
			target_y if absf(error) <= 220.0 else NAN)
		await _settle(0.15)
		_setup.append({"index": index, "physicalStart": [start.x, start.y], "physicalEnd": [finish.x, finish.y],
			"before": before, "held": held, "after": _geometry()})
	FileAccess.open(_output.path_join("setup-failure.json"), FileAccess.WRITE).store_string(JSON.stringify(_setup, "\t"))
	return false

func _gesture(start: Vector2, finish: Vector2, duration: float, hold_seconds := 0.0, refine_y := NAN) -> Dictionary:
	_send_touch(start, true)
	_dragging = true
	var started := Time.get_ticks_usec()
	var previous := start
	while true:
		await process_frame
		var fraction := minf(1.0, float(Time.get_ticks_usec() - started) / (duration * 1_000_000.0))
		var point := start.lerp(finish, fraction)
		_send_drag(previous, point, (finish - start) / duration)
		previous = point
		if fraction >= 1.0:
			break
	var actual_duration := float(Time.get_ticks_usec() - started) / 1_000_000.0
	var corrections: Array[Dictionary] = []
	if not is_nan(refine_y):
		for correction in range(8):
			await process_frame
			await process_frame
			var error := _next.get_global_rect().position.y - refine_y
			if error == 0.0:
				break
			var corrected := previous - Vector2(0, error * _scale)
			if not _scroll.get_global_rect().has_point(corrected / _scale):
				_fail("Setup correction would leave scroll clip")
				return {}
			corrections.append({"beforeY": _next.get_global_rect().position.y,
				"physicalStart": [previous.x, previous.y], "physicalEnd": [corrected.x, corrected.y]})
			_send_drag(previous, corrected, Vector2.ZERO)
			previous = corrected
	if hold_seconds > 0.0:
		await _settle(hold_seconds)
	var held := _geometry()
	held["actualDurationSeconds"] = actual_duration
	held["stationaryHoldSeconds"] = hold_seconds
	held["setupCorrections"] = corrections
	_dragging = false
	_send_touch(previous, false)
	return held

func _send_drag(previous: Vector2, point: Vector2, velocity: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = 0
	event.position = point
	event.relative = point - previous
	event.velocity = velocity
	Input.parse_input_event(event)
	_input_count += 1
	Input.flush_buffered_events()

func _send_touch(point: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = 0
	event.position = point
	event.pressed = pressed
	Input.parse_input_event(event)
	Input.flush_buffered_events()

func _geometry() -> Dictionary:
	var rect := _next.get_global_rect()
	var clip := _scroll.get_global_rect()
	return {"nextRect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
		"clipRect": [clip.position.x, clip.position.y, clip.size.x, clip.size.y],
		"scrollOffset": _scroll.scroll_vertical, "fullyVisible": clip.encloses(rect),
		"viewport": [root.get_visible_rect().size.x, root.get_visible_rect().size.y]}

func _reset_measurements() -> void:
	_gui_events.clear()
	_mouse_delta = Vector2.ZERO
	_screen_delta = Vector2.ZERO
	_mouse_count = 0
	_screen_count = 0
	_input_count = 0

func _observe_input(event: InputEvent) -> void:
	if not _dragging:
		return
	if event is InputEventMouseMotion:
		_mouse_count += 1
		_mouse_delta += event.relative
		_gui_events.append({"kind": "mouse", "relative": [event.relative.x, event.relative.y], "offset": _scroll.scroll_vertical, "device": event.device})
	elif event is InputEventScreenDrag:
		_screen_count += 1
		_screen_delta += event.relative
		_gui_events.append({"kind": "screen", "relative": [event.relative.x, event.relative.y], "offset": _scroll.scroll_vertical, "device": event.device})

func _capture(name: String) -> void:
	RenderingServer.force_draw()
	root.get_texture().get_image().save_png(_output.path_join(name + ".png"))
	FileAccess.open(_output.path_join(name + ".json"), FileAccess.WRITE).store_string(_main.diagnostics_document())

func _settle(seconds: float) -> void:
	await process_frame
	await process_frame
	await create_timer(seconds).timeout

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
