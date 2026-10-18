extends RefCounted
## The placeholder theme: plain words and shapes, no art. The default and the test theme. It owns every size and colour;
## screens only name a type variation ("HeaderLabel", "BigLabel", "MutedLabel", "PrimaryButton").

static func build() -> ThemeDef:
	var t := ThemeDef.new()
	t.id = "placeholder"
	t.title = "Plain"
	t.words = load("res://themes/placeholder/words.po")
	var th := t.godot_theme
	th.default_font_size = 18
	for pair in [["HeaderLabel", 26], ["BigLabel", 44], ["MutedLabel", 14]]:
		th.set_type_variation(pair[0], "Label")
		th.set_font_size("font_size", pair[0], pair[1])
	th.set_color("font_color", "MutedLabel", Color(0.6, 0.65, 0.72))
	th.set_type_variation("PrimaryButton", "Button")
	th.set_font_size("font_size", "PrimaryButton", 22)
	return t
