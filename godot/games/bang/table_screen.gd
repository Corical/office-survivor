class_name BangTableScreen
extends Control
## Bang! at the table while dice are rolled and resolved. From the neutral `view` model alone: every seat in table order, the five
## dice (tap to keep, dynamite stays), Roll / Roll again / Stop at the foot, and in the resolving step only the seats the server
## offers as targets are buttons. Looks come from the theme; words from bang.* keys.
## A press that is held keeps the same buttons until it is released (a rebuild under a finger loses the tap).

const WIDE_PX := 900                # chosen: at this width and above the screen uses two columns
const DIE_MIN_H := 84.0
const SEAT_BUTTON_H := 88.0        # chosen: room for the name and the line under it inside the button's frame
const HOLD_MAX_MS := 2000           # chosen: the longest a rebuild waits for a held press to be released

var _m: Dictionary = {}
var _kept: Dictionary = {}          # die index -> true, while the dice are being picked (local until a reroll is sent)
var _kept_key := ""
var _wide := false
var _building := false
var _sig := ""
var _held := {}
var _held_since_ms := 0
var _rebuild_waiting := false


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	resized.connect(_on_resized)
	var m: Dictionary = Feed.models.get("view", {})
	if not m.is_empty():
		_adopt(m)
	_build()


func _on_resized() -> void:
	if not _building and (size.x >= WIDE_PX) != _wide:
		_rebuild()


func _input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton:
		_note_press("mouse%d" % ev.button_index, ev.pressed)
	elif ev is InputEventScreenTouch:
		_note_press("touch%d" % ev.index, ev.pressed)


func _note_press(key: String, down: bool) -> void:
	if down:
		if _held.is_empty():
			_held_since_ms = Time.get_ticks_msec()
		_held[key] = true
		return
	_held.erase(key)
	if _held.is_empty() and _rebuild_waiting:
		call_deferred("_apply_waiting_rebuild")


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_WINDOW_FOCUS_OUT or what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_held.clear()
		if _rebuild_waiting:
			call_deferred("_apply_waiting_rebuild")


func _process(_delta: float) -> void:
	if _rebuild_waiting and not _held.is_empty() and Time.get_ticks_msec() - _held_since_ms > HOLD_MAX_MS:
		_rebuild()


func _apply_waiting_rebuild() -> void:
	if _rebuild_waiting and _held.is_empty():
		_rebuild()


func _rebuild() -> void:
	if not _held.is_empty() and Time.get_ticks_msec() - _held_since_ms <= HOLD_MAX_MS:
		_rebuild_waiting = true
		return
	_held.clear()
	_rebuild_waiting = false
	_build()


## Take a model in. The keep marks belong to one (turn, roll): a new one clears them.
func _adopt(m: Dictionary) -> void:
	_m = m
	var key := "%d|%d|%s" % [m.turn, m.rolls, m.phase]
	if key != _kept_key:
		_kept_key = key
		_kept = {}


func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "view":
		return
	if not _m.is_empty() and int(m.seq) < int(_m.seq):
		return                                   # an older view than the one drawn is never drawn over it
	_adopt(m)
	if _signature() != _sig:
		_rebuild()


func _signature() -> String:
	var copy := _m.duplicate()
	copy.erase("seq")
	return JSON.stringify([copy, _kept, _wide])


func _build() -> void:
	if _building:
		return
	_building = true
	_rebuild_waiting = false
	_wide = size.x >= WIDE_PX
	_sig = _signature()
	for c in get_children():
		remove_child(c)
		c.queue_free()
	if _m.is_empty():
		var page := Ui.page(self)
		page.add_child(Ui.label(Words.render("bang.nothing"), "empty"))
		_building = false
		return
	var pg := Ui.page_docked(self)
	var page: VBoxContainer = pg.col
	var picking: bool = bool(_m.my_turn) and str(_m.phase) == "resolve"
	var head := _head()
	var dice := _dice()
	var seats := _seats(picking)
	var log := _log()
	if _wide:
		var cols := HBoxContainer.new()
		cols.add_theme_constant_override("separation", 32)
		cols.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var left := Ui.vbox(16)
		var right := Ui.vbox(16)
		for s in [head, dice, log]:
			left.add_child(s)
		right.add_child(seats)
		cols.add_child(left)
		cols.add_child(right)
		page.add_child(cols)
	else:
		for s in ([head, seats, dice, log] if picking else [head, dice, seats, log]):
			page.add_child(s)
	_dock(pg.dock)
	_building = false


# ---- sections ----

func _head() -> Control:
	var card := Ui.card()
	var col := Ui.vbox(4)
	card.add_child(col)
	var role: String = _m.me.role
	if role != "":
		col.add_child(Ui.name_label(Words.render("bang.role_line", {"role": {"key": "bang.role." + role}}), "my_role", "YouLabel"))
		col.add_child(Ui.label(Words.render("bang.role_hint." + role), "my_role_hint", "MutedLabel"))
	var who := Words.render("bang.turn_yours") if _m.my_turn else (Words.render("bang.turn_of", {"name": _m.turn_name}) if _m.turn >= 0 else "")
	if who != "":
		col.add_child(Ui.name_label(who, "turn", "HeaderLabel"))
	col.add_child(Ui.label("%s  -  %s" % [Words.render("bang.rolls", {"n": _m.rolls, "max": _m.rolls_max}),
		Words.render("bang.pile", {"n": _m.pile})], "rolls", "MutedLabel"))
	return card


func _dice() -> Control:
	var card := Ui.card()
	var grid := GridContainer.new()
	grid.columns = 5 if _wide else 2
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_child(grid)
	if _m.dice.is_empty():
		card.visible = false
		return card
	var assigned := {}
	for a in _m.assigned:
		assigned[a.die] = a
	var rolling: bool = bool(_m.my_turn) and str(_m.phase) == "roll"
	for d in _m.dice:
		var lines: Array[String] = [Words.render("bang.face." + d.face)]
		var kept := bool(_kept.get(d.index, false))
		if d.locked:
			lines.append(Words.render("bang.die_locked"))
		elif assigned.has(d.index):
			lines.append(Words.render("bang.die_to", {"name": assigned[d.index].name}))
		elif kept:
			lines.append(Words.render("bang.die_kept"))
		var tappable: bool = rolling and bool(_m.can.reroll) and not d.locked
		var chosen: bool = kept or d.locked or (not _m.pending.is_empty() and _m.pending.die == d.index)
		var idx: int = d.index
		var b := Ui.button("", "die_%d" % idx, func(): _toggle(idx), not tappable, "ChosenButton" if chosen else "SkipPill")
		Ui.fill_person_card(b, null, lines[0], lines[1] if lines.size() > 1 else "", 0.0)      # fitted labels: a die never widens the page
		b.custom_minimum_size = Vector2(0, DIE_MIN_H)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(b)
	return card


## A tap on a die: keep it or let it go. A dynamite die cannot be let go, and none of this works out of turn or in another step.
func _toggle(idx: int) -> void:
	if not (bool(_m.my_turn) and str(_m.phase) == "roll" and bool(_m.can.reroll)):
		return
	for d in _m.dice:
		if d.index == idx:
			if d.locked:
				return
			_kept[idx] = not bool(_kept.get(idx, false))
			_rebuild()
			return


func _seats(picking: bool) -> Control:
	var col := Ui.vbox(8)
	for s in _m.seats:
		if picking and BangRuleset.may_target(_m, s.at):
			var at: int = s.at
			var b := Ui.button("", "seat_%d" % at, func(): _target(at), false, "ChosenButton")
			Ui.fill_person_card(b, null, _seat_name(s), _seat_line(s))
			b.custom_minimum_size = Vector2(0, SEAT_BUTTON_H)
			col.add_child(b)
			continue
		var card := Ui.card("CardHot" if s.is_turn else "Card")
		card.set_meta("id", "seat_%d" % s.at)
		var inner := Ui.vbox(2)
		card.add_child(inner)
		inner.add_child(Ui.name_label(_seat_name(s), "", "NameLabel"))
		inner.add_child(Ui.name_label(_seat_line(s), "", "MutedLabel"))
		col.add_child(card)
	return col


func _seat_name(s: Dictionary) -> String:
	return "%s (%s)" % [s.name, Words.render("bang.seat_you")] if s.is_me else str(s.name)


## Life, arrows, the role only when public, and who is out, away or on turn.
func _seat_line(s: Dictionary) -> String:
	var parts: Array[String] = []
	if not s.alive:
		parts.append(Words.render("bang.seat_out"))
	else:
		parts.append(Words.render("bang.seat_life", {"life": s.life, "max": s.max}))
	if s.arrows > 0:
		parts.append(Words.render("bang.seat_arrows", {"n": s.arrows}))
	if s.role != "":
		parts.append(Words.render("bang.role." + s.role))
	if s.away:
		parts.append(Words.render("bang.seat_away"))
	if s.is_turn:
		parts.append(Words.render("bang.seat_turn"))
	return "  -  ".join(parts)


func _log() -> Control:
	var card := Ui.card()
	var col := Ui.vbox(4)
	card.add_child(col)
	col.add_child(Ui.label(Words.render("bang.log_title"), "log_title", "HeaderLabel"))
	if _m.log.is_empty():
		col.add_child(Ui.label(Words.render("bang.log_empty"), "log_empty", "MutedLabel"))
	for l in _m.log:
		col.add_child(Ui.label(Words.render(l.key, l.slots), "log_line", "MutedLabel"))
	return card


func _dock(dock: VBoxContainer) -> void:
	var phase := str(_m.phase)
	if not _m.me.alive:
		dock.add_child(Ui.label(Words.render("bang.turn_out"), "status", "MutedLabel"))
		return
	if not _m.my_turn:
		var key := "bang.target_wait" if phase == "resolve" else "bang.wait"
		dock.add_child(Ui.label(Words.render(key, {"name": _m.turn_name}), "status", "MutedLabel"))
		return
	if phase == "resolve":
		var face: String = _m.pending.get("face", "unknown")
		dock.add_child(Ui.label(Words.render("bang.target_prompt", {"face": {"key": "bang.face." + face}}), "status", "HeaderLabel"))
		return
	if _m.can.roll:
		dock.add_child(Ui.button(Words.render("bang.act.roll"), "roll", func(): Intents.act("roll"), false, "PrimaryButton"))
		return
	dock.add_child(Ui.label(Words.render("bang.rolling_hint"), "status", "MutedLabel"))
	var again := Ui.button(Words.render("bang.act.reroll"), "reroll", _reroll, not BangRuleset.can_send_reroll(_m, _kept), "PrimaryButton")
	dock.add_child(again)
	dock.add_child(Ui.button(Words.render("bang.act.stop"), "stop", func(): Intents.act("stop"), not bool(_m.can.stop)))


func _reroll() -> void:
	if not BangRuleset.can_send_reroll(_m, _kept):
		return
	var mask := BangRuleset.keep_mask(_m.dice, _kept)
	if Intents.act("reroll", {"keep": mask}) == "":
		_kept = {}


## A tap on a seat: it goes out only if that seat is a target the server offers right now.
func _target(at: int) -> void:
	if BangRuleset.may_target(_m, at):
		Intents.act("target", {"at": at})
