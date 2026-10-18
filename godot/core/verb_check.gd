class_name VerbCheck
extends RefCounted
## The client's own look at an `act` before it goes out, against the ruleset's verb table. It mirrors the server's strict
## check (arena/platform/manifest.py) so a bad call is refused here with a short reason instead of costing a round trip.
## The server still checks everything: this is a courtesy and a guard against our own mistakes, never the authority.

## An argument is never named like a seat, player or secret (the server knows who you are from the connection).
const FORBIDDEN_ARG_NAMES := ["seat", "pid", "player", "player_id", "seat_id", "user", "user_id", "token", "seed", "sim"]
const DEFAULT_MAX_LEN := 64        # matches the server's ArgSpec default


## "" when `verb` with `args` is well-formed for `verbs`, else a reason: unknown_verb | bad_args | forbidden_arg.
static func check(verbs: Dictionary, verb: Variant, args: Variant) -> String:
	if not (verb is String) or not verbs.has(verb):
		return "unknown_verb"
	if not (args is Dictionary):
		return "bad_args"
	var specs: Dictionary = verbs[verb]
	for k in args:
		if not (k is String):
			return "bad_args"
		if k.to_lower() in FORBIDDEN_ARG_NAMES:
			return "forbidden_arg"
		if not specs.has(k):
			return "bad_args"
	for k in specs:
		var spec: Dictionary = specs[k]
		if not args.has(k):
			if not bool(spec.get("optional", false)):
				return "bad_args"
			continue
		if _bad_value(args[k], spec):
			return "bad_args"
	return ""


static func _bad_value(v: Variant, spec: Dictionary) -> bool:
	if v == null:
		return not bool(spec.get("nullable", false))
	match str(spec.get("type", "")):
		"int":
			if typeof(v) != TYPE_INT:                # a boolean, a float and a numeric string are not integers
				return true
			if spec.has("min") and v < int(spec.min):
				return true
			if spec.has("max") and v > int(spec.max):
				return true
		"str":
			if typeof(v) != TYPE_STRING or v.length() > int(spec.get("max_len", DEFAULT_MAX_LEN)):
				return true
		"bool":
			if typeof(v) != TYPE_BOOL:
				return true
		_:
			return true                               # a spec the client does not understand allows nothing
	var choices: Array = spec.get("choices", [])
	return not choices.is_empty() and not (v in choices)
