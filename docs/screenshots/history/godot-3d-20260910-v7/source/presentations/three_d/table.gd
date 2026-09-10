extends Control

const Card3D = preload("res://presentations/three_d/card_3d.gd")
const INK := Color("#191526")
const PAPER := Color("#f4f0e8")
const CITRON := Color("#d6ef82")
const COPPER := Color("#f16b48")
const MUTED := Color("#bab5c4")
const SURFACE := Color("#252133")
const OUTLINE := Color("#888190")

var _controller: Node
var _state: Dictionary = {}
var _layout: MarginContainer
var _stage: Control
var _viewport_container: SubViewportContainer
var _viewport: SubViewport
var _world: Node3D
var _camera: Camera3D
var _cards: Node3D
var _ornament: Node3D
var _hits: Control
var _card_bindings: Array = []
var _feedback: AudioStreamPlayer
var _layout_pending := false
var _motion_frames := 0
var _scroll_offsets: Dictionary = {}
var _history_visible := false
var _lobby_dialog: PanelContainer
var _last_public_cue := ""
var _focus_request: Dictionary = {}
var _context_pinned := false
var _hand_toggle_in_header := false


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_make_stage()
	_feedback = AudioStreamPlayer.new()
	_feedback.add_to_group("partydeck_feedback")
	add_child(_feedback)
	resized.connect(_resize)
	set_process(false)


func bind(controller: Node) -> void:
	_controller = controller
	_controller.state_changed.connect(_render)
	_render(_controller.presentation_state())


func _render(state: Dictionary) -> void:
	var same_page: bool = not _state.is_empty() and not _state.game.is_empty() and not state.game.is_empty() \
		and _state.game.phase == state.game.phase and _state.game.roundNumber == state.game.roundNumber
	if not same_page:
		_history_visible = false
	_state = state
	if _lobby_dialog != null and (state.closed or not state.foreground or not state.controls.canReturnToLobby):
		_close_lobby_dialog()
	if state.closed:
		_feedback.stop()
		_clear(_cards)
		_clear(_hits)
		return
	if state.game.is_empty():
		return
	if not state.foreground or not state.soundEnabled:
		_feedback.stop()
	if not state.foreground:
		_history_visible = false
	_build_layout(same_page)
	_show_cards()
	_public_sound()
	_viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE if state.foreground else SubViewport.UPDATE_ONCE
	_motion_frames = 12 if not state.reduceMotion and state.foreground else 1
	set_process(true)
	call_deferred("_position_targets")


func _make_stage() -> void:
	_stage = Control.new()
	_stage.custom_minimum_size = Vector2(0, 180)
	_stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_stage.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.resized.connect(_position_targets)
	add_child(_stage)
	_viewport_container = SubViewportContainer.new()
	_viewport_container.stretch = true
	_viewport_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_viewport_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_stage.add_child(_viewport_container)
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(640, 360)
	_viewport.own_world_3d = true
	_viewport.msaa_3d = Viewport.MSAA_2X
	_viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	_viewport_container.add_child(_viewport)
	_world = Node3D.new()
	_viewport.add_child(_world)
	var environment := WorldEnvironment.new()
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR
	settings.background_color = INK
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = PAPER
	settings.ambient_light_energy = 0.65
	environment.environment = settings
	_world.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-52, -30, 0)
	light.light_energy = 0.65
	light.light_color = Color("#fff7e8")
	light.shadow_enabled = false
	_world.add_child(light)
	_camera = Camera3D.new()
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	_camera.size = 7.25
	_camera.position = Vector3(0, 8, 9)
	_camera.far = 40
	_world.add_child(_camera)
	_camera.look_at(Vector3.ZERO)
	_camera.current = true
	_cylinder(4.15, 0.16, Vector3(0, -0.19, 0), OUTLINE.darkened(0.42), Vector3(1, 1, 0.69))
	_cylinder(4.07, 0.14, Vector3(0, -0.09, 0), SURFACE, Vector3(1, 1, 0.69))
	_cylinder(3.92, 0.01, Vector3(0, -0.013, 0), INK.lightened(0.045), Vector3(1, 1, 0.69))
	_cards = Node3D.new()
	_world.add_child(_cards)
	_ornament = Node3D.new()
	_world.add_child(_ornament)
	_hits = Control.new()
	_hits.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_hits.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stage.add_child(_hits)


func _build_layout(preserve_scroll: bool = true) -> void:
	_scroll_offsets.clear()
	_focus_request.clear()
	if preserve_scroll and is_instance_valid(_layout):
		_remember_scrolls(_layout)
		_remember_focus()
	var wide: bool = size.x >= 700 and size.y < 540 and _state.textScale < 1.3
	var large: bool = _state.textScale >= 1.3
	var scrollable: bool = large or _history_visible or (size.x < 700 and size.y < 700)
	_context_pinned = scrollable and not wide and _state.game.phase == "PLAYING"
	_hand_toggle_in_header = (wide or scrollable) and _state.game.phase == "PLAYING" and not _state.game.yourHand.is_empty() \
		and not (_state.game.forcedChallenge and _state.game.availableActions.canChallenge)
	if _stage.get_parent() != null:
		_stage.get_parent().remove_child(_stage)
	if is_instance_valid(_layout):
		remove_child(_layout)
		_layout.queue_free()
	_layout = MarginContainer.new()
	_layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		_layout.add_theme_constant_override("margin_" + side, 16)
	add_child(_layout)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	_layout.add_child(column)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	column.add_child(header)
	var exit_button := _button("‹", "partydeck_action_exit", _controller.request_exit, true, false)
	exit_button.custom_minimum_size.x = 48
	exit_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	exit_button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	exit_button.add_theme_font_size_override("font_size", 24)
	exit_button.autowrap_mode = TextServer.AUTOWRAP_OFF
	exit_button.accessibility_name = "Leave the table"
	header.add_child(exit_button)
	var brand := _label("Last Light", 18, false, PAPER)
	brand.add_theme_font_size_override("font_size", mini(22, int(18 * _state.textScale)))
	brand.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	brand.visible = not (_hand_toggle_in_header and size.x < 500)
	header.add_child(brand)
	if size.x >= 700 and size.y < 540 and _state.textScale < 1.3 and _state.game.phase == "PLAYING":
		var turn: String = "Your turn" if _state.game.viewerId == _state.game.turnPlayerId else "%s’s turn" % _name(_state.game.turnPlayerId)
		header.add_child(_label(turn, 16, false, CITRON if _state.game.viewerId == _state.game.turnPlayerId else MUTED))
	var round_label := _label("ROUND %d" % int(_state.game.roundNumber), 12, false, MUTED)
	round_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	round_label.visible = not (_hand_toggle_in_header and size.x < 500)
	header.add_child(round_label)
	if _hand_toggle_in_header:
		header.add_child(_hand_toggle())
	if _context_pinned:
		var context := VBoxContainer.new()
		context.add_theme_constant_override("separation", 3)
		column.add_child(context)
		context.add_child(_label("%s table · round %d" % [_rank(_state.game.tableRank), int(_state.game.roundNumber)], 16, false, PAPER))
		var turn: String = "Your turn" if _state.game.viewerId == _state.game.turnPlayerId else "%s’s turn" % _name(_state.game.turnPlayerId)
		context.add_child(_label(turn, 16, false, CITRON if _state.game.viewerId == _state.game.turnPlayerId else MUTED))
		if _state.game.latestClaim != null:
			context.add_child(_label(_claim_line(), 16, false, MUTED))
	if wide:
		var row := HBoxContainer.new()
		row.size_flags_vertical = Control.SIZE_EXPAND_FILL
		row.add_theme_constant_override("separation", 24)
		column.add_child(row)
		row.add_child(_stage)
		var scroll := ScrollContainer.new()
		scroll.name = "TableBodyScroll"
		scroll.follow_focus = true
		scroll.scroll_deadzone = 8
		scroll.custom_minimum_size.x = minf(size.x * 0.43, 400)
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		row.add_child(scroll)
		var sidebar := VBoxContainer.new()
		sidebar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		sidebar.add_theme_constant_override("separation", 16)
		scroll.add_child(sidebar)
		_public_info(sidebar, true)
		_hand_controls(sidebar, false)
	elif scrollable:
		var scroll := ScrollContainer.new()
		scroll.name = "TableBodyScroll"
		scroll.follow_focus = true
		scroll.scroll_deadzone = 8
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
		column.add_child(scroll)
		var content := VBoxContainer.new()
		content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		content.add_theme_constant_override("separation", 20)
		scroll.add_child(content)
		_public_info(content, false)
		_stage.custom_minimum_size.y = 220
		content.add_child(_stage)
		_hand_controls(content, large)
	else:
		_public_info(column, false)
		_stage.custom_minimum_size.y = 180
		column.add_child(_stage)
		_hand_controls(column, false)
	_layout.visible = _lobby_dialog == null
	if _lobby_dialog != null:
		move_child(_lobby_dialog, get_child_count() - 1)
	call_deferred("_restore_scrolls")


func _public_info(parent: VBoxContainer, compact: bool) -> void:
	var game: Dictionary = _state.game
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 6)
	parent.add_child(info)
	if game.phase == "PLAYING":
		var turn := "Your turn" if game.viewerId == game.turnPlayerId else "%s’s turn" % _name(game.turnPlayerId)
		if not compact and not _context_pinned:
			info.add_child(_label(turn, 16, false, CITRON if game.viewerId == game.turnPlayerId else MUTED))
		if not _context_pinned:
			info.add_child(_label("%s table" % _rank(game.tableRank), 30, true, PAPER))
		var claim = game.latestClaim
		var claim_text := "Play 1–3 cards face down. Wilds always match."
		if claim != null:
			claim_text = _claim_line() + (" Only a challenge remains." if game.forcedChallenge else " Challenge or play on.")
		if not _context_pinned or claim == null:
			info.add_child(_label(claim_text, 16, false, MUTED))
		_roster(info)
		if game.roundOutcome != null:
			info.add_child(_button("Hide last round" if _history_visible else "Last round · review reveal", "partydeck_action_history", _toggle_history,
				_state.foreground, false))
			if _history_visible:
				info.add_child(_label("ROUND %d · PREVIOUS REVEAL" % int(game.roundOutcome.roundNumber), 12, false, MUTED))
				_result_info(info, game.roundOutcome, true)
				_proof_words(info, game.roundOutcome)
	elif game.phase == "ROUND_ENDED":
		_result_info(info, game.roundOutcome)
		if _state.textScale >= 1.3:
			_proof_words(info, game.roundOutcome)
	else:
		info.add_child(_label("LAST LIGHT STANDING", 12, false, CITRON))
		info.add_child(_label("%s wins." % _name(game.winnerId), 30 if _state.textScale < 1.3 else 24, true, PAPER))
		info.add_child(_label("The last light at the table.", 15, false, MUTED))
		if game.roundOutcome != null:
			info.add_child(_label("Final reveal · round %d" % int(game.roundOutcome.roundNumber), 13, false, MUTED))
			_result_info(info, game.roundOutcome, true)
			if _state.textScale >= 1.3:
				_proof_words(info, game.roundOutcome)


func _result_info(parent: VBoxContainer, outcome: Dictionary, compact: bool = false) -> void:
	parent.add_to_group("partydeck_public_result")
	parent.set_meta("round_number", int(outcome.roundNumber))
	var truthful: bool = outcome.truthful
	parent.add_child(_label("The claim was true." if truthful else "Bluff caught.", 20 if compact else 30, true, CITRON if truthful else COPPER))
	parent.add_child(_label("%s tested light %d. %s" % [_name(outcome.penalizedPlayerId), int(outcome.penaltyAttempt),
		"Burned out." if outcome.burnedOut else "Still in."], 16, false, PAPER))
	parent.add_child(_label("%s challenged %s’s %d-card %s claim." % [_name(outcome.challengerId), _name(outcome.claimantId),
		outcome.revealedCards.size(), _rank(outcome.tableRank)], 16, false, MUTED))


func _proof_words(parent: VBoxContainer, outcome: Dictionary) -> void:
	for card in outcome.revealedCards:
		var match_text: String = "Matches" if card.rank == "WILD" or card.rank == outcome.tableRank else "Doesn’t match"
		parent.add_child(_label("%s · %s" % [_rank(card.rank), match_text], 16, false, PAPER))


func _roster(parent: VBoxContainer) -> void:
	var scroll := ScrollContainer.new()
	scroll.name = "RosterScroll"
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.follow_focus = true
	scroll.scroll_deadzone = 8
	scroll.custom_minimum_size.y = 60
	parent.add_child(scroll)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	scroll.add_child(row)
	for player in _state.game.players:
		var seat := VBoxContainer.new()
		seat.custom_minimum_size.x = 126
		seat.add_theme_constant_override("separation", 2)
		row.add_child(seat)
		var color := CITRON if player.id == _state.game.turnPlayerId else MUTED
		seat.add_child(_label(_name(player.id), 14, false, color))
		seat.add_child(_label("Out · watching" if player.eliminated else "%d cards · fuse %d/6" % [int(player.handCount), int(player.penaltyAttempts)], 13, false, MUTED))
	if size.x < 900:
		parent.add_child(_label("Swipe seats to see everyone →", 12, false, MUTED))


func _hand_controls(parent: VBoxContainer, large: bool) -> void:
	var game: Dictionary = _state.game
	var actions: Dictionary = game.availableActions
	var controls: Dictionary = _state.controls
	var pane := VBoxContainer.new()
	pane.add_theme_constant_override("separation", 10)
	parent.add_child(pane)
	if game.phase == "PLAYING":
		var viewer = _viewer()
		if viewer == null:
			pane.add_child(_label("Stay for the showdown.", 24, true, PAPER))
			pane.add_child(_label("You’re watching this match. See who keeps their last light.", 16, false, MUTED))
		elif viewer.eliminated:
			pane.add_child(_label("Stay for the showdown.", 24, true, PAPER))
			pane.add_child(_label("You’re out of this match. Keep watching to see who keeps their last light.", 16, false, MUTED))
		elif game.forcedChallenge and actions.canChallenge:
			pane.add_child(_label("One claim left.", 24, true, PAPER))
			pane.add_child(_label("You’re the last player holding cards. Challenge the claim.", 16, false, MUTED))
		elif game.yourHand.is_empty():
			pane.add_child(_label("Your last play can still be challenged." if game.latestClaim != null and game.latestClaim.playerId == game.viewerId else "You’re clear for this round.", 17, false, PAPER))
		else:
			var hand_header: BoxContainer = VBoxContainer.new() if large else HBoxContainer.new()
			hand_header.add_theme_constant_override("separation", 12)
			pane.add_child(hand_header)
			hand_header.add_child(_label("Your hand · %d cards" % game.yourHand.size(), 16, false, PAPER))
			var showing: bool = _state.handVisible
			if not _hand_toggle_in_header:
				hand_header.add_child(_hand_toggle())
			if large and showing:
				for index in range(game.yourHand.size()):
					var card: Dictionary = game.yourHand[index]
					var selected: bool = card.id in _state.selectedCardIds
					var button := _button(("Selected · " if selected else "Select · ") + _rank(card.rank), "partydeck_hand_card",
						_controller.toggle_card.bind(card.id), controls.canSendAction and actions.canPlay, selected)
					button.toggle_mode = true
					button.set_pressed_no_signal(selected)
					button.set_meta("card_index", index)
					button.add_to_group("partydeck_private_label")
					pane.add_child(button)
		var row: BoxContainer = VBoxContainer.new() if large else HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		pane.add_child(row)
		if actions.canPlay:
			var count: int = _state.selectedCardIds.size()
			row.add_child(_button("Play %d" % count if count > 0 else "Select cards", "partydeck_action_play", _play,
				controls.canSendAction and count > 0 and _state.handVisible, true))
		if actions.canChallenge:
			row.add_child(_button("Challenge %s" % _name(game.latestClaim.playerId), "partydeck_action_challenge", _challenge,
				controls.canSendAction, false, COPPER))
		if not actions.canPlay and not actions.canChallenge:
			pane.add_child(_label("Waiting for %s" % _name(game.turnPlayerId), 14, false, MUTED))
	elif game.phase == "ROUND_ENDED":
		if controls.isHost:
			pane.add_child(_button("Next round", "partydeck_action_next_round", _controller.next_round,
				controls.canSendAction and controls.canAdvanceRound, true))
		else:
			pane.add_child(_label("Waiting for the host.", 16, false, MUTED))
	elif controls.isHost:
		pane.add_child(_button("Back to room", "partydeck_action_lobby", _controller.return_to_lobby,
			controls.canSendAction and controls.canReturnToLobby, true))
	else:
		pane.add_child(_label("Waiting for the host.", 16, false, MUTED))
	if game.phase != "FINISHED" and controls.isHost and controls.canReturnToLobby:
		pane.add_child(_button("Return to lobby", "partydeck_action_lobby", _request_lobby,
			controls.canSendAction, false, COPPER))
	if not _state.status.is_empty():
		pane.add_child(_label(_state.status, 16, false, MUTED))


func _show_cards() -> void:
	_clear(_cards)
	_clear(_ornament)
	_clear(_hits)
	_card_bindings.clear()
	var game: Dictionary = _state.game
	var rank: String = game.tableRank
	_cylinder(0.67, 0.025, Vector3(0, 0.025, -0.45), CITRON, Vector3.ONE, _ornament)
	var symbol := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(0.95, 0.95)
	symbol.mesh = plane
	symbol.position = Vector3(0, 0.044, -0.45)
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	material.albedo_texture = load("res://assets/textures/ranks/%s.png" % rank.to_lower())
	symbol.material_override = material
	_ornament.add_child(symbol)
	for index in range(game.players.size()):
		var angle: float = PI + (index + 0.5) * PI / game.players.size()
		var player: Dictionary = game.players[index]
		var color := OUTLINE.darkened(0.4) if player.eliminated else (CITRON if player.id == game.turnPlayerId else MUTED.darkened(0.45))
		_cylinder(0.13, 0.06, Vector3(cos(angle) * 3.25, 0.04, sin(angle) * 1.9), color, Vector3.ONE, _ornament)
	if game.phase != "PLAYING":
		if game.roundOutcome != null:
			var revealed: Array = game.roundOutcome.revealedCards
			for index in range(revealed.size()):
				_add_card(revealed[index], index, revealed.size(), true, false, false, 1.1, game.roundOutcome.tableRank)
		return
	if game.latestClaim != null:
		for index in range(int(game.latestClaim.cardCount)):
			var card = Card3D.new()
			_cards.add_child(card)
			card.position = Vector3(index * 0.1, 0.08 + index * 0.035, -0.25)
			card.rotation_degrees.y = -8 + index * 8
			card.configure("", false, false, false)
	if not (game.forcedChallenge and game.availableActions.canChallenge):
		for index in range(game.yourHand.size()):
			var card: Dictionary = game.yourHand[index]
			_add_card(card, index, game.yourHand.size(), _state.handVisible, true,
				card.id in _state.selectedCardIds, 1.65)


func _add_card(card_data: Dictionary, index: int, count: int, face_up: bool, private_card: bool, selected: bool,
	depth: float, table_rank: String = "") -> void:
	var card = Card3D.new()
	_cards.add_child(card)
	if not private_card:
		card.add_to_group("partydeck_public_card")
	card.position = Vector3((index - (count - 1) / 2.0) * 1.35, 0.36, depth)
	card.rotation_degrees = Vector3(22, (index - (count - 1) / 2.0) * -3.5, 0)
	var rank: String = card_data.get("rank", "") if face_up else ""
	card.configure(rank, face_up, selected, private_card)
	card.lift(selected, _state.reduceMotion or not _state.foreground)
	if not face_up:
		return
	var label: Label
	if _state.textScale < 1.3:
		label = _label(_rank(rank), 14, false, CITRON if selected else PAPER)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.autowrap_mode = TextServer.AUTOWRAP_OFF
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if private_card:
			label.add_to_group("partydeck_private_label")
		_hits.add_child(label)
	var marker: PanelContainer
	if selected:
		marker = PanelContainer.new()
		marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var marker_style := _style(CITRON, INK)
		marker_style.set_corner_radius_all(12)
		marker_style.content_margin_left = 4
		marker_style.content_margin_right = 4
		marker_style.content_margin_top = 1
		marker_style.content_margin_bottom = 1
		marker.add_theme_stylebox_override("panel", marker_style)
		var check := _label("✓", 16, false, INK)
		check.add_theme_font_size_override("font_size", 16)
		check.autowrap_mode = TextServer.AUTOWRAP_OFF
		check.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		check.mouse_filter = Control.MOUSE_FILTER_IGNORE
		check.add_to_group("partydeck_private_label")
		marker.add_child(check)
		_hits.add_child(marker)
	var target: Button
	if private_card and _state.textScale < 1.3:
		target = Button.new()
		target.flat = true
		target.mouse_filter = Control.MOUSE_FILTER_PASS
		target.toggle_mode = true
		target.disabled = not (_state.controls.canSendAction and _state.game.availableActions.canPlay)
		target.set_pressed_no_signal(selected)
		target.accessibility_name = "%s card %d" % [_rank(rank), index + 1]
		target.add_to_group("partydeck_hand_card")
		target.set_meta("card_index", index)
		var empty := StyleBoxEmpty.new()
		for style in ["normal", "hover", "pressed", "disabled", "hover_pressed"]:
			target.add_theme_stylebox_override(style, empty)
		var focus := _style(Color.TRANSPARENT, CITRON)
		focus.set_border_width_all(2)
		focus.set_corner_radius_all(4)
		target.add_theme_stylebox_override("focus", focus)
		target.pressed.connect(_toggle_card.bind(card_data.id))
		_hits.add_child(target)
	var explanation: Label
	if not private_card and _state.textScale < 1.3:
		explanation = _label("Wild · matches" if rank == "WILD" else ("Matches" if rank == table_rank else "Doesn’t match"), 13, false,
			CITRON if rank == "WILD" or rank == table_rank else COPPER)
		explanation.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_hits.add_child(explanation)
	_card_bindings.append({"card": card, "label": label, "marker": marker, "target": target, "explanation": explanation})


func _position_targets() -> void:
	if not is_instance_valid(_stage) or _stage.size.x < 1 or _stage.size.y < 1:
		return
	# KEEP_WIDTH preserves width. Expand it on short viewports to keep the table in view.
	_camera.size = maxf(7.25, 4.7 * _stage.size.x / _stage.size.y)
	for binding in _card_bindings:
		var points: Array[Vector3] = binding.card.corners()
		var bounds := Rect2(_camera.unproject_position(points[0]), Vector2.ZERO)
		for point in points:
			bounds = bounds.expand(_camera.unproject_position(point))
		if binding.label != null:
			binding.label.position = Vector2(bounds.position.x, bounds.end.y + 6)
			binding.label.size = Vector2(bounds.size.x, 24 * _state.textScale)
		if binding.marker != null:
			binding.marker.position = Vector2(bounds.get_center().x - 12, bounds.position.y - 12)
			binding.marker.size = Vector2(24, 24)
		if binding.target != null:
			var hit_size := Vector2(maxf(48, bounds.size.x), maxf(48, bounds.size.y))
			binding.target.position = bounds.get_center() - hit_size * 0.5
			binding.target.size = hit_size
		if binding.explanation != null:
			var explanation_width := maxf(50, bounds.size.x + 4)
			binding.explanation.position = Vector2(bounds.get_center().x - explanation_width * 0.5, bounds.end.y + 30)
			binding.explanation.size = Vector2(explanation_width, 42 * _state.textScale)


func _process(_delta: float) -> void:
	_position_targets()
	_motion_frames -= 1
	if _motion_frames <= 0:
		set_process(false)


func _resize() -> void:
	if _state.is_empty() or _layout_pending:
		return
	_layout_pending = true
	call_deferred("_apply_resize")


func _apply_resize() -> void:
	_layout_pending = false
	if not _state.is_empty() and not _state.game.is_empty():
		_render(_state)


func _button(text: String, group: String, action: Callable, enabled: bool, primary: bool, accent: Color = CITRON) -> Button:
	var button := Button.new()
	button.text = text
	button.mouse_filter = Control.MOUSE_FILTER_PASS
	button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button.custom_minimum_size.y = maxf(52, 28 + 20 * _state.textScale)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.disabled = not enabled
	button.add_theme_font_override("font", load("res://assets/fonts/manrope_semibold.ttf"))
	button.add_theme_font_size_override("font_size", int(16 * _state.textScale))
	button.add_theme_color_override("font_color", INK if primary else accent)
	button.add_theme_color_override("font_hover_color", INK if primary else accent)
	button.add_theme_color_override("font_pressed_color", INK if primary else accent)
	button.add_theme_color_override("font_hover_pressed_color", INK if primary else accent)
	button.add_theme_color_override("font_focus_color", INK if primary else accent)
	button.add_theme_color_override("font_disabled_color", MUTED)
	button.add_theme_stylebox_override("normal", _style(accent if primary else SURFACE, accent if primary else OUTLINE))
	button.add_theme_stylebox_override("hover", _style(accent.lightened(0.04) if primary else SURFACE.lightened(0.06), accent))
	button.add_theme_stylebox_override("pressed", _style(accent.darkened(0.06) if primary else SURFACE.lightened(0.03), accent))
	button.add_theme_stylebox_override("disabled", _style(SURFACE, SURFACE))
	button.add_theme_stylebox_override("focus", _style(Color.TRANSPARENT, PAPER))
	button.add_to_group(group)
	button.pressed.connect(action)
	return button


func _label(text: String, point_size: int, editorial: bool, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.add_theme_font_override("font", load("res://assets/fonts/fraunces_semibold.ttf" if editorial else "res://assets/fonts/manrope_regular.ttf"))
	label.add_theme_font_size_override("font_size", int(point_size * _state.get("textScale", 1.0)))
	label.add_theme_color_override("font_color", color)
	return label


func _style(color: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(24)
	style.content_margin_left = 16
	style.content_margin_right = 16
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	return style


func _cylinder(radius: float, height_value: float, position_value: Vector3, color: Color,
	scale_value: Vector3, parent: Node3D = _world) -> void:
	var instance := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height_value
	mesh.radial_segments = 64 if radius > 1 else 24
	instance.mesh = mesh
	instance.position = position_value
	instance.scale = scale_value
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.94
	instance.material_override = material
	parent.add_child(instance)


func _rank(rank: String) -> String:
	return {"CROWN": "Crown", "MOON": "Moon", "STAR": "Star", "WILD": "Wild"}.get(rank, "Card")


func _name(id_value: Variant) -> String:
	for index in range(_state.game.players.size()):
		var player: Dictionary = _state.game.players[index]
		if player.id == id_value:
			var duplicate: bool = _state.game.players.filter(func(other): return other.displayName.to_lower() == player.displayName.to_lower()).size() > 1
			return "%s · seat %d" % [player.displayName, index + 1] if duplicate else player.displayName
	return "the table"


func _viewer() -> Variant:
	for player in _state.game.players:
		if player.id == _state.game.viewerId:
			return player
	return null


func _clear(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _toggle_card(id_value: String) -> void:
	_sound("ui_tap")
	_controller.toggle_card(id_value)


func _play() -> void:
	_sound("ui_tap")
	_controller.play_selected()


func _challenge() -> void:
	_sound("challenge")
	_controller.challenge()


func _sound(cue: String) -> void:
	if _state.soundEnabled and _state.foreground:
		_feedback.stream = load("res://assets/audio/%s.wav" % cue)
		_feedback.play()


func _remember_scrolls(node: Node) -> void:
	if node is ScrollContainer:
		_scroll_offsets[str(node.name)] = Vector2i(node.scroll_horizontal, node.scroll_vertical)
	for child in node.get_children():
		_remember_scrolls(child)


func _restore_scrolls() -> void:
	if not is_instance_valid(_layout):
		return
	_restore_scroll_node(_layout)
	if _lobby_dialog == null and not _focus_request.is_empty():
		for node in get_tree().get_nodes_in_group(_focus_request.group):
			if node is BaseButton and is_ancestor_of(node) and node.is_visible_in_tree() and not node.disabled \
				and int(node.get_meta("card_index", -1)) == _focus_request.index:
				node.grab_focus()
				break


func _restore_scroll_node(node: Node) -> void:
	if node is ScrollContainer and _scroll_offsets.has(str(node.name)):
		var offset: Vector2i = _scroll_offsets[str(node.name)]
		node.scroll_horizontal = offset.x
		node.scroll_vertical = offset.y
	for child in node.get_children():
		_restore_scroll_node(child)


func _remember_focus() -> void:
	var focused := get_viewport().gui_get_focus_owner()
	if focused == null or not is_ancestor_of(focused):
		return
	for group in focused.get_groups():
		if group == "partydeck_hand_card" or str(group).begins_with("partydeck_action_"):
			var next_group: String = group
			if group == "partydeck_action_reveal" and _state.handVisible:
				next_group = "partydeck_action_hide"
			elif group == "partydeck_action_hide" and not _state.handVisible:
				next_group = "partydeck_action_reveal"
			_focus_request = {"group": next_group, "index": int(focused.get_meta("card_index", -1))}
			return


func _toggle_history() -> void:
	_history_visible = not _history_visible
	_render(_state)


func _request_lobby() -> void:
	if _controller == null or not _state.controls.canReturnToLobby:
		return
	if _state.game.phase == "FINISHED":
		_controller.return_to_lobby()
		return
	if _lobby_dialog != null:
		return
	_controller.hide_hand()
	_layout.hide()
	_lobby_dialog = PanelContainer.new()
	_lobby_dialog.name = "LobbyConfirmation"
	_lobby_dialog.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var background := _style(INK, INK)
	background.set_corner_radius_all(0)
	background.content_margin_left = 24
	background.content_margin_right = 24
	background.content_margin_top = 24
	background.content_margin_bottom = 24
	_lobby_dialog.add_theme_stylebox_override("panel", background)
	add_child(_lobby_dialog)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.scroll_deadzone = 8
	_lobby_dialog.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 20)
	scroll.add_child(content)
	content.add_child(_label("Return to lobby?", 22 if _state.textScale >= 1.3 else 30, true, PAPER))
	content.add_child(_label("This ends the match for everyone.", 18, false, MUTED))
	content.add_child(_button("Return to lobby", "partydeck_action_lobby_confirm", _confirm_return_to_lobby, true, false, COPPER))
	var cancel := _button("Keep playing", "partydeck_action_lobby_cancel", _close_lobby_dialog, true, true)
	content.add_child(cancel)
	cancel.grab_focus()


func _confirm_return_to_lobby() -> void:
	_close_lobby_dialog()
	_controller.return_to_lobby()


func _close_lobby_dialog() -> void:
	if _lobby_dialog == null:
		return
	remove_child(_lobby_dialog)
	_lobby_dialog.queue_free()
	_lobby_dialog = null
	if is_instance_valid(_layout):
		_layout.show()


func _public_sound() -> void:
	var game: Dictionary = _state.game
	var claim_key: String = "none" if game.latestClaim == null else "%s:%d" % [game.latestClaim.playerId, int(game.latestClaim.cardCount)]
	var signature := "%s:%d:%s" % [game.phase, int(game.roundNumber), claim_key]
	var previous := _last_public_cue
	_last_public_cue = signature
	if previous.is_empty() or signature == previous or not _state.foreground:
		return
	if game.phase == "FINISHED":
		_sound("victory")
	elif game.phase == "ROUND_ENDED":
		_sound("light_out" if game.roundOutcome.burnedOut else "safe")
	elif game.latestClaim != null:
		_sound("card_place")


func _exit_tree() -> void:
	if _controller != null and _controller.state_changed.is_connected(_render):
		_controller.state_changed.disconnect(_render)
	if is_instance_valid(_feedback):
		_feedback.stop()
	_state = {}
	_focus_request.clear()
	_scroll_offsets.clear()


func _hand_toggle() -> Button:
	var showing: bool = _state.handVisible
	return _button("Hide hand" if showing else "Show hand", "partydeck_action_hide" if showing else "partydeck_action_reveal",
		_controller.hide_hand if showing else _reveal_hand, _state.foreground, false)


func _reveal_hand() -> void:
	_controller.reveal_hand()
	if _hand_toggle_in_header:
		call_deferred("_bring_hand_into_view")


func _bring_hand_into_view() -> void:
	if not is_inside_tree():
		return
	await get_tree().process_frame
	if not is_inside_tree() or not _state.get("handVisible", false):
		return
	for card in get_tree().get_nodes_in_group("partydeck_hand_card"):
		if not is_ancestor_of(card):
			continue
		var ancestor := card.get_parent()
		while ancestor != null:
			if ancestor is ScrollContainer:
				ancestor.ensure_control_visible(card)
			ancestor = ancestor.get_parent()
		return


func _claim_line() -> String:
	var claim: Dictionary = _state.game.latestClaim
	var count := int(claim.cardCount)
	return "%s claimed %d %s%s." % [_name(claim.playerId), count, _rank(_state.game.tableRank), "" if count == 1 else "s"]
