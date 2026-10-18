class_name RulesetRegistry
extends RefCounted
## One line per game. `preload` (not a directory listing) so exports carry the scripts.

const DEFAULT_ID := "survivors"
const RULESETS := {
	"survivors": preload("res://rulesets/survivors/ruleset.gd"),
}


static func make(id := DEFAULT_ID) -> Ruleset:
	var script: GDScript = RULESETS.get(id, RULESETS[DEFAULT_ID])
	return script.new()
