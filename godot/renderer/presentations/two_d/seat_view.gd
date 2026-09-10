extends PanelContainer
## Public seat identity, card count, and already-consumed fuse lights only.

const DeckStyle = preload("res://presentations/two_d/deck_style.gd")

var _name_label: Label
var _status: Label
var _lights: Label
var _number: Label

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var contents := VBoxContainer.new()
	contents.add_theme_constant_override("separation", 4)
	add_child(contents)
	_number = DeckStyle.label("", 12, DeckStyle.MUTED)
	contents.add_child(_number)
	_name_label = DeckStyle.label("", 17)
	contents.add_child(_name_label)
	_status = DeckStyle.label("", 14, DeckStyle.MUTED)
	contents.add_child(_status)
	_lights = DeckStyle.label("", 13, DeckStyle.COPPER)
	contents.add_child(_lights)

func configure(player: Dictionary, seat: int, viewer: String, turn: String, text_scale: float) -> void:
	var own := str(player.get("id", "")) == viewer
	var active := str(player.get("id", "")) == turn
	var eliminated := bool(player.get("eliminated", false))
	_number.text = tr("SEAT %02d · YOU") % seat if own else tr("SEAT %02d") % seat
	_name_label.text = str(player.get("displayName", ""))
	var count := int(player.get("handCount", 0))
	_status.text = tr("Out of this match") if eliminated else (tr("%d cards · playing") % count if active else tr("%d cards in hand") % count)
	var attempts := int(player.get("penaltyAttempts", 0))
	_lights.text = tr("No lights used") if attempts == 0 else (tr("1 light used") if attempts == 1 else tr("%d lights used") % attempts)
	_lights.add_theme_color_override("font_color", DeckStyle.MUTED if attempts == 0 else DeckStyle.COPPER)
	_number.add_theme_font_size_override("font_size", int(12 * text_scale))
	_name_label.add_theme_font_size_override("font_size", int(17 * text_scale))
	_status.add_theme_font_size_override("font_size", int(14 * text_scale))
	_lights.add_theme_font_size_override("font_size", int(13 * text_scale))
	add_theme_stylebox_override("panel", DeckStyle.box(DeckStyle.SURFACE if not active else Color("#30362C"), DeckStyle.CITRON if active else DeckStyle.DIVIDER, 2 if active else 1, 14))
	_name_label.add_theme_color_override("font_color", DeckStyle.MUTED if eliminated else DeckStyle.PAPER)
	accessibility_name = tr("Seat %d, %s. %s. %s.") % [seat, _name_label.text, _status.text, _lights.text]
