class_name EndScreen
extends Control
## The ending: who won, and the results table in the server's score order. A column is highlighted only if the model
## says so; being robbed is shown but never ranked or marked.


func _ready() -> void:
	Feed.model_changed.connect(func(kind, _m): if kind == "end": _build())
	_build()


func _build() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var col := Ui.page(self)
	var m: Dictionary = Feed.models.get("end", {})
	if m.is_empty():
		col.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	col.add_child(Ui.label(Words.render("ui.winners"), "", "HeaderLabel"))
	col.add_child(Ui.label(", ".join(m.winners), "winners", "BigLabel"))
	col.add_child(Ui.label(Words.render("ui.results"), "", "MutedLabel"))
	var grid := GridContainer.new()
	grid.columns = m.columns.size() + 2
	grid.set_meta("id", "results")
	grid.add_child(Ui.label("", ""))
	grid.add_child(Ui.label("", ""))
	for c in m.columns:
		grid.add_child(Ui.label(Words.render(c.key), "head_" + c.id, "MutedLabel"))
	var best := {}
	for c in m.columns:
		if c.highlight:
			var top := -1
			for r in m.rows:
				top = maxi(top, int(r.cells[c.id]))
			best[c.id] = top
	for r in m.rows:
		var who: String = r.alias
		if r.is_me:
			who += " " + Words.render("ui.you_mark")
		grid.add_child(Ui.label(who, "row_" + r.alias))
		var marks: Array = []
		if r.is_winner:
			marks.append(Words.render("ui.winner_mark"))
		if r.has_seat:
			marks.append(Words.render("ui.seat_mark"))
		marks.append(Words.render("ui.goal_met") if r.goal.done else Words.render("ui.goal_missed"))
		grid.add_child(Ui.label(", ".join(marks), "marks_" + r.alias, "MutedLabel"))
		for c in m.columns:
			var v: int = int(r.cells[c.id])
			var is_top: bool = c.highlight and best.get(c.id, -1) == v and v > 0
			grid.add_child(Ui.label(("[%d]" % v) if is_top else str(v), "cell_%s_%s" % [r.alias, c.id]))
	col.add_child(grid)
	col.add_child(Ui.button(Words.render("ui.back_to_title"), "back", func(): Intents.leave(), false, "PrimaryButton"))
