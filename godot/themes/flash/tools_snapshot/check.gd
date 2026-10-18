extends Node
## Checks the flash theme without touching the shared tests:
##   godot_console --headless --path godot res://themes/flash/tools_snapshot/check.tscn
## Registry, key set and {slot} set against the placeholder, an icon for every move / beat kind / band, the seven Stage
## colours, no emoji, every real server line renders with no hole, and a WCAG contrast table for the text pairs.

const A = preload("res://rulesets/survivors/adapter.gd")
const FlashTheme = preload("res://themes/flash/theme.gd")
const STAGE_COLOURS := ["text", "home", "home_me", "food", "loss", "shield", "marked"]
const VARIATIONS := {"HeaderLabel": "Label", "BigLabel": "Label", "MutedLabel": "Label", "PrimaryButton": "Button",
	"ChosenButton": "Button", "UrgentBar": "ProgressBar", "Card": "PanelContainer", "Banner": "PanelContainer"}

var problems: Array[String] = []


func _ready() -> void:
	_run()
	for p in problems:
		print("PROBLEM ", p)
	print("FLASH CHECK ", "PASS" if problems.is_empty() else "FAIL (%d)" % problems.size())
	get_tree().quit(0 if problems.is_empty() else 1)


func _run() -> void:
	if not ThemeRegistry.ids().has("flash"):
		problems.append("flash is not in the registry")
		return
	var t: ThemeDef = ThemeRegistry.make("flash")
	var ph: ThemeDef = ThemeRegistry.make("placeholder")
	if t.id != "flash":
		problems.append("id is " + t.id)
	_keys(t, ph)
	_icons(t)
	_look(t)
	_render(t)
	_contrast(t)


func _keys(t: ThemeDef, ph: ThemeDef) -> void:
	var a := t.words.get_message_list()
	var b := ph.words.get_message_list()
	var rx := RegEx.create_from_string("\\{(\\w+)\\}")
	for k in b:
		if not a.has(k):
			problems.append("missing key " + k)
			continue
		var s1 := _slots(rx, str(t.words.get_message(k)))
		var s2 := _slots(rx, str(ph.words.get_message(k)))
		if s1 != s2:
			problems.append("slots differ in %s: %s vs %s" % [k, s1, s2])
	for k in a:
		if not b.has(k):
			problems.append("extra key " + k)
		var txt := str(t.words.get_message(k))
		for i in txt.length():
			var c := txt.unicode_at(i)
			if not (c < 0x2000 or c == 0x2019):
				problems.append("non-text character U+%04X in %s" % [c, k])
				break
	print("keys: flash %d, placeholder %d" % [a.size(), b.size()])


func _slots(rx: RegEx, s: String) -> Array:
	var out := {}
	for m in rx.search_all(s):
		out[m.get_string(1)] = true
	var l := out.keys()
	l.sort()
	return l


func _icons(t: ThemeDef) -> void:
	var need: Array = []
	need.append_array(A.BEAT_KINDS)
	need.append_array(["scavenge", "guard", "steal", "investigate", "gift", "food", "shield", "bandit", "helicopter", "radio"])
	for b in A.BANDS:
		need.append("band." + b)
	for id in need:
		var tex: Texture2D = t.icons.get(id)
		if tex == null:
			problems.append("no icon for " + id)
		elif tex.get_width() < 32:
			problems.append("icon too small: " + id)
	print("icons: %d ids, need %d" % [t.icons.size(), need.size()])


func _look(t: ThemeDef) -> void:
	for c in STAGE_COLOURS:
		if not t.godot_theme.has_color(c, "Stage"):
			problems.append("Stage colour missing: " + c)
	for v in VARIATIONS:
		if t.godot_theme.get_type_variation_base(v) != VARIATIONS[v]:
			problems.append("variation %s is not based on %s" % [v, VARIATIONS[v]])
	for s in ["normal", "hover", "pressed", "disabled", "focus"]:
		if not t.godot_theme.has_stylebox(s, "Button") or not t.godot_theme.has_stylebox(s, "PrimaryButton"):
			problems.append("button style missing: " + s)
	for pair in [["background", "ProgressBar"], ["fill", "ProgressBar"], ["normal", "LineEdit"], ["focus", "LineEdit"],
			["panel", "ScrollContainer"], ["grabber", "VScrollBar"]]:
		if not t.godot_theme.has_stylebox(pair[0], pair[1]):
			problems.append("style missing: %s/%s" % pair)


func _render(t: ThemeDef) -> void:
	Words.use(t.words)
	var n := 0
	for r in Fixtures.of_type("reveal"):
		for part in ["news", "private"]:
			for l in r.msg[part]:
				var ln := A.line(l.code, l.args, part)
				var text := Words.render(ln.key, ln.slots)
				n += 1
				if text.begins_with("[") or "{" in text or "}" in text:
					problems.append("hole in rendered line: " + text)
	var radio := 0
	for r in Fixtures.of_type("round"):
		for ph in r.msg.get("radio_phrases", []):
			radio += 1
	print("rendered %d real lines, %d radio phrases seen" % [n, radio])


# WCAG 2.x relative luminance and contrast
func _lum(c: Color) -> float:
	var f := func(v: float) -> float: return v / 12.92 if v <= 0.03928 else pow((v + 0.055) / 1.055, 2.4)
	return 0.2126 * f.call(c.r) + 0.7152 * f.call(c.g) + 0.0722 * f.call(c.b)


func _ratio(a: Color, b: Color) -> float:
	var x := _lum(a)
	var y := _lum(b)
	return (maxf(x, y) + 0.05) / (minf(x, y) + 0.05)


func _contrast(_t: ThemeDef) -> void:
	var F = FlashTheme
	var pairs := [
		["body text on sky", F.PAPER, F.INK, 7.0],
		["body text on the glow (brightest backdrop)", F.PAPER, Color("5a322e"), 7.0],
		["muted text on sky", F.MUTED, F.INK, 7.0],
		["muted text on the glow", F.MUTED, Color("5a322e"), 4.5],
		["alias / room code (ember) on sky", F.EMBER_HI, F.INK, 7.0],
		["button label on raised", F.PAPER, F.RAISED, 7.0],
		["button label hovered", Color.WHITE, F.RAISED_HI, 7.0],
		["primary label on ember", F.ON_EMBER, F.EMBER, 7.0],
		["primary label on ember, hovered", F.ON_EMBER, F.EMBER_HI, 7.0],
		["primary label on ember, pressed", F.ON_EMBER, F.EMBER_LO, 7.0],
		["primary disabled label", Color("b4bdd0"), Color("2b3550"), 4.5],
		["secondary disabled label", F.DISABLED_TEXT, Color("141d33"), 3.0],
		["input text on well", F.PAPER, F.INK_DEEP, 7.0],
		["input placeholder on well", Color("8d9ab3"), F.INK_DEEP, 4.5],
		["timer fill on its track", F.EMBER, F.INK_DEEP, 3.0],
		["button edge on sky", F.EDGE, F.INK, 3.0],
		["Stage food on sky", Color("ffd56b"), F.INK, 3.0],
		["Stage loss on sky", Color("ff7466"), F.INK, 3.0],
		["Stage shield on sky", Color("6fdcf0"), F.INK, 3.0],
		["Stage marked on sky", Color("d9a8ff"), F.INK, 3.0],
		["Stage home on sky", Color("4f69a3"), F.INK, 3.0],
		["Stage me (ember) vs other homes", F.EMBER, Color("4f69a3"), 2.0],
	]
	for p in pairs:
		var r := _ratio(p[1], p[2])
		print("contrast %5.1f:1 (want %.1f)  %s" % [r, p[3], p[0]])
		if r < p[3]:
			problems.append("contrast %.1f < %.1f for %s" % [r, p[3], p[0]])
