class_name RoundScreen
extends Control
## The decision screen. From the model alone: who I am, how long is left, my resources and goal, everyone's home, the
## moves the server offers (with their targets and amounts), Lock, how many have locked, and the radio.
## Layout: one column on a phone with what you act on first (who you are, the clock, the moves, Lock); two columns on a
## wide window (acting on the left, information on the right). The look comes from the theme.

const WIDE_PX := 900                # chosen: at this width and above the screen uses two columns

var _m: Dictionary = {}
var _move: Dictionary = {}          # the picker being filled in (local, until a pick is sent)
var _target: Variant = null
var _radio_open := false
var _radio_phrase: Dictionary = {}
var _timer_label: Label
var _timer_bar: ProgressBar
var _wide := false
var _sig := ""                      # what the screen currently shows, so an unchanged push does not rebuild it
var _building := false


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	resized.connect(_on_resized)
	if Feed.models.has("round"):
		_m = Feed.models.round
	_build()


## Only a change between the phone layout and the wide one needs a rebuild (and never while one is running).
func _on_resized() -> void:
	if not _building and (size.x >= WIDE_PX) != _wide:
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
	if _signature(m) != _sig:
		_build()
	else:
		_refresh_live()       # only the clock and the locked count moved: update them in place, keep the buttons


## Everything the screen draws except the clock and the locked count. A server push that changes only those (a bot
## locking, say) must not rebuild the buttons: a tap whose press and release straddle a rebuild is lost.
func _signature(m: Dictionary) -> String:
	return JSON.stringify([m.round, m.rounds, m.me, m.goal, m.pickers, m.my_pick, m.lock, m.radio, m.roster,
		m.seats_total, m.timer.known])


func _refresh_live() -> void:
	var lc := Ui.find(self, "locked_count") as Label
	if lc != null:
		lc.text = Words.render("ui.locked_count", {"locked": _m.locked_count, "total": _m.seats_total})
	_tick()


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
	if _building:
		return
	_building = true
	_wide = size.x >= WIDE_PX
	_sig = _signature(_m) if not _m.is_empty() else ""
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_timer_label = null
	_timer_bar = null
	var page := Ui.page(self)
	if _m.is_empty():
		page.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		_building = false
		return
	var open: bool = _m.lock.picker_open
	var head := _head()
	var act := _act(open)
	var goal := _goal()
	var roster := _roster()
	var radio := _radio(open)
	if size.x >= WIDE_PX:
		var cols := HBoxContainer.new()
		cols.add_theme_constant_override("separation", 32)
		cols.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var left := Ui.vbox(16)
		var right := Ui.vbox(16)
		for s in [head, act]:
			left.add_child(s)
		for s in [goal, roster, radio]:
			right.add_child(s)
		cols.add_child(left)
		cols.add_child(right)
		page.add_child(cols)
	else:
		for s in [head, act, roster, goal, radio]:
			page.add_child(s)
	_building = false
	if _radio_open:
		call_deferred("_show_radio")


## The radio opens at the bottom of the page: scroll it into view so nobody has to hunt for it.
func _show_radio() -> void:
	var last: Control = null
	for c in Ui.find_all(self, "phrase_") + Ui.find_all(self, "about_"):
		last = c
	if last == null:
		return
	for n in find_children("*", "ScrollContainer", true, false):
		(n as ScrollContainer).ensure_control_visible(last)


## Who I am, the clock, what I have.
func _head() -> VBoxContainer:
	var s := Ui.vbox(6)
	s.add_child(Ui.label(Words.render("ui.you_are", {"alias": _m.me.alias}), "you_are", "BigLabel"))
	_timer_label = Ui.label("", "timer_label", "HeaderLabel")
	_timer_bar = ProgressBar.new()
	_timer_bar.set_meta("id", "timer_bar")
	_timer_bar.show_percentage = false
	_timer_bar.custom_minimum_size = Vector2(0, 14)
	s.add_child(_timer_label)
	s.add_child(_timer_bar)
	_tick()
	s.add_child(Ui.label(Words.render("ui.round_of", {"round": _m.round, "rounds": _m.rounds}), "round_of", "MutedLabel"))
	for r in _m.me.resources:
		s.add_child(Ui.label("%s: %s" % [Words.render(r.id), r.amount], "resource", "HeaderLabel"))
	for st in _m.me.statuses:
		if st.on:
			s.add_child(Ui.label(Words.render(st.id), "status"))
	return s


## The moves, their targets and amounts, my pick, Lock and the locked count.
func _act(open: bool) -> VBoxContainer:
	var s := Ui.vbox(10)
	s.add_child(Ui.label(Words.render("ui.pick_a_move"), "", "MutedLabel"))
	var moves := Ui.flow()
	for p in _m.pickers:
		var chosen: bool = (not _move.is_empty()) and _move.server_id == p.server_id
		var txt: String = Words.render(p.key) + (" *" if chosen else "")
		moves.add_child(Ui.button(txt, "move_" + p.server_id, func(): _choose(p), not open))
	s.add_child(moves)
	if not _move.is_empty() and _move.takes_target:
		s.add_child(Ui.label(Words.render("ui.pick_a_target"), "", "MutedLabel"))
		var targets := Ui.flow()
		for t in _move.targets:
			targets.add_child(Ui.button(t, "target_" + t, func(): _choose_target(t), not open))
		s.add_child(targets)
	if not _move.is_empty() and _target != null and not _move.amounts.is_empty():
		s.add_child(Ui.label(Words.render("ui.pick_an_amount"), "", "MutedLabel"))
		var amounts := Ui.flow()
		for a in _move.amounts:
			amounts.add_child(Ui.button(str(a), "amount_%s" % a, func(): _send(_move, _target, a), not open))
		s.add_child(amounts)
	if _m.my_pick != null:
		s.add_child(Ui.label(Words.render("ui.your_pick", {"pick": _describe(_m.my_pick)}), "my_pick"))
	var state: String = _m.lock.state
	var lock_key := "ui.lock" if state == "open" else ("ui.locking" if state == "sent" else "ui.locked")
	s.add_child(Ui.button(Words.render(lock_key), "lock", func(): _lock(), state != "open" or not open or _m.my_pick == null,
		"PrimaryButton"))
	s.add_child(Ui.label(Words.render("ui.locked_count", {"locked": _m.locked_count, "total": _m.seats_total}), "locked_count"))
	return s


func _goal() -> VBoxContainer:
	var s := Ui.vbox(4)
	s.add_child(Ui.label(Words.render("ui.goal"), "", "MutedLabel"))
	s.add_child(Ui.label(Words.render(_m.goal.key, _m.goal.slots), "goal"))
	var progress: String = Words.render(_m.goal.progress.key, _m.goal.progress.slots)
	# worded from a code, the progress already says how it stands; otherwise lead with the state word
	var status: String = progress if _m.goal.progress.from_code else "%s: %s" % [Words.render(_m.goal.state_key), progress]
	s.add_child(Ui.label(status, "goal_status", "MutedLabel"))
	return s


func _roster() -> VBoxContainer:
	var s := Ui.vbox(4)
	s.add_child(Ui.label(Words.render("ui.roster"), "", "MutedLabel"))
	for e in _m.roster:
		var line: String = e.alias
		if e.is_me:
			line += " " + Words.render("ui.you_mark")
		elif e.band != "":
			line += ": " + Words.render(e.band)
		s.add_child(Ui.label(line, "home_" + e.alias))
	return s


func _radio(open: bool) -> VBoxContainer:
	var s := Ui.vbox(8)
	if not _m.radio.available:
		return s
	s.add_child(Ui.button(Words.render("ui.radio"), "radio_toggle", func():
		_radio_open = not _radio_open
		_radio_phrase = {}
		_build(), not open))
	if _radio_open:
		var phrases := Ui.flow()
		for ph in _m.radio.phrases:
			phrases.add_child(Ui.button(Words.render(ph.key, {"a": "..."}), "phrase_" + ph.server_id,
				func(): _choose_phrase(ph), not open))
		s.add_child(phrases)
		if not _radio_phrase.is_empty() and _radio_phrase.needs_player:
			s.add_child(Ui.label(Words.render("ui.radio_pick_player"), "", "MutedLabel"))
			var who := Ui.flow()
			for e in _m.roster:
				if not e.is_me:
					who.add_child(Ui.button(e.alias, "about_" + e.alias, func(): _send_radio(_radio_phrase, e.alias), not open))
			s.add_child(who)
	return s


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
