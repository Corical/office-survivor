extends Node
## The active theme. `use` points Words at the theme's translation; screens call Words / Themes, never a theme file.
##
## What a screen may ask of the theme (all optional, all safe with the plain placeholder theme):
##   icon(id)        a glyph icon (a beat kind, a band, ...) or null
##   texture(id)     art (a backdrop, a hut, an avatar...) or null
##   nine_patch(id)  nine-slice art as a StyleBox, or null
##   color(name)     a named colour, never null
##   fx(name)        a parameter dictionary for an effect, {} = do not play it (always {} for a motion effect while
##                   reduced motion is on). The returned dictionary is shared: read it, never write it.

signal theme_changed(id: String)
signal motion_changed(reduced: bool)

var current: ThemeDef
## The player's reduced-motion setting: no shake, no particles, no parallax or drifting. Kept for the session.
var reduced_motion := false:
	set(v):
		if v != reduced_motion:
			reduced_motion = v
			motion_changed.emit(v)
			_save_settings()
## Where the player's settings are kept between launches. Null (the default) means they are not kept: tests and tools never
## touch the player's file. The app turns it on once at launch with `enable_settings`.
var settings_store: SessionStore = null
var _settings := {}                   # everything the file held, so a setting a newer build wrote is not lost by an older one
var _loading := false
var _textures := {}


## Keep settings from now on, in `store`, and apply what it holds. Only an explicit `true` counts for a flag: a file that was
## hand-edited, damaged or written by something else can never switch a setting on by accident.
func enable_settings(store: SessionStore) -> void:
	settings_store = store
	_settings = store.load_data() if store else {}
	_settings.erase("v")
	_loading = true
	var raw: Variant = _settings.get("reduced_motion", false)
	reduced_motion = typeof(raw) == TYPE_BOOL and raw           # (a text or number is not a bool: comparing it to true would throw)
	_loading = false


func _save_settings() -> void:
	if settings_store == null or _loading:
		return
	_settings["reduced_motion"] = reduced_motion
	settings_store.save_data(_settings)


func _ready() -> void:
	if current == null:
		use(ThemeRegistry.DEFAULT_ID)


func use(id: String) -> bool:
	if not ThemeRegistry.THEMES.has(id):
		Log.event("themes", "unknown_theme", {"id": id}, "WARN")
		id = ThemeRegistry.DEFAULT_ID
	current = ThemeRegistry.make(id)
	_textures = {}
	Words.use(current.words)
	RenderingServer.set_default_clear_color(current.clear_color)
	Log.event("themes", "use", {"id": id})
	theme_changed.emit(id)
	return true


func ids() -> Array:
	return ThemeRegistry.ids()


func icon(id: String) -> Texture2D:
	return current.icons.get(id) if current else null


## Art by id, or null. Looked up once per theme and remembered (a miss too).
func texture(id: String) -> Texture2D:
	if current == null:
		return null
	if _textures.has(id):
		return _textures[id]
	var t: Texture2D = null
	if current.texture_source.is_valid():
		t = current.texture_source.call(id)
	_textures[id] = t
	return t


func nine_patch(id: String) -> StyleBox:
	return current.nine_patches.get(id) if current else null


func color(name: String) -> Color:
	return current.color(name) if current else ThemeDef.DEFAULT_COLORS.get(name, ThemeDef.DEFAULT_COLORS.white)


## A named colour with its alpha replaced (screens may not build colours themselves).
func color_a(name: String, alpha: float) -> Color:
	var c := color(name)
	c.a = alpha
	return c


func fx(name: String) -> Dictionary:
	if name == "reduced_motion":
		return {"on": reduced_motion}
	if current == null:
		return {}
	var p: Dictionary = current.fx.get(name, {})
	if reduced_motion and p.get("motion", false):
		return {}
	return p
