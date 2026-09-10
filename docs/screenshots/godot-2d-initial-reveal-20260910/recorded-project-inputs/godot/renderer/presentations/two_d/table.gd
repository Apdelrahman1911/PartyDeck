extends Control
## Last Light's flat editorial presentation. The shared controller owns every action/state decision.

signal redraw_requested

const DeckStyle = preload("res://presentations/two_d/deck_style.gd")
const HandCard = preload("res://presentations/two_d/hand_card.gd")
const SeatView = preload("res://presentations/two_d/seat_view.gd")
const TableSurface = preload("res://presentations/two_d/table_surface.gd")

var _controller: Object
var _state: Dictionary = {}
var _built := false
var _text_scale := 1.0
var _last_phase := ""
var _last_hand_visible := false
var _hand_ids: Array[String] = []
var _cards: Array[Button] = []
var _seat_nodes: Array[PanelContainer] = []
var _margin: MarginContainer
var _page: VBoxContainer
var _header: HBoxContainer
var _header_space: Control
var _body_scroll: ScrollContainer
var _body: VBoxContainer
var _board_row: BoxContainer
var _rule: ColorRect
var _seat_panel: VBoxContainer
var _seat_grid: GridContainer
var _brand: Label
var _turn: Label
var _eyebrow: Label
var _rank: Label
var _claim: Label
var _surface: Control
var _proof_row: HFlowContainer
var _outcome: Label
var _hand_section: VBoxContainer
var _hand_title: Label
var _hand_hint: Label
var _hand_scroll: ScrollContainer
var _hand_row: HBoxContainer
var _cover_panel: PanelContainer
var _cover_art: TextureRect
var _cover_title: Label
var _cover_description: Label
var _reveal: Button
var _hide: Button
var _play: Button
var _challenge: Button
var _next: Button
var _lobby: Button
var _exit: Button
var _actions: BoxContainer
var _feedback: Label
var _lobby_dialog: PanelContainer
var _dialog_scroll: ScrollContainer
var _audio: AudioStreamPlayer
var _last_claim_sound_key := ""
var _lobby_requested := false
var _pending_sound := ""
var _applied_revision := ""

func _ready() -> void:
	_build()
	resized.connect(_request_redraw)

func bind(controller: Object) -> void:
	_controller = controller

func store_state(state: Dictionary) -> void:
	# CPU-only replacement: lifecycle callbacks must not keep an older private hand.
	_state = state
	if state.closed or not state.foreground or not state.controls.canReturnToLobby:
		_lobby_requested = false
	if not state.soundEnabled:
		_pending_sound = ""

func apply_state(state: Dictionary) -> void:
	_render(state)
	_applied_revision = _controller.revision

func _controls_current() -> bool:
	return is_inside_tree() and not is_queued_for_deletion() and is_instance_valid(_controller) \
		and _controller.revision == _applied_revision \
		and bool(_state.get("foreground", false)) and not bool(_state.get("closed", true))

func _request_redraw() -> void:
	redraw_requested.emit()

func _exit_tree() -> void:
	_erase_hand()
	_controller = null
	_state = {}
	_lobby_requested = false
	_pending_sound = ""
	_applied_revision = ""

func _build() -> void:
	_audio = AudioStreamPlayer.new()
	_audio.name = "TableFeedback"
	_audio.add_to_group("partydeck_feedback")
	add_child(_audio)
	var backdrop := ColorRect.new()
	backdrop.color = DeckStyle.INK
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)
	_margin = MarginContainer.new()
	_margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_margin)
	_page = VBoxContainer.new()
	_page.add_theme_constant_override("separation", 12)
	_margin.add_child(_page)
	_header = HBoxContainer.new()
	_header.add_theme_constant_override("separation", 12)
	_page.add_child(_header)
	_exit = _action(tr("Exit"), "exit", "request_exit", true)
	_exit.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_exit.custom_minimum_size.x = 80
	_header.add_child(_exit)
	_brand = DeckStyle.label(tr("Last Light"), 30, DeckStyle.PAPER, true)
	_brand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_brand.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_header.add_child(_brand)
	_header_space = Control.new()
	_header_space.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_header_space.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_header.add_child(_header_space)
	_hide = _action(tr("Cover"), "hide", "hide_hand", true)
	_hide.size_flags_horizontal = Control.SIZE_SHRINK_END
	_hide.custom_minimum_size.x = 90
	_header.add_child(_hide)
	_turn = DeckStyle.label("", 18, DeckStyle.CITRON)
	_turn.name = "TurnMessage"
	_page.add_child(_turn)
	_body_scroll = ScrollContainer.new()
	_body_scroll.name = "TableScroll"
	_body_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_body_scroll.scroll_deadzone = 8
	_body_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_body_scroll.follow_focus = true
	_page.add_child(_body_scroll)
	_body = VBoxContainer.new()
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.add_theme_constant_override("separation", 20)
	_body_scroll.add_child(_body)
	_board_row = BoxContainer.new()
	_board_row.add_theme_constant_override("separation", 28)
	_body.add_child(_board_row)
	var table_area := VBoxContainer.new()
	table_area.name = "PublicTable"
	table_area.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	table_area.add_theme_constant_override("separation", 6)
	_board_row.add_child(table_area)
	_eyebrow = DeckStyle.label("", 13, DeckStyle.MUTED)
	_eyebrow.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	table_area.add_child(_eyebrow)
	_rank = DeckStyle.label("", 56, DeckStyle.PAPER, true)
	_rank.name = "RequiredRank"
	_rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	table_area.add_child(_rank)
	_surface = TableSurface.new()
	_surface.custom_minimum_size.y = 190
	table_area.add_child(_surface)
	_proof_row = HFlowContainer.new()
	_proof_row.name = "PublicReveal"
	_proof_row.alignment = FlowContainer.ALIGNMENT_CENTER
	_proof_row.last_wrap_alignment = FlowContainer.LAST_WRAP_ALIGNMENT_CENTER
	_proof_row.add_theme_constant_override("h_separation", 12)
	_proof_row.add_theme_constant_override("v_separation", 12)
	table_area.add_child(_proof_row)
	_claim = DeckStyle.label("", 18)
	_claim.name = "ClaimMessage"
	_claim.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	table_area.add_child(_claim)
	_outcome = DeckStyle.label("", 17, DeckStyle.MUTED)
	_outcome.name = "OutcomeMessage"
	_outcome.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	table_area.add_child(_outcome)
	_seat_panel = VBoxContainer.new()
	_seat_panel.add_theme_constant_override("separation", 10)
	_board_row.add_child(_seat_panel)
	_seat_panel.add_child(DeckStyle.label(tr("AT THE TABLE"), 13, DeckStyle.MUTED))
	_seat_grid = GridContainer.new()
	_seat_grid.columns = 2
	_seat_grid.add_theme_constant_override("h_separation", 10)
	_seat_grid.add_theme_constant_override("v_separation", 10)
	_seat_panel.add_child(_seat_grid)
	_rule = ColorRect.new()
	_rule.custom_minimum_size.y = 1
	_rule.color = DeckStyle.DIVIDER
	_rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.add_child(_rule)
	_hand_section = VBoxContainer.new()
	_hand_section.name = "PrivateHand"
	_hand_section.add_theme_constant_override("separation", 8)
	_body.add_child(_hand_section)
	_hand_title = DeckStyle.label(tr("YOUR HAND"), 13, DeckStyle.MUTED)
	_hand_section.add_child(_hand_title)
	_cover_panel = PanelContainer.new()
	_cover_panel.name = "HandCover"
	_cover_panel.mouse_filter = Control.MOUSE_FILTER_PASS
	_cover_panel.add_theme_stylebox_override("panel", DeckStyle.box(DeckStyle.SURFACE, DeckStyle.OUTLINE, 1, 18))
	_hand_section.add_child(_cover_panel)
	var cover_row := HBoxContainer.new()
	cover_row.add_theme_constant_override("separation", 20)
	_cover_panel.add_child(cover_row)
	_cover_art = TextureRect.new()
	_cover_art.texture = DeckStyle.card_texture("BACK")
	_cover_art.custom_minimum_size = Vector2(76, 114)
	_cover_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_cover_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_cover_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cover_row.add_child(_cover_art)
	var cover_copy := VBoxContainer.new()
	cover_copy.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cover_copy.add_theme_constant_override("separation", 8)
	cover_row.add_child(cover_copy)
	_cover_title = DeckStyle.label("", 23, DeckStyle.PAPER, true)
	cover_copy.add_child(_cover_title)
	_cover_description = DeckStyle.label(tr("Keep them close. Reveal when you’re ready."), 16, DeckStyle.MUTED)
	cover_copy.add_child(_cover_description)
	_reveal = _action(tr("Reveal my hand"), "reveal", "reveal_hand")
	cover_copy.add_child(_reveal)
	_hand_scroll = ScrollContainer.new()
	_hand_scroll.name = "HandScroll"
	_hand_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_hand_scroll.scroll_deadzone = 8
	_hand_scroll.follow_focus = true
	_hand_section.add_child(_hand_scroll)
	_hand_row = HBoxContainer.new()
	_hand_row.name = "HandCards"
	_hand_row.add_theme_constant_override("separation", 12)
	_hand_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_hand_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_hand_scroll.add_child(_hand_row)
	_hand_hint = DeckStyle.label("", 15, DeckStyle.MUTED)
	_hand_section.add_child(_hand_hint)
	_feedback = DeckStyle.label("", 16, DeckStyle.MUTED)
	_feedback.name = "ActionMessage"
	_page.add_child(_feedback)
	_actions = BoxContainer.new()
	_actions.name = "Actions"
	_actions.add_theme_constant_override("separation", 10)
	_page.add_child(_actions)
	_play = _action(tr("Make a claim"), "play", "play_selected")
	_actions.add_child(_play)
	_challenge = _action(tr("Call the bluff"), "challenge", "challenge", false, DeckStyle.COPPER)
	_actions.add_child(_challenge)
	_next = _action(tr("Deal the next round"), "next_round", "next_round")
	_actions.add_child(_next)
	_lobby = DeckStyle.button(tr("Return to lobby"), 16, DeckStyle.CITRON, true)
	_lobby.name = "ReturnToLobby"
	_lobby.add_to_group("partydeck_action_lobby")
	_lobby.pressed.connect(_request_lobby)
	_header.add_child(_lobby)
	_built = true
	_relayout()

func _action(title: String, identifier: String, method: String, secondary: bool = false, accent: Color = DeckStyle.CITRON) -> Button:
	var button := DeckStyle.button(title, 18, accent, secondary)
	button.name = identifier.to_pascal_case()
	button.add_to_group("partydeck_action_" + identifier)
	button.accessibility_name = title
	button.pressed.connect(func() -> void:
		if _controls_current() and button.is_inside_tree() and not button.is_queued_for_deletion():
			_queue_sound("challenge" if method == "challenge" else "ui_tap")
			_controller.call(method)
	)
	return button

func _render(next_state: Dictionary) -> void:
	store_state(next_state)
	if not _built:
		return
	_text_scale = float(_state.get("textScale", 1.0))
	var game: Dictionary = _state.get("game", {})
	var controls: Dictionary = _state.get("controls", {})
	var foreground := bool(_state.get("foreground", true))
	var closed := bool(_state.get("closed", false))
	var playing := str(game.get("phase", "")) == "PLAYING"
	var phase := str(game.get("phase", ""))
	var can_send := bool(controls.get("canSendAction", false)) and foreground and not closed
	var available: Dictionary = game.get("availableActions", {})
	var hand_visible := bool(_state.get("handVisible", false)) and foreground and not closed and playing
	var selected: Array = _state.get("selectedCardIds", [])
	var hand: Array = game.get("yourHand", [])
	var status := str(_state.get("status", ""))
	var recipient_active: bool = game.get("viewerId") != null
	for player in game.get("players", []):
		if player.get("id") == game.get("viewerId") and bool(player.get("eliminated", false)):
			recipient_active = false
	_exit.disabled = closed or _controller == null
	_hide.visible = hand_visible
	_hide.disabled = not foreground or closed
	_hand_section.visible = playing and recipient_active and not closed
	_seat_panel.visible = not game.is_empty() and not closed
	_cover_panel.visible = not hand_visible
	_hand_scroll.visible = hand_visible
	_reveal.disabled = hand.is_empty() or not foreground or closed
	_cover_art.visible = _text_scale < 1.5 and size.x >= 420
	_cover_title.text = tr("%d cards. Yours to keep close.") % hand.size()
	if _text_scale >= 1.5:
		_cover_title.text = tr("%d cards, covered.") % hand.size()
	if not foreground:
		_cover_title.text = tr("Your hand is covered.")
	elif hand.is_empty():
		_cover_title.text = tr("Your hand is empty.")
	_cover_description.text = tr("Wait for the next deal. The table is still playing.") if hand.is_empty() else tr("Keep them close. Reveal when you’re ready.")
	_cover_description.visible = _text_scale < 1.5 or hand.is_empty()
	_reveal.visible = not hand.is_empty()
	_update_public_table(game, foreground, closed)
	_update_seats(game)
	_update_hand(hand, hand_visible, selected, can_send and bool(available.get("canPlay", false)), int(available.get("maxPlayableCards", 0)))
	_play.visible = playing and recipient_active and not bool(game.get("forcedChallenge", false)) and not closed
	_play.disabled = not (can_send and hand_visible and bool(available.get("canPlay", false)) and not selected.is_empty())
	var rank := str(game.get("tableRank", ""))
	_play.text = tr("Claim %d %s") % [selected.size(), DeckStyle.rank_name(rank) if selected.size() == 1 else DeckStyle.rank_plural(rank)] if not selected.is_empty() else tr("Choose cards to play")
	_play.accessibility_name = _play.text
	_challenge.visible = playing and recipient_active and not closed
	_challenge.disabled = not (can_send and bool(available.get("canChallenge", false)))
	_next.visible = phase == "ROUND_ENDED" and bool(controls.get("isHost", false)) and not closed
	_next.disabled = not (can_send and bool(controls.get("canAdvanceRound", false)))
	_lobby.visible = bool(controls.get("canReturnToLobby", false)) and not closed
	_lobby.disabled = not can_send
	_lobby.text = tr("Return to lobby")
	_lobby.accessibility_name = _lobby.text
	var lobby_accent := phase == "FINISHED"
	for color_key in ["font_color", "font_hover_color", "font_pressed_color"]:
		_lobby.add_theme_color_override(color_key, DeckStyle.INK if lobby_accent else DeckStyle.PAPER)
	var lobby_fill := DeckStyle.CITRON if lobby_accent else DeckStyle.SURFACE
	var lobby_border := DeckStyle.CITRON if lobby_accent else DeckStyle.OUTLINE
	_lobby.add_theme_stylebox_override("normal", DeckStyle.box(lobby_fill, lobby_border, 1, 24))
	_lobby.add_theme_stylebox_override("hover", DeckStyle.box(lobby_fill.lightened(0.07), lobby_border, 1, 24))
	_lobby.add_theme_stylebox_override("pressed", DeckStyle.box(lobby_fill.darkened(0.08), lobby_border, 2, 24))
	_feedback.text = status
	if status.is_empty() and phase == "ROUND_ENDED" and not bool(controls.get("isHost", false)):
		_feedback.text = tr("Waiting for the host to deal the next round.")
	elif status.is_empty() and playing and not recipient_active:
		_feedback.text = tr("You burned out. Watch the table.") if game.get("viewerId") != null else tr("Watching the table.")
	_feedback.visible = not _feedback.text.is_empty()
	if not _lobby_requested:
		_remove_lobby_dialog()
	_relayout(false)
	if hand_visible and not _last_hand_visible:
		_scroll_hand_into_view(true)
	elif not hand_visible and _last_hand_visible and playing and not hand.is_empty():
		_scroll_hand_into_view(false)
	elif phase != _last_phase:
		_body_scroll.scroll_vertical = 0
	_update_audio(game)
	if _lobby_requested:
		_show_lobby_dialog()
	if not _pending_sound.is_empty():
		_sound(_pending_sound)
		_pending_sound = ""
	_last_hand_visible = hand_visible
	_last_phase = phase

func _scroll_hand_into_view(revealed: bool) -> void:
	await get_tree().process_frame
	if is_inside_tree() and revealed == bool(_state.get("handVisible", false)):
		_body_scroll.ensure_control_visible(_hand_scroll if revealed else _cover_panel)

func _update_public_table(game: Dictionary, foreground: bool, closed: bool) -> void:
	var phase := str(game.get("phase", ""))
	var viewer := str(game.get("viewerId", ""))
	var turn := str(game.get("turnPlayerId", ""))
	var rank := str(game.get("tableRank", ""))
	var outcome: Dictionary = game.get("roundOutcome", {}) if game.get("roundOutcome") != null else {}
	var resolved := phase in ["ROUND_ENDED", "FINISHED"] and not outcome.is_empty() and int(outcome.get("roundNumber", -1)) == int(game.get("roundNumber", 0))
	_surface.visible = not resolved and not closed and _text_scale < 1.5
	_proof_row.visible = resolved and not closed
	_outcome.visible = resolved and not closed
	_claim.visible = true
	_clear_children(_proof_row)
	if closed:
		_eyebrow.text = tr("PARTYDECK")
		_rank.text = tr("Until the next hand.")
		_claim.text = tr("This presentation has ended.")
		_turn.text = ""
		return
	if game.is_empty():
		_eyebrow.text = tr("PARTYDECK")
		_rank.text = tr("Pull up a chair.")
		_claim.text = tr("Your table will appear here when it’s ready.")
		_turn.text = tr("Waiting for the table…")
		_surface.show_claim(0)
		return
	_eyebrow.text = tr("ROUND %02d · THE RANK TO CLAIM") % int(game.get("roundNumber", 0))
	if _text_scale >= 1.5:
		_eyebrow.text = tr("ROUND %02d · CLAIM") % int(game.get("roundNumber", 0))
	_rank.text = DeckStyle.rank_name(rank)
	if not foreground:
		_turn.text = tr("Your cards are covered while the table is inactive.")
	elif phase == "FINISHED":
		_turn.text = tr("Last light standing.")
	elif phase == "ROUND_ENDED":
		_turn.text = tr("The cards are on the table.")
	elif turn == viewer:
		_turn.text = tr("Your turn · challenge required.") if bool(game.get("forcedChallenge", false)) else tr("Your turn · claim %s.") % DeckStyle.rank_plural(rank)
	else:
		_turn.text = tr("%s is up.") % DeckStyle.player_name(game, turn)
	if phase == "PLAYING" and size.y < 500 and foreground:
		var actor := tr("Your turn") if turn == viewer else tr("%s’s turn") % DeckStyle.player_name(game, turn)
		_turn.text = tr("%s · %s table") % [actor, DeckStyle.rank_name(rank)]
		var last_claim: Dictionary = game.get("latestClaim", {}) if game.get("latestClaim") != null else {}
		if not last_claim.is_empty():
			_turn.text += tr(" · %s claimed %d") % [DeckStyle.player_name(game, str(last_claim.get("playerId", ""))), int(last_claim.get("cardCount", 0))]
	if resolved:
		_eyebrow.text = tr("ROUND %02d · CARDS REVEALED") % int(game.get("roundNumber", 0))
		if _text_scale >= 1.5:
			_eyebrow.text = tr("ROUND %02d · REVEAL") % int(game.get("roundNumber", 0))
		var truthful := bool(outcome.get("truthful", false))
		_rank.text = tr("The claim was true.") if truthful else tr("Bluff caught.")
		if phase == "FINISHED":
			_rank.text = tr("%s wins.") % DeckStyle.player_name(game, str(game.get("winnerId", "")))
		var claimant := DeckStyle.player_name(game, str(outcome.get("claimantId", "")))
		var challenger := DeckStyle.player_name(game, str(outcome.get("challengerId", "")))
		var loser := DeckStyle.player_name(game, str(outcome.get("penalizedPlayerId", "")))
		_claim.text = tr("%s challenged %s’s %s claim.") % [challenger, claimant, DeckStyle.rank_name(str(outcome.get("tableRank", rank)))]
		_outcome.text = tr("Every card was %s or Wild. %s used light %d.") % [DeckStyle.rank_name(rank), loser, int(outcome.get("penaltyAttempt", 0))] if truthful else tr("A revealed card wasn’t %s or Wild. %s used light %d.") % [DeckStyle.rank_name(rank), loser, int(outcome.get("penaltyAttempt", 0))]
		_outcome.text += " " + (tr("They burned out.") if bool(outcome.get("burnedOut", false)) else tr("They stay in.") )
		for card in outcome.get("revealedCards", []):
			_add_proof_card(str(card.get("rank", "")))
	else:
		var claim: Dictionary = game.get("latestClaim", {}) if game.get("latestClaim") != null else {}
		_surface.show_claim(int(claim.get("cardCount", 0)))
		_claim.text = tr("A fresh round. Who do you trust?")
		_claim.visible = not claim.is_empty() or _text_scale < 1.5
		if not claim.is_empty():
			var count := int(claim.get("cardCount", 0))
			_claim.text = tr("%s claimed %d %s.") % [DeckStyle.player_name(game, str(claim.get("playerId", ""))), count, DeckStyle.rank_name(rank) if count == 1 else DeckStyle.rank_plural(rank)]

func _add_proof_card(rank: String) -> void:
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 4)
	var card_width := maxf(72, 52 * _text_scale)
	column.custom_minimum_size.x = card_width
	var face := TextureRect.new()
	face.texture = DeckStyle.card_texture(rank)
	face.custom_minimum_size = Vector2(card_width, card_width * 1.5)
	face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(face)
	var caption := DeckStyle.label(DeckStyle.rank_name(rank), int(14 * _text_scale))
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(caption)
	column.accessibility_name = tr("Revealed %s") % DeckStyle.rank_name(rank)
	_proof_row.add_child(column)

func _update_seats(game: Dictionary) -> void:
	var players: Array = game.get("players", [])
	if _seat_nodes.size() != players.size():
		_clear_children(_seat_grid)
		_seat_nodes.clear()
		for index in players.size():
			var seat := SeatView.new()
			seat.name = "Seat%d" % index
			seat.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			_seat_grid.add_child(seat)
			_seat_nodes.append(seat)
	for index in players.size():
		_seat_nodes[index].configure(players[index], index + 1, str(game.get("viewerId", "")), str(game.get("turnPlayerId", "")), _text_scale)

func _update_hand(hand: Array, visible_hand: bool, selected: Array, can_play: bool, maximum: int) -> void:
	_hand_hint.visible = visible_hand
	if not visible_hand:
		_erase_hand()
		_hand_hint.text = ""
		return
	var ids: Array[String] = []
	for card in hand:
		# A controller-concealed card never becomes a rankless actionable front.
		if not card.has("rank"):
			_erase_hand()
			return
		ids.append(str(card.get("id", "")))
	if ids != _hand_ids:
		_erase_hand()
		_hand_ids.assign(ids)
		for index in hand.size():
			var card_button := HandCard.new()
			_hand_row.add_child(card_button)
			var card_id := ids[index]
			card_button.pressed.connect(func() -> void:
				if _controls_current() and card_button.is_inside_tree() and not card_button.is_queued_for_deletion():
					_queue_sound("ui_tap")
					_controller.toggle_card(card_id)
			)
			_cards.append(card_button)
	var card_width := _card_width()
	for index in hand.size():
		var chosen := str(hand[index].get("id", "")) in selected
		_cards[index].configure(hand[index], index, chosen, can_play and (chosen or selected.size() < maximum), card_width, _text_scale, bool(_state.get("reduceMotion", false)))
	var hand_width := hand.size() * card_width + maxi(0, hand.size() - 1) * 12
	var available_width := size.x - (44 if size.x < 860 or _text_scale >= 1.5 else 68)
	_hand_scroll.custom_minimum_size.y = card_width * 1.5 + 42 * _text_scale + (14 if hand_width > available_width else 0)
	_hand_hint.text = tr("%d selected · Your claim is %s.") % [selected.size(), DeckStyle.rank_plural(str(_state.get("game", {}).get("tableRank", "")))] if not selected.is_empty() else (tr("Select up to %d cards. Wilds match every rank.") % maximum if can_play else tr("Your hand stays yours while the table takes its turn."))

func _erase_hand() -> void:
	for card in _cards:
		if is_instance_valid(card):
			card.erase_private_content()
			card.get_parent().remove_child(card)
			card.queue_free()
	_cards.clear()
	_hand_ids.clear()

func _card_width() -> float:
	var base := 88.0 if size.y < 500 else (104.0 if size.x < 700 else (112.0 if size.y < 900 else 128.0))
	return maxf(base, 76.0 * _text_scale)

func _relayout(refresh_cards: bool = true) -> void:
	if not _built:
		return
	var narrow := size.x < 860 or _text_scale >= 1.5
	var large_text := _text_scale >= 1.5
	var short_window := size.y < 500
	var margin := 16 if narrow else 28
	_margin.add_theme_constant_override("margin_left", margin)
	_margin.add_theme_constant_override("margin_right", margin)
	_margin.add_theme_constant_override("margin_top", 8 if short_window else 12)
	_margin.add_theme_constant_override("margin_bottom", 8 if short_window else 12)
	_body.add_theme_constant_override("separation", 12 if size.y < 800 else 20)
	_board_row.vertical = narrow
	_body.move_child(_hand_section if short_window else _board_row, 0)
	_body.move_child(_rule, 1)
	_body.move_child(_board_row if short_window else _hand_section, 2)
	_hand_title.visible = not short_window
	_hand_section.add_theme_constant_override("separation", 6 if short_window else 8)
	var seat_parent: Node = _body if narrow else _board_row
	if _seat_panel.get_parent() != seat_parent:
		_seat_panel.reparent(seat_parent, false)
	var action_parent: Node = _body if large_text else _page
	if _actions.get_parent() != action_parent:
		_actions.reparent(action_parent, false)
	if large_text:
		_body.move_child(_actions, _hand_section.get_index() + 1)
	var finished := str(_state.get("game", {}).get("phase", "")) == "FINISHED"
	var lobby_parent: Node = _actions if finished else (_body if narrow else _header)
	if _lobby.get_parent() != lobby_parent:
		_lobby.reparent(lobby_parent, false)
	if narrow:
		_body.move_child(_seat_panel, _body.get_child_count() - 1)
		if lobby_parent == _body:
			_body.move_child(_lobby, _body.get_child_count() - 1)
	elif lobby_parent == _header:
		_header.move_child(_lobby, _hide.get_index())
	_lobby.size_flags_horizontal = Control.SIZE_SHRINK_END if lobby_parent == _header else Control.SIZE_EXPAND_FILL
	_lobby.custom_minimum_size.x = 180 * _text_scale if lobby_parent == _header else 56
	var wide_seat_columns := 3 if _seat_nodes.size() > 4 else 2
	_seat_panel.custom_minimum_size.x = 0 if narrow else (494 if wide_seat_columns == 3 else 326)
	_seat_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL if narrow else Control.SIZE_SHRINK_END
	_seat_grid.columns = 1 if large_text else (3 if size.x >= 520 else 2)
	if not narrow:
		_seat_grid.columns = wide_seat_columns
	_actions.vertical = size.x < 680 or _text_scale >= 1.5
	_brand.visible = not (narrow and large_text)
	_header_space.visible = not _brand.visible
	_exit.custom_minimum_size.x = 124 if large_text else 80
	_hide.custom_minimum_size.x = 140 if large_text else 90
	_brand.add_theme_font_size_override("font_size", int(28 * _text_scale))
	_turn.add_theme_font_size_override("font_size", int(18 * _text_scale))
	_eyebrow.add_theme_font_size_override("font_size", int(13 * _text_scale))
	_rank.add_theme_font_size_override("font_size", int((28 if large_text else (42 if narrow else 54)) * _text_scale))
	_claim.add_theme_font_size_override("font_size", int(18 * _text_scale))
	_outcome.add_theme_font_size_override("font_size", int(16 * _text_scale))
	_hand_title.add_theme_font_size_override("font_size", int(13 * _text_scale))
	_hand_hint.add_theme_font_size_override("font_size", int(15 * _text_scale))
	_cover_title.add_theme_font_size_override("font_size", int(23 * _text_scale))
	_cover_description.add_theme_font_size_override("font_size", int(16 * _text_scale))
	_feedback.add_theme_font_size_override("font_size", int(16 * _text_scale))
	for button in [_exit, _hide, _reveal, _play, _challenge, _next, _lobby]:
		button.add_theme_font_size_override("font_size", int(17 * _text_scale))
		button.custom_minimum_size.y = 56
	var surface_height := 136 if short_window else (148 if narrow else 152)
	if narrow and not short_window and not large_text and size.y < 800:
		# Leave room for the concealed hand above the fixed actions.
		surface_height = 124
	_surface.custom_minimum_size.y = surface_height
	_cover_art.visible = _text_scale < 1.5 and size.x >= 420
	if _dialog_scroll != null:
		_fit_lobby_dialog()
	if refresh_cards and not _state.is_empty():
		_update_public_table(_state.get("game", {}), bool(_state.get("foreground", true)), bool(_state.get("closed", false)))
	if refresh_cards and not _cards.is_empty():
		var hand: Array = _state.get("game", {}).get("yourHand", [])
		var available: Dictionary = _state.get("game", {}).get("availableActions", {})
		_update_hand(hand, true, _state.get("selectedCardIds", []), bool(_state.get("controls", {}).get("canSendAction", false)) and bool(available.get("canPlay", false)), int(available.get("maxPlayableCards", 0)))

func _request_lobby() -> void:
	if not _controls_current() \
		or not bool(_state.get("controls", {}).get("canReturnToLobby", false)):
		return
	_queue_sound("ui_tap")
	if str(_state.get("game", {}).get("phase", "")) == "FINISHED":
		_controller.return_to_lobby()
		return
	if _lobby_requested:
		return
	_lobby_requested = true
	_controller.hide_hand()
	_request_redraw()

func _show_lobby_dialog() -> void:
	if _lobby_dialog != null:
		return
	_margin.focus_behavior_recursive = Control.FOCUS_BEHAVIOR_DISABLED
	_lobby_dialog = PanelContainer.new()
	_lobby_dialog.name = "LobbyConfirmation"
	_lobby_dialog.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_lobby_dialog.add_theme_stylebox_override("panel", DeckStyle.box(DeckStyle.INK))
	add_child(_lobby_dialog)
	var center := CenterContainer.new()
	_lobby_dialog.add_child(center)
	_dialog_scroll = ScrollContainer.new()
	_dialog_scroll.follow_focus = true
	_dialog_scroll.scroll_deadzone = 8
	_dialog_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_fit_lobby_dialog()
	center.add_child(_dialog_scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 16)
	_dialog_scroll.add_child(content)
	content.add_child(DeckStyle.label(tr("Return to lobby?"), int((22 if _text_scale >= 1.5 else 30) * _text_scale), DeckStyle.PAPER, true))
	content.add_child(DeckStyle.label(tr("This ends the match for everyone."), int(18 * _text_scale), DeckStyle.MUTED))
	var confirm := DeckStyle.button(tr("Return to lobby"), int(18 * _text_scale), DeckStyle.COPPER)
	confirm.add_to_group("partydeck_action_lobby_confirm")
	confirm.pressed.connect(func() -> void:
		if not _controls_current() or not confirm.is_inside_tree() or confirm.is_queued_for_deletion():
			return
		_close_lobby_dialog()
		_controller.return_to_lobby()
	)
	content.add_child(confirm)
	var cancel := DeckStyle.button(tr("Keep playing"), int(18 * _text_scale), DeckStyle.CITRON, true)
	cancel.add_to_group("partydeck_action_lobby_cancel")
	cancel.pressed.connect(func() -> void:
		if _controls_current() and cancel.is_inside_tree() and not cancel.is_queued_for_deletion():
			_close_lobby_dialog()
	)
	content.add_child(cancel)
	cancel.grab_focus()

func _close_lobby_dialog() -> void:
	_lobby_requested = false
	_request_redraw()

func _remove_lobby_dialog() -> void:
	if _lobby_dialog != null:
		remove_child(_lobby_dialog)
		_lobby_dialog.queue_free()
		_lobby_dialog = null
		_dialog_scroll = null
		_margin.focus_behavior_recursive = Control.FOCUS_BEHAVIOR_INHERITED
		if bool(_state.get("foreground", false)) and _lobby.is_visible_in_tree() and not _lobby.disabled:
			_lobby.grab_focus()

func _fit_lobby_dialog() -> void:
	_dialog_scroll.custom_minimum_size = Vector2(minf(480, size.x - 40), minf(680 if _text_scale >= 1.5 else 460, size.y - 40))

func _queue_sound(cue: String) -> void:
	if bool(_state.get("soundEnabled", false)):
		_pending_sound = cue
		_request_redraw()

func _sound(cue: String) -> void:
	if not bool(_state.get("soundEnabled", false)) or not bool(_state.get("foreground", false)) or bool(_state.get("closed", false)):
		return
	_audio.stream = load("res://assets/audio/%s.wav" % cue)
	_audio.play()

func _update_audio(game: Dictionary) -> void:
	if not bool(_state.get("soundEnabled", false)):
		_audio.stop()
	var phase := str(game.get("phase", ""))
	var claim: Dictionary = game.get("latestClaim", {}) if game.get("latestClaim") != null else {}
	var claim_key := "" if claim.is_empty() else "%d/%s/%d" % [int(game.get("roundNumber", 0)), str(claim.get("playerId", "")), int(claim.get("cardCount", 0))]
	if not _last_phase.is_empty():
		if phase == "FINISHED" and _last_phase != phase:
			_sound("victory")
		elif phase == "ROUND_ENDED" and _last_phase == "PLAYING":
			var outcome: Dictionary = game.get("roundOutcome", {})
			_sound("light_out" if bool(outcome.get("burnedOut", false)) else "safe")
		elif phase == "PLAYING" and not claim_key.is_empty() and claim_key != _last_claim_sound_key:
			_sound("card_place")
	_last_claim_sound_key = claim_key

func _clear_children(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()
