extends RefCounted
## The placeholder theme: plain words and shapes, no art. The default and the test theme. It owns every size and colour;
## screens only name a type variation ("HeaderLabel", "BigLabel", "MutedLabel", "PrimaryButton") and the Stage asks for
## its colours by name from the "Stage" type.

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
	for e in {"text": Color(0.94, 0.94, 0.94), "home": Color(0.30, 0.34, 0.40), "home_me": Color(0.35, 0.50, 0.70),
			"food": Color(0.95, 0.78, 0.30), "loss": Color(0.90, 0.35, 0.30), "shield": Color(0.45, 0.80, 0.90),
			"marked": Color(0.95, 0.60, 0.25)}.keys():
		th.set_color(e, "Stage", {"text": Color(0.94, 0.94, 0.94), "home": Color(0.30, 0.34, 0.40),
			"home_me": Color(0.35, 0.50, 0.70), "food": Color(0.95, 0.78, 0.30), "loss": Color(0.90, 0.35, 0.30),
			"shield": Color(0.45, 0.80, 0.90), "marked": Color(0.95, 0.60, 0.25)}[e])
	return t
