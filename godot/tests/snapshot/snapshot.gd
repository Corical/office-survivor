extends Control
## Windowed screenshot run (not headless): the real router and screens, fed REAL harvested server views through the fake
## transport, saved as PNGs at phone (540x960) and desktop (1280x720) size. Reveal frames are taken MID-ANIMATION: a
## synthetic night holding every kind of beat is played and the clock is parked on each beat for a moment.
##   godot --path godot res://tests/snapshot/snapshot.tscn -- --out=<dir> --log=<file> [--theme=flash|placeholder]
## Aliases from the fixtures are renamed to realistic ones (one long, one short) so ellipsis and layout are judged fairly.

var NAMES := ["Mango", "SaltyPretzel", "Fig", "WobblyTable", "Kiwi", "Plum", "Juniper", "Marlowe"]
const LONG_NAMES := ["Bartholomew_Jr_III", "SaltyPretzelSupreme", "Wolfgang Amadeus", "WobblyTableLegsXL", "Kiwi", "Plum",
	"Juniper", "Marlowe"]
const PHONE := Vector2i(540, 960)
const DESKTOP := Vector2i(1280, 720)
const WIDE_SIZES := [Vector2i(1280, 720), Vector2i(1843, 925), Vector2i(2560, 1440)]    # the owner's window, and a big monitor

var out_dir := ""
var theme_id := "flash"
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control
const AUDIT_SIZES := [Vector2i(540, 960), Vector2i(700, 800), Vector2i(1280, 720), Vector2i(1843, 925)]
var audits := 0
var violations := 0
var violation_paths := {}              # distinct offenders, so a repeat at another size is not counted twice
var _names := {}                       # fixture alias -> the realistic one
var _rx := RegEx.create_from_string("Alias\\d+")


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
		elif a.begins_with("--theme="):
			theme_id = a.substr(8)
		elif a == "--long":
			NAMES = LONG_NAMES                        # the longest names a player can have: layout must hold
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
	await _audit_sizes("title")
	var settings := Ui.find(router.current, "settings_toggle") as Button
	if settings != null:
		settings.pressed.emit()
		await _wait(0.3)
		await _shot("01b_title_settings")
		(Ui.find(router.current, "settings_toggle") as Button).pressed.emit()      # the screen was rebuilt: find it again
	await _size(DESKTOP)
	await _shot("01c_title_desktop")
	await _size(PHONE)
	# the connection banner in its two looks: still trying (calm), and given up (alert)
	var overlay: Overlay = null
	for c in router.get_children():
		if c is Overlay:
			overlay = c
	if overlay != null:
		overlay._on_status({"net": "connecting", "net_key": "ui.net.connecting", "terminal": ""})
		await _wait(0.5)
		await _shot("01d_banner_connecting")
		overlay._on_status({"net": "unreachable", "net_key": "ui.net.unreachable", "terminal": ""})
		await _wait(0.5)
		await _shot("01e_banner_unreachable")
		overlay._on_status({"net": "online", "net_key": "ui.net.online", "terminal": ""})

	# the open-camps list in each state, and the new-camp sheet (the title asked for the list when it was built)
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	await _wait(0.3)
	fake.server_send({"t": "rooms", "rooms": []})
	await _wait(0.5)
	await _shot("01f_camps_empty")
	await _audit_sizes("camps empty")
	fake.server_send({"t": "rooms", "rooms": [{"code": "KXQM", "seats_taken": 2, "seats_total": 4, "age_s": 190, "name": "Friday night"}]})
	await _wait(0.5)
	await _shot("01g_camps_one")
	var eight: Array = []
	var camp_names := ["Friday night", "", "Fig's camp", "Bartholomew's Extremely Long Camp Name", "", "Quiet corner", "Newcomers welcome", ""]
	var ages := [5, 95, 400, 2400, 3700, 9000, 40000, 100000]
	for i in 8:
		eight.append({"code": "C%03d" % (i + 1), "seats_taken": 1 + i % 3, "seats_total": 4, "age_s": ages[i], "name": camp_names[i]})
	fake.server_send({"t": "rooms", "rooms": eight})
	await _wait(0.5)
	await _shot("01h_camps_eight")
	for s in [Vector2i(700, 800), Vector2i(1843, 925)]:
		await _size(s)
		await _wait(0.4)
		await _shot("01h_camps_eight_%dx%d" % [s.x, s.y])
	await _size(PHONE)
	await _audit_sizes("camps eight")
	var create_btn := Ui.find(router.current, "create") as Button
	if create_btn != null:
		create_btn.pressed.emit()
		await _wait(0.5)
		await _shot("01i_camp_sheet")
		await _size(Vector2i(1843, 925))
		await _wait(0.4)
		await _shot("01i_camp_sheet_1843x925")
		await _size(PHONE)
		await _audit_sizes("camp sheet")
		var priv := Ui.find(router.current, "vis_private") as Button
		if priv != null:
			priv.pressed.emit()
			var field := Ui.find(router.current, "camp_name") as LineEdit
			if field != null:
				field.text = "Bartholomew's Extremely Long Camp"
				field.text_changed.emit(field.text)
			await _wait(0.3)
			await _shot("01j_camp_sheet_private")
		var cancel := Ui.find(router.current, "sheet_cancel") as Button
		if cancel != null:
			cancel.pressed.emit()
			await _wait(0.3)

	# one consistent night: a busy round view and the reveal that follows it, with the fixtures' aliases renamed
	var base_round: Dictionary = _pick_round()
	var me: String = _name(base_round.me)
	var round_msg: Dictionary = _rename(base_round.msg)
	if NAMES == LONG_NAMES:
		round_msg.me.rations = 128                       # a three-digit food number: the plate must grow to hold it
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})
	fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 3, "seats_total": 4, "host": true})
	await _wait(0.9)
	await _shot("02_lobby_host")
	await _audit_sizes("lobby")

	round_msg["board"] = _board(round_msg)
	fake.server_send(round_msg)
	await _wait(1.0)
	await _shot("03_round_open")
	await _audit_sizes("round open")
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
		await _audit_sizes("round picked")
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
		await _audit_sizes("round locked")
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
	var pick_btn := Ui.find_all(router.current, "target_")
	if not pick_btn.is_empty():                                   # a selected target card on a wide window
		var steal_btn := Ui.find(router.current, "move_steal") as Button
		if steal_btn != null:
			steal_btn.pressed.emit()
			await _wait(0.4)
			var first := Ui.find_all(router.current, "target_")
			if not first.is_empty():
				var chosen_view: Dictionary = round_msg.duplicate(true)
				chosen_view["my_pick"] = {"kind": "steal", "target": (first[0] as Button).get_meta("id").substr(7), "amount": 0}
				fake.server_send(chosen_view)
				await _wait(0.5)
	await _size(Vector2i(1843, 925))
	await _wait(0.5)
	await _shot("10_round_1843x925")
	await _size(PHONE)

	# the reveal: a synthetic night with one of every beat, parked on each in turn
	fake.server_send(_night(round_msg, me))
	await _wait(0.9)
	await _shot("08_reveal_start")
	await _audit_sizes("reveal start")
	await _gallery("08", PHONE)
	await _size(Vector2i(700, 800))                     # audit every beat again in a narrow window and in the owner's
	await _gallery("a700", PHONE, [], false)
	await _size(Vector2i(1843, 925))
	await _gallery("a1843", PHONE, [], false)
	await _size(PHONE)
	await _size(DESKTOP)
	await _wait(0.6)
	await _gallery("11", DESKTOP, ["blocked", "move_resource"])
	await _size(PHONE)

	var end_row: Dictionary = Fixtures.of_type("end")[0]
	fake.server_send(_rename(end_row.msg))
	await _wait(1.6)
	await _shot("09_end")
	await _audit_sizes("end")
	for s in WIDE_SIZES:
		await _size(s)
		await _wait(0.6)
		await _shot("12_end_%dx%d" % [s.x, s.y])
	print("CLEARANCE TOTAL: %d violations in %d audits, %d distinct offenders" % [violations, audits, violation_paths.size()])
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
func _gallery(prefix: String, _size_hint: Vector2i, only: Array = [], shots := true) -> void:
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
		# five moments of the beat: the check sees numbers early in their rise and late, and two beats' numbers together
		var where := "beat %s @%s" % [g[0], str(get_window().size)]
		await _wait(dwell * 0.5)
		_audit(where + " t1")
		await _wait(dwell * 0.5)
		if shots:
			await _shot("%s_%02d_%s_a" % [prefix, n, g[0]])
		_audit(where + " t2")
		await _wait(dwell * 0.5)
		_audit(where + " t3")
		await _wait(dwell * 0.5)
		if shots:
			await _shot("%s_%02d_%s_b" % [prefix, n, g[0]])
		_audit(where + " t4")
		await _wait(dwell * 0.6)
		_audit(where + " t5")
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


## Run the clearance check on whatever is on screen now: nothing may sit on a frame. Every offender is printed with its path.
func _audit(tag: String) -> void:
	audits += 1
	var found := Clearance.check(router)
	for v in found:
		violations += 1
		violation_paths[v.get_slice(":", 0) + v.get_slice(":", 1).substr(0, 40)] = true
		print("CLEARANCE ", tag, ": ", v)
	print("CLEARANCE ", tag, " violations=", found.size())


## The same check at the four window sizes that matter (phone, a narrow window, a desktop, the owner's), then back.
func _audit_sizes(tag: String) -> void:
	var back := get_window().size
	for s in AUDIT_SIZES:
		await _size(s)
		await _wait(0.3)
		_audit("%s @%dx%d" % [tag, s.x, s.y])
	await _size(back)


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
