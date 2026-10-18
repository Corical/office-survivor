class_name ThemeDef
extends RefCounted
## What a theme is: the words, a Godot Theme for the look, icons, art and effect settings. Screens never touch these
## directly: words come through Words, the look through the root Theme, and everything else through Themes
## (icon / texture / nine_patch / color / fx).
##
## EVERY hook is optional. A theme that supplies nothing (the placeholder) gets plain shapes and no effects, and every
## screen must still work: Themes.texture() returns null, Themes.fx() returns {}, Themes.color() a neutral default.

var id := ""
var title := ""
var words: Translation
var godot_theme: Theme = Theme.new()
## icon id (a beat kind, a move id, a band id...) -> Texture2D. A missing id is fine: the Stage draws a plain shape.
var icons := {}
## beat kind -> PackedScene for a themed effect; optional, a default tween is used when absent.
var beat_scenes := {}
## art id -> Texture2D, produced on demand: `func(id: String) -> Texture2D` (null when the theme has no such art). The
## theme owns every path; Themes caches the result.
var texture_source: Callable = Callable()
## id -> StyleBox for nine-slice art (panels, buttons). Optional; the Godot theme normally uses these itself.
var nine_patches := {}
## colour name -> Color. Names a theme need not set fall back to DEFAULT_COLORS.
var colors := {}
## effect name -> Dictionary of parameters (durations in seconds, counts, strengths). A name that is missing or empty
## means "do not play this effect". `"motion": true` marks an effect reduced-motion switches off.
var fx := {}
## The window's clear colour (the area no control paints).
var clear_color := Color(0.3, 0.3, 0.3)

## Neutral colours every screen can rely on. A theme overrides by name.
const DEFAULT_COLORS := {
	"white": Color(1, 1, 1),
	"clear": Color(1, 1, 1, 0),
	"shade": Color(0, 0, 0, 0.5),
	"ink": Color(0.05, 0.06, 0.1),
	"warm": Color(1.0, 0.65, 0.25),
	"cold": Color(0.4, 0.55, 1.0),
	"hit": Color(1.0, 0.25, 0.25),
	"glow": Color(1.0, 0.75, 0.4),
	"star": Color(0.9, 0.93, 1.0),
	"ember": Color(1.0, 0.7, 0.28),
	"fog": Color(0.7, 0.75, 0.9),
	"gold": Color(1.0, 0.84, 0.42),
	"gain": Color(1.0, 0.9, 0.5),
	"loss": Color(1.0, 0.45, 0.4),
	"shield": Color(0.45, 0.85, 0.95),
	"mark": Color(0.85, 0.65, 1.0),
	"ring_track": Color(0.1, 0.12, 0.2),
	"ring_fill": Color(1.0, 0.7, 0.28),
	"ring_urgent": Color(1.0, 0.45, 0.4),
	"lock_fill": Color(1.0, 1.0, 1.0, 0.28),
}


func color(name: String) -> Color:
	if colors.has(name):
		return colors[name]
	return DEFAULT_COLORS.get(name, DEFAULT_COLORS.white)
