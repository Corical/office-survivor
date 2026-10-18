extends Control
## Windowed screenshot run (not headless): the real router and screens, fed REAL harvested server views through the fake
## transport, saved as PNGs at phone (540x960) and desktop (1280x720) size. Reveal frames are taken MID-ANIMATION: a
## synthetic night holding every kind of beat is played and the clock is parked on each beat for a moment.
##   godot --path godot res://tests/snapshot/snapshot.tscn -- --out=<dir> --log=<file> [--theme=flash|placeholder]
## Aliases from the fixtures are renamed to realistic ones (one long, one short) so ellipsis and layout are judged fairly.

const NAMES := ["Mango", "SaltyPretzel", "Fig", "WobblyTable", "Kiwi", "Plum", "Juniper", "Marlowe"]
const PHONE := Vector2i(540, 960)
const DESKTOP := Vector2i(1280, 720)

var out_dir := ""
var theme_id := "flash"
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
var _names := {}                       # fixture alias -> the realistic one
var _rx := RegEx.create_from_string("Alias\\d+")


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
		elif a.begins_with("--theme="):
			theme_id = a.substr(8)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use(theme_id)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	await _size(PHONE)
	await _wait(0.9)
	await _shot("01_title")
	var settings := Ui.find(router.current, "settings_toggle") as Button
	if settings != null:
		settings.pressed.emit()
		await _wait(0.3)
		await _shot("01b_title_settings")
		(Ui.find(router.current, "settings_toggle") as Button).pressed.emit()      # the screen was rebuilt: find it again
	await _size(DESKTOP)
	await _shot("01c_title_desktop")
	await _size(PHONE)

	# one consistent night: a busy round view and the reveal that follows it, with the fixtures' aliases renamed
	var base_round: Dictionary = _pick_round()
	var me: String = _name(base_round.me)
	var round_msg: Dictionary = _rename(base_round.msg)
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})
	fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 3, "seats_total": 4, "host": true})
	await _wait(0.9)
	await _shot("02_lobby_host")

	round_msg["board"] = _board(round_msg)
	fake.server_send(round_msg)
	await _wait(1.0)
	await _shot("03_round_open")
	var rs: Control = router.current
	var steal := Ui.find(rs, "move_steal") as Button
	if steal != null:
		steal.pressed.emit()
		await _wait(0.5)
		await _shot("04_round_choosing_a_target")
		var tgt := Ui.find_all(rs, "target_")
		var pick_target: Variant = null
		if not tgt.is_empty():
			pick_target = (tgt[0] as Button).get_meta("id").substr(7)
			(tgt[0] as Button).pressed.emit()
		var v: Dictionary = round_msg.duplicate(true)
		v["my_pick"] = {"kind": "steal", "target": pick_target, "amount": 0}
		fake.server_send(v)
		await _wait(0.6)
		await _shot("05_round_picked")
		var urgent: Dictionary = v.duplicate(true)
		urgent["seconds_left"] = 7.0
		fake.server_send(urgent)
		await _wait(0.7)
		await _shot("05b_round_last_seconds")
		(Ui.find(router.current, "lock") as Button).pressed.emit()
		await _wait(0.4)
		await _shot("06_round_locking")
		var locked: Dictionary = urgent.duplicate(true)
		locked["my_locked"] = true
		locked["locked_count"] = 3
		fake.server_send(locked)
		await _wait(0.4)
		await _shot("06b_round_locked")
	fake.server_close(1006)
	await _wait(0.5)
	await _shot("07_round_reconnecting")
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})
	fake.server_send(round_msg)
	await _wait(0.5)
	await _size(DESKTOP)
	await _wait(0.5)
	await _shot("10_round_desktop")
	await _size(PHONE)

	# the reveal: a synthetic night with one of every beat, parked on each in turn
	fake.server_send(_night(round_msg, me))
	await _wait(0.9)
	await _shot("08_reveal_start")
	await _gallery("08", PHONE)
	await _size(DESKTOP)
	await _wait(0.6)
	await _gallery("11", DESKTOP, ["blocked", "move_resource"])
	await _size(PHONE)

	var end_row: Dictionary = Fixtures.of_type("end")[0]
	fake.server_send(_rename(end_row.msg))
	await _wait(1.6)
	await _shot("09_end")
	await _size(DESKTOP)
	await _wait(0.6)
	await _shot("12_end_desktop")
	print("SNAPSHOTS DONE ", out_dir)
	get_tree().quit(0)


# ---------------- the reveal gallery ----------------

## (name, beat kind, style or "" for any): the first beat of that kind at or after the current position.
const GALLERY := [
	["scavenge", "move_resource", "scavenge"], ["shield_on", "shield_on", ""], ["steal", "move_resource", "steal"],
	["blocked", "blocked", "guard"], ["empty", "empty", ""], ["learn", "learn", ""], ["marked", "marked", ""],
	["gift", "move_resource", "gift"], ["charm", "charm", ""], ["camp", "camp", ""], ["status", "status", "enter"],
	["total", "total", ""],
]


## Park the timeline on each beat in turn, wait a moment of REAL time so the effects have flown, and take a picture.
## `only` limits it to some beat kinds; a beat is photographed at a quarter and at half way.
func _gallery(prefix: String, _size_hint: Vector2i, only: Array = []) -> void:
	var tl: Timeline = Feed.player.timeline
	var beats: Array = Feed.models.reveal.beats
	var from := 0
	var n := 0
	for g in GALLERY:
		if not only.is_empty() and not (g[1] in only):
			continue
		var idx := -1
		for i in range(from, beats.size()):
			if beats[i].kind == g[1] and (g[2] == "" or beats[i].style == g[2]):
				idx = i
				break
		if idx < 0:
			print("gallery: no beat ", g)
			continue
		from = idx
		tl.finished = false
		tl.index = idx
		tl.elapsed_ms = 0.0
		var dwell := 0.2 if g[1] == "total" else 0.28
		await _wait(dwell)
		await _shot("%s_%02d_%s_a" % [prefix, n, g[0]])
		await _wait(dwell)
		await _shot("%s_%02d_%s_b" % [prefix, n, g[0]])
		n += 1
	# everything played: the written log lit at its last line
	tl.snap_to_end()
	await _wait(0.8)
	await _shot("%s_99_after" % prefix)


## A night that contains every kind of beat. `before` is the round view this follows (the Stage's before-state).
func _night(round_view: Dictionary, me: String) -> Dictionary:
	var others: Array = round_view.aliases.duplicate()
	others.sort()
	var x: String = others[0]
	var y: String = others[1] if others.size() > 1 else others[0]
	var z: String = others[2] if others.size() > 2 else others[0]
	var rations: int = int(round_view.me.rations)
	return {"t": "reveal", "round": int(round_view.round), "seconds_left": 40.0, "board": _board(round_view),
		"news": [
			{"code": "news_bandit", "args": {"player": x}},
			{"code": "news_hit_1", "args": {"victim": z, "total": 2}},
		],
		"private": [
			{"code": "scavenged", "args": {"found": 2}},
			{"code": "guard_up_1", "args": {"night": int(round_view.round)}},
			{"code": "stole", "args": {"target": y, "amount": 2}},
			{"code": "steal_caught", "args": {"target": z, "paid": 2}},
			{"code": "steal_empty", "args": {"target": x}},
			{"code": "watched", "args": {"target": x, "saw": "guard", "saw_target": y}},
			{"code": "exposed_by_me", "args": {"thief": y, "paid": 1}},
			{"code": "gave", "args": {"receiver": x, "amount": 1}},
			{"code": "idol_found", "args": {}},
			{"code": "event", "args": {"event": "feast", "line": "Feast night: everyone eats well", "scope": "camp"}},
			{"code": "became_bandit_me", "args": {}},
			{"code": "now_have", "args": {"rations": rations + 3}},
		],
		"radio": [{"phrase": "trust", "about": x}]}


func _board(round_view: Dictionary) -> Array:
	var bands := ["well_fed", "starving", "getting_by", "bandit"]
	var out: Array = []
	var all: Array = round_view.aliases.duplicate()
	all.append(round_view.me.alias)
	all.sort()
	for i in all.size():
		out.append({"alias": all[i], "band": bands[i % bands.size()]})
	return out


# ---------------- helpers ----------------

func _name(alias: String) -> String:
	if not _names.has(alias):
		_names[alias] = NAMES[_names.size() % NAMES.size()]
	return _names[alias]


## The same message with every fixture alias replaced by its realistic name.
func _rename(msg: Dictionary) -> Dictionary:
	var text := JSON.stringify(msg)
	var found: Array = []
	for m in _rx.search_all(text):
		if not (m.get_string() in found):
			found.append(m.get_string())
	found.sort()
	for a in found:
		_name(a)
	for a in found:
		text = text.replace('"%s"' % a, '"%s"' % _names[a])
	var parsed: Variant = SafeJson.parse(text)
	return Net.normalize(parsed)


func _size(s: Vector2i) -> void:
	get_window().size = s
	await _wait(0.5)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


## What the scene tree says about itself right now: sizes and a sample of text, so a blank picture can be explained.
func _describe() -> String:
	var cur: Control = router.current
	if cur == null:
		return "no current screen"
	var texts: Array = Ui.texts(cur)
	return "router=%s screen=%s size=%s visible=%s texts=%d first=%s" % [router.size, cur.name, cur.size, cur.visible,
		texts.size(), str(texts.slice(0, 2))]


func _shot(shot_name: String) -> void:
	print("tree ", shot_name, ": ", _describe())
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := out_dir.path_join(shot_name + ".png")
	var err := img.save_png(path)
	print("shot ", shot_name, " ", img.get_size(), " err=", err)


## A real round view that has a board (bands shown) and offers a steal and a gift, so the screen has something to show.
func _pick_round() -> Dictionary:
	for r in Fixtures.of_type("round"):
		if r.msg.legal.has("steal") and r.msg.legal.has("gift") and r.msg.aliases.size() >= 3 and r.msg.round >= 3:
			return r
	return Fixtures.of_type("round")[0]
