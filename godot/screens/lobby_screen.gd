class_name LobbyScreen
extends Control
## Room code, how many seats are taken, and Start for the host.


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	_build()


var _sig := ""


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
	var col := Ui.page(self)
	var m: Dictionary = Feed.models.get("lobby", {})
	if m.is_empty():
		col.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	col.add_child(Ui.label(Words.render("ui.room_code", {"code": m.room_code}), "room_code", "BigLabel"))
	col.add_child(Ui.label(Words.render("ui.seats", {"taken": m.seats_taken, "total": m.seats_total}), "seats"))
	if m.is_host:
		col.add_child(Ui.button(Words.render("ui.start"), "start", func(): Intents.start(), false, "PrimaryButton"))
	else:
		col.add_child(Ui.label(Words.render("ui.waiting_for_host"), "waiting", "MutedLabel"))
	col.add_child(Ui.button(Words.render("ui.leave"), "leave", func(): Intents.leave()))
