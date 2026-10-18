class_name LobbyScreen
extends Control
## The waiting room: the camp code shown big with a Copy button (it is what you tell your friends), a lantern per seat
## (lit when taken), and for the host a Start button with an honest note when seats are empty (bots take them). A guest
## sees a clear "waiting for the host" card and no Start.

const LANTERN := Vector2(40, 60)          # chosen: the lantern art has a clear margin, so this shows about 24 x 36 of lantern
const KICK_WIDTH := 170.0                 # chosen: "Send away" with its studs and a margin, in the widest word the themes use
var copied_seconds := 1.6                # how long the Copy button says it worked (a test shortens it)

var _sig := ""
var _intro_played := false
var _copy_button: Button
var _kicking := ""                        # the handle of the seat just sent away, until the next lobby shows it gone
var _confirm_card: Control                # the card showing a question, to scroll into view
var _confirming := ""                    # the handle of a seat that is here and is being asked about
var _copy_gen := 0                       # a later press must not be undone by an earlier press's timer


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	_build()


## An identical push (the server re-sends the same view on every action) must not rebuild the screen under a finger.
func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "lobby":
		return
	if _sig_of(m) != _sig or _kicking != "":
		# a push while a kick is out is the server's answer (the seat is gone) or a refusal (it is still there: the button
		# comes back, and a second tap meets the "in flight" guard if the first is still travelling)
		if _sig_of(m) == _sig:
			_kicking = ""
		_build()


func _sig_of(m: Dictionary) -> String:
	return JSON.stringify(m.get("lines", m)) + JSON.stringify(m.get("radio", [])) + str(m.get("is_host", "")) + str(m.get("seats_taken", "")) + JSON.stringify(m.get("seats", []))


func _build() -> void:
	_sig = _sig_of(Feed.models.get("lobby", {}))
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var menu := Ui.menu_column(Ui.page(self))
	var m: Dictionary = Feed.models.get("lobby", {})
	if m.is_empty():
		menu.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	var entries: Array = []
	var sign_card := Ui.card()
	var inner := Ui.vbox(10)
	sign_card.add_child(inner)
	var caption := Ui.label(Words.render("ui.code_caption"), "code_caption", "MutedLabel")
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(caption)
	var code := Ui.name_label(str(m.room_code), "room_code", "CodeLabel")
	code.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(code)
	inner.add_child(_copy_row(str(m.room_code)))
	# The host knows which of the taken seats have dropped off. Counting them as "taken" said "4 of 4" while one was out in the
	# dark, so then the header says who is here and who is away, and the dropped seat's lantern is dim. A guest has no seat list
	# (away = 0), so its header is unchanged.
	var away := _away_count(m)
	var taken := int(m.seats_taken)
	var lit := _lanterns(int(m.seats_total), maxi(0, taken - away))
	if lit != null:
		inner.add_child(lit)
	var count_text := Words.render("ui.seats", {"taken": m.seats_taken, "total": m.seats_total}) if away == 0 \
		else Words.render("ui.seats_away", {"here": maxi(0, taken - away), "away": away})
	var seats := Ui.label(count_text, "seats")
	seats.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(seats)
	menu.add_child(sign_card)
	entries.append(sign_card)
	if m.is_host:
		var seat_rows := _seat_list(m.get("seats", []))
		if seat_rows != null:
			menu.add_child(seat_rows)
		if int(m.seats_taken) < int(m.seats_total):
			var bots := Ui.label(Words.render("ui.bots_fill"), "bots_note", "MutedLabel")
			bots.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			menu.add_child(bots)
		var start := Ui.button(Words.render("ui.start"), "start", func(): Intents.start(), false, "PrimaryButton")
		menu.add_child(start)
		entries.append(start)
	else:
		var wait_card := Ui.card("Plate")
		wait_card.set_meta("id", "waiting_card")
		var wait := Ui.label(Words.render("ui.waiting_for_host"), "waiting", "HeaderLabel")
		wait.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		wait_card.add_child(wait)
		menu.add_child(wait_card)
		entries.append(wait_card)
	var leave := Ui.button(Words.render("ui.leave"), "leave", func(): Intents.leave())
	menu.add_child(leave)
	entries.append(leave)
	if not _intro_played:
		_intro_played = true
		Ui.intro_all(entries)


## The host's list of the OTHER seats, one row per entry of the latest lobby model, named by position ("Seat 1".."Seat n":
## the server gives no names and neither does this). Each row says whether that seat is here (lit lantern) or dropped off (dim
## lantern) and has a Send away button. A dropped seat is sent away with one tap. A seat that is here needs a second, explicit
## tap (the confirm row), so one stray tap can never remove a player who is there. Null when there is nobody to list.
## Nothing is decided locally after a kick: the server sends a fresh lobby and the row is gone. The pressed row's button is
## off until then (a second tap would only come back "in flight").
func _seat_list(seats: Array) -> Control:
	var handles: Array = seats.map(func(s): return s.id)
	if _kicking != "" and not handles.has(_kicking):
		_kicking = ""                                      # that seat is gone: the kick worked
	if _confirming != "" and not handles.has(_confirming):
		_confirming = ""
	if seats.is_empty():
		return null
	var col := Ui.vbox(8)
	col.set_meta("id", "seat_list")
	var any_dropped := false
	for i in seats.size():
		var seat: Dictionary = seats[i]
		any_dropped = any_dropped or not seat.connected
		col.add_child(_seat_row(i + 1, seat))
	if any_dropped:
		var help := Ui.label(Words.render("ui.kick_help"), "kick_help", "MutedLabel")
		help.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		col.add_child(help)
	return col


## How many of the host's other seats have dropped off, from the latest model (0 for a guest: it has no list).
func _away_count(m: Dictionary) -> int:
	if not m.get("is_host", false):
		return 0
	var n := 0
	for s in m.get("seats", []):
		if not s.connected:
			n += 1
	return n


func _seat_row(n: int, seat: Dictionary) -> Control:
	var id: String = seat.id
	var card := Ui.card("Plate")
	card.set_meta("id", "seat_row_%d" % n)
	var row := Ui.hbox(10)
	card.add_child(row)
	var tex := Themes.texture("lantern_on" if seat.connected else "lantern_off")
	if tex != null:
		row.add_child(Ui.picture(tex, Vector2(40, 60)))
	var text := Ui.vbox(0)
	text.add_child(Ui.name_label(Words.render("ui.seat_n", {"n": n}), "seat_name_%d" % n, "NameLabel"))
	var state := Ui.name_label(Words.render("ui.seat_here" if seat.connected else "ui.seat_dropped"), "seat_state_%d" % n, "MutedLabel")
	text.add_child(state)
	row.add_child(text)
	var busy := _kicking == id
	if _confirming == id and not busy:
		# Compact and inline: the seat's own line stays as it is, the question sits under it across the whole card (it wraps
		# by words there, never by letters), and the two choices side by side under that, each half the card wide.
		var ask := Ui.label(Words.render("ui.kick_confirm"), "seat_confirm_%d" % n, "NameLabel")
		ask.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_confirm_card = card
		var yes := Ui.button(Words.render("ui.kick"), "kick_yes_%d" % n, func(): _send_kick(id))
		var no := Ui.button(Words.render("ui.cancel"), "kick_no_%d" % n, func():
			_confirming = ""
			_build())
		card.remove_child(row)
		var stack := Ui.vbox(8)
		stack.add_child(row)
		stack.add_child(ask)
		var choice := Ui.hbox(8)
		yes.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		no.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		choice.add_child(yes)
		choice.add_child(no)
		stack.add_child(choice)
		card.add_child(stack)
		return card
	var kick := Ui.button(Words.render("ui.kick"), "kick_%d" % n, func(): _on_kick_tap(id, seat.connected), busy)
	kick.size_flags_horizontal = Control.SIZE_SHRINK_END
	kick.custom_minimum_size = Vector2(KICK_WIDTH, Ui.MIN_ART_BUTTON_HEIGHT)          # room for the word between the two studs
	row.add_child(kick)
	return card


func _on_kick_tap(id: String, connected: bool) -> void:
	if connected:
		_confirming = id                                    # a seat that is here: ask first
		_build()
		_show_confirm.call_deferred()
		return
	_send_kick(id)


## Once the question is laid out, scroll the page so the whole question and both choices are in view (on a short window
## they would otherwise be below the fold, out of reach until the player scrolls).
func _show_confirm() -> void:
	await get_tree().process_frame
	if _confirm_card == null or not is_instance_valid(_confirm_card) or not _confirm_card.is_inside_tree():
		return
	var scroll: Node = _confirm_card.get_parent()
	while scroll != null and not (scroll is ScrollContainer):
		scroll = scroll.get_parent()
	if scroll != null:
		(scroll as ScrollContainer).ensure_control_visible(_confirm_card)


func _send_kick(id: String) -> void:
	_confirming = ""
	if Intents.kick(id) == "":
		_kicking = id
	_build()


## A small Copy button under the code; it says "Copied" for a moment after it worked.
func _copy_row(text: String) -> Control:
	var row := Ui.hbox(0)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	var b := Ui.button(Words.render("ui.copy"), "copy_code", func(): _on_copy(text))
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	b.custom_minimum_size = Vector2(180, Ui.MIN_ART_BUTTON_HEIGHT)          # a wood button is never shorter than its art's edges
	_copy_button = b
	row.add_child(b)
	return row


func _on_copy(text: String) -> void:
	if Intents.copy_text(text) != "" or _copy_button == null:
		return
	_copy_button.text = Words.render("ui.copied")
	_copy_gen += 1
	var mine := _copy_gen
	await get_tree().create_timer(copied_seconds).timeout
	if mine == _copy_gen and is_instance_valid(_copy_button):
		_copy_button.text = Words.render("ui.copy")


## A lantern per seat, lit when taken. Null when the theme has no lantern art.
func _lanterns(total: int, taken: int) -> HBoxContainer:
	var on := Themes.texture("lantern_on")
	var off := Themes.texture("lantern_off")
	if on == null or off == null:
		return null
	var row := Ui.hbox(8)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.set_meta("id", "seat_lanterns")
	for i in total:
		row.add_child(Ui.picture(on if i < taken else off, LANTERN))
	return row
