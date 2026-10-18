class_name Fixtures
extends RefCounted
## Real server views harvested by tools/harvest_fixtures.py (read-only use of the server's own room engine).

const HARVEST := "res://tests/fixtures/harvest.jsonl"
const CODES := "res://tests/fixtures/codes.json"
static var _rows: Array = []


## [{game, pid, me, others, msg, why}], msg already normalised like Net does (whole numbers become ints).
static func rows() -> Array:
	if _rows.is_empty():
		for l in FileAccess.get_file_as_string(HARVEST).split("\n", false):
			var r: Dictionary = SafeJson.parse(l)
			r.msg = Net.normalize(r.msg)
			_rows.append(r)
	return _rows


static func of_type(t: String) -> Array:
	return rows().filter(func(r): return r.msg.t == t)


static func seen_codes() -> Dictionary:
	return SafeJson.parse(FileAccess.get_file_as_string(CODES))
