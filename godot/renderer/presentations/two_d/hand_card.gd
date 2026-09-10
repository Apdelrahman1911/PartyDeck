extends Button
## A real focusable card button. Its private texture/text are explicitly erased on cover.

const DeckStyle = preload("res://presentations/two_d/deck_style.gd")

var card_id := ""
var card_index := 0
var _face: TextureRect
var _caption: Label
var _badge: PanelContainer
var _selected := false
var _lift: Tween
var _text_scale := 1.0

func _ready() -> void:
	focus_mode = Control.FOCUS_ALL
	toggle_mode = true
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	add_to_group("partydeck_hand_card")
	_face = TextureRect.new()
	_face.add_to_group("partydeck_private_face")
	_face.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_face.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_face.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	add_child(_face)
	_caption = DeckStyle.label("", 16)
	_caption.add_to_group("partydeck_private_label")
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_caption)
	_badge = PanelContainer.new()
	_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var badge_style := DeckStyle.box(DeckStyle.CITRON, DeckStyle.INK, 1, 12)
	badge_style.content_margin_left = 4
	badge_style.content_margin_right = 4
	badge_style.content_margin_top = 4
	badge_style.content_margin_bottom = 4
	_badge.add_theme_stylebox_override("panel", badge_style)
	var check := TextureRect.new()
	check.texture = load("res://assets/vectors/icon_check.svg")
	check.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	check.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	check.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_badge.add_child(check)
	add_child(_badge)
	_badge.hide()
	resized.connect(_layout)
	add_theme_stylebox_override("focus", DeckStyle.box(Color.TRANSPARENT, DeckStyle.PAPER, 3, 16))
	_layout()

func configure(card: Dictionary, index: int, selected: bool, enabled: bool, width: float, text_scale: float, reduce_motion: bool) -> void:
	card_id = str(card.get("id", ""))
	card_index = index
	set_meta("card_index", index)
	name = "HandCard%d" % index
	var rank := str(card.get("rank", ""))
	var rank_text := DeckStyle.rank_name(rank)
	_text_scale = text_scale
	disabled = not enabled
	custom_minimum_size = Vector2(width, width * 1.5 + 42.0 * text_scale)
	_face.texture = DeckStyle.card_texture(rank)
	_caption.text = rank_text
	_caption.add_theme_font_size_override("font_size", int(16 * text_scale))
	accessibility_name = tr("%s, card %d") % [rank_text, index + 1]
	accessibility_description = tr("Selected") if selected else tr("Not selected")
	tooltip_text = accessibility_name + ". " + accessibility_description
	var changed := selected != _selected
	_selected = selected
	set_pressed_no_signal(selected)
	_badge.visible = selected
	add_theme_stylebox_override("normal", DeckStyle.box(DeckStyle.SURFACE, DeckStyle.CITRON if selected else DeckStyle.OUTLINE, 3 if selected else 1, 16))
	add_theme_stylebox_override("hover", DeckStyle.box(DeckStyle.SURFACE.lightened(0.06), DeckStyle.CITRON, 2, 16))
	add_theme_stylebox_override("pressed", DeckStyle.box(DeckStyle.SURFACE, DeckStyle.CITRON, 3, 16))
	add_theme_stylebox_override("disabled", DeckStyle.box(DeckStyle.SURFACE, DeckStyle.DIVIDER, 1, 16))
	_layout()
	if changed and not reduce_motion and is_visible_in_tree():
		if _lift != null:
			_lift.kill()
		_face.position.y = 10.0 if selected else 2.0
		_lift = create_tween()
		_lift.tween_property(_face, "position:y", 2.0 if selected else 10.0, 0.13).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	queue_redraw()

func erase_private_content() -> void:
	if _lift != null:
		_lift.kill()
	card_id = ""
	_face.texture = null
	_caption.text = ""
	accessibility_name = ""
	accessibility_description = ""
	tooltip_text = ""
	_selected = false
	set_pressed_no_signal(false)
	_badge.hide()
	hide()

func _layout() -> void:
	if _face == null:
		return
	var caption_height := 42.0 * _text_scale
	var face_height := maxf(0.0, size.y - caption_height)
	_face.position.x = 8
	if _lift == null or not _lift.is_running():
		_face.position.y = 2 if _selected else 10
	_face.size = Vector2(maxf(0.0, size.x - 16), maxf(0.0, face_height - 12))
	_caption.position = Vector2(6, face_height)
	_caption.size = Vector2(maxf(0.0, size.x - 12), caption_height - 6)
	_badge.position = Vector2(size.x - 28, 4)
	_badge.size = Vector2(24, 24)
