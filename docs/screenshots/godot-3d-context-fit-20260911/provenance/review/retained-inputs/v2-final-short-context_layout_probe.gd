extends "/tmp/partydeck-3d-context-fit-20260911-_jvzo1j7/inputs/three_d_scene_check.gd"
## Private read-only layout observations plus real wheel input through the existing renderer.
## The fixture is an unchanged authority-derived recipient launch; no authority actions are accepted here.

var _wheel_trace: Array[Dictionary] = []

func _run() -> void:
	_output = str(_options.get("output", ""))
	var fixture_path := str(_options.get("fixture", ""))
	if not _output.is_absolute_path() or not fixture_path.is_absolute_path():
		_fail("Absolute fixture and output paths are required.")
		return
	DirAccess.make_dir_recursive_absolute(_output)
	root.size = Vector2i(int(_options.get("width", "681")), int(_options.get("height", "377")))
	_main = load("res://main.tscn").instantiate()
	_main.bridge_event.connect(func(document: String) -> void: _events.append(JSON.parse_string(document)))
	root.add_child(_main)
	current_scene = _main
	var density := float(_options.get("density", "1.75"))
	if not _main._configure_native_display_scale(density):
		_fail("The renderer rejected the retained native display density.")
		return
	if not _main.receive_document(FileAccess.get_file_as_string(fixture_path)):
		_fail("The shared renderer rejected the authority-derived fixture.")
		return
	await _settle()
	var state: Dictionary = _main.controller.presentation_state()
	var initial_revision: String = _main.controller.revision
	if state.game.phase != "PLAYING" or state.game.latestClaim == null or not _private_nodes_erased():
		_fail("The focused fixture must have a concealed hand and a current public claim.")
		return
	var claim := _find_claim(_main)
	if claim == null:
		_fail("The renderer omitted the public claim.")
		return
	var table: Control = _main._presentation
	var scroll: ScrollContainer = _main.find_child("TableBodyScroll", true, false)
	var round_label := _find_round(_main, int(state.game.roundNumber))
	if round_label == null:
		_fail("The renderer omitted the current round number from visible public content.")
		return
	var round_context := {"text": round_label.text, "inBodyScroll": scroll != null and scroll.is_ancestor_of(round_label),
		"initialGeometry": _claim_observation(round_label)}
	var in_scroll := scroll != null and scroll.is_ancestor_of(claim)
	var initial := _claim_observation(claim)
	await _capture("01-initial")
	var seen := {}
	var observations: Array[Dictionary] = []
	var complete := _record_visible_characters(claim, seen)
	observations.append(_claim_observation(claim))
	var capture_count := 1
	var wheel_count := 0
	if in_scroll:
		for step in range(100):
			if complete:
				break
			var clip: Rect2 = _main._control_clip_rect(scroll, root.get_visible_rect())
			clip = clip.intersection(scroll.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, scroll.size))
			if not clip.has_area():
				break
			var before := scroll.scroll_vertical
			var before_seen := seen.size()
			await _wheel(_vertical_scroll_point(scroll))
			wheel_count += 1
			complete = _record_visible_characters(claim, seen)
			var observation := _claim_observation(claim)
			observation["wheelInput"] = wheel_count
			observation["coveredCharacters"] = seen.size()
			observations.append(observation)
			if seen.size() > before_seen:
				capture_count += 1
				await _capture("%02d-claim-scroll" % capture_count)
			if scroll.scroll_vertical == before:
				break
	var claim_wheel_count := wheel_count
	# Observe complete native action rectangles without dispatching an authority intent.
	# This only qualifies reachability for this exact fixture and viewport.
	var actions := {}
	var action_nodes: Array[Button] = []
	for group in ["partydeck_action_play", "partydeck_action_challenge"]:
		var expected: bool = state.game.availableActions.canPlay if group == "partydeck_action_play" \
			else state.game.availableActions.canChallenge
		if not expected:
			continue
		for node in get_nodes_in_group(group):
			if node is Button and _main.is_ancestor_of(node) and node.is_visible_in_tree():
				action_nodes.append(node)
				actions[group] = {"text": node.text, "disabled": node.disabled, "fullyEnclosed": false}
				break
		if not actions.has(group):
			_fail("A projected action is missing: " + group)
			return
	for step in range(160):
		var all_actions := true
		var new_action := false
		for node in action_nodes:
			var group := "partydeck_action_play" if node.is_in_group("partydeck_action_play") else "partydeck_action_challenge"
			if actions[group].fullyEnclosed:
				continue
			var rect: Rect2 = node.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, node.size)
			var clip: Rect2 = _main._control_clip_rect(node, root.get_visible_rect())
			if clip.encloses(rect):
				actions[group]["fullyEnclosed"] = true
				actions[group]["rect"] = _rect(rect)
				actions[group]["clipRect"] = _rect(clip)
				actions[group]["scrollVertical"] = scroll.scroll_vertical
				new_action = true
			else:
				all_actions = false
		if new_action:
			capture_count += 1
			await _capture("%02d-actions-scroll" % capture_count)
		if all_actions or scroll == null:
			break
		var clip: Rect2 = _main._control_clip_rect(scroll, root.get_visible_rect())
		clip = clip.intersection(scroll.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, scroll.size))
		if not clip.has_area():
			break
		var before := scroll.scroll_vertical
		await _wheel(_vertical_scroll_point(scroll))
		wheel_count += 1
		if scroll.scroll_vertical == before:
			break
	var authority_safe: bool = _events.size() == 1 and _events[0].get("type") == "ready" \
		and _main.controller.revision == initial_revision \
		and _main.controller.presentation_state().selectedCardIds.is_empty() and _private_nodes_erased()
	var result := {"kind": "real-renderer-context-fit", "fixture": fixture_path,
		"godotVersion": Engine.get_version_info().string,
		"physicalSurface": [root.size.x, root.size.y], "density": density,
		"logicalViewport": [root.get_visible_rect().size.x, root.get_visible_rect().size.y],
		"textScale": state.textScale, "pinned": table._context_pinned, "claimInBodyScroll": in_scroll,
		"initialClaim": initial, "publicClaimText": claim.text, "allClaimCharactersReached": complete,
		"roundContext": round_context, "actions": actions,
		"wheelInputs": wheel_count, "claimWheelInputs": claim_wheel_count, "scrollObservations": observations,
		"wheelInputTrace": _wheel_trace,
		"passiveInputEndpointChecksPassed": authority_safe, "events": _events,
		"revisionBefore": initial_revision, "revisionAfter": _main.controller.revision,
		"scrollRect": _rect(scroll.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, scroll.size)) if scroll != null else [],
		"limitations": "Real desktop OpenGL rendering and engine input at retained native density/geometry. No native device acceptance or authority-accepted action is asserted."}
	FileAccess.open(_output.path_join("layout-report.json"), FileAccess.WRITE).store_string(JSON.stringify(result, "\t"))
	if not authority_safe:
		_fail("Passive public-content scrolling changed authority, selection, or concealment.")
		return
	var expectation := str(_options.get("expect", "observe"))
	if expectation == "scroll" and (table._context_pinned or not in_scroll or not complete):
		_fail("Short surface did not expose the complete claim through its actual scroll body.")
		return
	if expectation == "pinned" and (not table._context_pinned or in_scroll or not complete):
		_fail("Adequate-height surface did not retain a fully visible pinned claim.")
		return
	if expectation != "observe":
		for action in actions.values():
			if not action.fullyEnclosed:
				_fail("A projected action could not be fully enclosed in the actual scroll clip.")
				return
	_main.queue_free()
	await process_frame
	quit(0)

func _find_claim(node: Node) -> Label:
	if node is Label and " claimed " in node.text:
		return node
	for child in node.get_children():
		var label := _find_claim(child)
		if label != null:
			return label
	return null

func _find_round(node: Node, round_number: int) -> Label:
	if node is Label and node.is_visible_in_tree() \
		and (node.text == "ROUND %d" % round_number or node.text.ends_with(" · round %d" % round_number)):
		return node
	for child in node.get_children():
		var label := _find_round(child, round_number)
		if label != null:
			return label
	return null

func _record_visible_characters(label: Label, seen: Dictionary) -> bool:
	var clip: Rect2 = _main._control_clip_rect(label, root.get_visible_rect())
	var required := 0
	for index in range(label.text.length()):
		if label.text.substr(index, 1).strip_edges().is_empty():
			continue
		required += 1
		var bounds: Rect2 = label.get_global_transform_with_canvas() * label.get_character_bounds(index)
		if bounds.has_area() and clip.encloses(bounds):
			seen[index] = true
	return seen.size() == required

func _claim_observation(label: Label) -> Dictionary:
	var rect: Rect2 = label.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, label.size)
	var clip: Rect2 = _main._control_clip_rect(label, root.get_visible_rect())
	var scroll: ScrollContainer = _main.find_child("TableBodyScroll", true, false)
	return {"rect": _rect(rect), "clipRect": _rect(clip), "fullyEnclosed": clip.encloses(rect),
		"scrollVertical": scroll.scroll_vertical if scroll != null else -1, "lineCount": label.get_line_count()}

func _rect(value: Rect2) -> Array:
	return [value.position.x, value.position.y, value.size.x, value.size.y]

func _vertical_scroll_point(scroll: ScrollContainer) -> Vector2:
	# The roster intentionally routes wheel input horizontally. Target the real
	# vertical scrollbar when qualifying the outer body's vertical reachability.
	var bar := scroll.get_v_scroll_bar()
	var rect: Rect2 = bar.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, bar.size)
	return rect.intersection(_main._control_clip_rect(bar, root.get_visible_rect())).get_center()

func _wheel(point: Vector2) -> void:
	# Window::_window_input forwards physical positions; Viewport::_make_input_local
	# applies this transform's inverse before GUI dispatch, including native density.
	var logical_point := point
	point = root.get_final_transform() * point
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	await process_frame
	var hovered := root.gui_get_hovered_control()
	_wheel_trace.append({"logicalPosition": [logical_point.x, logical_point.y],
		"physicalPosition": [point.x, point.y],
		"hoveredClass": hovered.get_class() if hovered != null else "none",
		"hoveredPath": str(hovered.get_path()) if hovered != null else "none"})
	var down := InputEventMouseButton.new()
	down.position = point
	down.global_position = point
	down.button_index = MOUSE_BUTTON_WHEEL_DOWN
	down.pressed = true
	Input.parse_input_event(down)
	await process_frame
	var up := InputEventMouseButton.new()
	up.position = point
	up.global_position = point
	up.button_index = MOUSE_BUTTON_WHEEL_DOWN
	up.pressed = false
	Input.parse_input_event(up)
	await _settle()
