class_name ThemeRegistry
extends RefCounted
## One line per theme. `preload` (not a directory listing) so exports carry the scripts. A new theme is a folder under
## themes/ with a theme.gd and words.po, plus one line here.

const DEFAULT_ID := "placeholder"
const THEMES := {
	"placeholder": preload("res://themes/placeholder/theme.gd"),
	"flash": preload("res://themes/flash/theme.gd"),
}


static func ids() -> Array:
	return THEMES.keys()


static func make(id: String) -> ThemeDef:
	var script: GDScript = THEMES.get(id, THEMES[DEFAULT_ID])
	return script.build()
