extends BaseTest
## The host's "Send away" on a seat that is HERE asks first. The question must be readable (it wrapped one letter per line and
## pushed its two buttons off the screen), both choices must be in view without scrolling, and the header must say plainly when a
## taken seat is away. A camp of four: the host, two seats that are here and one that dropped.

const SIZES := [Vector2(360, 640), Vector2(450, 800), Vector2(540, 960), Vector2(1904, 1001)]

var _mounted: Array = []


func setup() -> void:
	super.setup()
	Themes.use("flash")


func teardown() -> void:
	super.teardown()
	Themes.use("placeholder")
	for c in _mounted:
		if is_instance_valid(c):
			c.free()
	_mounted.clear()


func _seats() -> Array:
	return [{"id": "h-0", "connected": true}, {"id": "h-1", "connected": true}, {"id": "h-2", "connected": false}]


func _host_lobby(seats: Array, taken := 4) -> void:
	go_online()
	give_seat("tok", "ABCD", true)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": taken, "seats_total": 4, "host": true, "seats": seats})


func _mount(size: Vector2) -> Control:
	var holder := Control.new()
	holder.theme = Themes.current.godot_theme
	holder.size = size
	add_child(holder)
	var s: Control = LobbyScreen.new()
	holder.add_child(s)
	_mounted.append(holder)
	return holder


func _settle() -> void:
	for i in 4:
		await get_tree().process_frame


func _scroll_of(n: Node) -> ScrollContainer:
	return n.find_children("*", "ScrollContainer", true, false)[0] as ScrollContainer


func test_the_confirm_is_readable_and_in_view_at_every_size() -> void:
	for size in SIZES:
		setup()
		_host_lobby(_seats())
		var holder := _mount(size)
		await _settle()
		(Ui.find(holder, "kick_1") as Button).pressed.emit()          # a seat that is here
		await _settle()
		var ask := Ui.find(holder, "seat_confirm_1") as Label
		check(ask != null, "the question shows at %s" % size)
		if ask == null:
			continue
		check(ask.size.x >= 150.0 and ask.size.y < 70.0, "the question reads across the card, not a letter a line: %s at %s" % [ask.size, size])
		var view := _scroll_of(holder).get_global_rect()
		for id in ["kick_yes_1", "kick_no_1", "seat_confirm_1"]:
			var c := Ui.find(holder, id) as Control
			var r := c.get_global_rect()
			check(r.position.y >= view.position.y - 1.0 and r.end.y <= view.end.y + 1.0,
				"%s is fully in view without scrolling at %s: %s inside %s" % [id, size, r, view])
			if c is Button:
				check(r.size.y >= Ui.MIN_ART_BUTTON_HEIGHT, "%s keeps the wood minimum height at %s: %s" % [id, size, r.size.y])
		for v in NineFit.check(holder):
			check(false, "%s: %s" % [size, v])
		for v in Clearance.check(holder):
			check(false, "clearance %s: %s" % [size, v])
		(Ui.find(holder, "kick_no_1") as Button).pressed.emit()
		eq(fake.count("kick"), 0, "cancel sends nothing at %s" % size)


func test_the_confirm_buttons_sit_side_by_side_and_the_yes_sends_one_kick() -> void:
	_host_lobby(_seats())
	var holder := _mount(Vector2(450, 800))
	await _settle()
	(Ui.find(holder, "kick_2") as Button).pressed.emit()              # the second seat that is here
	await _settle()
	var yes := Ui.find(holder, "kick_yes_2") as Control
	var no := Ui.find(holder, "kick_no_2") as Control
	check(absf(yes.global_position.y - no.global_position.y) < 2.0, "on one line")
	check(yes.global_position.x < no.global_position.x, "yes then no")
	(Ui.find(holder, "kick_yes_2") as Button).pressed.emit()
	eq(fake.count("kick"), 1, "one kick")
	eq(fake.last("kick").get("seat"), "h-1", "for that seat")


func test_the_header_says_who_is_here_and_who_is_away() -> void:
	_host_lobby(_seats())                                              # host + 3 others, one of them dropped
	var holder := _mount(Vector2(450, 800))
	await _settle()
	var text := (Ui.find(holder, "seats") as Label).text
	eq(text, "3 at the fire, 1 out in the dark", "plain, in the theme's words")
	check(not ("4 of 4" in text), "no longer claims 4 of 4")
	var row := Ui.find(holder, "seat_lanterns")
	var lit := 0
	for c in row.get_children():
		if (c as TextureRect).texture == Themes.texture("lantern_on"):
			lit += 1
	eq(lit, 3, "three lanterns burn, the fourth is dim")


func test_with_nobody_away_the_header_is_the_old_one() -> void:
	_host_lobby([{"id": "h-0", "connected": true}, {"id": "h-1", "connected": true}, {"id": "h-2", "connected": true}])
	var holder := _mount(Vector2(450, 800))
	await _settle()
	eq((Ui.find(holder, "seats") as Label).text, "4 of 4 places by the fire", "unchanged when everyone is here")


func test_a_guest_keeps_the_old_header_whatever_the_server_sends() -> void:
	go_online()
	give_seat("tok", "ABCD", false)
	fake.server_send({"t": "lobby", "room_code": "ABCD", "seats_taken": 4, "seats_total": 4, "host": false,
		"seats": [{"id": "x-1", "connected": false}]})
	var holder := _mount(Vector2(450, 800))
	await _settle()
	eq((Ui.find(holder, "seats") as Label).text, "4 of 4 places by the fire", "a guest has no list and no away count")


func test_every_seat_dropped_and_a_bigger_away_count_than_taken_never_breaks_the_header() -> void:
	_host_lobby([{"id": "a", "connected": false}, {"id": "b", "connected": false}, {"id": "c", "connected": false}], 2)
	var holder := _mount(Vector2(450, 800))
	await _settle()
	var text := (Ui.find(holder, "seats") as Label).text
	check(text.begins_with("0 at the fire"), "never a negative count: " + text)
