class_name RevealScreen
extends Control
## What happened in the night, as the written log plus the radio, with Continue. The animated Stage arrives in step 5;
## this is the text half, and it is always complete: it shows every line, including the ones the animation skips.

var _timer_label: Label


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	_build()


## Skip the animation: the log below is always complete, so nothing is lost.
func _skip() -> void:
	if Feed.player.timeline != null:
		Feed.player.timeline.snap_to_end()


func _process(_delta: float) -> void:
	if _timer_label != null:
		_timer_label.text = Words.render("ui.seconds", {"n": Feed.seconds_left()})


var _sig := ""


## An identical push (the server re-sends the same view on every action) must not rebuild the screen under a finger.
func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "reveal":
		return
	if _sig_of(m) != _sig:
		_build()


func _sig_of(m: Dictionary) -> String:
	return JSON.stringify(m.get("lines", m)) + JSON.stringify(m.get("radio", [])) + str(m.get("is_host", "")) + str(m.get("seats_taken", ""))


func _build() -> void:
	_sig = _sig_of(Feed.models.get("reveal", {}))
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_timer_label = null
	var col := Ui.page(self)
	var m: Dictionary = Feed.models.get("reveal", {})
	if m.is_empty():
		col.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		return
	col.add_child(Ui.label(Words.render("ui.reveal_title"), "reveal_title", "HeaderLabel"))
	_timer_label = Ui.label("", "timer_label", "MutedLabel")
	col.add_child(_timer_label)
	var stage := Stage.new()
	stage.set_meta("id", "stage")
	stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_child(stage)
	col.add_child(Ui.button(Words.render("ui.skip"), "skip", func(): _skip()))
	for i in m.lines.size():
		var ln: Dictionary = m.lines[i]
		col.add_child(Ui.label(Words.render(ln.key, ln.slots), "line_%d" % i))
	if not m.radio.is_empty():
		col.add_child(Ui.label(Words.render("ui.radio_heard"), "", "MutedLabel"))
		for i in m.radio.size():
			col.add_child(Ui.label(Words.render(m.radio[i].key, m.radio[i].slots), "radio_%d" % i))
	col.add_child(Ui.button(Words.render("ui.continue"), "continue", func(): Intents.proceed(), false, "PrimaryButton"))
