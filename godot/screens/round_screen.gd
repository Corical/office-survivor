class_name RoundScreen
extends Control
## The decision screen. From the model alone: who I am, how long is left, my resources and goal, everyone's home, the
## moves the server offers (with their targets and amounts), Lock, how many have locked, and the radio.
## Layout: one column on a phone with what you act on first (who you are and the clock, the moves, the targets) and the
## Lock button fixed at the foot of the screen; two columns on a wide window (acting on the left, information on the
## right). The look comes from the theme: medallion moves, player cards, a ring clock, lanterns for the locked seats.

const WIDE_PX := 900                # chosen: at this width and above the screen uses two columns
const RING_PX := 112.0              # chosen: the clock ring, large enough to hold "180 s" with room round it
const TIMER_VARIATIONS := ["HeaderLabel", "TimerWarn", "TimerUrgent"]       # calm, under 30 s, under 10 s (the theme owns the colours)
const MOVE_MIN_H := 142.0
const AVATAR_PX := 76.0

var _m: Dictionary = {}
var _move: Dictionary = {}          # the picker being filled in (local, until a pick is sent)
var _target: Variant = null
var _amount := 0                    # the amount tapped for a move that has amounts (a pick goes out when move, target and amount are all in)
var _radio_open := false
var _goal_open := false             # phone width: the goal card shows the goal; a tap shows how it is going and what a seat is
var _radio_phrase: Dictionary = {}
var _timer_label: Label
var _ring: RingTimer
var _lock_btn: Button
var _charge: ChargeFill
var _lanterns: HBoxContainer
var _wide := false
var _sig := ""                      # what the screen currently shows, so an unchanged push does not rebuild it
var _building := false
var _avatars := {}                  # alias -> avatar number for this roster
var _intro_played := false
var _pulsing := false
var _pulse_tween: Tween
var _left_int := -1                 # the whole seconds last shown, and when they changed (to move the ring smoothly)
var _left_changed_ms := 0
static var _seen_moves: Array = []         # every move offered so far this game, in the order first seen (keeps the row stable)
static var _seen_round := 0
var _prompt: Label                  # the line above the moves; it becomes "Pick a move!" when time is short and nothing is picked


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
		var words := Words.render("ui.locked_count", {"locked": _m.locked_count, "total": _m.seats_total})
		if lc is FitLabel:
			(lc as FitLabel).set_fit_text(words)
		else:
			lc.text = words
	if _lanterns != null:
		Ui.set_lit(_lanterns, int(_m.locked_count))
	_tick()


func _process(_delta: float) -> void:
	_tick()


func _tick() -> void:
	if _timer_label == null or _m.is_empty():
		return
	var t: Dictionary = _m.timer
	if not t.known:
		_say(_timer_label, Words.render("ui.timer_unknown"))
		_set_variation(_timer_label, "MutedLabel")
		if _ring != null:
			_ring.value = 0.0
			_ring.state = 0
		_set_pulse(false)
		return
	var left := Feed.seconds_left()
	_say(_timer_label, Words.render("ui.seconds", {"n": left}))
	# The server's clock reaches us in whole seconds. The ring and the charge are drawn from the milliseconds since the last
	# change (read from the engine's own clock, so a slow frame cannot stall them): they drain a little every frame.
	var now_ms := Time.get_ticks_msec()
	if left != _left_int:
		_left_int = left
		_left_changed_ms = now_ms
	var age := clampf(float(now_ms - _left_changed_ms) / 1000.0, 0.0, 1.0)
	var smooth := maxf(0.0, float(left) - age)
	var total := maxf(1.0, float(t.total_s))
	var tm := Themes.fx("timer")
	var stage := 2 if smooth <= float(tm.get("urgent_s", 10)) else (1 if smooth <= float(tm.get("warn_s", 30)) else 0)
	_set_variation(_timer_label, TIMER_VARIATIONS[stage])
	if _ring != null:
		_ring.max_value = total
		_ring.value = smooth
		_ring.state = stage
	if _charge != null:
		var lock_live: bool = _m.lock.state == "open" and _lock_btn != null and not _lock_btn.disabled
		_charge.fraction = (1.0 - smooth / total) if lock_live else 0.0       # a greyed-out Lock has no light moving across it
	var open: bool = _m.lock.picker_open
	if _prompt != null and _m.my_pick == null:    # under 20 s with nothing picked, the line above the moves turns into a call to act
		var nag := open and _m.my_pick == null and smooth <= float(tm.get("prompt_s", 20))
		_set_variation(_prompt, "PromptLabel" if nag else "MutedLabel")
		var words := Words.render("ui.pick_prompt") if nag else Words.render("ui.pick_a_move")
		if _prompt.text != words:
			_prompt.text = words
	_set_pulse(stage == 2 and open and _lock_btn != null and not _lock_btn.disabled)


## Set a label's words; a fitted label is refitted at once.
static func _say(l: Label, words: String) -> void:
	if l.text == words:
		return
	if l is FitLabel:
		(l as FitLabel).set_fit_text(words)
	else:
		l.text = words


static func _set_variation(l: Control, variation: String) -> void:
	if l.theme_type_variation != variation:
		l.theme_type_variation = variation
		if l is FitLabel:
			(l as FitLabel).restyle()                  # its font size is part of the variation: fit again from the new one


## The Lock button breathes while there is little time left and a pick waiting to be locked.
func _set_pulse(on: bool) -> void:
	if on == _pulsing or _lock_btn == null:
		return
	var p := Themes.fx("pulse")
	if on and p.is_empty():
		return
	_pulsing = on
	if _pulse_tween != null and _pulse_tween.is_valid():
		_pulse_tween.kill()
	if not on:
		_lock_btn.scale = Vector2.ONE
		return
	var s := 1.0 + float(p.get("scale", 0.05))
	var t := float(p.get("time", 0.45))
	_pulse_tween = _lock_btn.create_tween().set_loops()
	_pulse_tween.tween_property(_lock_btn, "scale", Vector2(s, s), t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_pulse_tween.tween_property(_lock_btn, "scale", Vector2.ONE, t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


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
	_ring = null
	_prompt = null
	_lock_btn = null
	_charge = null
	_lanterns = null
	_pulsing = false
	_left_int = -1
	if _m.is_empty():
		var page := Ui.page(self)
		page.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		_building = false
		return
	_avatars = Ui.avatar_ids(_m.roster.map(func(e): return e.alias))
	var pg := Ui.page_docked(self)
	var page: VBoxContainer = pg.col
	var open: bool = _m.lock.picker_open
	var head := _head()
	var act := _act(open)
	var goal := _goal()
	var roster := _roster()
	var radio := _radio(open)
	if _wide:
		var cols := HBoxContainer.new()
		cols.add_theme_constant_override("separation", 32)
		cols.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var left := Ui.vbox(16)
		var right := Ui.vbox(16)
		for s in [head, act]:
			left.add_child(s)
		for s in [roster, goal, radio]:
			right.add_child(s)
		cols.add_child(left)
		cols.add_child(right)
		page.add_child(cols)
	else:
		# the goal sits right under the header (nobody scrolls to find their own goal) -- except while a target or amount is being
		# picked: then the pickers take that place, so the whole pick is on screen above the dock
		var order := [head, act, goal, roster, radio] if _picking() else [head, goal, act, roster, radio]
		for s in order:
			page.add_child(s)
	_dock(pg.dock, open)
	_building = false
	if not _intro_played:
		_intro_played = true
		Ui.intro_all([head, act, roster, goal])
	_tick()
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
func _head() -> Control:
	var card := Ui.card()
	var row := Ui.hbox(14)
	card.add_child(row)
	var face := Ui.avatar(str(_m.me.alias), _avatars)
	if face != null:
		row.add_child(Ui.picture(face, Vector2(AVATAR_PX, AVATAR_PX), "me_avatar"))
	var s := Ui.vbox(4)
	# "You are" small, the name under it with the whole width: a 12-letter name shrinks a little to fit instead of being cut
	s.add_child(Ui.label(Words.render("ui.you_are_prefix"), "you_are_prefix", "MutedLabel"))
	s.add_child(Ui.name_label(str(_m.me.alias), "you_are", "YouLabel"))
	s.add_child(Ui.label(Words.render("ui.round_of", {"round": _m.round, "rounds": _m.rounds}), "round_of", "MutedLabel"))
	for r in _m.me.resources:
		var line := Ui.hbox(8)
		var icon := Themes.icon(r.id)
		if icon != null:
			line.add_child(Ui.picture(icon, Vector2(30, 30)))
		line.add_child(Ui.label("%s: %s" % [Words.render(r.id), r.amount], "resource", "HeaderLabel"))
		s.add_child(line)
	for st in _m.me.statuses:
		if st.on:
			var line := Ui.hbox(8)
			var icon := Themes.icon(st.id)
			if icon != null:
				line.add_child(Ui.picture(icon, Vector2(26, 26)))
			line.add_child(Ui.label(Words.render(st.id), "status"))
			s.add_child(line)
	row.add_child(s)
	_ring = RingTimer.new()
	_ring.set_meta("id", "timer_bar")
	_ring.custom_minimum_size = Vector2(RING_PX, RING_PX)
	_ring.size_flags_horizontal = Control.SIZE_SHRINK_END
	_ring.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_timer_label = Ui.name_label("", "timer_label", "HeaderLabel")
	_timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_timer_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_timer_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ring.add_child(_timer_label)
	_timer_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_timer_label.offset_left = 22                       # clear of the ring's stroke on both sides
	_timer_label.offset_right = -22
	row.add_child(_ring)
	return card


## The moves, their targets and amounts, and my pick. (Lock lives in the dock.)
func _act(open: bool) -> VBoxContainer:
	var s := Ui.vbox(10)
	# one line above the moves: the quiet label, the call to act when time is short, or the pick once there is one
	var picked: bool = _m.my_pick != null
	_prompt = Ui.label(Words.render("ui.your_pick", {"pick": _describe(_m.my_pick)}) if picked else Words.render("ui.pick_a_move"),
		"my_pick" if picked else "pick_prompt", "NameLabel" if picked else "MutedLabel")
	_prompt.custom_minimum_size = Vector2(0, 30)       # the same height whether it is the quiet label or the prompt: nothing jumps
	_prompt.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	s.add_child(_prompt)
	var moves := Ui.hbox(6)
	var offered := {}
	for p in _m.pickers:
		offered[str(p.server_id)] = p
	for p in _row_moves():
		var live: bool = offered.has(str(p.server_id))
		moves.add_child(_move_button(offered[str(p.server_id)] if live else p, live and _is_chosen(p), open and live, not live))
	s.add_child(moves)
	# the reason a medallion is greyed out; the line is always there so the page does not move when it comes and goes
	var why := Ui.name_label("", "why_unavailable", "")
	why.custom_minimum_size = Vector2(0, 26)
	var gone: Array = []
	for p in _row_moves():
		if not offered.has(str(p.server_id)):
			gone.append(Words.render(str(p.key)))
	if not gone.is_empty():
		why.set_fit_text(Words.render("ui.move_unavailable", {"move": ", ".join(gone)}))
	s.add_child(why)
	if not _move.is_empty() and not _move.amounts.is_empty():
		# the amount sits with the move and the target, never below them: one row, chosen in either order
		var arow := Ui.hbox(8)
		var alabel := Ui.label(Words.render("ui.pick_an_amount"), "", "MutedLabel")
		alabel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		arow.add_child(alabel)
		for a in _move.amounts:
			var b := Ui.button(str(a), "amount_%s" % a, func(): _choose_amount(a), not open,
				"ChosenButton" if _amount == int(a) else "SkipPill")
			b.custom_minimum_size = Vector2(64, 48)
			arow.add_child(b)
		s.add_child(arow)
	if not _move.is_empty() and _move.takes_target:
		s.add_child(Ui.label(Words.render("ui.pick_a_target"), "", "MutedLabel"))
		var targets := GridContainer.new()
		targets.columns = 3 if _wide else 2
		targets.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for t in _move.targets:
			targets.add_child(_target_button(str(t), _target != null and str(_target) == str(t), open))
		s.add_child(targets)
	return s


## Every move that has been on offer this game, in the order first seen, plus any on offer now. A move that is not on offer
## tonight stays in the row (greyed out, with the reason below) so the row never changes shape from one night to the next.
func _row_moves() -> Array:
	var round_no := int(_m.round)
	if round_no < _seen_round or round_no <= 1:
		_seen_moves = []                                   # a new game
	_seen_round = round_no
	for p in _m.pickers:
		var known := false
		for q in _seen_moves:
			if str(q.server_id) == str(p.server_id):
				known = true
				break
		if not known:
			_seen_moves.append(p)
	return _seen_moves


## Is this the move I have picked? Either what I tapped here, or what the server says I picked (after a reconnect).
func _is_chosen(p: Dictionary) -> bool:
	if not _move.is_empty():
		return _move.server_id == p.server_id
	if _m.my_pick != null:
		return str(_m.my_pick.move_id) == str(p.server_id) or str(_m.my_pick.move_id) == str(p.move_id)
	return false


## A move: a medallion with its word underneath (a plain button when the theme has no art for it). The one you picked
## glows and lifts.
func _move_button(p: Dictionary, chosen: bool, open: bool, off := false) -> Button:
	var word: String = Words.render(p.key)
	var id := "move_" + str(p.server_id)
	var art := Themes.texture(id)
	var cb := func(): _choose(p)
	if art == null:
		return Ui.button(word, id, cb, not open, "ChosenButton" if chosen else "")
	var b := Ui.button("", id, cb, not open, "MoveButton")
	b.tooltip_text = word
	b.set_meta("caption", word)
	var cap := Ui.name_label(word, "", "MoveCaptionChosen" if chosen else "MoveCaption")
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	cap.offset_top = -30
	cap.offset_bottom = -4
	cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(cap)
	b.icon = art
	b.expand_icon = true
	b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
	var icon_w := clampf((size.x - 32.0 - 24.0) / 5.0, 56.0, 92.0)   # five across: the medallion and its caption fit the width
	b.custom_minimum_size = Vector2(0, minf(MOVE_MIN_H, icon_w + 36.0))
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if not open:
		b.modulate.a = 0.6
	if off:                                       # a tag over the medallion: this is closed tonight, not loading
		var tag := Ui.card("Banner")
		tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var tl := Ui.label(Words.render("ui.move_off"), "", "MutedLabel")
		tl.autowrap_mode = TextServer.AUTOWRAP_OFF
		tag.add_child(tl)
		tag.anchor_left = 0.5
		tag.anchor_right = 0.5
		tag.grow_horizontal = Control.GROW_DIRECTION_BOTH
		tag.offset_top = 30
		tag.modulate.a = 1.0 / 0.6                  # undo the button's fade for the tag itself
		b.add_child(tag)
	if chosen:
		_glow_and_lift(b)
	return b


func _glow_and_lift(b: Button) -> void:
	var lift := Themes.fx("lift")
	var ring_art := Themes.texture("fx_ring")
	if ring_art != null:
		var ring := Ui.picture(ring_art, Vector2.ZERO)
		ring.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
		ring.offset_left = -4
		ring.offset_right = 4
		ring.offset_top = -10
		ring.offset_bottom = 110
		ring.modulate = Themes.color("ember")
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		ring.material = add
		b.add_child(ring)
		if not lift.is_empty() and not Themes.reduced_motion:
			var tw := ring.create_tween().set_loops()
			tw.tween_property(ring, "modulate:a", 0.45, 0.7).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
			tw.tween_property(ring, "modulate:a", 1.0, 0.7).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	if lift.is_empty():
		return
	var s := float(lift.get("scale", 1.1))
	var t := float(lift.get("time", 0.2))
	b.pivot_offset = Vector2(b.custom_minimum_size.x * 0.5, 50.0)
	b.create_tween().tween_property(b, "scale", Vector2(s, s), t).from(Vector2.ONE).set_trans(Tween.TRANS_BACK) \
		.set_ease(Tween.EASE_OUT)


## A person I can pick: their face, their name, and their band (the only thing anyone is shown about another's food).
func _target_button(alias: String, chosen: bool, open: bool) -> Button:
	var band := ""
	for e in _m.roster:
		if e.alias == alias and e.band != "":
			band = Words.render(e.band)
	var face := Ui.avatar(alias, _avatars)
	var variation := ""
	if face != null:
		variation = "PlayerCardChosen" if chosen else "PlayerCard"
	elif chosen:
		variation = "ChosenButton"
	if face == null:                                   # no art: a plain button with the name and band as its words
		var plain := Ui.button(alias if band == "" else "%s\n%s" % [alias, band], "target_" + alias,
			func(): _choose_target(alias), not open, variation)
		plain.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		return plain
	var b := Ui.button("", "target_" + alias, func(): _choose_target(alias), not open, variation)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.custom_minimum_size = Vector2(0, 76)
	Ui.fill_person_card(b, face, alias, band)          # the name is fitted to the card, never cut at a phone's width
	return b


## The foot of the screen: the lanterns (one per seat, lit when that seat has locked), their count in words, and Lock.
func _dock(dock: VBoxContainer, open: bool) -> void:
	var top := Ui.hbox(12)
	top.alignment = BoxContainer.ALIGNMENT_CENTER
	if _m.radio.available:
		var radio := Ui.button(Words.render("ui.radio"), "radio_toggle", func():
			_radio_open = not _radio_open
			_radio_phrase = {}
			_build(), not open, "SkipPill", "radio")                 # a flat pill: the wood art needs 62 px and this sits in the dock at 48
		radio.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		radio.custom_minimum_size = Vector2(0, 48)
		top.add_child(radio)
	_lanterns = Ui.lanterns(int(_m.seats_total), int(_m.locked_count), "lanterns")
	if _lanterns != null:
		_lanterns.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		top.add_child(_lanterns)
	var count := Ui.name_label(Words.render("ui.locked_count", {"locked": _m.locked_count, "total": _m.seats_total}),
		"locked_count", "MutedLabel")
	top.add_child(count)
	dock.add_child(top)
	var state: String = _m.lock.state
	var lock_key := "ui.lock" if state == "open" else ("ui.locking" if state == "sent" else "ui.locked")
	_lock_btn = Ui.button(Words.render(lock_key), "lock", func(): _lock(), not _lock_ready(open), "PrimaryButton")
	if _wide:                                   # on a wide window the main action is a button, not a bar across the screen
		_lock_btn.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		_lock_btn.custom_minimum_size.x = 520.0
	_charge = ChargeFill.new()
	_lock_btn.add_child(_charge)
	dock.add_child(_lock_btn)
	# why the Lock is grey, in one line under it (the line keeps its height when empty, so the dock never jumps)
	var hint := Ui.name_label(_lock_hint(open), "lock_hint", "MutedLabel")
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.custom_minimum_size = Vector2(0, 22)
	dock.add_child(hint)


## The Lock works exactly when a pick is in (the server's own view says so) and the night is still open.
func _lock_ready(open: bool) -> bool:
	return _m.lock.state == "open" and open and _m.my_pick != null


## One line that says what is missing while the Lock is grey ("" when it is live or already used).
func _lock_hint(open: bool) -> String:
	if _m.lock.state != "open":
		return ""
	if not open:
		return Words.render("ui.hint_closed")
	if _m.my_pick != null:
		return ""
	if _move.is_empty():
		return Words.render("ui.hint_pick_move")
	if _move.takes_target and _target == null:
		return Words.render("ui.hint_pick_target")
	if not _move.amounts.is_empty() and _amount == 0:
		return Words.render("ui.hint_pick_amount")
	return Words.render("ui.hint_sending")


func _goal() -> Control:
	var card := Ui.card()
	var s := Ui.vbox(4)
	card.add_child(s)
	var compact: bool = not _wide
	var open_now: bool = _goal_open or not compact
	var top := Ui.hbox(8)
	var title := Ui.label(Words.render("ui.goal"), "", "MutedLabel")
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(title)
	if compact:                                       # a tap anywhere on the card opens or closes the detail
		var hint := Ui.label(Words.render("ui.goal_tap_less" if _goal_open else "ui.goal_tap_more"), "goal_toggle_hint", "MutedLabel")
		hint.autowrap_mode = TextServer.AUTOWRAP_OFF
		top.add_child(hint)
		card.gui_input.connect(func(ev: InputEvent):
			if ev is InputEventMouseButton and ev.pressed == false and ev.button_index == MOUSE_BUTTON_LEFT:
				_goal_open = not _goal_open
				_build())
	s.add_child(top)
	s.add_child(Ui.label(Words.render(_m.goal.key, _m.goal.slots), "goal"))
	if not open_now:
		return card
	var progress: String = Words.render(_m.goal.progress.key, _m.goal.progress.slots)
	# worded from a code, the progress already says how it stands; otherwise lead with the state word
	var status: String = progress
	if not _m.goal.progress.from_code:
		# the state word, then the server's own detail if it sent one (the old form said the state word twice)
		var detail := str(_m.goal.get("progress_text", ""))
		status = Words.render(_m.goal.state_key) + (": " + detail if detail != "" else "")
	s.add_child(Ui.label(status, "goal_status", "MutedLabel"))
	var note: String = str(_m.goal.get("note_key", ""))
	if note != "":
		s.add_child(Ui.label(Words.render(note), "goal_note", "MutedLabel"))
	return card


## Everyone around the fire: a face, a name, and the band (never a number) for the others.
func _roster() -> Control:
	var card := Ui.card() if _wide else Ui.card("LogLine")        # phone width: a flat card, no thick frame, so the names get the room
	var s := Ui.vbox(8)
	card.add_child(s)
	s.add_child(Ui.label(Words.render("ui.roster"), "", "MutedLabel"))
	var grid := GridContainer.new()
	var one_row: bool = not _wide and size.x >= 420.0       # four across, each a face over its name (a long name shrinks, then wraps)
	grid.columns = 4 if one_row else 2                # otherwise two a row: a face beside the name and band
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 10)
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for e in _m.roster:
		var cell: BoxContainer = Ui.vbox(2) if one_row else Ui.hbox(10)
		cell.set_meta("id", "home_" + e.alias)
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var face := Ui.avatar(e.alias, _avatars)
		if face != null:
			var px := 54.0 if _wide else 40.0
			var pic := Ui.picture(face, Vector2(px, px))
			pic.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
			cell.add_child(pic)
		var words := Ui.vbox(0)
		words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var nm := Ui.name_label(e.alias, "", "NameLabel")
		if one_row:
			nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		words.add_child(nm)
		var sub := ""
		if e.is_me:
			sub = Words.render("ui.you_mark")
		elif e.band != "":
			sub = Words.render(e.band)
		if sub != "":
			var sl := Ui.name_label(sub, "", "MutedLabel")
			if one_row:
				sl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			words.add_child(sl)
		cell.add_child(words)
		grid.add_child(cell)
	s.add_child(grid)
	return card


func _radio(open: bool) -> VBoxContainer:
	var s := Ui.vbox(8)
	if not _m.radio.available:
		return s
	if _radio_open:                                    # (the Radio button itself lives in the dock, where it cannot be hidden)
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


## A move that needs a target (and maybe an amount) is open and not yet complete.
func _picking() -> bool:
	if _move.is_empty() or not _move.takes_target:
		return false
	return _target == null or (not _move.amounts.is_empty() and _amount == 0)


func _choose(p: Dictionary) -> void:
	_move = p
	_target = null
	_amount = 0
	if not p.takes_target:
		_send(p, null, 0)          # nothing more to choose: a move with no target goes out at once
		return
	_build()


func _choose_target(t: String) -> void:
	_target = t
	if _move.amounts.is_empty():
		_send(_move, t, 0)
		return
	if _amount > 0:
		_send(_move, t, _amount)
		return
	_build()


func _choose_amount(a: Variant) -> void:
	_amount = int(a)
	if _target != null:
		_send(_move, _target, _amount)
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
