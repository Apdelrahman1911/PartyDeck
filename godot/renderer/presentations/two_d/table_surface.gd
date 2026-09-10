extends Control
## Original flat table geometry and a public face-down claim; never draws a private hand.

const DeckStyle = preload("res://presentations/two_d/deck_style.gd")

var claim_count := 0
var _back: Texture2D

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_back = DeckStyle.card_texture("BACK")
	resized.connect(queue_redraw)

func show_claim(count: int) -> void:
	claim_count = count
	queue_redraw()

func _draw() -> void:
	var middle := size * Vector2(0.5, 0.57)
	var major := maxf(20, size.x * 0.46)
	var minor := maxf(20, size.y * 0.43)
	draw_ellipse(middle, major, minor, Color("#211D2D"), true, -1, true)
	draw_ellipse(middle, major, minor, DeckStyle.DIVIDER, false, 1, true)
	draw_ellipse(middle, major - 10, minor - 9, Color("#373042"), false, 1, true)
	var card_size := Vector2(70, 105) * clampf(size.y / 210.0, 0.75, 1.25)
	var pile_center := middle + Vector2(0, 4)
	if claim_count > 0 and _back != null:
		for index in mini(claim_count, 3):
			var angle := deg_to_rad(float(index - 1) * 8.0)
			draw_set_transform(pile_center + Vector2((index - 1) * 13, -index * 3), angle)
			draw_texture_rect(_back, Rect2(-card_size / 2, card_size), false)
		draw_set_transform(Vector2.ZERO)
	else:
		var empty := DeckStyle.box(Color.TRANSPARENT, DeckStyle.DIVIDER, 1, 12)
		draw_style_box(empty, Rect2(pile_center - card_size / 2, card_size))
		draw_circle(pile_center, 5, DeckStyle.CITRON, true, -1, true)
	for direction in [-1, 1]:
		var decoration := middle + Vector2(direction * major * 0.79, 0)
		draw_line(decoration - Vector2(13, 0), decoration + Vector2(13, 0), DeckStyle.DIVIDER, 1, true)
		draw_circle(decoration, 2, DeckStyle.MUTED, true, -1, true)
