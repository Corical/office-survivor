extends BaseTest
## The layer split is a rule the tests enforce, not a hope: screens and the stage consume neutral models and
## translation keys only. Nothing under screens/ or stage/ may know the Survivors protocol, the theme's words, a
## colour or an asset path.

const A = preload("res://rulesets/survivors/adapter.gd")
const GUARDED_DIRS := ["res://screens", "res://stage"]
## Survivors contract fields and game words: if one appears in a screen, a ruleset detail has leaked upward.
## (`seconds_left` and `locked_count` are deliberately NOT listed: the neutral models reuse those two names.)
const CONTRACT_FIELDS := ["gift_amounts", "times_robbed", "gave_away", "guards_left", "goal_progress", "radio_phrases",
	"my_locked", "legal"]
const GAME_WORDS := ["ration", "bandit", "helicopter", "scavenge", "steal", "investigate", "gift", "guard", "idol",
	"survivor"]
## Literals that make a screen own its look.
const LOOK_LITERALS := ["Color(", "Color8(", "Color.", "res://themes/", "res://assets", ".ttf", ".png", ".svg", ".tres",
	"Theme.new", "StyleBoxFlat", "add_theme_color", "add_theme_font"]
## Screens talk to the world through Feed (models), Intents (taps), Words (text) and Themes (icons). These are the
## doors they must not use: Session / Net hold the raw view, the rulesets and the registries know the game.
const FORBIDDEN_DOORS := ["Session.", "Net.", "SurvivorsAdapter", "SurvivorsRuleset", "RulesetRegistry",
	"ThemeRegistry", "rulesets/", "res://core/", "SessionStore", "Transport"]


func _scripts(dir: String) -> Array[String]:
	var out: Array[String] = []
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.ends_with(".gd"):
			out.append(dir.path_join(f))
	for sub in d.get_directories():
		out.append_array(_scripts(dir.path_join(sub)))
	return out


## Source with comments and string-free lines only matter for code; strip full-line and trailing comments.
func _code(path: String) -> String:
	var kept: Array[String] = []
	for line in FileAccess.get_file_as_string(path).split("\n"):
		var s := line.strip_edges()
		if s.begins_with("#"):
			continue
		var i := line.find(" #")
		kept.append(line if i < 0 else line.substr(0, i))
	return "\n".join(kept)


func _guarded() -> Array[String]:
	var all: Array[String] = []
	for d in GUARDED_DIRS:
		all.append_array(_scripts(d))
	return all


func test_the_guard_actually_sees_files() -> void:
	check(_guarded().size() >= 2, "the guarded directories contain scripts (otherwise this test guards nothing)")


func test_no_screen_or_stage_script_knows_the_protocol_or_the_games_words() -> void:
	var codes := A.line_codes()
	for path in _guarded():
		var code := _code(path).to_lower()
		for w in CONTRACT_FIELDS + GAME_WORDS:
			# word-START boundary: catches "rations" and "ration_count", not "duration"
			var rx := RegEx.create_from_string("(^|[^a-z0-9])" + w)
			check(rx.search(code) == null, "%s mentions '%s'" % [path, w])
		for c in codes:
			check(not ('"%s"' % c in code), "%s names the server line code '%s'" % [path, c])


func test_no_screen_or_stage_script_owns_a_colour_font_or_asset_path() -> void:
	for path in _guarded():
		var code := _code(path)
		for lit in LOOK_LITERALS:
			check(not (lit in code), "%s contains '%s': looks belong to the theme" % [path, lit])


func test_no_screen_or_stage_script_uses_a_door_it_must_not() -> void:
	for path in _guarded():
		var code := _code(path)
		for d in FORBIDDEN_DOORS:
			check(not (d in code), "%s uses '%s': go through Feed / Intents / Words / Themes" % [path, d])


func test_ruleset_code_does_not_depend_on_screens_or_theme_files() -> void:
	for path in _scripts("res://rulesets"):
		var code := _code(path)
		check(not ("res://screens" in code or "res://stage" in code or "res://themes" in code),
			"%s depends on a layer above it" % path)
