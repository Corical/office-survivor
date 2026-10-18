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
var _wide := false
var _building := false


func _ready() -> void:
	Feed.model_changed.connect(func(kind, _m): if kind == "end": _build())
	resized.connect(_on_resized)
	_build()


## The window grew past (or shrank below) the width where the board sits beside the podium: lay it out again.
func _on_resized() -> void:
	if not _building and (size.x >= WIDE_PX) != _wide:
		_build()


func _build() -> void:
	_building = true
	_wide = size.x >= WIDE_PX
	_build_screen()
	_building = false


func _build_screen() -> void:
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
	if _wide:
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


## The places, grouped: everyone level on a place is ONE group (a three-way tie for second is one group of three), groups
## in order of place. Public so a test can check that however the ties fall, every player is in exactly one group.
## Each group is {"place": int, "members": [row index, ...]} with members in the server's order.
func place_groups(m: Dictionary, ranks: Array) -> Array:
	var by_place := {}
	var places: Array = []
	for i in m.rows.size():
		var p: int = ranks[i]
		if not by_place.has(p):
			by_place[p] = []
			places.append(p)
		by_place[p].append(i)
	places.sort()
	return places.map(func(p): return {"place": p, "members": by_place[p]})


## The podium: one step for each of the first three PLACES (not three players), so a tie never drops anyone and never shows a
## place twice. Whoever stands level on a step stands on that step together; a lone player is shown large, a group as a short
## list of faces and names. Anyone beyond the third place is in the ordered list below, once.
func _podium(m: Dictionary, ranks: Array) -> HBoxContainer:
	var row := Ui.hbox(10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.set_meta("id", "podium")
	var groups := place_groups(m, ranks).slice(0, 3)
	for tier in PODIUM_ORDER:
		if tier >= groups.size():
			continue
		var g: Dictionary = groups[tier]
		var members: Array = g.members
		var column := Ui.vbox(6)
		column.size_flags_vertical = Control.SIZE_SHRINK_END
		column.size_flags_stretch_ratio = 1.0 + 0.7 * float(members.size() - 1)
		column.set_meta("id", "podium_place_%d" % g.place)
		if members.size() == 1:
			var r: Dictionary = m.rows[members[0]]
			column.set_meta("id", "podium_" + r.alias)
			if r.is_winner:
				var crown := Themes.texture("crown")
				if crown != null:
					column.add_child(Ui.picture(crown, Vector2(0, 40)))
			var face := Ui.avatar(r.alias, _avatars)
			if face != null:
				column.add_child(Ui.picture(face, Vector2(0, 96 if tier == 0 else 76)))
			var who := Ui.name_label(r.alias, "podium_name_" + r.alias, "NameLabel")
			who.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			column.add_child(who)
		else:
			for i in members:
				column.add_child(_podium_member(m.rows[i]))
		var step := Ui.card("PlinthFirst" if tier == 0 else "Plinth")
		step.custom_minimum_size = Vector2(0, STEP_MIN_H[tier])
		var rank := Ui.label(Words.render("ui.rank", {"n": g.place}), "", "RankLabel")
		rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		step.add_child(rank)
		column.add_child(step)
		row.add_child(column)
	return row


## One of several people on the same step: a small face, the name (fitted), a small crown if they won.
func _podium_member(r: Dictionary) -> Control:
	var line := Ui.hbox(8)
	line.set_meta("id", "podium_" + r.alias)
	var face := Ui.avatar(r.alias, _avatars)
	if face != null:
		line.add_child(Ui.picture(face, Vector2(44, 44)))
	line.add_child(Ui.name_label(r.alias, "podium_name_" + r.alias, "NameLabel"))
	if r.is_winner:
		var crown := Themes.texture("crown")
		if crown != null:
			var c := Ui.picture(crown, Vector2(28, 22))
			c.size_flags_horizontal = Control.SIZE_SHRINK_END
			line.add_child(c)
	return line


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
	var info := Ui.vbox(0)
	var who_row := Ui.hbox(6)                             # the name (fitted), then "(you)" beside it: neither can cut the other
	who_row.add_child(Ui.name_label(r.alias, "row_" + r.alias, "NameLabel"))
	if r.is_me:
		var me := Ui.label(Words.render("ui.you_mark"), "you_" + r.alias, "MutedLabel")
		me.autowrap_mode = TextServer.AUTOWRAP_OFF
		me.size_flags_horizontal = Control.SIZE_SHRINK_END
		who_row.add_child(me)
	info.add_child(who_row)
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
