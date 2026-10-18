class_name EndScreen
extends Control
## The ending: who won, a podium, and one card per player in the server's order. Everyone is on the podium exactly once:
## players level on a place stand together on one step, the first three places are steps, any further place is a line
## under the podium. A value in [ ] is the highest of its column (ties all bracketed, a column whose top is 0 none, and a
## column the model does not rank is never bracketed); a legend line says so. Names are one line each (trimmed with an
## ellipsis, never broken mid-word). Everything pictorial comes from the theme and is optional.

const WIDE_PX := 900
const PODIUM_ORDER := [1, 0, 2]            # the winner in the middle, second on the left, third on the right
const STEP_MIN_H := [118.0, 84.0, 60.0]    # chosen: heights of the first, second and third step
const SHARED_FACE := 48.0                  # chosen: a face on a step shared by several players
const SHARED_RATIO := 1.7                  # chosen: a shared step is a little wider than a lone one (its names are listed)
const HINT_SLACK := 6.0                    # px of scroll left below which the "more below" hint is hidden

var _intro_played := false
var _avatars := {}
var _wide := false
var _building := false
var _scroll: ScrollContainer
var _hint: Label
var _more_below := false


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
	_scroll = null
	_hint = null
	var m: Dictionary = Feed.models.get("end", {})
	if m.is_empty():
		var empty := Ui.page(self)
		empty.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	_avatars = Ui.avatar_ids(m.rows.map(func(r): return r.alias))
	var pg := Ui.page_docked(self)
	var col: VBoxContainer = pg.col
	_hint = Ui.label(Words.render("ui.scroll_more", {"n": m.rows.size()}), "scroll_hint", "MutedLabel")
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.visible = false
	pg.dock.add_child(_hint)
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
	_watch_scroll(col.get_parent() as ScrollContainer)
	if not _intro_played:
		_intro_played = true
		var steps: Array = []
		for step in podium.get_children():
			steps.push_front(step)               # the lowest step first: the winner arrives last
		Ui.intro_all([header] + steps, 0.0)


## Show the "more below" hint exactly while the list runs past the bottom of the view.
func _watch_scroll(sc: ScrollContainer) -> void:
	_scroll = sc
	if sc == null:
		return
	var bar := sc.get_v_scroll_bar()
	bar.changed.connect(_update_hint)
	bar.value_changed.connect(func(_v): _update_hint())
	sc.resized.connect(_update_hint)
	_update_hint.call_deferred()


func _update_hint() -> void:
	if _scroll == null or not is_instance_valid(_scroll) or _hint == null:
		return
	var bar := _scroll.get_v_scroll_bar()
	var left := bar.max_value - bar.page - bar.value
	_more_below = bar.page > 0.0 and left > HINT_SLACK
	_hint.visible = _more_below


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


## Rows grouped by place, best place first, the server's order kept inside a group and winners leading it:
## [{"place": 2, "rows": [row index, ...]}, ...]. Every row is in exactly one group.
func _groups(m: Dictionary, ranks: Array) -> Array:
	var places: Array = []
	for p in ranks:
		if not places.has(p):
			places.append(p)
	places.sort()
	var out: Array = []
	for p in places:
		var members: Array = []
		for i in m.rows.size():
			if ranks[i] == p and m.rows[i].is_winner:
				members.append(i)
		for i in m.rows.size():
			if ranks[i] == p and not m.rows[i].is_winner:
				members.append(i)
		out.append({"place": p, "rows": members})
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


## The first three places as steps (second, first, third from the left), each holding everyone level on it; places beyond
## the third come as lines under the steps. Every player is built once, with the id "podium_<name>".
func _podium(m: Dictionary, ranks: Array) -> VBoxContainer:
	var wrap := Ui.vbox(10)
	wrap.set_meta("id", "podium")
	var row := Ui.hbox(10)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	wrap.add_child(row)
	var groups := _groups(m, ranks)
	var on_steps := mini(3, groups.size())
	for slot in PODIUM_ORDER:
		if slot >= on_steps:
			continue
		row.add_child(_step(m, groups[slot], slot))
	for g in groups.slice(3):
		wrap.add_child(_place_line(m, g))
	return wrap


func _step(m: Dictionary, g: Dictionary, tier: int) -> Control:
	var members: Array = g.rows
	var shared := members.size() > 1
	var column := Ui.vbox(6)
	column.size_flags_vertical = Control.SIZE_SHRINK_END
	column.size_flags_stretch_ratio = SHARED_RATIO if shared else 1.0
	column.set_meta("id", "step_%d" % int(g.place))
	var people := Ui.vbox(8)
	column.add_child(people)
	for i in members:
		people.add_child(_standing(m.rows[i], tier, shared))
	var step := Ui.card("PlinthFirst" if tier == 0 else "Plinth")
	step.custom_minimum_size = Vector2(0, STEP_MIN_H[tier])
	var rank := Ui.label(Words.render("ui.rank", {"n": g.place}), "", "RankLabel")
	rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	step.add_child(rank)
	column.add_child(step)
	return column


## One player on a step: crown if a winner, face, name.
func _standing(r: Dictionary, tier: int, shared: bool) -> Control:
	var crown := Themes.texture("crown") if r.is_winner else null
	var face := Ui.avatar(r.alias, _avatars)
	if shared:
		# level players are listed one under another, face and name side by side, so a long name keeps its width
		var line := Ui.hbox(6)
		line.set_meta("id", "podium_" + r.alias)
		if face != null:
			line.add_child(Ui.picture(face, Vector2(SHARED_FACE, SHARED_FACE)))
		var name_col := Ui.vbox(0)
		if crown != null:
			var small := Ui.picture(crown, Vector2(30, 22))
			small.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
			name_col.add_child(small)
		name_col.add_child(Ui.name_label(r.alias, "", "NameLabel"))
		line.add_child(name_col)
		return line
	var one := Ui.vbox(4)
	one.set_meta("id", "podium_" + r.alias)
	if crown != null:
		one.add_child(Ui.picture(crown, Vector2(0, 40)))
	if face != null:
		one.add_child(Ui.picture(face, Vector2(0, 96.0 if tier == 0 else 76.0)))
	var who := Ui.name_label(r.alias, "", "NameLabel")
	who.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	one.add_child(who)
	return one


## A place past the third step: "#4  Name, Name".
func _place_line(m: Dictionary, g: Dictionary) -> Control:
	var line := Ui.hbox(10)
	line.set_meta("id", "place_%d" % int(g.place))
	var n := Ui.label(Words.render("ui.rank", {"n": g.place}), "", "HeaderLabel")
	n.custom_minimum_size = Vector2(54, 0)
	n.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	line.add_child(n)
	for i in g.rows:
		var who: Dictionary = m.rows[i]
		var holder := Ui.hbox(4)
		holder.set_meta("id", "podium_" + who.alias)
		holder.add_child(Ui.name_label(who.alias, "", "NameLabel"))
		line.add_child(holder)
	return line


## One card per player, in the server's order: place, face, name, marks, and the numbers.
func _board(m: Dictionary, ranks: Array) -> Control:
	var s := Ui.vbox(12)
	s.add_child(Ui.label(Words.render("ui.results"), "", "MutedLabel"))
	s.add_child(Ui.label(Words.render("ui.best_legend"), "legend", "MutedLabel"))
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
	info.add_child(Ui.name_label(r.alias, "row_" + r.alias, "NameLabel"))
	var marks: Array = []
	if r.is_me:
		marks.append(Words.render("ui.you_mark"))
	if r.is_winner:
		marks.append(Words.render("ui.winner_mark"))
	if r.has_seat:
		marks.append(Words.render("ui.seat_mark"))
	marks.append(Words.render("ui.goal_met") if r.goal.done else Words.render("ui.goal_missed"))
	info.add_child(Ui.name_label(", ".join(marks), "marks_" + r.alias, "MutedLabel"))
	top.add_child(info)
	if r.has_seat:
		var seat := Themes.icon("mark.seat")
		if seat != null:
			top.add_child(Ui.picture(seat, Vector2(40, 40)))
	s.add_child(top)
	# one equal-width cell per column, header over value, both centred and on one line, so the numbers line up
	var stats := HBoxContainer.new()
	stats.add_theme_constant_override("separation", 2)
	stats.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for c in m.columns:
		var v: int = int(r.cells[c.id])
		var is_top: bool = c.highlight and best.get(c.id, -1) == v and v > 0
		var cell := Ui.vbox(0)
		cell.size_flags_stretch_ratio = 1.0
		cell.custom_minimum_size = Vector2(1, 0)
		var head := Ui.name_label(Words.render(c.key), "head_" + c.id, "MutedLabel")
		head.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(head)
		var value := Ui.name_label(("[%d]" % v) if is_top else str(v), "cell_%s_%s" % [r.alias, c.id],
			"StatLabelHot" if is_top else "StatLabel")
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(value)
		stats.add_child(cell)
	s.add_child(stats)
	return card
