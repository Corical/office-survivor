extends "res://tests/snapshot/snapshot.gd"
## Motion and wide-window evidence run (windowed). Records the frames of every screen change at a fixed 30 fps and prints the
## difference between each pair of consecutive frames, so a cut shows up as one big number instead of an opinion; also takes the
## reveal in its "waiting for the others" state and the round and reveal screens at the wide sizes.
##   godot --path godot --fixed-fps 30 res://tests/snapshot/motion.tscn -- --out=<dir> [--tag=before|after]
## Frame difference: the mean absolute difference of the red, green and blue values (0..255) between two consecutive frames,
## measured on the picture shrunk four times.

var tag := "run"
var _csv := PackedStringArray()


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out_dir = a.substr(6)
		elif a.begins_with("--tag="):
			tag = a.substr(6)
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
	await _size(PHONE)
	await _wait(0.9)

	var base_round: Dictionary = _pick_round()
	var me: String = _name(base_round.me)
	var round_msg: Dictionary = _rename(base_round.msg)
	round_msg["board"] = _board(round_msg)
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})
	fake.server_send({"t": "rooms", "rooms": []})
	await _wait(0.5)

	# ---- 1. title -> lobby: the real Create tap, then the server's answer a few frames later
	var create_btn := Ui.find(router.current, "create") as Button
	await _record("create_tap_sheet", func(): create_btn.pressed.emit(), 12)
	await _wait(0.4)
	await _record("title_to_lobby", func():
		var go := Ui.find(router.current, "sheet_create") as Button
		if go != null:
			go.pressed.emit()
		await _frames(4)
		fake.server_send({"t": "seat", "token": "snap-token", "room_code": "KXQM", "alias": me, "host": true})
		fake.server_send({"t": "lobby", "room_code": "KXQM", "seats_taken": 3, "seats_total": 4, "host": true}), 54)
	await _wait(0.6)

	# ---- 2. lobby -> round
	await _record("lobby_to_round", func(): fake.server_send(round_msg), 40)
	await _wait(0.8)
	await _shot("%s_round_phone" % tag)

	# ---- 3. round -> reveal
	await _record("round_to_reveal", func(): fake.server_send(_night(round_msg, me)), 40)
	await _wait(0.4)

	# ---- 4. reveal at the sizes that matter: mid-animation, then everything played and waiting
	for s in [Vector2i(540, 960), Vector2i(700, 800), Vector2i(1904, 1001)]:
		await _size(s)
		await _wait(0.3)
		var tl: Timeline = Feed.player.timeline
		tl.finished = false
		tl.index = 2
		tl.elapsed_ms = 300.0
		await _wait(0.9)
		await _shot("%s_reveal_mid_%dx%d" % [tag, s.x, s.y])
		tl.snap_to_end()
		await _wait(0.5)
		await _shot("%s_reveal_waiting_a_%dx%d" % [tag, s.x, s.y])
		await _wait(1.3)
		await _shot("%s_reveal_waiting_b_%dx%d" % [tag, s.x, s.y])
		_audit("reveal waiting %dx%d" % [s.x, s.y])
	await _size(PHONE)

	# ---- 5. reveal -> end
	var end_row: Dictionary = Fixtures.of_type("end")[0]
	await _record("reveal_to_end", func(): fake.server_send(_rename(end_row.msg)), 40)
	await _wait(0.6)

	# ---- 6. wide round (the backdrop): fresh round view at three window sizes
	fake.server_send(round_msg)
	await _wait(0.8)
	for s in [Vector2i(540, 960), Vector2i(700, 800), Vector2i(1280, 720), Vector2i(1904, 1001), Vector2i(2560, 1440)]:
		await _size(s)
		await _wait(0.5)
		await _shot("%s_round_%dx%d" % [tag, s.x, s.y])
		_audit("round %dx%d" % [s.x, s.y])
	await _size(Vector2i(1904, 1001))
	await _wait(0.3)
	fake.server_send(_night(round_msg, me))
	await _wait(1.0)
	var tl2: Timeline = Feed.player.timeline
	tl2.snap_to_end()
	await _wait(0.5)
	await _shot("%s_reveal_end_1904x1001" % tag)

	var f := FileAccess.open(out_dir.path_join("%s_frame_diffs.csv" % tag), FileAccess.WRITE)
	f.store_string("\n".join(_csv))
	f.close()
	print("CLEARANCE TOTAL: %d violations in %d audits, %d distinct offenders" % [violations, audits, violation_paths.size()])
	print("MOTION DONE ", out_dir)
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


## Run `action`, grab `n` frames from that moment, save a contact sheet of them and print each pair's difference.
func _record(label: String, action: Callable, n: int) -> void:
	var imgs: Array[Image] = []
	imgs.append(await _grab())
	action.call()
	for i in n:
		imgs.append(await _grab())
	var diffs: Array[float] = []
	for i in range(1, imgs.size()):
		diffs.append(_diff(imgs[i - 1], imgs[i]))
	var peak := 0.0
	var peak_at := 0
	for i in diffs.size():
		if diffs[i] > peak:
			peak = diffs[i]
			peak_at = i + 1
	var line := "%s,%s,peak=%.1f,at_frame=%d,diffs=%s" % [tag, label, peak, peak_at, ";".join(diffs.map(func(d): return "%.1f" % d))]
	_csv.append(line)
	print("TRANSITION ", line)
	_sheet(label, imgs)


func _grab() -> Image:
	await RenderingServer.frame_post_draw
	return get_viewport().get_texture().get_image()


func _diff(a: Image, b: Image) -> float:
	var x := a.duplicate() as Image
	var y := b.duplicate() as Image
	x.resize(maxi(1, x.get_width() / 4), maxi(1, x.get_height() / 4), Image.INTERPOLATE_BILINEAR)
	y.resize(x.get_width(), x.get_height(), Image.INTERPOLATE_BILINEAR)
	x.convert(Image.FORMAT_RGB8)
	y.convert(Image.FORMAT_RGB8)
	var da := x.get_data()
	var db := y.get_data()
	var total := 0
	for i in da.size():
		total += absi(int(da[i]) - int(db[i]))
	return float(total) / float(da.size())


## A contact sheet: every second frame, shrunk, in rows of ten.
func _sheet(label: String, imgs: Array[Image]) -> void:
	var picks: Array[Image] = []
	for i in range(0, imgs.size(), 2):
		picks.append(imgs[i])
	var w := imgs[0].get_width() / 4
	var h := imgs[0].get_height() / 4
	var cols := 10
	var rows := ceili(float(picks.size()) / cols)
	var sheet := Image.create(w * cols, h * rows, false, Image.FORMAT_RGB8)
	for i in picks.size():
		var p := picks[i].duplicate() as Image
		p.resize(w, h, Image.INTERPOLATE_BILINEAR)
		p.convert(Image.FORMAT_RGB8)
		sheet.blit_rect(p, Rect2i(0, 0, w, h), Vector2i((i % cols) * w, (i / cols) * h))
	sheet.save_png(out_dir.path_join("%s_%s_frames.png" % [tag, label]))
