class_name SafeJson
extends RefCounted
## JSON.parse_string prints an engine-level ERROR for bad input, which makes a harmless garbage frame look like a
## crash in the log. JSON.new().parse() returns the error silently. Returns null for anything that does not parse.

static func parse(text: String) -> Variant:
	var j := JSON.new()
	if j.parse(text) != OK:
		return null
	return j.data
