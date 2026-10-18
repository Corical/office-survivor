class_name FitLabel
extends Label
## A name (or any short text) that must be readable in full at phone size. It keeps its theme look and, when the text is wider
## than the room it has, tries in this order:
##   1. a smaller font, down to `min_scale` of the theme's size (a 12-letter name at 450 px wide is only a little too wide);
##   2. two lines, broken anywhere (only for a name that is far too long even at the smallest size);
##   3. an ellipsis, as the very last resort (a name longer than two full lines).
## The text never changes; only how it is set does. It measures its own room, so it refits when its container resizes.

var min_scale := 0.6
var _settings: LabelSettings
var _fitting := false
var _base_size := 0


func _ready() -> void:
	clip_text = true                                    # min width 0: a long name must not widen its container
	text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	autowrap_mode = TextServer.AUTOWRAP_OFF
	resized.connect(_fit)
	_fit()


## Set the words and fit them at once.
func set_fit_text(t: String) -> void:
	text = t
	_fit()


## The theme variation changed (a different font size or colour): read it afresh and fit again.
func restyle() -> void:
	_settings = null
	label_settings = null
	_fit()


func _fit() -> void:
	if _fitting or not is_inside_tree() or size.x < 8.0:
		return
	_fitting = true
	var font := get_theme_font("font")
	if _settings == null:
		_settings = LabelSettings.new()
		_base_size = get_theme_font_size("font_size")
		_settings.font = font
		_settings.font_color = get_theme_color("font_color")
		_settings.outline_size = get_theme_constant("outline_size")
		_settings.outline_color = get_theme_color("font_outline_color")
		_settings.shadow_color = get_theme_color("font_shadow_color")
		_settings.shadow_offset = Vector2(float(get_theme_constant("shadow_offset_x")), float(get_theme_constant("shadow_offset_y")))
		_settings.line_spacing = float(get_theme_constant("line_spacing"))
		label_settings = _settings
	var room := size.x - float(_settings.outline_size)
	var smallest := maxi(10, int(floorf(float(_base_size) * min_scale)))
	var s := _base_size
	while s > smallest and font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x > room:
		s -= 1
	_settings.font_size = s
	var fits := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x <= room
	if fits:
		autowrap_mode = TextServer.AUTOWRAP_OFF
		max_lines_visible = -1
	else:
		autowrap_mode = TextServer.AUTOWRAP_ARBITRARY       # a name too long even when small: two lines, then an ellipsis
		max_lines_visible = 2
	_fitting = false


## What it is showing right now, for tests: {size, lines, trimmed}.
func describe() -> Dictionary:
	var font := get_theme_font("font")
	var s := _settings.font_size if _settings != null else get_theme_font_size("font_size")
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x
	var room := size.x - (float(_settings.outline_size) if _settings != null else 0.0)
	var lines := 1 if autowrap_mode == TextServer.AUTOWRAP_OFF else clampi(int(ceilf(w / maxf(room, 1.0))), 1, 2)
	return {"size": s, "base": _base_size, "lines": lines, "trimmed": w > room * 2.0 or (lines == 1 and w > room)}
