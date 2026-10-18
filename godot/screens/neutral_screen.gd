class_name NeutralScreen
extends Control
## The server sent a phase this app has no picture for. The game goes on without us: say so, name the game if the server did, and
## offer the way out. It knows no game; the name comes from the server's list.


func _ready() -> void:
	var col := Ui.menu_column(Ui.page(self))
	var game := Feed.room_game()
	if not game.is_empty():
		var name_label := Ui.name_label(str(game.name), "game_name", "MutedLabel")
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		col.add_child(name_label)
	var dots := Ui.hbox(8)
	dots.alignment = BoxContainer.ALIGNMENT_CENTER
	dots.set_meta("id", "neutral_mark")
	for i in 3:
		dots.add_child(PulseDot.new())
	col.add_child(dots)
	var title := Ui.label(Words.render("ui.neutral_title"), "neutral_title", "HeaderLabel")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(title)
	var body := Ui.label(Words.render("ui.neutral_body"), "neutral_body", "MutedLabel")
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(body)
	col.add_child(Ui.button(Words.render("ui.leave_game"), "leave_game", func(): Intents.leave()))
