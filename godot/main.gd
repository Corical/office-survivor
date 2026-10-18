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
const SHARED_SCREENS := ["title", "upgrade"]        # the rest are a game's, shown only through its ruleset's phases
## The order the backdrop pans through as a game moves along (a screen not listed pans like the title).
const DEFAULT_FADE := {"fade": 0.4, "slide": 0.0}          # chosen: the same length as the flash theme's, without the drift
const MAX_STEP := 1.0 / 30.0                # chosen: a fade moves at most this much per frame, however long the frame was
const PAN_ORDER := ["title", "lobby", "round", "reveal", "end"]

var _fades: Array = []                      # the changes of screen still fading: {old, now, t, dur, lead, out, slide}
## For tests: builds the screen called `name` instead of the real one (so a swap can be checked without a whole game's state).
var screen_factory: Callable
var current_name := ""
var current: Control
var backdrop: Backdrop
var _slot: Control
var _vignette: TextureRect


func _ready() -> void:
	if Themes.settings_store == null and DisplayServer.get_name() != "headless":
		Themes.enable_settings(SessionStore.new("user://settings.json"))      # calm mode survives a restart
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


## A shared screen always; a game's screen only when the room's ruleset names it and a screen is drawn for it.
func _routable(screen: String) -> bool:
	return SCREENS.has(screen) and (screen in SHARED_SCREENS or screen in Feed.game_screens())


func _route(st: Dictionary) -> void:
	var want: String = st.screen if _routable(st.screen) else "title"
	if want == current_name:
		return
	var old := current
	current = screen_factory.call(want) if screen_factory.is_valid() else SCREENS[want].new()
	current_name = want
	_slot.add_child(current)
	backdrop.pan_to(maxi(0, PAN_ORDER.find(want)))
	var fade := Themes.fx("transition")
	if fade.is_empty():
		fade = DEFAULT_FADE                       # a theme with no setting of its own still never swaps a screen in one frame
	_cross_fade(old, current, fade)


## The old screen fades and drifts up while the new one fades in and settles. The old one stops taking input at once;
## reduced motion keeps the fade and drops the drift.
func _cross_fade(old: Control, now: Control, fade: Dictionary) -> void:
	var t := float(fade.get("fade", 0.25))
	var slide := 0.0 if Themes.reduced_motion else float(fade.get("slide", 0.0))
	now.modulate.a = 0.0
	now.offset_top = slide
	now.offset_bottom = slide
	# A screen that is the new one of an earlier, unfinished change stops being animated as "new": it now fades out as the old one.
	for f in _fades:
		if f.now == old:
			f.now = null
	if old != null:
		old.process_mode = Node.PROCESS_MODE_DISABLED
		Ui.inert(old)                                    # takes no tap while it fades out
		Ui.freeze(old, [Feed, Themes, Intents])          # no relayout while it fades out
	# Only the content fades; the backdrop never does. The two screens overlap: the old one is gone in the first 45% of the
	# time and the new one rises from 15% to the end, so the change is spread over many frames and never a single cut.
	var lead := t * 0.15 if old != null else 0.0
	_fades.append({"old": old, "now": now, "t": 0.0, "dur": t, "lead": lead, "out": t * 0.45, "slide": slide})


## The fade is stepped here, not by a Tween: building the new screen can make the next frame very long, and a Tween (real time)
## would spend the whole fade in that one frame, which is a hard cut. Each frame advances the fade by at most MAX_STEP.
func _process(delta: float) -> void:
	if _fades.is_empty():
		return
	var step := minf(delta, MAX_STEP)
	for f in _fades.duplicate():
		f.t += step
		_apply_fade(f)
		if f.t >= f.dur:
			_fades.erase(f)


func _apply_fade(f: Dictionary) -> void:
	var done: bool = f.t >= f.dur
	var now: Control = f.now if is_instance_valid(f.now) else null
	if now != null:
		var p := 1.0 if done else clampf((f.t - f.lead) / (f.dur - f.lead), 0.0, 1.0)
		now.modulate.a = sin(p * PI * 0.5)                                    # ease out
		var rest: float = f.slide * pow(1.0 - p, 3.0)                         # drifts up into place, slowing
		now.offset_top = rest
		now.offset_bottom = rest
	var old: Control = f.old if is_instance_valid(f.old) else null
	if old == null:
		return
	if done or f.t >= f.out:
		_slot.remove_child(old)
		old.queue_free()
		f.old = null
		return
	var q := clampf(f.t / f.out, 0.0, 1.0)
	old.modulate.a = cos(q * PI * 0.5)                                        # ease in
	old.offset_top = -f.slide * 0.5 * q
	old.offset_bottom = -f.slide * 0.5 * q
