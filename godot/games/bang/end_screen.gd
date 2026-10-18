class_name BangEndScreen
extends Control
## Bang! when the game is over: which side won, whether mine did, who the winners were, and everyone's role (all are public now).
## Eliminated seats see this too. Words come from bang.* keys, looks from the theme.

const WIDE_PX := 900

var _m: Dictionary = {}
var _wide := false
var _building := false


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	resized.connect(_on_resized)
	_m = Feed.models.get("view", {})
	_build()


func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "view" or (not _m.is_empty() and int(m.seq) < int(_m.seq)):
		return
	_m = m
	_build()


func _on_resized() -> void:
	if not _building and (size.x >= WIDE_PX) != _wide:
		_build()


func _build() -> void:
	if _building:
		return
	_building = true
	_wide = size.x >= WIDE_PX
	for c in get_children():
		remove_child(c)
		c.queue_free()
	if _m.is_empty():
		Ui.page(self).add_child(Ui.label(Words.render("bang.nothing"), "empty"))
		_building = false
		return
	var pg := Ui.page_docked(self)
	pg.dock.add_child(Ui.button(Words.render("ui.back_to_title"), "back", func(): Intents.leave(), false, "PrimaryButton"))
	var col: VBoxContainer = pg.col
	col.add_child(_header())
	col.add_child(_winners())
	col.add_child(_roles())
	_building = false


func _header() -> Control:
	var card := Ui.card("CardHot")
	var col := Ui.vbox(4)
	card.add_child(col)
	var w: Dictionary = _m.winner
	var team: String = w.get("team", "unknown")
	col.add_child(Ui.name_label(Words.render("bang.team." + team), "team", "BigLabel"))
	if not w.is_empty() and team != "abandoned":
		col.add_child(Ui.label(Words.render("bang.end.win" if w.mine else "bang.end.lose"), "mine", "HeaderLabel"))
	return card


func _winners() -> Control:
	var card := Ui.card()
	var col := Ui.vbox(4)
	card.add_child(col)
	var w: Dictionary = _m.winner
	if w.is_empty() or w.ats.is_empty():
		card.visible = false
		return card
	col.add_child(Ui.label(Words.render("bang.end.winners"), "winners_title", "HeaderLabel"))
	for s in _m.seats:
		if s.at in w.ats:
			col.add_child(Ui.name_label(_row(s), "winner_%d" % s.at, "NameLabel"))
	return card


func _roles() -> Control:
	var card := Ui.card()
	var col := Ui.vbox(4)
	card.add_child(col)
	col.add_child(Ui.label(Words.render("bang.end.roles"), "roles_title", "HeaderLabel"))
	for s in _m.seats:
		col.add_child(Ui.name_label(_row(s), "role_%d" % s.at, "NameLabel"))
	return card


func _row(s: Dictionary) -> String:
	var who: String = s.name
	if s.is_me:
		who = "%s (%s)" % [who, Words.render("bang.seat_you")]
	var role := Words.render("bang.role." + (s.role if s.role != "" else "unknown"))
	if not s.alive:
		return "%s  -  %s  -  %s" % [who, role, Words.render("bang.seat_out")]
	return "%s  -  %s" % [who, role]
