class_name RulesetRegistry
extends RefCounted
## One line per game. `preload` (not a directory listing) so exports carry the scripts.

const DEFAULT_ID := "survivors"
const RULESETS := {
	"survivors": preload("res://rulesets/survivors/ruleset.gd"),
}


static func has(id: Variant) -> bool:
	return id is String and RULESETS.has(id)


## The ruleset for `id`, or null when this client does not know the game (it must not be played as another game).
static func try_make(id: Variant) -> Ruleset:
	return RULESETS[id].new() if has(id) else null


static func make(id := DEFAULT_ID) -> Ruleset:
	var script: GDScript = RULESETS.get(id, RULESETS[DEFAULT_ID])
	return script.new()
