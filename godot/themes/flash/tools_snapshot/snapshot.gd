extends Control
## Windowed screenshot run (not headless): the real router and screens, fed REAL harvested server views through the fake
## transport, saved as PNGs at phone and desktop size. The first time anything is drawn.
##   godot --path godot res://tests/snapshot/snapshot.tscn -- --out=<dir> --log=<file>

var out_dir := ""
var fake := FakeTransport.new()
var clock := FakeClock.new()
var router: Control


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out_dir)
	await get_tree().process_frame
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Session.reset(MemorySessionStore.new(), clock)
	Session.server_url = "ws://test"
	Feed.reset()
	Themes.use("flash")
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	await _frames()
	get_window().size = Vector2i(450, 800)
	await _frames()
	await _shot("01_title")

	var round_row := _pick_round()
	var me: String = round_row.me
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	Session.act("create_room")
	fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})
	fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 2, "seats_total": 4, "host": true})
	await _frames()
	await _shot("02_lobby_host")

	fake.server_send(round_row.msg)
	await _frames()
	await _shot("03_round_open")

	var rs: Control = router.current
	var steal := Ui.find(rs, "move_steal") as Button
	if steal != null:
		steal.pressed.emit()
		await _frames()
		await _shot("04_round_choosing_a_target")
		var tgt := Ui.find_all(rs, "target_")
		if not tgt.is_empty():
			(tgt[0] as Button).pressed.emit()
	var v: Dictionary = round_row.msg.duplicate(true)
	v["my_pick"] = {"kind": "steal", "target": (Ui.find_all(rs, "target_")[0] as Button).text if not Ui.find_all(rs, "target_").is_empty() else null, "amount": 0}
	fake.server_send(v)
	await _frames()
	await _shot("05_round_picked")
	(Ui.find(router.current, "lock") as Button).pressed.emit()
	await _frames()
	await _shot("06_round_locking")
	var radio_btn := Ui.find(router.current, "radio_toggle") as Button
	if radio_btn != null:
		radio_btn.pressed.emit()
		await _frames()
		await _shot("06b_radio_open")

	fake.server_close(1006)
	await _frames()
	await _shot("07_round_reconnecting")
	clock.advance(1100)
	Net.tick()
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})

	var reveal_row := _pick_reveal()
	fake.server_send(round_row.msg)
	fake.server_send(reveal_row.msg)
	await _frames()
	await _shot("08_reveal")
	for step in 4:
		await get_tree().create_timer(1.1).timeout
		await _shot("08%s_reveal_t%d" % ["bcde"[step], step + 1])

	var end_row: Dictionary = Fixtures.of_type("end")[0]
	fake.server_send(end_row.msg)
	await _frames()
	await _shot("09_end")

	# the same round and reveal at desktop width
	get_window().size = Vector2i(1280, 720)
	fake.server_send(round_row.msg)
	await _frames()
	await _shot("10_round_desktop")
	print("SNAPSHOTS DONE ", out_dir)
	get_tree().quit(0)


func _frames() -> void:
	for i in 4:
		await get_tree().process_frame


## What the scene tree says about itself right now: sizes and a sample of text, so a blank picture can be explained.
func _describe() -> String:
	var cur: Control = router.current
	if cur == null:
		return "no current screen"
	var texts: Array = Ui.texts(cur)
	return "router=%s screen=%s size=%s visible=%s texts=%d first=%s" % [router.size, cur.name, cur.size, cur.visible,
		texts.size(), str(texts.slice(0, 2))]


func _shot(name: String) -> void:
	print("tree ", name, ": ", _describe())
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := out_dir.path_join(name + ".png")
	var err := img.save_png(path)
	print("shot ", name, " ", img.get_size(), " err=", err)


## A real round view that has a board (bands shown) and offers a steal, so the screen has something to show.
func _pick_round() -> Dictionary:
	for r in Fixtures.of_type("round"):
		if r.msg.board != null and r.msg.legal.has("steal") and r.msg.legal.has("gift") and r.msg.round >= 3:
			return r
	return Fixtures.of_type("round")[0]


## The reveal with the most lines: the busiest night.
func _pick_reveal() -> Dictionary:
	var best: Dictionary = Fixtures.of_type("reveal")[0]
	for r in Fixtures.of_type("reveal"):
		if r.msg.news.size() + r.msg.private.size() > best.msg.news.size() + best.msg.private.size():
			best = r
	return best
