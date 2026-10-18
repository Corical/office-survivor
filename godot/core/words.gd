class_name Words
extends RefCounted
## All player-facing text comes through here: a translation key plus typed slots, rendered with the active theme's
## Translation (a .po file). Screens and the adapter never contain a sentence.
##
## Slot values: a plain value, or {"key": "<translation key>"} (translated first, e.g. a move word), or
## {"list": [..]} (joined the theme's way: "3", "3 and 4", "3, 4 and 5").

static var translation: Translation
static var missing_seen := {}


static func use(t: Translation) -> void:
	translation = t
	missing_seen = {}


static func has(key: String) -> bool:
	return translation != null and str(translation.get_message(key)) != ""


static func keys() -> Array[String]:
	var out: Array[String] = []
	if translation:
		for k in translation.get_message_list():
			out.append(str(k))
	return out


## The words for `key` with `slots` filled in. A missing key renders as "[key]" (visible, never silent) and is logged
## once, so a theme gap shows up in testing instead of as an empty label.
static func render(key: String, slots := {}) -> String:
	var msg := str(translation.get_message(key)) if translation else ""
	if msg == "":
		if not missing_seen.has(key):
			missing_seen[key] = true
			Log.event("words", "missing_key", {"key": key}, "WARN")
		return "[%s]" % key
	return fill(msg, _prepare(slots))


static var _slot_rx: RegEx


## Replace {name} in one pass. A value is never re-scanned, so an alias like "{amount}" stays literal text.
## A {name} with no value stays visible as written, so a missing slot shows up in testing.
static func fill(template: String, values: Dictionary) -> String:
	if _slot_rx == null:
		_slot_rx = RegEx.create_from_string("\\{(\\w+)\\}")
	var out := ""
	var pos := 0
	for m in _slot_rx.search_all(template):
		out += template.substr(pos, m.get_start() - pos)
		var name := m.get_string(1)
		out += str(values[name]) if values.has(name) else m.get_string()
		pos = m.get_end()
	return out + template.substr(pos)


static func _prepare(slots: Dictionary) -> Dictionary:
	var out := {}
	for k in slots:
		var v: Variant = slots[k]
		if v == null:
			out[k] = ""                       # a missing value renders as nothing, never as "<null>"
			continue
		if v is Dictionary:
			if v.has("key"):
				out[k] = render(str(v.key))
			elif v.has("list"):
				out[k] = join_list(v.list)
			else:
				out[k] = str(v)
		else:
			out[k] = str(v)
	return out


static func join_list(items: Array) -> String:
	var parts: Array[String] = []
	for i in items:
		parts.append(str(i))
	match parts.size():
		0:
			return ""
		1:
			return parts[0]
		_:
			return "%s %s %s" % [", ".join(parts.slice(0, parts.size() - 1)), render("list.and"), parts.back()]
