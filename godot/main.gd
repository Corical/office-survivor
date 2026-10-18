extends Control
## The router: one screen at a time, chosen by the connection status, plus the overlay. Knows screens, not rules.

const SCREENS := {
	"title": preload("res://screens/title_screen.gd"),
	"lobby": preload("res://screens/lobby_screen.gd"),
	"round": preload("res://screens/round_screen.gd"),
	"reveal": preload("res://screens/reveal_screen.gd"),
	"end": preload("res://screens/end_screen.gd"),
	"upgrade": preload("res://screens/upgrade_screen.gd"),
}

var current_name := ""
var current: Control
var _slot: Control


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if Themes.current:
		theme = Themes.current.godot_theme
	_slot = Control.new()
	_slot.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_slot)
	add_child(Overlay.new())
	Feed.status_changed.connect(_route)
	_route(Feed.status())
	Intents.resume()                         # a stored seat resumes on launch


func _route(st: Dictionary) -> void:
	var want: String = st.screen if SCREENS.has(st.screen) else "title"
	if want == current_name:
		return
	if current != null:
		_slot.remove_child(current)
		current.queue_free()
	current = SCREENS[want].new()
	current_name = want
	_slot.add_child(current)
