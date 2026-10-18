class_name LobbyScreen
extends Control
## The waiting room: the camp code shown big with a Copy button (it is what you tell your friends), a lantern per seat
## (lit when taken), and for the host a Start button with an honest note when seats are empty (bots take them). A guest
## sees a clear "waiting for the host" card and no Start.

const LANTERN := Vector2(40, 60)          # chosen: the lantern art has a clear margin, so this shows about 24 x 36 of lantern
var copied_seconds := 1.6                 # how long the Copy button says it worked (a test shortens it)

var _sig := ""
var _intro_played := false
var _copy_button: Button
var _copy_gen := 0                        # a later press must not be undone by an earlier press's timer


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	_build()


## An identical push (the server re-sends the same view on every action) must not rebuild the screen under a finger.
func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "lobby":
		return
	if _sig_of(m) != _sig:
		_build()


func _sig_of(m: Dictionary) -> String:
	return JSON.stringify(m.get("lines", m)) + JSON.stringify(m.get("radio", [])) + str(m.get("is_host", "")) + str(m.get("seats_taken", ""))


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
	var lit := _lanterns(int(m.seats_total), int(m.seats_taken))
	if lit != null:
		inner.add_child(lit)
	var seats := Ui.label(Words.render("ui.seats", {"taken": m.seats_taken, "total": m.seats_total}), "seats")
	seats.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	inner.add_child(seats)
	menu.add_child(sign_card)
	entries.append(sign_card)
	if m.is_host:
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
