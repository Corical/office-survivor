class_name EndScreen
extends Control
## The ending: who won, a podium for the top places, and one card per player in the server's order. A column is
## highlighted only if the model says so; being robbed is shown but never ranked or marked. Names are one line each
## (trimmed with an ellipsis, never broken mid-word). Everything pictorial comes from the theme and is optional.

const WIDE_PX := 900
const PODIUM_ORDER := [1, 0, 2]            # the winner in the middle, second on the left, third on the right
const STEP_MIN_H := [118.0, 84.0, 60.0]    # chosen: heights of the first, second and third step

var _intro_played := false
var _avatars := {}


func _ready() -> void:
	Feed.model_changed.connect(func(kind, _m): if kind == "end": _build())
	_build()


func _build() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var m: Dictionary = Feed.models.get("end", {})
	if m.is_empty():
		var empty := Ui.page(self)
		empty.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	_avatars = Ui.avatar_ids(m.rows.map(func(r): return r.alias))
	var pg := Ui.page_docked(self)
	var col: VBoxContainer = pg.col
	pg.dock.add_child(Ui.button(Words.render("ui.back_to_title"), "back", func(): Intents.leave(), false, "PrimaryButton"))
	var ranks := _ranks(m)
	var header := _header(m)
	var podium := _podium(m, ranks)
	var board := _board(m, ranks)
	if size.x >= WIDE_PX:
		var cols := HBoxContainer.new()
		cols.add_theme_constant_override("separation", 32)
		cols.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var left := Ui.vbox(16)
		left.add_child(header)
		left.add_child(podium)
		cols.add_child(left)
		cols.add_child(board)
		col.add_child(cols)
	else:
		col.add_child(header)
		col.add_child(podium)
		col.add_child(board)
	if not _intro_played:
		_intro_played = true
		var steps: Array = []
		for step in podium.get_children():
			steps.push_front(step)               # the lowest step first: the winner arrives last
		Ui.intro_all([header] + steps, 0.0)


## Each row's place: one more than the number of rows ahead of it on the first ranked column (rows level on it share a
## place). With no ranked column the server's order is the place.
func _ranks(m: Dictionary) -> Array:
	var key := ""
	for c in m.columns:
		if c.highlight:
			key = c.id
			break
	var out: Array = []
	for i in m.rows.size():
		if key == "":
			out.append(i + 1)
			continue
		var ahead := 0
		for r in m.rows:
			if int(r.cells[key]) > int(m.rows[i].cells[key]):
				ahead += 1
		out.append(ahead + 1)
	return out


func _header(m: Dictionary) -> Control:
	var card := Ui.card()
	var s := Ui.vbox(6)
	card.add_child(s)
	var title := Ui.label(Words.render("ui.winners"), "", "HeaderLabel")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	s.add_child(title)
	var crown := Themes.texture("crown")
	if crown != null:
		var pic := Ui.picture(crown, Vector2(0, 56), "winner_crown")
		s.add_child(pic)
	var names := Ui.label(", ".join(m.winners), "winners", "BigLabel")
	names.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	s.add_child(names)
	return card


## The top places as steps: face above, name, then the step with its number.
func _podium(m: Dictionary, ranks: Array) -> HBoxContainer:
	var row := Ui.hbox(10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.set_meta("id", "podium")
	var shown := mini(3, m.rows.size())
	var by_place: Array = []                        # winners take the top steps; the server's order decides within each group
	for i in m.rows.size():
		if m.rows[i].is_winner:
			by_place.append(i)
	for i in m.rows.size():
		if not m.rows[i].is_winner:
			by_place.append(i)
	for slot in PODIUM_ORDER:
		if slot >= shown:
			continue
		var r: Dictionary = m.rows[by_place[slot]]
		var column := Ui.vbox(6)
		column.size_flags_vertical = Control.SIZE_SHRINK_END
		column.set_meta("id", "podium_" + r.alias)
		if r.is_winner:
			var crown := Themes.texture("crown")
			if crown != null:
				column.add_child(Ui.picture(crown, Vector2(0, 40)))
		var place: int = int(ranks[by_place[slot]])          # steps are built from the place, so rows level on points stand level
		var tier := clampi(place - 1, 0, 2)
		var face := Ui.avatar(r.alias, _avatars)
		if face != null:
			column.add_child(Ui.picture(face, Vector2(0, 96 if tier == 0 else 76)))
		var who := Ui.name_label(r.alias, "", "NameLabel")
		who.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		column.add_child(who)
		var step := Ui.card("PlinthFirst" if tier == 0 else "Plinth")
		step.custom_minimum_size = Vector2(0, STEP_MIN_H[tier])
		var rank := Ui.label(Words.render("ui.rank", {"n": ranks[by_place[slot]]}), "", "RankLabel")
		rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		step.add_child(rank)
		column.add_child(step)
		row.add_child(column)
	return row


## One card per player, in the server's order: place, face, name, marks, and the numbers.
func _board(m: Dictionary, ranks: Array) -> Control:
	var s := Ui.vbox(12)
	s.add_child(Ui.label(Words.render("ui.results"), "", "MutedLabel"))
	var holder := Ui.vbox(10)
	holder.set_meta("id", "results")
	s.add_child(holder)
	var best := {}
	for c in m.columns:
		if c.highlight:
			var top := -1
			for r in m.rows:
				top = maxi(top, int(r.cells[c.id]))
			best[c.id] = top
	for i in m.rows.size():
		holder.add_child(_player_card(m, m.rows[i], ranks[i], best))
	return s


func _player_card(m: Dictionary, r: Dictionary, rank: int, best: Dictionary) -> Control:
	var card := Ui.card("CardHot" if r.is_winner else "Card")
	var s := Ui.vbox(8)
	card.add_child(s)
	var top := Ui.hbox(10)
	var place := Ui.label(Words.render("ui.rank", {"n": rank}), "", "HeaderLabel")
	place.custom_minimum_size = Vector2(54, 0)
	place.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	top.add_child(place)
	var face := Ui.avatar(r.alias, _avatars)
	if face != null:
		top.add_child(Ui.picture(face, Vector2(56, 56)))
	var who: String = r.alias
	if r.is_me:
		who += " " + Words.render("ui.you_mark")
	var info := Ui.vbox(0)
	info.add_child(Ui.name_label(who, "row_" + r.alias, "NameLabel"))
	var marks: Array = []
	if r.is_winner:
		marks.append(Words.render("ui.winner_mark"))
	if r.has_seat:
		marks.append(Words.render("ui.seat_mark"))
	marks.append(Words.render("ui.goal_met") if r.goal.done else Words.render("ui.goal_missed"))
	info.add_child(Ui.label(", ".join(marks), "marks_" + r.alias, "MutedLabel"))
	top.add_child(info)
	if r.is_winner:
		var crown := Themes.texture("crown")
		if crown != null:
			top.add_child(Ui.picture(crown, Vector2(48, 36)))
	if r.has_seat:
		var seat := Themes.icon("mark.seat")
		if seat != null:
			top.add_child(Ui.picture(seat, Vector2(40, 40)))
	s.add_child(top)
	var stats := Ui.hbox(6)
	for c in m.columns:
		var v: int = int(r.cells[c.id])
		var is_top: bool = c.highlight and best.get(c.id, -1) == v and v > 0
		var cell := Ui.vbox(0)
		var head := Ui.label(Words.render(c.key), "head_" + c.id, "MutedLabel")
		head.custom_minimum_size = Vector2(0, 42)           # room for two lines in every column, so the numbers line up
		head.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
		cell.add_child(head)
		var value := Ui.name_label(("[%d]" % v) if is_top else str(v), "cell_%s_%s" % [r.alias, c.id], "StatLabel")
		cell.add_child(value)
		stats.add_child(cell)
	s.add_child(stats)
	return card
