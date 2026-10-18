extends RefCounted
## The placeholder theme: plain words and shapes, no art. The default and the test theme.

static func build() -> ThemeDef:
	var t := ThemeDef.new()
	t.id = "placeholder"
	t.title = "Plain"
	t.words = load("res://themes/placeholder/words.po")
	return t
