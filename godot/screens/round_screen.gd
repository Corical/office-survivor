class_name RoundScreen
extends Control
## The decision screen. From the model alone: who I am, how long is left, my resources and goal, everyone's home, the
## moves the server offers (with their targets and amounts), Lock, how many have locked, and the radio.
## Layout is a neutral placeholder; the look comes from the theme.

var _m: Dictionary = {}
var _move: Dictionary = {}          # the picker being filled in (local, until a pick is sent)
var _target: Variant = null
var _radio_open := false
var _radio_phrase: Dictionary = {}
var _timer_label: Label
var _timer_bar: ProgressBar


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	if Feed.models.has("round"):
		_m = Feed.models.round
	_build()


func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "round":
		return
	if int(m.get("round", -1)) != int(_m.get("round", -2)):
		_move = {}
		_target = null
		_radio_open = false
		_radio_phrase = {}
	_m = m
	_build()


func _process(_delta: float) -> void:
	_tick()


func _tick() -> void:
	if _timer_label == null or _m.is_empty():
		return
	var t: Dictionary = _m.timer
	if not t.known:
		_timer_label.text = Words.render("ui.timer_unknown")
		_timer_bar.value = 0
		return
	var left := Feed.seconds_left()
	_timer_label.text = Words.render("ui.seconds", {"n": left})
	_timer_bar.max_value = maxf(1.0, t.total_s)
	_timer_bar.value = left


func _build() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_timer_label = null
	_timer_bar = null
	var col := Ui.page(self)
	if _m.is_empty():
		col.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	var open: bool = _m.lock.picker_open

	# header: where we are in the game, and the clock
	col.add_child(Ui.label(Words.render("ui.round_of", {"round": _m.round, "rounds": _m.rounds}), "round_of", "HeaderLabel"))
	_timer_label = Ui.label("", "timer_label", "HeaderLabel")
	_timer_bar = ProgressBar.new()
	_timer_bar.set_meta("id", "timer_bar")
	_timer_bar.show_percentage = false
	_timer_bar.custom_minimum_size = Vector2(0, 14)
	col.add_child(_timer_label)
	col.add_child(_timer_bar)
	_tick()

	# me
	col.add_child(Ui.label(Words.render("ui.you_are", {"alias": _m.me.alias}), "you_are", "HeaderLabel"))
	for r in _m.me.resources:
		col.add_child(Ui.label("%s: %s" % [Words.render(r.id), r.amount], "resource"))
	for s in _m.me.statuses:
		if s.on:
			col.add_child(Ui.label(Words.render(s.id), "status"))

	# goal
	col.add_child(Ui.label(Words.render("ui.goal"), "", "MutedLabel"))
	col.add_child(Ui.label(Words.render(_m.goal.key, _m.goal.slots), "goal"))
	col.add_child(Ui.label("%s: %s" % [Words.render(_m.goal.state_key), Words.render(_m.goal.progress.key,
		_m.goal.progress.slots)], "goal_status", "MutedLabel"))

	# everyone
	col.add_child(Ui.label(Words.render("ui.roster"), "", "MutedLabel"))
	for e in _m.roster:
		var line: String = e.alias
		if e.is_me:
			line += " " + Words.render("ui.you_mark")
		elif e.band != "":
			line += ": " + Words.render(e.band)
		col.add_child(Ui.label(line, "home_" + e.alias))

	# the moves
	col.add_child(Ui.label(Words.render("ui.pick_a_move"), "", "MutedLabel"))
	var moves := Ui.flow()
	for p in _m.pickers:
		var chosen: bool = (not _move.is_empty()) and _move.server_id == p.server_id
		var txt: String = Words.render(p.key) + (" *" if chosen else "")
		moves.add_child(Ui.button(txt, "move_" + p.server_id, func(): _choose(p), not open))
	col.add_child(moves)
	if not _move.is_empty() and _move.takes_target:
		col.add_child(Ui.label(Words.render("ui.pick_a_target"), "", "MutedLabel"))
		var targets := Ui.flow()
		for t in _move.targets:
			targets.add_child(Ui.button(t, "target_" + t, func(): _choose_target(t), not open))
		col.add_child(targets)
	if not _move.is_empty() and _target != null and not _move.amounts.is_empty():
		col.add_child(Ui.label(Words.render("ui.pick_an_amount"), "", "MutedLabel"))
		var amounts := Ui.flow()
		for a in _move.amounts:
			amounts.add_child(Ui.button(str(a), "amount_%s" % a, func(): _send(_move, _target, a), not open))
		col.add_child(amounts)
	if _m.my_pick != null:
		col.add_child(Ui.label(Words.render("ui.your_pick", {"pick": _describe(_m.my_pick)}), "my_pick"))

	# lock
	var state: String = _m.lock.state
	var lock_key := "ui.lock" if state == "open" else ("ui.locking" if state == "sent" else "ui.locked")
	col.add_child(Ui.button(Words.render(lock_key), "lock", func(): _lock(), state != "open" or not open or _m.my_pick == null,
		"PrimaryButton"))
	col.add_child(Ui.label(Words.render("ui.locked_count", {"locked": _m.locked_count, "total": _m.seats_total}), "locked_count"))

	# radio
	if _m.radio.available:
		col.add_child(Ui.button(Words.render("ui.radio"), "radio_toggle", func():
			_radio_open = not _radio_open
			_radio_phrase = {}
			_build(), not open))
		if _radio_open:
			_build_radio(col, open)


func _build_radio(col: VBoxContainer, open: bool) -> void:
	var phrases := Ui.flow()
	for ph in _m.radio.phrases:
		phrases.add_child(Ui.button(Words.render(ph.key, {"a": "..."}), "phrase_" + ph.server_id, func(): _choose_phrase(ph), not open))
	col.add_child(phrases)
	if not _radio_phrase.is_empty() and _radio_phrase.needs_player:
		col.add_child(Ui.label(Words.render("ui.radio_pick_player"), "", "MutedLabel"))
		var who := Ui.flow()
		for e in _m.roster:
			if not e.is_me:
				who.add_child(Ui.button(e.alias, "about_" + e.alias, func(): _send_radio(_radio_phrase, e.alias), not open))
		col.add_child(who)


func _choose(p: Dictionary) -> void:
	_move = p
	_target = null
	if not p.takes_target:
		_send(p, null, 0)          # nothing more to choose: a move with no target goes out at once
		return
	_build()


func _choose_target(t: String) -> void:
	_target = t
	if _move.amounts.is_empty():
		_send(_move, t, 0)
		return
	_build()


func _send(p: Dictionary, target: Variant, amount: int) -> void:
	var why := Intents.pick(p.server_id, target, amount)
	if why != "":
		Log.event("round_screen", "pick_refused", {"why": why}, "WARN")


func _choose_phrase(ph: Dictionary) -> void:
	_radio_phrase = ph
	if not ph.needs_player:
		_send_radio(ph, null)
		return
	_build()


func _send_radio(ph: Dictionary, about: Variant) -> void:
	Intents.radio(ph.server_id, about)
	_radio_open = false
	_radio_phrase = {}


func _lock() -> void:
	var why := Intents.lock()
	if why != "":
		Log.event("round_screen", "lock_refused", {"why": why}, "WARN")


## The pick as words: the move's name, and its target / amount when it has them.
func _describe(p: Dictionary) -> String:
	var shown: String = p.move_id
	for q in _m.pickers:
		if q.server_id == p.move_id or q.move_id == p.move_id:
			shown = Words.render(q.key)
	var out: String = shown
	if p.target != null:
		out += " > " + str(p.target)
	if int(p.amount) > 0:
		out += " x" + str(p.amount)
	return out
