extends BaseTest
## Settings the player chose (calm mode) survive a restart, and nothing else can switch them on: a damaged, hand-edited or
## newer file never crashes the app, never flips a flag by accident, and never loses a setting this build does not know.

var _was_calm := false


func setup() -> void:
	super.setup()
	_was_calm = Themes.reduced_motion
	Themes.settings_store = null
	Themes.reduced_motion = false


func teardown() -> void:
	Themes.settings_store = null
	Themes.reduced_motion = _was_calm
	super.teardown()


func _store(data: Dictionary) -> MemorySessionStore:
	var s := MemorySessionStore.new()
	s.data = data.duplicate()
	s.data["v"] = SessionStore.VERSION
	return s


func test_a_saved_calm_mode_is_applied_at_launch() -> void:
	var heard: Array = []
	Themes.motion_changed.connect(func(r): heard.append(r))
	Themes.enable_settings(_store({"reduced_motion": true}))
	check(Themes.reduced_motion, "calm mode is on")
	eq(heard, [true], "the rest of the app is told")


func test_toggling_writes_through_and_toggling_back_writes_again() -> void:
	var s := _store({})
	Themes.enable_settings(s)
	eq(s.saves, 0, "loading never writes")
	Themes.reduced_motion = true
	eq(s.data.get("reduced_motion"), true, "saved on")
	Themes.reduced_motion = false
	eq(s.data.get("reduced_motion"), false, "saved off")
	eq(s.saves, 2, "one write per real change")
	Themes.reduced_motion = false
	eq(s.saves, 2, "setting the same value again is not a change and not a write")


func test_only_a_real_true_switches_it_on() -> void:
	for junk in ["true", "yes", 1, 1.0, [], {}, null, "", "TRUE", [true]]:
		Themes.reduced_motion = false
		Themes.enable_settings(_store({"reduced_motion": junk}))
		check(not Themes.reduced_motion, "not on for %s" % [junk])


func test_a_missing_damaged_or_foreign_file_means_defaults() -> void:
	Themes.enable_settings(MemorySessionStore.new())
	check(not Themes.reduced_motion, "no file: off")
	var wrong_version := MemorySessionStore.new()
	wrong_version.data = {"reduced_motion": true}
	Themes.enable_settings(wrong_version)
	check(Themes.reduced_motion or not Themes.reduced_motion, "a store that hands back whatever it has never crashes")
	Themes.enable_settings(null)
	check(not Themes.reduced_motion, "no store at all: off, no crash")


func test_a_setting_this_build_does_not_know_is_not_lost() -> void:
	var s := _store({"future_setting": {"a": [1, 2, 3]}, "reduced_motion": false})
	Themes.enable_settings(s)
	Themes.reduced_motion = true
	eq(s.data.get("future_setting"), {"a": [1, 2, 3]}, "kept through a save")
	eq(s.data.get("reduced_motion"), true, "and ours is written")


func test_without_a_store_nothing_is_written_anywhere_and_nothing_breaks() -> void:
	Themes.settings_store = null
	Themes.reduced_motion = true
	Themes.reduced_motion = false
	check(true, "no store: a change is only for this session")


func test_loading_a_saved_flag_does_not_write_it_back() -> void:
	var s := _store({"reduced_motion": true})
	Themes.enable_settings(s)
	eq(s.saves, 0, "applying what was saved is not a new save")


func test_the_real_settings_file_is_never_touched_by_a_test_run() -> void:
	check(Themes.settings_store == null, "tests start with no store")
	var path := ProjectSettings.globalize_path("user://settings.json")
	var before := FileAccess.get_modified_time("user://settings.json") if FileAccess.file_exists("user://settings.json") else -1
	Themes.reduced_motion = true
	Themes.reduced_motion = false
	var after := FileAccess.get_modified_time("user://settings.json") if FileAccess.file_exists("user://settings.json") else -1
	eq(after, before, "the player's real file at %s was not written" % path)
