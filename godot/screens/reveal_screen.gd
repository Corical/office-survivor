class_name RevealScreen
extends Control
## What happened in the night, as the written log plus the radio, with Continue. The animated Stage arrives in step 5;
## this is the text half, and it is always complete: it shows every line, including the ones the animation skips.

var _timer_label: Label


func _ready() -> void:
	Feed.model_changed.connect(func(kind, _m): if kind == "reveal": _build())
	_build()


func _process(_delta: float) -> void:
	if _timer_label != null:
		_timer_label.text = Words.render("ui.seconds", {"n": Feed.seconds_left()})


func _build() -> void:
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
	for i in m.lines.size():
		var ln: Dictionary = m.lines[i]
		col.add_child(Ui.label(Words.render(ln.key, ln.slots), "line_%d" % i))
	if not m.radio.is_empty():
		col.add_child(Ui.label(Words.render("ui.radio_heard"), "", "MutedLabel"))
		for i in m.radio.size():
			col.add_child(Ui.label(Words.render(m.radio[i].key, m.radio[i].slots), "radio_%d" % i))
	col.add_child(Ui.button(Words.render("ui.continue"), "continue", func(): Intents.proceed(), false, "PrimaryButton"))
