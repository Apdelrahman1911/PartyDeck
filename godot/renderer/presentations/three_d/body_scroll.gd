extends ScrollContainer

# Pointer focus is assigned before gui_input. Revealing a partly clipped button
# at that point would add a jump before the user's drag has even started.
var _pointer_focus_paused := false
var _pointer_focus_target: Control
var _focus_viewport: Viewport


func _input(event: InputEvent) -> void:
	_restore_focus_following()
	if not follow_focus or not is_visible_in_tree():
		return
	# Touch gets key focus through Godot's emulated mouse event. Raw ScreenTouch
	# dispatch does not assign it and must not suppress programmatic focus.
	if not event is InputEventMouseButton or event.button_index != MOUSE_BUTTON_LEFT or not event.pressed:
		return
	var point: Vector2 = get_global_transform_with_canvas().affine_inverse() * event.position
	if not Rect2(Vector2.ZERO, size).has_point(point):
		return
	var target := _hovered_focus_target()
	if target == null or target == get_viewport().gui_get_focus_owner():
		return
	# Native ScrollContainer registers its listener after script _ready. Connect
	# at the first input instead, so it observes the pause before our restoration.
	if _focus_viewport == null:
		_focus_viewport = get_viewport()
		_focus_viewport.gui_focus_changed.connect(_follow_non_pointer_focus)
	_pointer_focus_target = target
	_pointer_focus_paused = true
	follow_focus = false
	_restore_focus_following.call_deferred()


func _hovered_focus_target() -> Control:
	# Viewport updates mouse-over before _input. Match its focusable ancestor and
	# stopping rules, including recursive focus/mouse-filter accessibility policy.
	var item: CanvasItem = get_viewport().gui_get_hovered_control()
	while item != null:
		var control := item as Control
		if control != null:
			var mode := control.get_focus_mode_with_override()
			var focusable := mode == Control.FOCUS_ALL or mode == Control.FOCUS_CLICK \
				or (mode == Control.FOCUS_ACCESSIBILITY and get_tree().is_accessibility_enabled())
			if control.is_visible_in_tree() and focusable:
				return control if is_ancestor_of(control) else null
			if control.get_mouse_filter_with_override() == Control.MOUSE_FILTER_STOP:
				return null
		if item.is_set_as_top_level():
			return null
		item = item.get_parent() as CanvasItem
	return null


func _gui_input(_event: InputEvent) -> void:
	# GUI focus assignment has already completed when this callback runs.
	_restore_focus_following()


func _unhandled_input(_event: InputEvent) -> void:
	_restore_focus_following()


func _follow_non_pointer_focus(control: Control) -> void:
	if not _pointer_focus_paused:
		return
	var pointer_focus := control == _pointer_focus_target and not _focus_viewport.is_input_handled()
	_restore_focus_following()
	# Only the pending pointer focus is skipped. Any other destination is revealed
	# exactly once, including focus changes inside a child's GUI handler.
	if not pointer_focus and is_ancestor_of(control):
		ensure_control_visible(control)


func _restore_focus_following() -> void:
	if _pointer_focus_paused:
		_pointer_focus_paused = false
		_pointer_focus_target = null
		follow_focus = true


func _exit_tree() -> void:
	_restore_focus_following()
	if _focus_viewport != null:
		_focus_viewport.gui_focus_changed.disconnect(_follow_non_pointer_focus)
		_focus_viewport = null
