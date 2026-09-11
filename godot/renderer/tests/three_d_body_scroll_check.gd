extends SceneTree
## Actual Godot body-scroll behavior with synthetic host controls and input.
## This is not Android execution, screen-reader qualification or pixel acceptance.

const BodyScroll = preload("res://presentations/three_d/body_scroll.gd")

var _viewport: SubViewport
var _output := ""
var _focus_style := 0
var _checks: Array[Dictionary] = []
var _failures := 0


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-output="):
			_output = argument.trim_prefix("--check-output=")
		elif argument.begins_with("--check-focus-style="):
			_focus_style = int(argument.trim_prefix("--check-focus-style="))
	ProjectSettings.set_setting("gui/common/show_focus_state_on_pointer_event", _focus_style)
	Input.emulate_touch_from_mouse = true
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(389, 215)
	_viewport.disable_3d = true
	root.add_child(_viewport)
	_viewport.notify_mouse_entered()
	_run.call_deferred()


func _run() -> void:
	if not _output.is_absolute_path() or _focus_style not in [0, 2]:
		push_error("Use absolute --check-output and --check-focus-style=0 or 2.")
		quit(1)
		return
	_check(DisplayServer.is_touchscreen_available(), "host touch emulation enables native drag behavior")
	await _pointer_cases()
	await _focus_cases()
	await _drag_case()
	await _lifecycle_cases()
	await _table_wiring_cases()
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks,
		"godotVersion": Engine.get_version_info().string, "pointerFocusStyle": _focus_style,
		"scope": "Actual BodyScroll and GUI dispatch with synthetic host controls/events; no native acceptance."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("3D body scroll checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _mount(use_body: bool = true, disabled: bool = false, consume: bool = false) -> Dictionary:
	var scroll: ScrollContainer = BodyScroll.new() if use_body else ScrollContainer.new()
	scroll.position = Vector2(16, 96)
	scroll.size = Vector2(357, 103)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.scroll_deadzone = 8
	scroll.follow_focus = true
	var content := Control.new()
	content.mouse_filter = Control.MOUSE_FILTER_PASS
	content.custom_minimum_size = Vector2(349, 1000)
	scroll.add_child(content)
	var origin := Button.new()
	origin.text = "Disabled Play" if disabled else "Previous round review"
	origin.position = Vector2(0, 76 if disabled else 37)
	origin.size = Vector2(349, 68 if disabled else 108)
	origin.disabled = disabled
	origin.mouse_filter = Control.MOUSE_FILTER_STOP if consume else Control.MOUSE_FILTER_PASS
	content.add_child(origin)
	var destination := Button.new()
	destination.text = "Keyboard or programmatic destination"
	destination.position = Vector2(0, 420)
	destination.size = Vector2(300, 50)
	destination.mouse_filter = Control.MOUSE_FILTER_PASS
	content.add_child(destination)
	origin.focus_next = origin.get_path_to(destination)
	var fixture := {"scroll": scroll, "origin": origin, "destination": destination, "presses": 0}
	origin.pressed.connect(func() -> void: fixture.presses += 1)
	_viewport.add_child(scroll)
	await _settle()
	return fixture


func _dispose(fixture: Dictionary) -> void:
	_viewport.remove_child(fixture.scroll)
	fixture.scroll.queue_free()
	await _settle()


func _pointer_cases() -> void:
	var baseline := await _mount(false)
	_mouse_button(Vector2(194, 181), true)
	_check(baseline.origin.has_focus() and baseline.scroll.scroll_vertical == 42,
		"unmodified ScrollContainer reproduces the clipped-button DOWN focus jump")
	_mouse_button(Vector2(194, 181), false)
	await _dispose(baseline)
	for disabled in [false, true]:
		var fixture := await _mount(true, disabled)
		_mouse_button(Vector2(194, 181), true)
		_check(fixture.origin.has_focus() and fixture.scroll.scroll_vertical == 0,
			"pointer focuses %s without moving the body" % ("disabled Play" if disabled else "history"))
		_check(fixture.origin.has_focus(true) == (_focus_style == 2),
			"pointer focus visibility follows the selected project policy")
		_mouse_button(Vector2(194, 181), false)
		_check(fixture.presses == (0 if disabled else 1), "ordinary click semantics survive focus suppression")
		fixture.destination.grab_focus()
		await _check_destination(fixture, "focus after pointer release reveals its complete destination")
		await _dispose(fixture)
	var nested := await _mount()
	var label := Label.new()
	label.text = "Nested pointer target"
	label.position = Vector2(10, 10)
	label.size = Vector2(250, 24)
	label.mouse_filter = Control.MOUSE_FILTER_PASS
	nested.origin.add_child(label)
	await _settle()
	_mouse_button(Vector2(40, 153), true)
	_check(nested.origin.has_focus() and nested.scroll.scroll_vertical == 0,
		"a nonfocusable pointer child resolves to its focusable ancestor")
	_mouse_button(Vector2(40, 153), false)
	await _dispose(nested)


func _focus_cases() -> void:
	for method in ["Tab", "programmatic", "inside child GUI", "already focused child GUI", "raw touch child GUI"]:
		var fixture := await _mount(true, false, true)
		if method == "already focused child GUI":
			fixture.origin.grab_focus()
			fixture.scroll.scroll_vertical = 0
			await _settle()
		if "child GUI" in method:
			fixture.origin.gui_input.connect(func(event: InputEvent) -> void:
				if (event is InputEventMouseButton and event.pressed) \
					or (event is InputEventScreenTouch and event.pressed):
					# Deliberately before accept_event and automatic STOP handling.
					fixture.destination.grab_focus()
			)
		if method == "raw touch child GUI":
			_touch(Vector2(194, 181), true)
		else:
			_mouse_button(Vector2(194, 181), true)
		if method == "Tab":
			_key_tab(true)
			_key_tab(false)
		elif method == "programmatic":
			fixture.destination.grab_focus()
		_check(fixture.destination.has_focus() and fixture.scroll.scroll_vertical > 0,
			"%s focuses and reveals synchronously in the pointer frame" % method)
		await _check_destination(fixture, "%s leaves the complete destination enclosed" % method)
		if method == "raw touch child GUI":
			_touch(Vector2(194, 181), false, true)
		else:
			_mouse_button(Vector2(194, 181), false)
		await _dispose(fixture)


func _drag_case() -> void:
	var fixture := await _mount()
	var start := Vector2(194, 181)
	var end := start - Vector2(0, 41.2)
	_mouse_button(start, true)
	_check(fixture.scroll.scroll_vertical == 0, "a bounded drag starts without a focus jump")
	var previous := start
	for index in range(1, 49):
		await create_timer(1.646 / 48).timeout
		var point := start.lerp(end, float(index) / 48)
		_mouse_motion(point, point - previous, true)
		previous = point
	_mouse_button(end, false)
	await create_timer(0.4).timeout
	_check(fixture.scroll.scroll_vertical > 0 and fixture.scroll.scroll_vertical <= 51.5,
		"the real host drag moves content within the half-clip interval")
	_check(fixture.presses == 0, "crossing the native scroll deadzone cancels history activation")
	fixture.destination.grab_focus()
	await _check_destination(fixture, "focus after a completed drag still reveals the whole target")
	await _dispose(fixture)


func _lifecycle_cases() -> void:
	var fixture := await _mount(true, false, true)
	_touch(Vector2(194, 181), true)
	_touch(Vector2(194, 181), false, true)
	fixture.destination.grab_focus()
	await _check_destination(fixture, "touch cancellation leaves normal focus following available")
	await _dispose(fixture)
	fixture = await _mount()
	fixture.scroll.follow_focus = false
	_mouse_button(Vector2(194, 181), true)
	_mouse_button(Vector2(194, 181), false)
	fixture.destination.grab_focus()
	await _settle()
	_check(not fixture.scroll.follow_focus and fixture.scroll.scroll_vertical == 0,
		"an explicit follow_focus opt-out remains disabled")
	await _dispose(fixture)
	var listeners := _viewport.gui_focus_changed.get_connections().size()
	fixture = await _mount(true, false, true)
	_mouse_button(Vector2(194, 181), true)
	await _dispose(fixture)
	_mouse_button(Vector2(194, 181), false)
	_check(_viewport.gui_focus_changed.get_connections().size() == listeners,
		"removing the layout releases its focus listeners")
	fixture = await _mount()
	fixture.destination.grab_focus()
	await _check_destination(fixture, "a replacement layout starts with normal focus following")
	await _dispose(fixture)


func _table_wiring_cases() -> void:
	var launch := FileAccess.get_file_as_string("res://tests/fixtures/short-public-context-launch.json")
	for pane in [Vector2i(389, 215), Vector2i(844, 390)]:
		_viewport.size = pane
		var main: Node = load("res://main.tscn").instantiate()
		var events: Array[Dictionary] = []
		main.bridge_event.connect(func(document: String) -> void: events.append(JSON.parse_string(document)))
		_viewport.add_child(main)
		# The existing strict fixture already contains integer protocol tokens.
		var document := launch.replace('"textScale":2.0', '"textScale":1.0') if pane.x > 700 else launch
		_check(main.receive_document(document), "the actual renderer accepts the existing launch at %s" % pane)
		await _settle()
		await _settle()
		var body := main.find_child("TableBodyScroll", true, false) as ScrollContainer
		_check(body != null and body.get_script() == BodyScroll and body.follow_focus,
			"the %s table mounts the production BodyScroll with normal following" % ("wide" if pane.x > 700 else "short"))
		_check(get_nodes_in_group("partydeck_private_face").is_empty() \
			and main.controller.presentation_state().selectedCardIds.is_empty(),
			"mounting the %s table keeps the hand concealed and unselected" % pane)
		_check(events.size() == 1 and events[0].type == "ready", "mounting the real table emits only Ready")
		_viewport.remove_child(main)
		main.queue_free()
		await _settle()


func _check_destination(fixture: Dictionary, label: String) -> void:
	await _settle()
	var scroll: Control = fixture.scroll
	var target: Control = fixture.destination
	_check(target.has_focus() and scroll.get_global_rect().encloses(target.get_global_rect()), label)


func _settle() -> void:
	await process_frame
	await process_frame


func _mouse_button(point: Vector2, pressed: bool) -> void:
	if pressed:
		_mouse_motion(point, Vector2.ZERO, false)
	var event := InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	event.pressed = pressed
	_viewport.push_input(event, true)


func _mouse_motion(point: Vector2, relative: Vector2, pressed: bool) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = relative
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	_viewport.push_input(event, true)


func _touch(point: Vector2, pressed: bool, canceled: bool = false) -> void:
	var event := InputEventScreenTouch.new()
	event.position = point
	event.index = 0
	event.pressed = pressed
	event.canceled = canceled
	_viewport.push_input(event, true)


func _key_tab(pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_TAB
	event.physical_keycode = KEY_TAB
	event.pressed = pressed
	_viewport.push_input(event, true)


func _check(passed: bool, label: String) -> void:
	_checks.append({"label": label, "passed": passed})
	if not passed:
		_failures += 1
		push_error(label)
