extends SceneTree
## Desktop comparison-only transport and input probe. Never included in the renderer PCK.

const MAX_FRAME_BYTES := 131072
const MAX_QUEUED_FRAMES := 16
const MAIN_SCENE := "res://main.tscn"

var _peer := StreamPeerTCP.new()
var _incoming := PackedByteArray()
var _outgoing: Array[PackedByteArray] = []
var _write_offset := 0
var _expected_bytes := -1
var _main: Node
var _busy := false
var _hello_sent := false
var _closing := false
var _quit_requested := false
var _quit_deadline := 0
var _deadline := 0
var _output := ""
var _token := ""


func _initialize() -> void:
	var arguments: Dictionary = {}
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--comparison-") and "=" in argument:
			var parts := argument.split("=", true, 1)
			arguments[parts[0]] = parts[1]
	var port := str(arguments.get("--comparison-port", "0")).to_int()
	_token = str(arguments.get("--comparison-token", ""))
	_output = str(arguments.get("--comparison-output", ""))
	var seconds := str(arguments.get("--comparison-seconds", "180")).to_int()
	if port < 1 or port > 65535 or _token.length() != 64 or not _output.is_absolute_path() \
		or seconds < 10 or seconds > 3600 or "--manual-bridge" not in OS.get_cmdline_user_args():
		_fail("Invalid comparison launch arguments")
		return
	_deadline = Time.get_ticks_msec() + seconds * 1000
	if DirAccess.make_dir_recursive_absolute(_output) != OK:
		_fail("Comparison output directory is unavailable")
		return
	if _peer.connect_to_host("127.0.0.1", port) != OK:
		_fail("Comparison loopback connection failed")
		return
	_load_main.call_deferred()


func _load_main() -> void:
	var scene = load(MAIN_SCENE)
	if not scene is PackedScene:
		_fail("Renderer main scene could not be loaded")
		return
	_main = scene.instantiate()
	if not _main.has_method("receive_document") or not _main.has_signal("bridge_event"):
		_fail("Renderer does not implement the agreed bridge interface")
		return
	_main.connect("bridge_event", _on_bridge_event)
	root.add_child(_main)
	current_scene = _main


func _process(_delta: float) -> bool:
	if _closing:
		return false
	if _quit_requested:
		_flush()
		if _outgoing.is_empty():
			_closing = true
			_peer.disconnect_from_host()
			quit(0)
		elif Time.get_ticks_msec() >= _quit_deadline:
			_fail("Comparison quit reply did not drain")
		return false
	if Time.get_ticks_msec() >= _deadline:
		_fail("Comparison lifetime expired")
		return false
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerSocket.STATUS_CONNECTING:
		return false
	if status != StreamPeerSocket.STATUS_CONNECTED:
		_fail("Comparison loopback connection closed")
		return false
	if not _hello_sent and is_instance_valid(_main) and _main.is_inside_tree():
		_peer.set_no_delay(true)
		_hello_sent = true
		var version := Engine.get_version_info()
		_enqueue({"kind": "hello", "protocol": 1, "token": _token,
			"godotVersion": version.string, "versionMajor": version.major,
			"versionMinor": version.minor, "versionPatch": version.patch, "versionStatus": version.status})
	_flush()
	if not _busy:
		_read_request()
	return false


func _read_request() -> void:
	var available := _peer.get_available_bytes()
	if available > 0:
		var part: Array = _peer.get_partial_data(mini(available, 16384))
		if part[0] != OK:
			_fail("Comparison read failed")
			return
		_incoming.append_array(part[1])
	if _incoming.size() > MAX_FRAME_BYTES + 4:
		_fail("Comparison receive buffer exceeded its bound")
		return
	if _expected_bytes < 0 and _incoming.size() >= 4:
		_expected_bytes = (_incoming[0] << 24) | (_incoming[1] << 16) | (_incoming[2] << 8) | _incoming[3]
		_incoming = _incoming.slice(4)
		if _expected_bytes < 1 or _expected_bytes > MAX_FRAME_BYTES:
			_fail("Comparison frame length is invalid")
			return
	if _expected_bytes < 0 or _incoming.size() < _expected_bytes:
		return
	var document := _incoming.slice(0, _expected_bytes).get_string_from_utf8()
	_incoming = _incoming.slice(_expected_bytes)
	_expected_bytes = -1
	var request = JSON.parse_string(document)
	if not request is Dictionary or request.get("kind") != "request" \
		or not request.get("id") is String or request.id.length() > 8 or not request.id.is_valid_int():
		_fail("Comparison request is invalid")
		return
	_busy = true
	_dispatch(request)


func _dispatch(request: Dictionary) -> void:
	var identifier: String = request.id
	match request.get("operation"):
		"document":
			if not request.get("document") is String or request.document.to_utf8_buffer().size() > 65536:
				_reply(identifier, false, "Invalid bridge document size")
				return
			var accepted: bool = _main.call("receive_document", request.document)
			await process_frame
			await process_frame
			_reply(identifier, accepted, _state())
		"state":
			await process_frame
			_reply(identifier, true, _state())
		"click":
			await _click(identifier, request)
		"capture":
			await _capture(identifier, request)
		"reset":
			_main.queue_free()
			await process_frame
			_load_main()
			await process_frame
			await process_frame
			_reply(identifier, true, _state())
		"quit":
			_reply(identifier, true, {})
			_quit_requested = true
			_quit_deadline = Time.get_ticks_msec() + 1000
		_:
			_reply(identifier, false, "Unknown comparison operation")


func _click(identifier: String, request: Dictionary) -> void:
	var group := str(request.get("group", ""))
	if not group.begins_with("partydeck_") or group.length() > 80:
		_reply(identifier, false, "Invalid input group")
		return
	var wanted_index := int(request.get("cardIndex", -1))
	var target: Button = null
	for node in get_nodes_in_group(group):
		if node is Button and node.is_visible_in_tree() and not node.disabled \
			and (wanted_index < 0 or int(node.get_meta("card_index", -1)) == wanted_index):
			if target != null:
				_reply(identifier, false, "Input group is ambiguous")
				return
			target = node
	if target == null:
		_reply(identifier, false, "No visible enabled Button in input group: " + group)
		return
	# Like a UI test's scroll-to operation, reveal the actual control before input.
	var ancestor := target.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(target)
			await process_frame
		ancestor = ancestor.get_parent()
	await process_frame
	await process_frame
	var full_rect: Rect2 = target.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, target.size)
	var hit_rect := full_rect.intersection(root.get_visible_rect())
	ancestor = target.get_parent()
	while ancestor != null:
		if ancestor is Control and ancestor.clip_contents:
			var clip: Rect2 = ancestor.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, ancestor.size)
			hit_rect = hit_rect.intersection(clip)
		ancestor = ancestor.get_parent()
	if not hit_rect.has_area():
		_reply(identifier, false, "Button is clipped outside the viewport: " + group)
		return
	if not hit_rect.grow(1.0).encloses(full_rect):
		_reply(identifier, false, "Button remains partially clipped after scrolling: " + group)
		return
	var point: Vector2 = hit_rect.get_center()
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	await process_frame
	var pressed := InputEventMouseButton.new()
	pressed.position = point
	pressed.global_position = point
	pressed.button_index = MOUSE_BUTTON_LEFT
	pressed.button_mask = MOUSE_BUTTON_MASK_LEFT
	pressed.pressed = true
	Input.parse_input_event(pressed)
	await process_frame
	var released := InputEventMouseButton.new()
	released.position = point
	released.global_position = point
	released.button_index = MOUSE_BUTTON_LEFT
	released.pressed = false
	Input.parse_input_event(released)
	await process_frame
	await process_frame
	_reply(identifier, true, {"state": _state(), "input": {
		"group": group, "cardIndex": wanted_index, "x": point.x, "y": point.y,
		"fullRect": [full_rect.position.x, full_rect.position.y, full_rect.size.x, full_rect.size.y],
		"clipRect": [hit_rect.position.x, hit_rect.position.y, hit_rect.size.x, hit_rect.size.y],
	}})


func _capture(identifier: String, request: Dictionary) -> void:
	var name := str(request.get("name", ""))
	var valid_name := RegEx.new()
	valid_name.compile("^[a-z0-9_-]{1,64}$")
	if valid_name.search(name) == null:
		_reply(identifier, false, "Invalid capture name")
		return
	await create_timer(0.35).timeout
	# A static low-processor scene may schedule no further draw. Force a fresh frame
	# on the main thread before reading the viewport, without changing product settings.
	RenderingServer.force_draw()
	var image: Image = root.get_texture().get_image()
	var path := _output.path_join(name + ".png")
	if image == null or image.is_empty() or image.save_png(path) != OK:
		_reply(identifier, false, "Viewport capture failed")
		return
	_reply(identifier, true, {"path": path, "width": image.get_width(), "height": image.get_height(), "state": _state()})


func _state() -> Dictionary:
	if not is_instance_valid(_main):
		return {}
	var controller = _main.get("controller")
	var state: Dictionary = controller.call("presentation_state") if controller != null else {}
	var diagnostics: Dictionary = {}
	if _main.has_method("diagnostics_document"):
		var decoded = JSON.parse_string(_main.call("diagnostics_document"))
		if decoded is Dictionary:
			diagnostics = decoded
	return {"presentation": state, "diagnostics": diagnostics}


func _on_bridge_event(document: String) -> void:
	if document.to_utf8_buffer().size() > 4096:
		_fail("Renderer event exceeds the bridge limit")
		return
	_enqueue({"kind": "event", "document": document})


func _reply(identifier: String, ok: bool, result) -> void:
	_enqueue({"kind": "reply", "id": identifier, "ok": ok, "result": result})
	_busy = false


func _enqueue(message: Dictionary) -> void:
	var bytes := JSON.stringify(message).to_utf8_buffer()
	if bytes.size() < 1 or bytes.size() > MAX_FRAME_BYTES or _outgoing.size() >= MAX_QUEUED_FRAMES:
		_fail("Comparison send queue exceeded its bound")
		return
	var size := bytes.size()
	var frame := PackedByteArray([(size >> 24) & 255, (size >> 16) & 255, (size >> 8) & 255, size & 255])
	frame.append_array(bytes)
	_outgoing.append(frame)


func _flush() -> void:
	if _outgoing.is_empty():
		return
	var result: Array = _peer.put_partial_data(_outgoing[0].slice(_write_offset))
	if result[0] != OK:
		_fail("Comparison write failed")
		return
	_write_offset += int(result[1])
	if _write_offset == _outgoing[0].size():
		_outgoing.pop_front()
		_write_offset = 0


func _fail(reason: String) -> void:
	if _closing:
		return
	_closing = true
	push_error(reason)
	_peer.disconnect_from_host()
	quit(2)
