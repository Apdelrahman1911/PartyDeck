extends SceneTree
## Desktop boundary regression. Registry doubles do not execute Android JNI.

class JavaRegistry:
	extends RefCounted
	var methods := {&"get_display_scale": true, &"renderer_diagnostics": true}
	var queries: Array[StringName] = []
	func has_java_method(method_name: StringName) -> bool:
		queries.append(method_name)
		return methods.has(method_name)


class OrdinaryBridge:
	extends Object
	signal command_received(document: String)
	signal diagnostics_requested(request_id: String)
	var launch := ""
	var events: Array[Dictionary] = []
	var diagnostics: Array[Dictionary] = []
	var java_queries := 0
	func has_java_method(_method_name: StringName) -> bool:
		java_queries += 1
		return false
	func get_launch_document() -> String:
		return launch
	func get_display_scale() -> float:
		return 1.75
	func renderer_event(document: String) -> void:
		events.append(JSON.parse_string(document))
	func renderer_diagnostics(document: String) -> void:
		diagnostics.append(JSON.parse_string(document))


var _checks: Array[Dictionary] = []
var _failures := 0
var _output := ""
var _fixtures := ""


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-output="):
			_output = argument.trim_prefix("--check-output=")
		elif argument.begins_with("--check-fixtures="):
			_fixtures = argument.trim_prefix("--check-fixtures=")
	_run.call_deferred()


func _run() -> void:
	if not _output.is_absolute_path() or not _fixtures.is_absolute_path():
		push_error("Absolute --check-output and --check-fixtures paths are required.")
		quit(1)
		return
	var probe: Node = load("res://scripts/main.gd").new()
	_check(not probe._plugin_has_method("get_display_scale"), "An absent plugin has no optional method")
	probe._plugin = RefCounted.new()
	_check(not probe._plugin_has_method("get_display_scale"), "An ordinary object without the method is rejected")
	var registry := JavaRegistry.new()
	probe._plugin = registry
	for method_name in [&"get_display_scale", &"renderer_diagnostics"]:
		_check(not registry.has_method(method_name), "Registry-only method is absent from Object: " + method_name)
		_check(probe._plugin_has_method(method_name), "Registry-only method is discovered: " + method_name)
	_check(not probe._plugin_has_method("unknown_bridge_method"), "An unregistered Java method is rejected")
	_check(registry.queries == [&"get_display_scale", &"renderer_diagnostics", &"unknown_bridge_method"],
		"Discovery queries the registered Java method names")
	var ordinary := OrdinaryBridge.new()
	probe._plugin = ordinary
	_check(probe._plugin_has_method("get_display_scale"), "An ordinary density method is discovered")
	_check(probe._plugin_has_method("renderer_diagnostics"), "An ordinary diagnostics method is discovered")
	_check(ordinary.java_queries == 0, "Ordinary methods take precedence over the Java registry")
	probe.free()
	ordinary.free()
	for mode in ["2d", "3d"]:
		await _check_lifetime(mode)
	var report := {"result": "passed" if _failures == 0 else "failed", "checks": _checks,
		"godotVersion": Engine.get_version_info().string,
		"limitations": "Desktop registry doubles and actual renderer scenes. Android JNI invocation and native readiness require the Android runner."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("Native bridge boundary checks: %d passed, %d failed." % [_checks.size() - _failures, _failures])
	quit(0 if _failures == 0 else 1)


func _check_lifetime(mode: String) -> void:
	var bridge := OrdinaryBridge.new()
	bridge.launch = FileAccess.get_file_as_string(_fixtures.path_join("launch-%s.json" % mode))
	Engine.register_singleton("PartyDeckBridge", bridge)
	root.size = Vector2i(720, 1120)
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	await process_frame
	_check(bridge.events.size() == 1 and bridge.events[0].get("type") == "ready", mode + ": native launch emits exactly Ready")
	_check(main._native_display_scale_valid and is_equal_approx(root.content_scale_factor, 1.75), mode + ": discovered density is applied")
	_check(is_equal_approx(root.get_visible_rect().size.x, 720.0 / 1.75), mode + ": logical viewport uses native density")
	var controller: Node = main.controller
	_check(controller.presentation_state().presentationMode == mode, mode + ": requested presentation is instantiated")
	bridge.diagnostics_requested.emit("17")
	_check(bridge.diagnostics.size() == 1 and bridge.diagnostics[0].requestId == "17", mode + ": diagnostic request reaches the callback")
	if bridge.diagnostics.size() == 1:
		var diagnostic: Dictionary = bridge.diagnostics[0]
		_check(diagnostic.handConcealed and diagnostic.privateFaceCount == 0 and diagnostic.privateLabelCount == 0,
			mode + ": initial diagnostics confirm private bindings are absent")
		_check(diagnostic.coordinateSpace == "root_viewport" and is_equal_approx(diagnostic.viewport.width, 720.0 / 1.75),
			mode + ": diagnostic coordinates use the logical root viewport")
	bridge.diagnostics_requested.emit("1e3")
	_check(bridge.diagnostics.size() == 1, mode + ": invalid diagnostic request IDs are ignored")
	var reveal: BaseButton = get_first_node_in_group("partydeck_action_reveal")
	if _check(reveal != null, mode + ": the local reveal control is attached"):
		reveal.pressed.emit()
	await process_frame
	bridge.diagnostics_requested.emit("18")
	_check(bridge.diagnostics.size() == 2 and not bridge.diagnostics.back().handConcealed,
		mode + ": read-only diagnostics can observe local reveal")
	var presentation_id: String = controller.presentation_id
	bridge.command_received.emit(JSON.stringify({"protocolVersion": 1, "presentationId": presentation_id,
		"type": "foreground", "isForeground": false}))
	bridge.diagnostics_requested.emit("19")
	if _check(bridge.diagnostics.size() == 3, mode + ": diagnostics remain callable while backgrounded"):
		var concealed: Dictionary = bridge.diagnostics.back()
		_check(not concealed.foreground and concealed.handConcealed and concealed.privateFaceCount == 0 and concealed.privateLabelCount == 0,
			mode + ": background commands synchronously remove private bindings")
	_check(bridge.events.size() == 1, mode + ": local changes and diagnostics emit no authority intent")
	_check(bridge.java_queries == 0, mode + ": ordinary callback dispatch preserves Object precedence")
	bridge.command_received.emit(JSON.stringify({"protocolVersion": 1, "presentationId": presentation_id, "type": "close"}))
	_check(controller.presentation_state().closed, mode + ": native close reaches the controller")
	root.remove_child(main)
	main.queue_free()
	Engine.unregister_singleton("PartyDeckBridge")
	paused = false
	root.content_scale_factor = 1.0
	await process_frame
	bridge.free()


func _check(condition: bool, description: String) -> bool:
	_checks.append({"check": description, "passed": condition})
	if not condition:
		_failures += 1
		push_error(description)
	return condition
