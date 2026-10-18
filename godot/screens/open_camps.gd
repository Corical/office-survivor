class_name OpenCamps
extends VBoxContainer
## The "Open camps" section of the title screen: one card per camp that is waiting for players (its name or code, how many
## seats are taken as lit and unlit lanterns, how long ago it opened); tap a card to join that camp. It reads the Feed's
## "rooms" model only. The section shows nothing at all until the server has shown it can list camps (and a quiet header
## while it is finding out), says "no open camps" when there are none, and dims the last list when the connection drops.
##
## The rows are DIFFED, never rebuilt: a refresh every three seconds changes a row's words in place and adds or removes only
## the rows that came or went, so nothing under a finger moves when nothing changed.
##
## Who asks the server for the list is the title screen (Intents.rooms_watch); this only shows what arrives.

const CARD_MIN_H := 76.0
const GAME_TAG_H := 24.0                   # chosen: one more line of the muted size, when the card names its game
const LANTERN_ROOM := 150.0

var _header: HBoxContainer
var _dot: PulseDot
var _list: VBoxContainer
var _empty: Label
var _rows := {}                       # code -> {button, title, sub, lanterns, total}
var _shown_once := false


func _ready() -> void:
	set_meta("id", "open_camps")
	add_theme_constant_override("separation", 8)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mouse_filter = Control.MOUSE_FILTER_PASS
	_header = Ui.hbox(8)
	_header.add_child(Ui.label(Words.render("ui.open_camps"), "open_camps_title", "MutedLabel"))
	_dot = PulseDot.new()
	_dot.set_meta("id", "open_camps_dot")
	_header.add_child(_dot)
	add_child(_header)
	_empty = Ui.label(Words.render("ui.no_open_camps"), "no_open_camps", "MutedLabel")
	_empty.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_empty)
	_list = Ui.vbox(8)
	_list.set_meta("id", "camp_list")
	add_child(_list)
	Feed.model_changed.connect(_on_model)
	_apply(Feed.rooms_model())


func _on_model(kind: String, m: Dictionary) -> void:
	if kind == "games":
		_apply(Feed.rooms_model())          # the labels follow the games the server offers
	elif kind == "rooms":
		_apply(m)


## Show the model: hide or show the section, then bring the rows to match it.
func _apply(m: Dictionary) -> void:
	_dot.modulate.a = 1.0
	var known: bool = m.supported
	visible = known or m.loading
	_dot.visible = m.loading and not known            # the quiet "finding out" marker; gone once the server has answered
	_empty.visible = known and m.rooms.is_empty()
	_list.visible = known
	_list.modulate.a = 0.5 if m.stale else 1.0         # the last list we had: still readable, plainly not live
	if not known:
		return
	_sync_rows(m.rooms)
	if _shown_once:
		_blip()
	_shown_once = true


## Add the rows that came, remove the ones that went, update the rest in place, and put them in the server's order.
func _sync_rows(rooms: Array) -> void:
	var want := {}
	for r in rooms:
		want[r.code] = r
	for code in _rows.keys():
		if not want.has(code):
			var row: Dictionary = _rows[code]
			_list.remove_child(row.button)
			(row.button as Node).queue_free()
			_rows.erase(code)
	var index := 0
	for r in rooms:
		if not _rows.has(r.code):
			_rows[r.code] = _make_row(r)
		_update_row(_rows[r.code], r)
		_list.move_child(_rows[r.code].button, index)
		index += 1


func _make_row(r: Dictionary) -> Dictionary:
	var b := Button.new()
	b.set_meta("id", "camp_" + r.code)
	b.theme_type_variation = "CampCard"
	b.custom_minimum_size = Vector2(0, CARD_MIN_H)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var code: String = r.code
	b.pressed.connect(func(): _tap(code))
	Ui.juice(b)
	_list.add_child(b)
	# the content sits inside the card's own content margins (read from the style, not written here)
	var sb := b.get_theme_stylebox("normal")
	var pad := MarginContainer.new()
	pad.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pad.add_theme_constant_override("margin_left", int(sb.get_margin(SIDE_LEFT)))
	pad.add_theme_constant_override("margin_right", int(sb.get_margin(SIDE_RIGHT)))
	pad.add_theme_constant_override("margin_top", int(sb.get_margin(SIDE_TOP)))
	pad.add_theme_constant_override("margin_bottom", int(sb.get_margin(SIDE_BOTTOM)))
	b.add_child(pad)
	var row := Ui.hbox(10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pad.add_child(row)
	var words := Ui.vbox(0)
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var title := Ui.name_label("", "", "NameLabel")
	var sub := Ui.name_label("", "", "MutedLabel")
	words.add_child(title)
	words.add_child(sub)
	var tag := Ui.name_label("", "game_tag", "MutedLabel")          # which game this card is for; shown only when the server offers more than one
	tag.visible = false
	words.add_child(tag)
	row.add_child(words)
	return {"button": b, "title": title, "sub": sub, "tag": tag, "row": row, "lanterns": null, "total": -1, "taken": -1, "count": null}


func _update_row(row: Dictionary, r: Dictionary) -> void:
	var title: String = r.name if r.name != "" else Words.render("ui.room_code", {"code": r.code})
	(row.title as Label).text = title
	var seats := Words.render("ui.camp_seats", {"taken": r.seats_taken, "total": r.seats_total})
	(row.sub as Label).text = "%s - %s" % [seats, age_text(int(r.age_s))]
	_set_game_tag(row, Feed.game_label(r.get("game")))
	if int(row.total) != int(r.seats_total):                    # a different size of camp: its lanterns are made again
		if row.lanterns != null:
			(row.lanterns as Node).queue_free()
			row.lanterns = null
		var l := Ui.lanterns(int(r.seats_total), int(r.seats_taken), "camp_lanterns_" + r.code)
		if l != null:
			l.size_flags_horizontal = Control.SIZE_SHRINK_END
			l.custom_minimum_size = Vector2(minf(LANTERN_ROOM, 34.0 * float(r.seats_total)), 0)
			(row.row as Node).add_child(l)
			row.lanterns = l
		row.total = int(r.seats_total)
	elif row.lanterns != null and int(row.taken) != int(r.seats_taken):
		Ui.set_lit(row.lanterns, int(r.seats_taken))
	row.taken = int(r.seats_taken)


## The game's name on a card: the server's name for the card's game; the neutral "another game" when the server did not list that
## id; nothing at all on a lone-game server (the label is `{}` then).
func _set_game_tag(row: Dictionary, label: Dictionary) -> void:
	var tag: Label = row.tag
	tag.visible = not label.is_empty()
	# the card's content is laid over it, so a third line needs a taller card, or it sits on the border
	(row.button as Button).custom_minimum_size = Vector2(0, CARD_MIN_H + (GAME_TAG_H if tag.visible else 0.0))
	if label.is_empty():
		return
	tag.text =Words.render("ui.game_unknown") if label.get("unknown", false) else str(label.name)


## "just now", "3 min ago", "2 h ago", "1 d ago": plain words from the theme.
static func age_text(age_s: int) -> String:
	if age_s < 60:
		return Words.render("ui.camp_just_now")
	if age_s < 3600:
		return Words.render("ui.camp_min_ago", {"n": age_s / 60})
	if age_s < 86400:
		return Words.render("ui.camp_hours_ago", {"n": age_s / 3600})
	return Words.render("ui.camp_days_ago", {"n": age_s / 86400})


## The card was tapped: join that camp through the ordinary join path. A refusal (it filled or closed first) comes back as a
## neutral notice and a fresh list.
func _tap(code: String) -> void:
	Intents.join_room(code, true)


## A quiet sign that a fresh list arrived: the marker flashes once and settles. Nothing moves.
func _blip() -> void:
	if Themes.reduced_motion or not is_inside_tree():
		return
	_dot.visible = true
	_dot.modulate.a = 1.0
	var tw := create_tween()
	tw.tween_property(_dot, "modulate:a", 0.0, 0.7)
	tw.tween_callback(func(): _dot.visible = false)
