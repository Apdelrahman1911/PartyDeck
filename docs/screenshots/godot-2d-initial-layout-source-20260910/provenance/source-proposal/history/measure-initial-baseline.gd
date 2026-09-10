extends SceneTree
## Off-repo source layout measurement. No rendered image or authority execution is claimed.

var _output := ""
var _fixture_path := ""
var _cases_path := ""
var _main: Node

func _initialize() -> void:
	for option in OS.get_cmdline_user_args():
		if option.begins_with("--measure-output="):
			_output = option.trim_prefix("--measure-output=")
		elif option.begins_with("--measure-fixture="):
			_fixture_path = option.trim_prefix("--measure-fixture=")
		elif option.begins_with("--measure-cases="):
			_cases_path = option.trim_prefix("--measure-cases=")
	_run.call_deferred()

func _run() -> void:
	var cases: Array = JSON.parse_string(FileAccess.get_file_as_string(_cases_path))
	var results: Array[Dictionary] = []
	for settings in cases:
		root.size = Vector2i(int(settings.width), int(settings.height))
		var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(_fixture_path))
		fixture.presentationMode = "2d"
		fixture.preferences.textScale = settings.textScale
		fixture.preferences.soundEnabled = false
		fixture.preferences.reduceMotion = true
		if settings.has("tableRank"):
			fixture.payload.game.tableRank = settings.tableRank
		if settings.has("playerName"):
			for player in fixture.payload.game.players:
				player.displayName = settings.playerName
		if settings.get("opponentTurn", false):
			fixture.payload.game.turnPlayerId = "seat-2"
			fixture.payload.game.availableActions.canPlay = false
		if settings.get("latestClaim", false):
			fixture.payload.game.latestClaim = {"playerId": "seat-2", "cardCount": 3}
			fixture.payload.game.availableActions.canChallenge = true
		_restore_integer_tokens(fixture)
		_main = load("res://main.tscn").instantiate()
		var events: Array[String] = []
		_main.bridge_event.connect(func(document: String) -> void: events.append(document))
		root.add_child(_main)
		current_scene = _main
		if not _main.receive_document(JSON.stringify(fixture)):
			push_error("Rejected measurement fixture: " + str(settings))
			quit(1)
			return
		var frames: Array[Dictionary] = []
		for frame in range(1, 13):
			await process_frame
			if frame in [1, 2, 4, 8, 12]:
				frames.append({"frame": frame, "measurement": _measurement()})
		results.append({"case": settings, "events": events, "frames": frames})
		root.remove_child(_main)
		_main.free()
		await process_frame
	var report := {"engine": Engine.get_version_info(), "source_project": ProjectSettings.globalize_path("res://"),
		"cases": results, "scope": "Real Godot source layout and diagnostics, headless; no PNG, native execution or authority acceptance."}
	FileAccess.open(_output, FileAccess.WRITE).store_string(JSON.stringify(report, "\t") + "\n")
	print("Measured ", results.size(), " source layout cases: ", _output)
	quit(0)

func _measurement() -> Dictionary:
	var result := {"diagnostics": JSON.parse_string(_main.diagnostics_document()), "components": {}}
	var presentation: Node = _main.get("_presentation")
	if presentation == null:
		return result
	for key in ["_margin", "_page", "_header", "_turn", "_body_scroll", "_body", "_board_row", "_rank", "_eyebrow", "_claim", "_surface", "_rule", "_hand_section", "_hand_title", "_cover_panel", "_cover_art", "_cover_title", "_cover_description", "_reveal", "_actions", "_feedback", "_seat_panel"]:
		var control: Control = presentation.get(key)
		var rect := control.get_global_rect()
		var entry := {"rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
			"minimum": [control.get_combined_minimum_size().x, control.get_combined_minimum_size().y],
			"visible": control.is_visible_in_tree(), "index": control.get_index()}
		if control is Label or control is Button:
			entry.text = control.text
		if control is ScrollContainer:
			entry.scrollVertical = control.scroll_vertical
			entry.scrollMax = control.get_v_scroll_bar().max_value
			entry.scrollPage = control.get_v_scroll_bar().page
		result.components[key] = entry
	return result

func _restore_integer_tokens(value: Variant) -> void:
	if value is Dictionary:
		for key in value:
			if value[key] is float and value[key] == floor(value[key]):
				value[key] = int(value[key])
			else:
				_restore_integer_tokens(value[key])
	elif value is Array:
		for child in value:
			_restore_integer_tokens(child)
