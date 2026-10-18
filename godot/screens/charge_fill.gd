class_name ChargeFill
extends Control
## A light that fills a button from the left as the night runs down (the Lock button "charges" while you have not
## locked). It sits on top of the button, lets every tap through, and paints the theme's "ChargeFill" fill box.

const INSET_X := 10.0
const INSET_TOP := 8.0
const INSET_BOTTOM := 16.0                 # the wood button has a lip under it

var fraction := 0.0:
	set(v):
		v = clampf(v, 0.0, 1.0)
		if not is_equal_approx(v, fraction):
			fraction = v
			queue_redraw()


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func _draw() -> void:
	var w := (size.x - INSET_X * 2.0) * fraction
	if w < 14.0:
		return
	var sb := get_theme_stylebox("fill", "ChargeFill")
	draw_style_box(sb, Rect2(INSET_X, INSET_TOP, w, size.y - INSET_TOP - INSET_BOTTOM))
