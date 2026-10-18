extends Control
## The router: one screen at a time, chosen by the connection status, plus the scene behind everything and the overlay.
## Knows screens, not rules. A change of screen cross-fades (about a quarter of a second) when the theme asks for it.

const SCREENS := {
	"title": preload("res://screens/title_screen.gd"),
	"lobby": preload("res://screens/lobby_screen.gd"),
	"round": preload("res://screens/round_screen.gd"),
	"reveal": preload("res://screens/reveal_screen.gd"),
	"end": preload("res://screens/end_screen.gd"),
	"upgrade": preload("res://screens/upgrade_screen.gd"),
}
## The order the backdrop pans through as a game moves along (a screen not listed pans like the title).
const PAN_ORDER := ["title", "lobby", "round", "reveal", "end"]

var current_name := ""
var current: Control
var backdrop: Backdrop
var _slot: Control
var _vignette: TextureRect


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if Themes.current:
		theme = Themes.current.godot_theme
	backdrop = Backdrop.new()
	add_child(backdrop)
	_slot = Control.new()
	_slot.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_slot)
	_vignette = TextureRect.new()
	_vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_vignette.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_vignette.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_vignette.stretch_mode = TextureRect.STRETCH_SCALE
	add_child(_vignette)
	_apply_vignette()
	add_child(Overlay.new())
	Feed.status_changed.connect(_route)
	Themes.theme_changed.connect(_on_theme)
	_route(Feed.status())
	Intents.resume()                         # a stored seat resumes on launch


## F11 or Alt+Enter toggles full screen on a desktop. `_input`, not `_unhandled_input`: a focused text box would swallow Enter.
func _input(event: InputEvent) -> void:
	if WindowModes.is_toggle(event):
		WindowModes.toggle()
		get_viewport().set_input_as_handled()


## The soft dark edge that frames the picture. The theme may have none.
func _apply_vignette() -> void:
	_vignette.texture = Themes.texture("vignette")
	_vignette.visible = _vignette.texture != null


## A new theme: restyle the whole window and rebuild the current screen in the new words.
func _on_theme(_id: String) -> void:
	theme = Themes.current.godot_theme
	_apply_vignette()
	current_name = ""
	_route(Feed.status())


func _route(st: Dictionary) -> void:
	var want: String = st.screen if SCREENS.has(st.screen) else "title"
	if want == current_name:
		return
	var old := current
	current = SCREENS[want].new()
	current_name = want
	_slot.add_child(current)
	backdrop.pan_to(maxi(0, PAN_ORDER.find(want)))
	var fade := Themes.fx("transition")
	if fade.is_empty():
		if old != null:
			_slot.remove_child(old)
			old.queue_free()
		return
	_cross_fade(old, current, fade)


## The old screen fades and drifts up while the new one fades in and settles. The old one stops taking input at once;
## reduced motion keeps the fade and drops the drift.
func _cross_fade(old: Control, now: Control, fade: Dictionary) -> void:
	var t := float(fade.get("fade", 0.25))
	var slide := 0.0 if Themes.reduced_motion else float(fade.get("slide", 0.0))
	now.modulate.a = 0.0
	now.offset_top = slide
	now.offset_bottom = slide
	var tw := create_tween().set_parallel(true)
	# the old screen is nearly gone before the new one shows (only the content fades; the backdrop never does), so the two
	# are never both half-visible for long
	var lead := t * 0.4 if old != null else 0.0
	tw.tween_property(now, "modulate:a", 1.0, t * 0.6).set_delay(lead).set_trans(Tween.TRANS_SINE)
	tw.tween_property(now, "offset_top", 0.0, t * 0.6).set_delay(lead).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(now, "offset_bottom", 0.0, t * 0.6).set_delay(lead).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	if old == null:
		return
	old.process_mode = Node.PROCESS_MODE_DISABLED
	old.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tw.tween_property(old, "modulate:a", 0.0, lead)
	tw.tween_property(old, "offset_top", -slide * 0.5, lead)
	tw.tween_property(old, "offset_bottom", -slide * 0.5, lead)
	tw.chain().tween_callback(func():
		if is_instance_valid(old):
			_slot.remove_child(old)
			old.queue_free())
