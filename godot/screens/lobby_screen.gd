class_name LobbyScreen
extends Control
## Room code, how many seats are taken (a lantern per seat, lit when taken), and Start for the host.

var _sig := ""
var _intro_played := false


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	_build()


## An identical push (the server re-sends the same view on every action) must not rebuild the screen under a finger.
func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "lobby":
		return
	if _sig_of(m) != _sig:
		_build()


func _sig_of(m: Dictionary) -> String:
	return JSON.stringify(m.get("lines", m)) + JSON.stringify(m.get("radio", [])) + str(m.get("is_host", "")) + str(m.get("seats_taken", ""))


func _build() -> void:
	_sig = _sig_of(Feed.models.get("lobby", {}))
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var menu := Ui.menu_column(Ui.page(self))
	var m: Dictionary = Feed.models.get("lobby", {})
	if m.is_empty():
		menu.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	var entries: Array = []
	var sign_card := Ui.card()
	var inner := Ui.vbox(10)
	sign_card.add_child(inner)
	var code := Ui.label(Words.render("ui.room_code", {"code": m.room_code}), "room_code", "BigLabel")
	code.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(code)
	var lit := Ui.lanterns(int(m.seats_total), int(m.seats_taken), "seat_lanterns")
	if lit != null:
		inner.add_child(lit)
	var seats := Ui.label(Words.render("ui.seats", {"taken": m.seats_taken, "total": m.seats_total}), "seats")
	seats.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(seats)
	menu.add_child(sign_card)
	entries.append(sign_card)
	if m.is_host:
		var start := Ui.button(Words.render("ui.start"), "start", func(): Intents.start(), false, "PrimaryButton")
		menu.add_child(start)
		entries.append(start)
	else:
		var wait := Ui.label(Words.render("ui.waiting_for_host"), "waiting", "MutedLabel")
		wait.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		menu.add_child(wait)
	var leave := Ui.button(Words.render("ui.leave"), "leave", func(): Intents.leave())
	menu.add_child(leave)
	entries.append(leave)
	if not _intro_played:
		_intro_played = true
		Ui.intro_all(entries)
