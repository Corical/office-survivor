class_name ScrollHint
extends Control
## "There is more below": a soft fade at the bottom edge of a scrolling page and a small chevron, shown only while there is
## content below the view. It replaces the scrollbar (which is hidden so it can never take width and re-lay the page out when
## it appears). It lets every tap through. Colours come from the theme by name.

const FADE_H := 56.0
const BAND := 10

var _scroll: ScrollContainer
var _more := false
var _t := 0.0


func setup(scroll: ScrollContainer) -> void:
	_scroll = scroll
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func _process(delta: float) -> void:
	if _scroll == null or not is_instance_valid(_scroll):
		return
	var bar := _scroll.get_v_scroll_bar()
	var more := bar.max_value - bar.page - bar.value > 8.0
	if more != _more:
		_more = more
		queue_redraw()
	if _more and not Themes.reduced_motion:
		_t += delta
		queue_redraw()


## True while a page has content below what is showing (for tests).
func shows_more() -> bool:
	return _more


func _draw() -> void:
	if not _more:
		return
	var band_h := FADE_H / float(BAND)
	for i in BAND:
		var k := float(i + 1) / float(BAND)
		draw_rect(Rect2(0.0, size.y - FADE_H + float(i) * band_h, size.x, band_h + 1.0), Themes.color_a("ink", 0.72 * k * k))
	var bob := 0.0 if Themes.reduced_motion else sin(_t * 3.2) * 2.5
	var c := Vector2(size.x * 0.5, size.y - 16.0 + bob)
	var col := Themes.color_a("gold", 0.95)
	draw_polyline(PackedVector2Array([c + Vector2(-11, -6), c + Vector2(0, 5), c + Vector2(11, -6)]), col, 4.0, true)
