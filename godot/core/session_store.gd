class_name SessionStore
extends RefCounted
## The seat-token store port. Default: a versioned JSON file written atomically (temp file, then rename), so a crash
## mid-write never loses the seat. `MemorySessionStore` is the test double.

const VERSION := 1

var path := "user://session.json"


func _init(p := "user://session.json") -> void:
	path = p


func load_data() -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var data: Variant = SafeJson.parse(FileAccess.get_file_as_string(path))
	if not (data is Dictionary):
		Log.event("store", "unreadable", {"path": path})
		return {}
	if int(data.get("v", 0)) != VERSION:
		Log.event("store", "version_mismatch", {"path": path, "v": data.get("v")})
		return {}
	return data


func save_data(data: Dictionary) -> bool:
	var out := data.duplicate()
	out["v"] = VERSION
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		Log.event("store", "write_failed", {"path": tmp, "error": FileAccess.get_open_error()}, "ERROR")
		return false
	f.store_string(JSON.stringify(out))
	f.close()
	var err := DirAccess.rename_absolute(ProjectSettings.globalize_path(tmp), ProjectSettings.globalize_path(path))
	if err != OK:
		Log.event("store", "rename_failed", {"path": path, "error": err}, "ERROR")
		return false
	return true
