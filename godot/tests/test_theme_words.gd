extends BaseTest
## Words and theme completeness: every key the adapter can emit exists in the theme, nothing renders with a hole in it,
## and nothing stale lingers in the theme.

const A = preload("res://rulesets/survivors/adapter.gd")
const PO := "res://themes/placeholder/words.po"


func setup() -> void:
	super.setup()
	A.forget_unknowns()
	Words.use(load(PO))


func test_the_theme_loads() -> void:
	check(Words.translation != null, "words.po loaded as a Translation")
	check(Words.keys().size() > 80, "keys present: %d" % Words.keys().size())


func _needed() -> Array[String]:
	var out: Array[String] = []
	out.append_array(A.all_keys())
	out.append_array(UiKeys.ALL)
	return out


func test_completeness_every_key_a_ruleset_or_screen_can_ask_for_is_in_the_theme() -> void:
	var missing: Array[String] = []
	for k in _needed():
		if not Words.has(k):
			missing.append(k)
	eq(missing, [], "theme is missing keys")


func test_no_stale_keys_left_in_the_theme() -> void:
	var allowed := {}
	for k in _needed():
		allowed[k] = true
	var stale: Array[String] = []
	for k in Words.keys():
		if not allowed.has(k) and k != "":
			stale.append(k)
	eq(stale, [], "theme has keys nothing can emit")


func test_every_real_line_renders_without_holes() -> void:
	var n := 0
	for r in Fixtures.of_type("reveal"):
		for part in ["news", "private"]:
			for l in r.msg[part]:
				var ln := A.line(l.code, l.args, part)
				var text := Words.render(ln.key, ln.slots)
				n += 1
				check(not text.begins_with("["), "missing key rendered: " + text)
				check(not ("{" in text or "}" in text), "unfilled slot in: " + text)
				check(text.length() > 3, "empty text for " + l.code)
	check(n > 100, "enough lines rendered: %d" % n)


func test_placeholder_theme_has_no_emoji() -> void:
	for k in Words.keys():
		var t := str(Words.translation.get_message(k))
		for i in t.length():
			var c := t.unicode_at(i)
			if not (c < 0x2000 or c == 0x2019):
				failures.append("non-text character U+%04X at %d in %s: %s" % [c, i, k, t])
				break


func test_list_slots_join_the_english_way() -> void:
	eq(Words.join_list([3]), "3", "one")
	eq(Words.join_list([3, 4]), "3 and 4", "two")
	eq(Words.join_list([3, 4, 5]), "3, 4 and 5", "three")
	eq(Words.join_list([]), "", "none")
	var ln := A.line("guard_up_n", {"nights": [3, 4, 5]})
	eq(Words.render(ln.key, ln.slots), "You're on guard for nights 3, 4 and 5.", "through a real line")


func test_move_slots_are_translated_words() -> void:
	var ln := A.line("watched_target", {"target": "Bo", "saw": "steal", "saw_target": "Cy"})
	eq(Words.render(ln.key, ln.slots), "You watched Bo: they chose steal (Cy).", "move word from the theme")


func test_a_missing_key_is_visible_and_logged_once() -> void:
	eq(Words.render("line.does_not_exist"), "[line.does_not_exist]", "visible hole")
	Words.render("line.does_not_exist")
	eq(Log.since(mark, "WARN").filter(func(l): return "does_not_exist" in l).size(), 1, "logged once")


func test_slot_values_that_look_like_templates_do_not_inject() -> void:
	var ln := A.line("stole", {"target": "{amount}", "amount": 2})
	var text := Words.render(ln.key, ln.slots)
	check("{amount}" in text or text.count("2") <= 2, "an alias cannot rewrite the template: " + text)
	eq(text, "You stole 2 from {amount}.", "alias text is shown literally")


func test_swapping_the_translation_changes_the_words_without_touching_the_adapter() -> void:
	var t := Translation.new()
	t.locale = "en"
	for k in _needed():
		t.add_message(k, "<%s>" % k)
	Words.use(t)
	var ln := A.line("stole", {"target": "Bo", "amount": 2})
	eq(Words.render(ln.key, ln.slots), "<line.stole>", "a different theme owns the words")
	var missing := _needed().filter(func(k): return not Words.has(k))
	eq(missing, [], "a generated theme is complete too")
