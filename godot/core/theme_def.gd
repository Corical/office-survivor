class_name ThemeDef
extends RefCounted
## What a theme is: the words, a Godot Theme for the look, and the icons. Screens never touch these directly: words
## come through Words, the look through the root Theme, icons through Themes.icon().

var id := ""
var title := ""
var words: Translation
var godot_theme: Theme = Theme.new()
## icon id (a beat kind, a move id, a band id...) -> Texture2D. A missing id is fine: the Stage draws a plain shape.
var icons := {}
## beat kind -> PackedScene for a themed effect; optional, a default tween is used when absent.
var beat_scenes := {}
