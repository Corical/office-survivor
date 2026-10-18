class_name RingTimer
extends Control
## The clock as a ring: a dark track, an arc that drains as time runs out (redrawn every frame the value moves), and whatever
## the screen puts in the middle (the number, as a child Label). The arc has three looks, chosen by the screen from how much
## time is left: calm, "running short" and "urgent"; in the urgent stage it also pulses. Colours come from the theme by name
## (ring_fill, ring_warn, ring_urgent), so the warning is never colour alone (the number grows and the ring beats as well).
## `value` / `max_value` mirror ProgressBar so a screen and its tests treat it the same way.

const WIDTH := 10.0
const PULSE_RATE := 7.0
const COLOR_NAMES := ["ring_fill", "ring_warn", "ring_urgent"]

var value := 0.0:
	set(v):
		if not is_equal_approx(v, value):
			value = v
			queue_redraw()
var max_value := 1.0:
	set(v):
		max_value = maxf(v, 0.001)
		queue_redraw()
## 0 calm, 1 running short, 2 urgent
var state := 0:
	set(v):
		if v != state:
			state = v
			queue_redraw()
			if v != 2:
				scale = Vector2.ONE
var _pulse := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	pivot_offset = size * 0.5
	resized.connect(func(): pivot_offset = size * 0.5)


func _process(delta: float) -> void:
	if state == 2:
		_pulse += delta * PULSE_RATE
		scale = Vector2.ONE * (1.0 + 0.05 * maxf(0.0, sin(_pulse)))
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
	var col := Themes.color(COLOR_NAMES[clampi(state, 0, 2)])
	var from := -PI * 0.5
	if state == 2:
		col = col.lightened(0.18 * (0.5 + 0.5 * sin(_pulse)))
	# a wider, fainter arc under the bright one is the glow
	var glow := col
	glow.a = 0.28
	draw_arc(c, r, from, from + TAU * frac, 72, glow, WIDTH + 7.0, true)
	draw_arc(c, r, from, from + TAU * frac, 72, col, WIDTH, true)
