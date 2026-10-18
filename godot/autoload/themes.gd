extends Node
## The active theme. `use` points Words at the theme's translation; screens call Words / Themes, never a theme file.

signal theme_changed(id: String)

var current: ThemeDef


func _ready() -> void:
	if current == null:
		use(ThemeRegistry.DEFAULT_ID)


func use(id: String) -> bool:
	if not ThemeRegistry.THEMES.has(id):
		Log.event("themes", "unknown_theme", {"id": id}, "WARN")
		id = ThemeRegistry.DEFAULT_ID
	current = ThemeRegistry.make(id)
	Words.use(current.words)
	Log.event("themes", "use", {"id": id})
	theme_changed.emit(id)
	return true


func icon(id: String) -> Texture2D:
	return current.icons.get(id) if current else null
