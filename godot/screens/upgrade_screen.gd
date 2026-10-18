class_name UpgradeScreen
extends Control
## This app cannot go on: the server needs a newer app (the protocol), or the room plays a game this app does not have. It says
## so. For a room it cannot play there is also a way out (leave it), because the seat is held.


func _ready() -> void:
	var col := Ui.menu_column(Ui.page(self))
	var app_name := Ui.label(Words.render("ui.app_name"), "app_name", "BigLabel")
	app_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(app_name)
	var title := Ui.label(Words.render("notice.upgrade_required"), "upgrade", "HeaderLabel")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(title)
	var room_game: bool = Feed.status().get("unsupported_game", "") != ""
	var body := Ui.label(Words.render("ui.update_game_body" if room_game else "ui.update_body"), "upgrade_body", "MutedLabel")
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(body)
	if room_game:
		col.add_child(Ui.button(Words.render("ui.leave_game"), "leave_game", func(): Intents.leave()))
