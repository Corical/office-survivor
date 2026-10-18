extends BaseTest
## Every change of screen is a cross-fade, never a swap in one frame: for every ordered pair of screens, under every theme,
## the old screen is still there (and nearly opaque) and the new one has only begun to appear one frame after the change.

const SCREENS := ["title", "lobby", "round", "reveal", "end", "upgrade"]
var _routers: Array = []


func teardown() -> void:
	super.teardown()
	for r in _routers:
		if is_instance_valid(r):
			r.free()
	_routers.clear()
	Themes.use("flash")
	Themes.reduced_motion = false


func _router(first: String) -> Control:
	var r: Control = (load("res://main.tscn") as PackedScene).instantiate()
	r.screen_factory = func(n: String) -> Control:
		var c := Control.new()
		c.name = n
		return c
	_routers.append(r)
	add_child(r)
	r._route({"screen": first})
	return r


func _check_every_pair(theme: String, calm: bool) -> void:
	Themes.use(theme)
	Themes.reduced_motion = calm
	for a in SCREENS:
		for b in SCREENS:
			if a == b:
				continue
			var r := _router(a)
			var old: Control = r.current
			var tag := "%s -> %s (%s%s)" % [a, b, theme, ", calm" if calm else ""]
			r._route({"screen": b})
			var now: Control = r.current
			check(old != now, "%s: a new screen was made" % tag)
			check(is_instance_valid(old) and old.is_inside_tree(), "%s: the old screen is not removed in the same frame" % tag)
			check(now.is_inside_tree(), "%s: the new screen is in" % tag)
			check(now.modulate.a < 0.05, "%s: the new screen starts invisible, not at full strength: %s" % [tag, now.modulate.a])
			await get_tree().process_frame
			check(is_instance_valid(old) and old.is_inside_tree(), "%s: the old screen is still there a frame later" % tag)
			check(old.modulate.a > 0.5, "%s: the old screen has not vanished in one frame: %s" % [tag, old.modulate.a])
			check(now.modulate.a < 0.5, "%s: the new screen has not appeared in one frame: %s" % [tag, now.modulate.a])
			r.free()
			_routers.erase(r)


func test_no_pair_of_screens_swaps_in_one_frame_flash() -> void:
	await _check_every_pair("flash", false)


func test_no_pair_of_screens_swaps_in_one_frame_placeholder_theme() -> void:
	await _check_every_pair("placeholder", false)


func test_no_pair_of_screens_swaps_in_one_frame_in_calm_mode() -> void:
	await _check_every_pair("flash", true)


func test_a_fast_chain_of_changes_leaves_exactly_one_screen_and_leaks_none() -> void:
	var r := _router("title")
	for n in ["lobby", "round", "reveal", "round", "end", "title"]:
		r._route({"screen": n})
		await get_tree().process_frame
	check(r._slot.get_child_count() >= 2, "several are mid-fade")
	await get_tree().create_timer(0.9).timeout
	eq(r._slot.get_child_count(), 1, "after the fades only the current screen is left")
	eq(r.current_name, "title", "and it is the last one asked for")
	eq(r.current.modulate.a, 1.0, "fully visible")


func test_a_very_long_frame_right_after_the_change_does_not_eat_the_fade() -> void:
	# building the round screen takes a long time: the next frame's delta can be half a second (stranger pass 2, N6)
	for hitch in [0.15, 0.5, 2.0, 30.0]:
		var r := _router("lobby")
		var old: Control = r.current
		r._route({"screen": "round"})
		r._process(hitch)
		check(is_instance_valid(old) and old.is_inside_tree(), "a %s s frame: the old screen is still in" % hitch)
		check(old.modulate.a > 0.8, "a %s s frame: the old screen has barely started to fade (%s)" % [hitch, old.modulate.a])
		check(r.current.modulate.a < 0.2, "a %s s frame: the new screen has barely started to appear (%s)" % [hitch, r.current.modulate.a])
		var frames := 0
		while not r._fades.is_empty() and frames < 200:
			r._process(hitch)
			frames += 1
		check(frames >= 8, "a %s s hitch: the change still takes at least 8 frames (took %d)" % [hitch, frames])
		r.free()
		_routers.erase(r)


func test_the_old_screen_cannot_be_tapped_while_it_fades() -> void:
	var r := _router("title")
	var old: Control = r.current
	var b := Button.new()
	old.add_child(b)
	r._route({"screen": "lobby"})
	eq(b.mouse_filter, Control.MOUSE_FILTER_IGNORE, "its button ignores the mouse")
