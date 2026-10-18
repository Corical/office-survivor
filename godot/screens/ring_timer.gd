class_name RingTimer
extends Control
## The clock as a ring: a dark track, an arc that runs down as time runs out, and whatever the screen puts in the
## middle (the number, as a child Label). In the last seconds the arc changes colour and pulses; the number keeps
## counting, so the warning is never colour alone. Colours come from the theme by name.
## `value` / `max_value` mirror ProgressBar so a screen and its tests treat it the same way.

const WIDTH := 10.0

var value := 0.0:
	set(v):
		if not is_equal_approx(v, value):
			value = v
			queue_redraw()
var max_value := 1.0:
	set(v):
		max_value = maxf(v, 0.001)
		queue_redraw()
var urgent := false:
	set(v):
		if v != urgent:
			urgent = v
			queue_redraw()
var _pulse := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	if urgent:
		_pulse += delta * 7.0
		queue_redraw()


func _draw() -> void:
	var c := size * 0.5
	var r := minf(size.x, size.y) * 0.5 - WIDTH
	if r <= 4.0:
		return
	draw_circle(c, r + WIDTH * 0.5, Themes.color("shade"))
	draw_arc(c, r, 0.0, TAU, 56, Themes.color("ring_track"), WIDTH, true)
	var frac := clampf(value / max_value, 0.0, 1.0)
	if frac <= 0.0:
		return
	var col := Themes.color("ring_urgent") if urgent else Themes.color("ring_fill")
	var from := -PI * 0.5
	if urgent:
		col = col.lightened(0.18 * (0.5 + 0.5 * sin(_pulse)))
	# a wider, fainter arc under the bright one is the glow
	var glow := col
	glow.a = 0.28
	draw_arc(c, r, from, from + TAU * frac, 72, glow, WIDTH + 7.0, true)
	draw_arc(c, r, from, from + TAU * frac, 72, col, WIDTH, true)
