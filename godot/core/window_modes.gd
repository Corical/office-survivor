class_name WindowModes
extends RefCounted
## Full screen on and off for the desktop build. The decision is a pure function so a test can drive it; applying it is one
## line in `apply`. Phones are always full screen already, so nothing here does anything there.

const WINDOWED := DisplayServer.WINDOW_MODE_WINDOWED
const FULLSCREEN := DisplayServer.WINDOW_MODE_FULLSCREEN


## The mode a toggle goes to. Anything that is not full screen (windowed, minimised, maximised, exclusive full screen, or a
## value nobody expected) goes to full screen; full screen goes back to windowed. Never returns an unexpected mode.
static func next(current: int) -> int:
	if current == FULLSCREEN or current == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN:
		return WINDOWED
	return FULLSCREEN


## True for a key press that means "toggle full screen": F11, or Alt+Enter. Not Enter alone, not Alt alone, not an echo
## (a held key must not flicker the window), and not a release.
static func is_toggle(event: InputEvent) -> bool:
	if not (event is InputEventKey):
		return false
	var k := event as InputEventKey
	if not k.pressed or k.echo:
		return false
	if k.keycode == KEY_F11:
		return true
	return k.alt_pressed and (k.keycode == KEY_ENTER or k.keycode == KEY_KP_ENTER)


## Desktop builds only: a phone has no windows to toggle.
static func available() -> bool:
	return OS.has_feature("pc")


static func toggle() -> void:
	if not available():
		return
	DisplayServer.window_set_mode(next(DisplayServer.window_get_mode()))
