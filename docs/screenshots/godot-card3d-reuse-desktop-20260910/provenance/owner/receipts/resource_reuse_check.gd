extends SceneTree
## Private contract probe for sharing/lifetime; no authority action or native timing.

var _output := ""
var _fixture_path := ""
var _main: Node
var _checks: Array[Dictionary] = []
var _snapshots: Array[Dictionary] = []
var _failed := false

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--check-output="):
			_output = argument.trim_prefix("--check-output=")
		elif argument.begins_with("--check-fixture="):
			_fixture_path = argument.trim_prefix("--check-fixture=")
	_run.call_deferred()

func _run() -> void:
	if not _output.is_absolute_path() or not _fixture_path.is_absolute_path() \
		or DisplayServer.get_name() == "headless" or RenderingServer.get_current_rendering_method() != "gl_compatibility":
		push_error("Absolute fixture/output paths and an actual compatibility renderer are required.")
		quit(1)
		return
	var launch: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(_fixture_path))
	launch.presentationMode = "3d"
	launch.preferences.reduceMotion = true
	launch.preferences.soundEnabled = false
	launch.preferences.textScale = 1.0
	# An explicit source-test projection exercises both claim and hand creation paths.
	# It does not assert that the authority accepted a play or describe the native run.
	for player in launch.payload.game.players:
		if player.id != launch.payload.game.viewerId:
			launch.payload.game.latestClaim = {"playerId": player.id, "cardCount": 3}
			break
	launch.payload.game.availableActions.canChallenge = true
	_restore_integer_tokens(launch)
	root.size = Vector2i(390, 844)
	await _mount(launch)
	if not is_instance_valid(_main._presentation):
		_finish()
		return
	var table: Node = _main._presentation
	var first_bundle_id: int = table._card_resources.get_instance_id()
	var bundle_ref: WeakRef = weakref(table._card_resources)
	var geometry_refs := _weak_resources(table)
	var first := _inspect(table, "concealed claim and hand")
	_check(first.card_nodes.size() == launch.payload.game.yourHand.size() + 3, "both creation paths produced all claim and hand cards")
	_check(get_nodes_in_group("partydeck_private_face").is_empty(), "concealed cards have no private-face group")
	_main.controller.reveal_hand()
	await _settle()
	var revealed := _inspect(table, "revealed hand")
	_check(revealed.mesh_ids == first.mesh_ids and revealed.solid_material_ids == first.solid_material_ids, "reveal retains the same five immutable resources")
	_check(_disjoint(first.card_nodes, revealed.card_nodes), "reveal still replaces each card node")
	_check(_disjoint(first.face_material_ids, revealed.face_material_ids), "reveal still creates fresh face materials")
	_check(get_nodes_in_group("partydeck_private_face").size() == launch.payload.game.yourHand.size(), "only the own hand receives private-face groups")
	_main.controller.toggle_card(launch.payload.game.yourHand[0].id)
	await _settle()
	root.size = Vector2i(844, 390)
	await _settle()
	var resized := _inspect(table, "selected landscape rebuild")
	_check(resized.mesh_ids == first.mesh_ids and resized.solid_material_ids == first.solid_material_ids, "selection and resize retain the same five resources")
	_check(_disjoint(revealed.card_nodes, resized.card_nodes), "resize keeps card nodes unique to the rebuilt scene")
	_check(_main.controller.presentation_state().selectedCardIds.size() == 1, "selection remains intact through resize")
	_check(_main.receive_document(JSON.stringify({"protocolVersion": 1, "presentationId": launch.presentationId, "type": "close"})), "Close is accepted")
	await _settle()
	_check(not is_instance_valid(table), "Close destroys the old table")
	_check(bundle_ref.get_ref() == null, "Close releases the presentation bundle")
	for index in geometry_refs.size():
		_check(geometry_refs[index].get_ref() == null, "Close releases shared resource %d" % index)
	_check(get_nodes_in_group("partydeck_private_face").is_empty() and get_nodes_in_group("partydeck_private_label").is_empty(), "Close erases private groups")
	_main.queue_free()
	await _settle()
	await _mount(launch)
	var next_table: Node = _main._presentation
	var fresh := _inspect(next_table, "fresh presentation")
	_check(next_table._card_resources.get_instance_id() != first_bundle_id, "fresh entry owns a fresh bundle")
	_check(_disjoint(first.mesh_ids, fresh.mesh_ids) and _disjoint(first.solid_material_ids, fresh.solid_material_ids), "no shared resources survive into the next presentation")
	_main.queue_free()
	await _settle()
	_finish()

func _mount(launch: Dictionary) -> void:
	paused = false
	_main = load("res://main.tscn").instantiate()
	root.add_child(_main)
	_check(_main.receive_document(JSON.stringify(launch)), "source-test launch is accepted")
	await _settle()

func _inspect(table: Node, label: String) -> Dictionary:
	var snapshot := {"label": label, "card_nodes": [], "mesh_instance_nodes": [], "mesh_ids": [], "solid_material_ids": [], "face_material_ids": []}
	for card in table._cards.get_children():
		snapshot.card_nodes.append(card.get_instance_id())
		for instance in card.get_children():
			snapshot.mesh_instance_nodes.append(instance.get_instance_id())
			if instance.mesh.get_instance_id() not in snapshot.mesh_ids:
				snapshot.mesh_ids.append(instance.mesh.get_instance_id())
			var material_ids: Array = snapshot.face_material_ids if instance == card.face else snapshot.solid_material_ids
			if instance.material_override.get_instance_id() not in material_ids:
				material_ids.append(instance.material_override.get_instance_id())
	_check(snapshot.mesh_ids.size() == 3, label + ": all cards share exactly three mesh resources")
	_check(snapshot.solid_material_ids.size() == 2, label + ": all cards share exactly two solid materials")
	_check(snapshot.face_material_ids.size() == snapshot.card_nodes.size(), label + ": face materials remain unique per card")
	_check(snapshot.mesh_instance_nodes.size() == 3 * snapshot.card_nodes.size(), label + ": three mesh-instance nodes remain per card")
	_snapshots.append(snapshot)
	return snapshot

func _weak_resources(table: Node) -> Array[WeakRef]:
	var refs: Array[WeakRef] = []
	var card: Node = table._cards.get_child(0)
	for instance in card.get_children():
		refs.append(weakref(instance.mesh))
		if instance != card.face:
			refs.append(weakref(instance.material_override))
	return refs

func _disjoint(left: Array, right: Array) -> bool:
	for value in left:
		if value in right:
			return false
	return true

func _settle() -> void:
	await process_frame
	await process_frame
	await process_frame
	RenderingServer.force_draw()

func _check(passed: bool, name: String) -> void:
	_checks.append({"name": name, "passed": passed})
	_failed = _failed or not passed

func _finish() -> void:
	var report := {"result": "failed" if _failed else "passed", "checks": _checks, "snapshots": _snapshots,
		"scope": "Actual desktop resource identity, fresh-node and release behavior. Source-test projection only; no authority acceptance or native latency claim."}
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output.path_join("report.json"), FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("Resource reuse checks: %d checks, passed=%s" % [_checks.size(), not _failed])
	quit(1 if _failed else 0)

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
