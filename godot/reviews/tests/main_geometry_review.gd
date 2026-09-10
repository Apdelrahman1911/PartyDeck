extends SceneTree

var failures: Array[String] = []
var checks := 0


func _initialize() -> void:
	_run.call_deferred()


func check(value: bool, description: String) -> void:
	checks += 1
	if not value:
		failures.append(description)


func control(parent: Node, at: Vector2, extent: Vector2, clipping: bool = false) -> Control:
	var item := Control.new()
	parent.add_child(item)
	item.position = at
	item.size = extent
	item.clip_contents = clipping
	return item


func button(parent: Node, at: Vector2, extent: Vector2, group: String) -> Button:
	var item := Button.new()
	parent.add_child(item)
	item.position = at
	item.size = extent
	item.add_to_group(group)
	return item


func _run() -> void:
	root.size = Vector2i(720, 1050)
	var main = load("res://scripts/main.gd").new()
	root.add_child(main)
	await process_frame
	check(root.get_visible_rect().size.is_equal_approx(Vector2(720, 1050)), "Desktop coordinates changed without native configuration")
	check(main._configure_native_display_scale(1.75), "Native fractional density rejected")
	await process_frame
	var viewport := root.get_visible_rect()
	check(viewport.size.is_equal_approx(Vector2(720.0 / 1.75, 600)), "Native density did not produce logical viewport units")
	check(root.size == Vector2i(720, 1050), "Physical viewport changed")
	check(root.get_stretch_transform().get_scale().is_equal_approx(Vector2(1.75, 1.75)), "Physical transform differs from density")

	var presentation := control(main, Vector2.ZERO, viewport.size)
	main._presentation = presentation
	var outer := control(presentation, Vector2(40, 50), Vector2(100, 100), true)
	var inner := control(outer, Vector2(10, 20), Vector2(80, 60), true)
	var nested := button(inner, Vector2(70, 45), Vector2(50, 30), "partydeck_action_play")
	check(main._control_clip_rect(nested, viewport).is_equal_approx(Rect2(50, 70, 80, 60)), "Nested clipping did not use root logical coordinates")

	var top := button(outer, Vector2.ZERO, Vector2(50, 30), "partydeck_action_hide")
	top.top_level = true
	top.position = Vector2(200, 200)
	check(main._control_clip_rect(top, viewport).is_equal_approx(viewport), "Top-level control inherited parent clipping")
	var top_parent := control(outer, Vector2.ZERO, Vector2(100, 80), true)
	top_parent.top_level = true
	top_parent.position = Vector2(200, 50)
	var top_child := button(top_parent, Vector2(70, 60), Vector2(50, 40), "partydeck_action_reveal")
	check(main._control_clip_rect(top_child, viewport).is_equal_approx(Rect2(200, 50, 100, 80)), "Clipping crossed a top-level ancestor")

	var layer := CanvasLayer.new()
	layer.offset = Vector2(180, 200)
	outer.add_child(layer)
	var layer_clip := control(layer, Vector2.ZERO, Vector2(80, 60), true)
	var layered := button(layer_clip, Vector2(60, 40), Vector2(50, 30), "partydeck_action_challenge")
	check(layered.get_canvas() != outer.get_canvas(), "Test did not create separate canvases")
	check(main._control_clip_rect(layered, viewport).is_equal_approx(Rect2(180, 200, 80, 60)), "Clipping crossed a CanvasLayer boundary")

	var child_viewport := SubViewport.new()
	child_viewport.size = Vector2i(64, 64)
	presentation.add_child(child_viewport)
	var foreign := button(child_viewport, Vector2.ZERO, Vector2(50, 30), "partydeck_action_exit")
	check(not main._control_clip_rect(foreign, viewport).has_area(), "Child viewport was interpreted as root coordinates")
	await process_frame
	var first: Dictionary = JSON.parse_string(main.diagnostics_document("81"))
	check(first.requestId == "81" and first.sequence == "0", "Diagnostic correlation changed")
	check(first.controls.size() == 4, "Child viewport leaked into root diagnostics")
	var by_group := {}
	for item in first.controls:
		by_group[item.group] = item
	check(not by_group.has("partydeck_action_exit"), "Foreign viewport button was reported")
	check(by_group.partydeck_action_play.rect == [120.0, 115.0, 50.0, 30.0], "Full control bounds were clipped or scaled to pixels")
	check(by_group.partydeck_action_play.clipRect == [50.0, 70.0, 80.0, 60.0], "Diagnostic clip region was replaced by hit intersection")
	check(by_group.partydeck_action_play.visible, "Partially visible button was hidden")
	check(by_group.partydeck_action_hide.visible and by_group.partydeck_action_reveal.visible and by_group.partydeck_action_challenge.visible, "Canvas boundary controls inherited foreign clipping")
	nested.position = Vector2(500, 500)
	var next: Dictionary = JSON.parse_string(main.diagnostics_document("82"))
	for item in next.controls:
		if item.group == "partydeck_action_play":
			check(not item.visible and item.rect[2] == 50.0, "Fully clipped button kept visible or lost full dimensions")
	check(next.requestId == "82" and next.sequence == "1", "Diagnostic sequence failed to advance")
	root.remove_child(main)
	main.free()
	root.content_scale_factor = 1.0
	print(JSON.stringify({"result": "PASS" if failures.is_empty() else "FAIL", "checks": checks, "failures": failures, "logicalViewport": [viewport.size.x, viewport.size.y], "engine": Engine.get_version_info().string}))
	quit(0 if failures.is_empty() else 1)
