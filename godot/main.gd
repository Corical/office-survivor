extends Control
## Router: one screen at a time, chosen by Session.screen. Step 1 stub: a label per screen until the real screens
## land in step 4. A stored seat resumes on launch.

var _label: Label


func _ready() -> void:
	_label = Label.new()
	_label.name = "ScreenLabel"
	_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	add_child(_label)
	Session.screen_changed.connect(func(_s): _refresh())
	Net.state_changed.connect(func(_s): _refresh())
	_refresh()
	Session.resume_if_stored()


func _refresh() -> void:
	_label.text = "%s\n(%s)" % [Session.screen, Net.state]
