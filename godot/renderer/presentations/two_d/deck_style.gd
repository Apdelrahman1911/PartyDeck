extends RefCounted
## Shared visual helpers for this presentation. No game decisions or bridge access.

const INK := Color("#191526")
const SURFACE := Color("#252133")
const PAPER := Color("#F4F0E8")
const MUTED := Color("#BAB5C4")
const CITRON := Color("#D6EF82")
const COPPER := Color("#F16B48")
const OUTLINE := Color("#888190")
const DIVIDER := Color("#575163")

static func font(display: bool = false) -> Font:
	var path := "res://assets/fonts/fraunces_semibold.ttf" if display else "res://assets/fonts/manrope_regular.ttf"
	return load(path) as Font

static func box(fill: Color, border: Color = Color.TRANSPARENT, stroke: int = 0, radius: int = 14) -> StyleBoxFlat:
	var result := StyleBoxFlat.new()
	result.bg_color = fill
	result.border_color = border
	result.set_border_width_all(stroke)
	result.set_corner_radius_all(radius)
	result.content_margin_left = 16.0
	result.content_margin_right = 16.0
	result.content_margin_top = 12.0
	result.content_margin_bottom = 12.0
	return result

static func label(value: String, point_size: int = 18, color: Color = PAPER, display: bool = false) -> Label:
	var result := Label.new()
	result.text = value
	result.add_theme_font_override("font", font(display))
	result.add_theme_font_size_override("font_size", point_size)
	result.add_theme_color_override("font_color", color)
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	result.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return result

static func button(value: String, point_size: int = 18, accent: Color = CITRON, secondary: bool = false) -> Button:
	var result := Button.new()
	result.text = value
	result.custom_minimum_size = Vector2(56, 56)
	result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	result.focus_mode = Control.FOCUS_ALL
	result.mouse_filter = Control.MOUSE_FILTER_PASS
	result.add_theme_font_override("font", font())
	result.add_theme_font_size_override("font_size", point_size)
	result.add_theme_color_override("font_color", PAPER if secondary else INK)
	result.add_theme_color_override("font_hover_color", PAPER if secondary else INK)
	result.add_theme_color_override("font_pressed_color", PAPER if secondary else INK)
	result.add_theme_color_override("font_disabled_color", MUTED)
	result.add_theme_stylebox_override("normal", box(SURFACE if secondary else accent, OUTLINE if secondary else accent, 1, 24))
	result.add_theme_stylebox_override("hover", box(Color("#342E44") if secondary else accent.lightened(0.07), PAPER if secondary else accent, 1, 24))
	result.add_theme_stylebox_override("pressed", box(SURFACE if secondary else accent.darkened(0.08), PAPER if secondary else accent, 2, 24))
	result.add_theme_stylebox_override("disabled", box(SURFACE, DIVIDER, 1, 24))
	var focus := box(Color.TRANSPARENT, PAPER, 3, 24)
	focus.content_margin_left = 0
	focus.content_margin_right = 0
	focus.content_margin_top = 0
	focus.content_margin_bottom = 0
	result.add_theme_stylebox_override("focus", focus)
	return result

static func rank_name(rank: String) -> String:
	match rank:
		"CROWN": return TranslationServer.translate("Crown")
		"MOON": return TranslationServer.translate("Moon")
		"STAR": return TranslationServer.translate("Star")
		"WILD": return TranslationServer.translate("Wild")
	return ""

static func rank_plural(rank: String) -> String:
	match rank:
		"CROWN": return TranslationServer.translate("Crowns")
		"MOON": return TranslationServer.translate("Moons")
		"STAR": return TranslationServer.translate("Stars")
		"WILD": return TranslationServer.translate("Wilds")
	return ""

static func card_texture(rank: String) -> Texture2D:
	if rank == "BACK":
		return load("res://assets/textures/cards/back.png") as Texture2D
	if rank not in ["CROWN", "MOON", "STAR", "WILD"]:
		return null
	return load("res://assets/textures/cards/face_%s.png" % rank.to_lower()) as Texture2D

static func player_name(game: Dictionary, player_id: String) -> String:
	var players: Array = game.get("players", [])
	for index in players.size():
		var player: Dictionary = players[index]
		if str(player.get("id", "")) == player_id:
			var name := str(player.get("displayName", ""))
			var matches := 0
			for other in players:
				if str(other.get("displayName", "")).nocasecmp_to(name) == 0:
					matches += 1
			return TranslationServer.translate("%s · seat %d") % [name, index + 1] if matches > 1 else name
	return TranslationServer.translate("The player")
