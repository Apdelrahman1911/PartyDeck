extends Control

var _bridge: Object
var _presentation_id := ""
var _sequence := 0
var _angle := 0.0
var _foreground := true
var _closed := false
var _exit_button: Button


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_label("Native Godot scene", 0.10, 0.21, 26)
	_label("An actual engine surface inside the host", 0.21, 0.28, 15)
	_label("Touch the scene to send its exit event.\nThis diagnostic does not play Last Light.", 0.69, 0.88, 16)
	_exit_button = Button.new()
	_exit_button.text = "Exit scene"
	_exit_button.anchor_left = 0.15
	_exit_button.anchor_right = 0.85
	_exit_button.anchor_top = 0.43
	_exit_button.anchor_bottom = 0.59
	_exit_button.add_theme_font_size_override("font_size", 23)
	_exit_button.pressed.connect(_request_exit)
	add_child(_exit_button)
	if not Engine.has_singleton("PartyDeckBridge"):
		# A desktop source/import check can render this diagnostic without a host.
		_exit_button.disabled = true
		return
	_bridge = Engine.get_singleton("PartyDeckBridge")
	_bridge.connect("command_received", _receive_document)
	var document: String = _bridge.call("get_launch_document")
	var launch: Variant = JSON.parse_string(document)
	if not launch is Dictionary or launch.get("type") != "launch":
		return
	_presentation_id = launch.presentationId
	# Exercise the actual native gate, then send Ready with sequence 0. These
	# malformed/replayed documents must not advance its accepted sequence.
	var identity := JSON.stringify(_presentation_id)
	var duplicate := '{"protocolVersion":1,"type":"ready","presentationId":%s,"sequence":"99","sequence":"0"}' % identity
	if _bridge.call("renderer_event", duplicate):
		push_error("The native bridge accepted a duplicate key.")
		return
	if _bridge.call("renderer_event", " ".repeat(4097)):
		push_error("The native bridge accepted an oversized event.")
		return
	_emit("ready")
	var replay := '{"protocolVersion":1,"type":"exit","presentationId":%s,"sequence":"0"}' % identity
	if _bridge.call("renderer_event", replay):
		push_error("The native bridge accepted a replayed sequence.")


func _label(text: String, top: float, bottom: float, font_size: int) -> void:
	var label := Label.new()
	label.text = text
	label.anchor_left = 0.04
	label.anchor_right = 0.96
	label.anchor_top = top
	label.anchor_bottom = bottom
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", Color("#f4f1df"))
	add_child(label)


func _process(delta: float) -> void:
	if _foreground and not _closed:
		_angle = fmod(_angle + delta * 1.5, TAU)
		queue_redraw()


func _draw() -> void:
	var center := Vector2(size.x * 0.5, size.y * 0.35)
	draw_circle(center, 19.0, Color("#263c33"))
	draw_arc(center, 19.0, _angle, _angle + PI * 1.4, 28, Color("#d9ea70"), 4.0, true)


func _receive_document(document: String) -> void:
	var command: Variant = JSON.parse_string(document)
	if not command is Dictionary or command.get("presentationId") != _presentation_id:
		return
	if command.type == "foreground":
		_foreground = command.isForeground
		_exit_button.disabled = not _foreground
	elif command.type == "close":
		_closed = true
		_exit_button.disabled = true
		set_process(false)


func _request_exit() -> void:
	if _foreground and not _closed:
		_emit("exit")
		_closed = true
		_exit_button.disabled = true


func _emit(type: String) -> void:
	_bridge.call("renderer_event", JSON.stringify({
		"protocolVersion": 1, "type": type,
		"presentationId": _presentation_id, "sequence": str(_sequence)
	}))
	_sequence += 1
