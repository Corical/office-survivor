class_name PulseDot
extends Control
## A small dot that breathes: "something is happening, wait" (used by the calm connection banner). Colour by theme name;
## it only animates while visible, and holds still under reduced motion.

const SIZE := 16.0

var _t := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(SIZE + 4.0, SIZE + 4.0)
	size_flags_vertical = Control.SIZE_SHRINK_CENTER
	visibility_changed.connect(func(): set_process(is_visible_in_tree()))
	set_process(is_visible_in_tree())


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _draw() -> void:
	var c := size * 0.5
	var k := 0.5 if Themes.reduced_motion else 0.5 + 0.5 * sin(_t * 4.2)
	draw_circle(c, SIZE * (0.62 + 0.3 * k), Themes.color_a("warm", 0.22 + 0.2 * k))
	draw_circle(c, SIZE * 0.34, Themes.color("warm"))
