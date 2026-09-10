extends Node

signal bridge_event(document: String)

const Controller = preload("res://scripts/renderer_controller.gd")
const MAX_BYTES := 65_536
const PRESENTATIONS := {
	"2d": "res://presentations/two_d/table.tscn",
	"3d": "res://presentations/three_d/table.tscn",
}
const ACTION_GROUPS := ["partydeck_action_reveal", "partydeck_action_hide", "partydeck_action_play",
	"partydeck_action_challenge", "partydeck_action_next_round", "partydeck_action_lobby", "partydeck_action_exit",
	"partydeck_action_lobby_confirm", "partydeck_action_lobby_cancel",
	"partydeck_hand_card"]

var controller: Node
var _presentation: Node
var _mode := ""
var _plugin: Object
var _diagnostic_sequence := 0
var _manual_bridge := false
var _waiting: CanvasLayer
var _native_display_scale_valid := true


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	get_tree().auto_accept_quit = false
	controller = Controller.new()
	controller.name = "Controller"
	add_child(controller)
	controller.state_changed.connect(_on_state)
	controller.bridge_event.connect(_on_bridge_event)
	var options := _options()
	_manual_bridge = options.has("manual-bridge")
	controller.presentation_mode = options.get("presentation", "3d")
	_show_waiting()
	if _manual_bridge:
		return
	if Engine.has_singleton("PartyDeckBridge"):
		_plugin = Engine.get_singleton("PartyDeckBridge")
		_plugin.connect("command_received", receive_document)
		if _plugin.has_signal("diagnostics_requested"):
			_plugin.connect("diagnostics_requested", _send_diagnostics)
		if _plugin.has_method("get_display_scale"):
			_native_display_scale_valid = _configure_native_display_scale(_plugin.call("get_display_scale"))
		elif OS.has_feature("android"):
			push_error("PartyDeck Android bridge did not provide its display density.")
			_native_display_scale_valid = false
		receive_document(_plugin.call("get_launch_document"))
	elif options.has("launch-file"):
		var file := FileAccess.open(options["launch-file"], FileAccess.READ)
		if file == null or file.get_length() > MAX_BYTES:
			return
		var bytes := file.get_buffer(file.get_length())
		file.close()
		var document := bytes.get_string_from_utf8()
		if document.to_utf8_buffer() == bytes:
			receive_document(document)


func receive_document(document: String) -> bool:
	return controller != null and controller.receive_document(document)


func _configure_native_display_scale(value: Variant) -> bool:
	# Android DisplayMetrics.density is pixels per dp, separate from launch textScale:
	# https://developer.android.com/reference/android/util/DisplayMetrics#density
	if not (value is float or value is int) or not is_finite(float(value)) \
		or float(value) < 0.5 or float(value) > 8.0:
		push_error("PartyDeck native display density must be a finite number between 0.5 and 8.")
		return false
	var window := get_window()
	# Tagged 4.7.2 Window::_update_viewport_size keeps physical rendering resolution
	# with disabled stretch and sets the logical viewport to size / content_scale_factor.
	# https://github.com/godotengine/godot/blob/4.7.2-stable/scene/main/window.cpp
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	window.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_FRACTIONAL
	window.content_scale_factor = float(value)
	return true


func _on_state(state: Dictionary) -> void:
	if state.closed:
		_quiet_feedback()
		_remove_presentation()
		get_tree().paused = true
		return
	if state.game.is_empty():
		return
	if not _native_display_scale_valid:
		# Launch has bound its presentation ID, but Ready has not been emitted yet.
		controller.fail("INITIALIZATION_FAILED")
		return
	if _presentation == null or _mode != state.presentationMode:
		_remove_presentation()
		var path: String = PRESENTATIONS.get(state.presentationMode, "")
		if path.is_empty() or not ResourceLoader.exists(path):
			controller.fail("INITIALIZATION_FAILED")
			return
		var scene := load(path) as PackedScene
		if scene == null:
			controller.fail("INITIALIZATION_FAILED")
			return
		_presentation = scene.instantiate()
		_presentation.process_mode = Node.PROCESS_MODE_PAUSABLE
		_mode = state.presentationMode
		add_child(_presentation)
		if not _presentation.has_method("bind"):
			controller.fail("INITIALIZATION_FAILED")
			return
		_presentation.bind(controller)
		if _waiting != null:
			_waiting.queue_free()
			_waiting = null
	# Renderers synchronously receive the same state signal, remove private bindings, then pause.
	if not state.foreground or not state.soundEnabled:
		_quiet_feedback()
	AudioServer.set_bus_mute(0, not state.soundEnabled)
	get_tree().paused = not state.foreground


func _on_bridge_event(document: String) -> void:
	bridge_event.emit(document)
	if _plugin != null:
		_plugin.call("renderer_event", document)
	elif not _manual_bridge:
		# Standalone snapshots have no authority loop; only coarse event type is logged.
		var event: Dictionary = JSON.parse_string(document)
		print("PartyDeck renderer event: ", event.type)
		if event.type == "exit":
			get_tree().quit()


func _notification(what: int) -> void:
	if not is_instance_valid(controller):
		return
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		controller.set_window_foreground(false)
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		controller.set_window_foreground(true)
	elif what in [NOTIFICATION_WM_CLOSE_REQUEST, NOTIFICATION_WM_GO_BACK_REQUEST]:
		controller.request_exit()


func _remove_presentation() -> void:
	if is_instance_valid(_presentation):
		remove_child(_presentation)
		_presentation.queue_free()
	_presentation = null
	_mode = ""


func _quiet_feedback() -> void:
	for node in get_tree().get_nodes_in_group("partydeck_feedback"):
		if node is AudioStreamPlayer or node is AudioStreamPlayer3D:
			node.stop()


func _show_waiting() -> void:
	_waiting = CanvasLayer.new()
	var label := Label.new()
	label.text = "Connect a table to begin."
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_waiting.add_child(label)
	add_child(_waiting)


func _options() -> Dictionary:
	var result := {}
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--"):
			var parts := argument.substr(2).split("=", true, 1)
			result[parts[0]] = parts[1] if parts.size() == 2 else true
	return result


## Prototype-only, read-only observations. Never a success flag or an authority event.
func diagnostics_document(request_id: String = "0") -> String:
	var state: Dictionary = controller.presentation_state()
	var viewport := get_viewport().get_visible_rect()
	var controls: Array = []
	var selected_count := 0
	for group in ACTION_GROUPS:
		for node in get_tree().get_nodes_in_group(group):
			if not node is BaseButton or not is_instance_valid(_presentation) or not _presentation.is_ancestor_of(node):
				continue
			if node.get_viewport() != get_viewport():
				continue
			if controls.size() >= 32:
				break
			var rect: Rect2 = node.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, node.size)
			var clip_rect := _control_clip_rect(node, viewport)
			var visible: bool = node.is_visible_in_tree() and rect.intersection(clip_rect).has_area()
			if group == "partydeck_hand_card" and node.button_pressed:
				selected_count += 1
			controls.append({"group": group, "cardIndex": int(node.get_meta("card_index", -1)),
				"rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
				"clipRect": [clip_rect.position.x, clip_rect.position.y, clip_rect.size.x, clip_rect.size.y],
				"visible": visible, "enabled": not node.disabled, "selected": node.button_pressed})
	var private_faces := 0
	for node in get_tree().get_nodes_in_group("partydeck_private_face"):
		if not is_instance_valid(_presentation) or not _presentation.is_ancestor_of(node):
			continue
		var texture: Texture2D
		if node is TextureRect:
			texture = node.texture
		elif node is MeshInstance3D and node.material_override is BaseMaterial3D:
			texture = node.material_override.albedo_texture
		if texture != null and texture.resource_path.get_file().begins_with("face_"):
			private_faces += 1
	var private_labels := 0
	for node in get_tree().get_nodes_in_group("partydeck_private_label"):
		if is_instance_valid(_presentation) and _presentation.is_ancestor_of(node) \
			and (node is Label or node is Button) and not node.text.is_empty():
			private_labels += 1
	var document := {
		"schemaVersion": 1, "requestId": request_id, "sequence": str(_diagnostic_sequence), "presentationId": controller.presentation_id,
		"revision": controller.revision, "presentationMode": state.presentationMode,
		"coordinateSpace": "root_viewport", "foreground": state.foreground,
		"viewport": {"width": viewport.size.x, "height": viewport.size.y},
		"handConcealed": not state.handVisible, "selectedCount": selected_count,
		"privateFaceCount": private_faces, "privateLabelCount": private_labels, "controls": controls,
	}
	_diagnostic_sequence += 1
	return JSON.stringify(document)


func _control_clip_rect(control: Control, viewport: Rect2) -> Rect2:
	# CanvasItem.get_global_transform_with_canvas maps to its own viewport's logical
	# coordinates. A child SubViewport must never be mislabeled as root_viewport.
	if control.get_viewport() != get_viewport():
		return Rect2()
	# Keep the clip region separate from full control bounds, so a checker can detect
	# partial clipping and swipe the actual scroll viewport before choosing a target.
	var rect := viewport
	if control.is_set_as_top_level():
		return rect
	var ancestor := control.get_parent()
	while ancestor != null and ancestor != get_viewport() and rect.has_area():
		if ancestor is CanvasItem:
			# Clipping does not cross a CanvasLayer or top-level canvas-item boundary.
			if ancestor.get_canvas() != control.get_canvas():
				break
			if ancestor is Control and ancestor.clip_contents:
				# ScrollContainer enables clip_contents in its tagged 4.7.2 constructor;
				# intersect the actual viewport rectangle, not the scrolled content size.
				var clip: Rect2 = ancestor.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, ancestor.size)
				rect = rect.intersection(clip)
			if ancestor.is_set_as_top_level():
				break
		ancestor = ancestor.get_parent()
	return rect


func _send_diagnostics(request_id: String) -> void:
	if not Controller.Validator.counter(request_id):
		return
	if _plugin != null and _plugin.has_method("renderer_diagnostics"):
		_plugin.call("renderer_diagnostics", diagnostics_document(request_id))
