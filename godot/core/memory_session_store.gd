class_name MemorySessionStore
extends SessionStore
## Test double: keeps the data in memory, never touches user://.

var data := {}
var saves := 0


func load_data() -> Dictionary:
	return data.duplicate()


func save_data(d: Dictionary) -> bool:
	data = d.duplicate()
	data["v"] = VERSION
	saves += 1
	return true
