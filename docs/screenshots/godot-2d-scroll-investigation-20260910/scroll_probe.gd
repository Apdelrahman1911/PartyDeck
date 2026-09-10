extends SceneTree
## Exact reference round/density; real Godot input, no scene scroll setters.

var _options := {}
var _main: Node
var _scroll: ScrollContainer
var _next: Button
var _output := ""
var _events: Array[Dictionary] = []
var _gui_events: Array[Dictionary] = []
var _dragging := false
var _mouse_delta := Vector2.ZERO
var _screen_delta := Vector2.ZERO
var _mouse_count := 0
var _screen_count := 0
var _input_count := 0
var _scale := 1.75

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--probe-") and "=" in argument:
			var parts := argument.substr(8).split("=", true, 1)
			_options[parts[0]] = parts[1]
	Input.emulate_mouse_from_touch = true
	# Makes desktop ScrollContainer use its normal touchscreen branch.
	Input.emulate_touch_from_mouse = true
	ProjectSettings.set_setting("input_devices/pointing/emulate_touch_from_mouse", true)
	_run.call_deferred()

func _run() -> void:
	_output = str(_options.get("output", ""))
	if not _output.is_absolute_path() or DirAccess.make_dir_recursive_absolute(_output) != OK:
		push_error("Fresh absolute --probe-output required")
		quit(1)
		return
	root.size = Vector2i(720, 1204)
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	root.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_FRACTIONAL
	root.content_scale_factor = _scale
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void: _events.append(JSON.parse_string(document)))
	root.add_child(_main)
	current_scene = _main
	var launch := FileAccess.get_file_as_string("/tmp/partydeck-native-2d-scroll-investigation/round-four-launch-2d.json")
	if not _main.receive_document(launch):
		push_error("Safe authority fixture rejected")
		quit(1)
		return
	await _settle(0.3)
	_scroll = _main.find_child("TableScroll", true, false)
	_next = get_first_node_in_group("partydeck_action_next_round")
	_scroll.gui_input.connect(_observe_input)
	var before := _geometry()
	await _capture("01-before")
	# Native trace was in display coordinates, with engine surface y=312.
	# Remove only the host offset: the positions here remain physical pixels.
	var start := Vector2(359, 1291 - 312)
	var finish := Vector2(359, 884 - 312)
	var duration := float(_options.get("duration", "0.25"))
	var kind := str(_options.get("kind", "touch"))
	var held := await _gesture(start, finish, duration, kind)
	await _settle(1.4)
	var after := _geometry()
	await _capture("02-after-release")
	var next_requested := false
	if bool(after["fullyVisible"]):
		var point := _next.get_global_rect().get_center() * _scale
		_send_down(point, kind)
		await process_frame
		_send_up(point, kind)
		await _settle(0.15)
		next_requested = _events.size() == 2 and _events.back().get("type") == "intent" and _events.back().get("payload", {}).get("type") == "advance_round"
	var report := {
		"kind": "2d-native-geometry-scroll-investigation", "inputKind": kind,
		"durationRequestedSeconds": duration, "physicalStart": [start.x, start.y], "physicalEnd": [finish.x, finish.y],
		"displayScale": _scale, "expectedLogicalDrag": [(finish.x-start.x)/_scale, (finish.y-start.y)/_scale],
		"touchscreenAvailable": DisplayServer.is_touchscreen_available(),
		"before": before, "held": held, "afterRelease": after,
		"injectedDrags": _input_count, "mouseMotionsAtScroll": _mouse_count, "screenDragsAtScroll": _screen_count,
		"summedMouseRelative": [_mouse_delta.x, _mouse_delta.y], "summedScreenRelative": [_screen_delta.x, _screen_delta.y],
		"nextRequestedByActualTap": next_requested, "bridgeEvents": _events,
		"guiEvents": _gui_events,
		"limitations": "Real Godot X11/Mesa rendering and input with the exact native logical viewport, display density and authority view. This does not reproduce Android OS touch delivery or timing. Renderer source is unchanged."
	}
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print(JSON.stringify({"before": before, "held": held, "afterRelease": after, "injectedDrags": _input_count,
		"mouseCount": _mouse_count, "screenCount": _screen_count, "sumMouseRelative": str(_mouse_delta),
		"sumScreenRelative": str(_screen_delta), "nextRequested": next_requested}))
	quit(0)

func _geometry() -> Dictionary:
	var rect := _next.get_global_rect()
	var clip := _scroll.get_global_rect()
	return {"nextRect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
		"clipRect": [clip.position.x, clip.position.y, clip.size.x, clip.size.y],
		"scrollOffset": _scroll.scroll_vertical, "fullyVisible": clip.encloses(rect),
		"viewport": [root.get_visible_rect().size.x, root.get_visible_rect().size.y]}

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

func _gesture(start: Vector2, finish: Vector2, duration: float, kind: String) -> Dictionary:
	_send_down(start, kind)
	_dragging = true
	var started := Time.get_ticks_usec()
	var previous := start
	while true:
		await process_frame
		var fraction := minf(1.0, float(Time.get_ticks_usec() - started) / (duration * 1_000_000.0))
		var point := start.lerp(finish, fraction)
		if kind == "touch":
			var event := InputEventScreenDrag.new()
			event.index = 0
			event.position = point
			event.relative = point - previous
			event.velocity = (finish - start) / duration
			Input.parse_input_event(event)
		else:
			var event := InputEventMouseMotion.new()
			event.position = point
			event.global_position = point
			event.relative = point - previous
			event.button_mask = MOUSE_BUTTON_MASK_LEFT
			Input.parse_input_event(event)
		_input_count += 1
		Input.flush_buffered_events()
		previous = point
		if fraction >= 1.0:
			break
	var held := _geometry()
	held["actualDurationSeconds"] = float(Time.get_ticks_usec() - started) / 1_000_000.0
	_dragging = false
	_send_up(finish, kind)
	return held

func _send_down(point: Vector2, kind: String) -> void:
	if kind == "touch":
		var event := InputEventScreenTouch.new()
		event.index = 0
		event.position = point
		event.pressed = true
		Input.parse_input_event(event)
	else:
		var hover := InputEventMouseMotion.new()
		hover.position = point
		hover.global_position = point
		Input.parse_input_event(hover)
		var event := InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.button_mask = MOUSE_BUTTON_MASK_LEFT
		event.pressed = true
		Input.parse_input_event(event)
	Input.flush_buffered_events()

func _send_up(point: Vector2, kind: String) -> void:
	if kind == "touch":
		var event := InputEventScreenTouch.new()
		event.index = 0
		event.position = point
		event.pressed = false
		Input.parse_input_event(event)
	else:
		var event := InputEventMouseButton.new()
		event.position = point
		event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = false
		Input.parse_input_event(event)
	Input.flush_buffered_events()

func _capture(name: String) -> void:
	RenderingServer.force_draw()
	var pixels := root.get_texture().get_image()
	pixels.save_png(_output.path_join(name + ".png"))
	FileAccess.open(_output.path_join(name + ".json"), FileAccess.WRITE).store_string(_main.diagnostics_document())

func _settle(seconds: float) -> void:
	await process_frame
	await process_frame
	await create_timer(seconds).timeout
