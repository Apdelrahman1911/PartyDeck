extends SceneTree
## Observes the actual 2D scene early and late without moving its scroll position.

var _options := {}
var _main: Node
var _output := ""
var _events: FileAccess
var _started := 0
var _samples: Array[Dictionary] = []


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--probe-") and "=" in argument:
			var parts := argument.substr(8).split("=", true, 1)
			_options[parts[0]] = parts[1]
	_run.call_deferred()


func _run() -> void:
	_output = str(_options.get("output", ""))
	if not _output.is_absolute_path() or DirAccess.dir_exists_absolute(_output):
		_fail("Fresh absolute output path required")
		return
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		_fail("Cannot create evidence directory")
		return
	_events = FileAccess.open(_output.path_join("bridge-events.jsonl"), FileAccess.WRITE)
	if _events == null:
		_fail("Cannot preserve bridge events")
		return
	root.size = Vector2i(720, int(_options.get("height", "1244")))
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	root.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_FRACTIONAL
	root.content_scale_factor = 1.75
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void:
		_events.store_line(document)
		_events.flush()
	)
	root.add_child(_main)
	current_scene = _main
	_started = Time.get_ticks_msec()
	if not _main.receive_document(FileAccess.get_file_as_string(str(_options.get("fixture", "")))):
		_fail("The authority launch was rejected")
		return
	for frame in range(1, 61):
		await process_frame
		if frame == 4 or frame == 60:
			if not _capture("01-early" if frame == 4 else "02-late", frame):
				return
	var observations := FileAccess.open(_output.path_join("observations.json"), FileAccess.WRITE)
	if observations == null or _samples.size() != 2:
		_fail("Two preserved observations are required")
		return
	observations.store_string(JSON.stringify(_samples, "\t"))
	quit(0)


func _capture(name: String, frame_callbacks: int) -> bool:
	var table: Node = _main._presentation
	var reveal: Button = get_first_node_in_group("partydeck_action_reveal")
	if not is_instance_valid(table) or not is_instance_valid(reveal) or not reveal.is_visible_in_tree():
		_fail("The actual presentation and visible Reveal control are required")
		return false
	var scroll: ScrollContainer = table.find_child("TableScroll", true, false)
	var cover: Control = table.find_child("HandCover", true, false)
	if scroll == null or cover == null:
		_fail("The actual body scroll and hand cover are required")
		return false
	var rect := reveal.get_global_rect()
	var clip := scroll.get_global_rect()
	var cover_rect := cover.get_global_rect()
	var observation := {
		"name": name,
		"processFrameCallbacksSinceLaunch": frame_callbacks,
		"elapsedMsSinceLaunch": Time.get_ticks_msec() - _started,
		"revealRect": _rect(rect),
		"clipRect": _rect(clip),
		"coverRect": _rect(cover_rect),
		"revealFullyVisible": clip.encloses(rect),
		"coverFullyVisible": clip.encloses(cover_rect),
		"bottomOverflow": maxf(0, rect.end.y - clip.end.y),
		"scrollOffset": scroll.scroll_vertical,
		"decorativeSurfaceMinimumHeight": table._surface.custom_minimum_size.y,
		"viewport": _rect(root.get_visible_rect()),
	}
	_samples.append(observation)
	RenderingServer.force_draw()
	if root.get_texture().get_image().save_png(_output.path_join(name + ".png")) != OK:
		_fail("Cannot preserve rendered image")
		return false
	var diagnostic := FileAccess.open(_output.path_join(name + ".json"), FileAccess.WRITE)
	if diagnostic == null:
		_fail("Cannot preserve paired diagnostics")
		return false
	diagnostic.store_string(_main.diagnostics_document())
	print(JSON.stringify(observation))
	return true


func _rect(value: Rect2) -> Array:
	return [value.position.x, value.position.y, value.size.x, value.size.y]


func _fail(message: String) -> void:
	push_error(message)
	quit(1)
