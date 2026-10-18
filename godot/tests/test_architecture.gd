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


# ---------------- shared screens versus game screens (docs/SCREENS.md is the table) ----------------

const SCREENS_DOC := "res://docs/SCREENS.md"
## Game nouns a shared screen must not use. (The ids of the adapter's moves and bands are added from the adapter itself.)
const GAME_NOUNS := ["ration", "bandit", "guard", "scavenge", "steal", "gift", "investigate", "idol", "survivor", "helicopter",
	"outcast", "camp"]
## A shared script that still holds a game word: path -> {word: [most occurrences allowed, why, the step that removes it]}.
## A count may fall, never rise; a word not listed here fails. Never widen this to make a test pass: fix the script, or
## write the reason and the step here and in docs/SCREENS.md.
const ALLOWED := {
	"res://screens/title_screen.gd": {"camp": [7, "the create sheet's camp-name field, its keys, the theme's glow texture", "3.5"]},
	"res://screens/open_camps.gd": {"camp": [15, "the open-rooms list: node ids, ui.camp_* keys, the CampCard variation", "3.5"]},
	"res://stage/backdrop.gd": {"camp": [1, "the theme's campfire_glow texture name", "3.5"]},
}


## {path: owner} from the table in docs/SCREENS.md: rows whose first cell is a backticked path.
func _owners() -> Dictionary:
	var out := {}
	for line in FileAccess.get_file_as_string(SCREENS_DOC).split("\n"):
		var cells := line.split("|")
		if cells.size() < 4:
			continue
		var path := cells[1].strip_edges().trim_prefix("`").trim_suffix("`")
		if path.ends_with(".gd") and not out.has("res://" + path):
			out["res://" + path] = cells[2].strip_edges()
	return out


func _scripts_of(owner: String) -> Array[String]:
	var out: Array[String] = []
	var o := _owners()
	for p in o:
		if o[p] == owner:
			out.append(p)
	return out


func _count_word(code: String, w: String) -> int:
	return RegEx.create_from_string("(^|[^a-z0-9])" + w).search_all(code).size()


## What a script says about a word that is a game's: the nouns, the adapter's move and band ids, and its other ids as quoted literals.
func _shared_violations(code_in: String, path: String) -> Array[String]:
	var code := code_in.to_lower()
	var out: Array[String] = []
	var words: Array = GAME_NOUNS.duplicate()
	words.append_array(A.MOVES)
	words.append_array(A.BANDS)
	var allowed: Dictionary = ALLOWED.get(path, {})
	for w in words:
		var n := _count_word(code, str(w))
		var ceiling: int = allowed.get(w, [0])[0]
		if n > ceiling:
			out.append("%s: '%s' x%d (allowed %d)" % [path, w, n, ceiling])
	for id in A.RADIO + A.EVENT_CAMP + A.EVENT_FIND.keys() + A.EVENT_LOSE.keys():
		if ('"%s"' % id) in code:
			out.append("%s: names the Survivors id \"%s\"" % [path, id])
	for k in A.all_keys():
		if ('"%s"' % k) in code:
			out.append("%s: names the Survivors translation key \"%s\"" % [path, k])
	return out


## Another game's ruleset, adapter, directory or id inside a game's own script. `games` are the ids on the registry.
func _foreign_refs(code: String, own: String, games: Array) -> Array[String]:
	var out: Array[String] = []
	for g in games:
		if g == own:
			continue
		var camel: String = str(g).capitalize().replace(" ", "")
		for needle in ["rulesets/%s/" % g, "games/%s/" % g, camel + "Ruleset", camel + "Adapter"]:
			if needle in code:
				out.append("references the game '%s' (%s)" % [g, needle])
	return out


func test_every_screen_and_stage_script_has_an_owner_in_the_table() -> void:
	var o := _owners()
	check(o.size() >= 10, "the table in docs/SCREENS.md was read (%d rows)" % o.size())
	for path in _guarded():
		check(o.has(path), "%s has no row in docs/SCREENS.md: decide whether it is shared or a game's" % path)
	for path in o:
		check(FileAccess.file_exists(path), "docs/SCREENS.md lists %s, which does not exist" % path)
		check(o[path] == "shared" or RulesetRegistry.has(o[path]), "%s: owner '%s' is neither 'shared' nor a registered game" % [path, o[path]])


func test_a_shared_screen_contains_no_game_word_beyond_its_recorded_exceptions() -> void:
	var shared := _scripts_of("shared")
	check(shared.size() >= 8, "there are shared scripts to look at (%d)" % shared.size())
	for path in shared:
		for v in _shared_violations(_code(path), path):
			check(false, v)


func test_every_recorded_exception_is_still_needed_and_names_its_removal_step() -> void:
	var shared := _scripts_of("shared")
	for path in ALLOWED:
		check(path in shared, "%s is in ALLOWED but is not a shared script" % path)
		var code := _code(path).to_lower()
		for w in ALLOWED[path]:
			var e: Array = ALLOWED[path][w]
			check(_count_word(code, w) > 0, "%s no longer uses '%s': delete its ALLOWED entry" % [path, w])
			eq(_count_word(code, w), e[0], "%s: '%s' is used this many times; set the ceiling to it (it may fall, never rise)" % [path, w])
			check(str(e[1]) != "" and str(e[2]) != "", "%s '%s' needs a reason and a removing step" % [path, w])


func test_a_game_screen_references_no_other_games_ruleset_or_words() -> void:
	var games: Array = RulesetRegistry.RULESETS.keys()
	for g in games:
		for path in _scripts_of(g):
			for r in _foreign_refs(_code(path), g, games):
				check(false, "%s %s" % [path, r])


# ---- the checkers themselves must bite (a rule that cannot fail guards nothing) ----

func test_the_shared_check_catches_a_planted_game_word() -> void:
	for planted in ["var x = 'ration'", "Words.render('ui.bandit_hint')", "var m = \"scavenge\"", "if a == 'Guard':", "var y := \"saw\"",
			"var k := \"move.steal\"", "# only a comment is stripped by _code, so this is code: gifts"]:
		check(not _shared_violations(planted, "res://screens/title_screen.gd").is_empty(), "missed: %s" % planted)
	check(_shared_violations("var duration := 3  # nothing here", "res://screens/ui.gd").is_empty(), "'duration' is not 'ration'")
	check(_shared_violations("var t := 'campaign'", "res://screens/ui.gd").size() == 1, "a word start counts, as the older test does")
	# an exception is a ceiling: one more than recorded fails
	var many := "camp ".repeat(11)
	check(not _shared_violations(many, "res://screens/title_screen.gd").is_empty(), "past the ceiling fails")
	check(_shared_violations("camp ".repeat(3), "res://screens/title_screen.gd").is_empty(), "within the ceiling passes")
	check(not _shared_violations("steal", "res://screens/title_screen.gd").is_empty(), "an exception for 'camp' does not cover 'steal'")


func test_the_foreign_check_catches_another_games_ruleset() -> void:
	var games := ["survivors", "bang"]
	check(not _foreign_refs("var r = BangRuleset.new()", "survivors", games).is_empty(), "a ruleset class")
	check(not _foreign_refs("preload('res://rulesets/bang/adapter.gd')", "survivors", games).is_empty(), "a path")
	check(not _foreign_refs("var a = BangAdapter", "survivors", games).is_empty(), "an adapter")
	check(_foreign_refs("var r = SurvivorsRuleset.new()", "survivors", games).is_empty(), "its own is its own")
	check(not _foreign_refs("SurvivorsAdapter.MOVES", "bang", games).is_empty(), "the other way round")


func test_ruleset_code_does_not_depend_on_screens_or_theme_files() -> void:
	for path in _scripts("res://rulesets"):
		var code := _code(path)
		check(not ("res://screens" in code or "res://stage" in code or "res://themes" in code),
			"%s depends on a layer above it" % path)
