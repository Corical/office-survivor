extends Node
## Two real launches against a real file (user://settings_probe.json, never the player's real settings):
##   godot --path godot res://tests/perf/settings_persist.tscn -- --phase=1     turns calm mode on and quits
##   godot --path godot res://tests/perf/settings_persist.tscn -- --phase=2     must start with calm mode already on
## Phase 2 prints SETTINGS PASS and deletes the probe file.

const PROBE := "user://settings_probe.json"


func _ready() -> void:
	var phase := 0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--phase="):
			phase = int(a.trim_prefix("--phase="))
	Themes.settings_store = SessionStore.new(PROBE)          # main.gd then leaves it alone
	Themes.enable_settings(Themes.settings_store)
	add_child(load("res://main.tscn").instantiate())
	await get_tree().process_frame
	await get_tree().process_frame
	if phase == 1:
		print("SETTINGS phase 1 start calm=", Themes.reduced_motion)
		Themes.reduced_motion = true
		print("SETTINGS phase 1 wrote calm=true")
		get_tree().quit(0)
	elif phase == 2:
		var restored := Themes.reduced_motion
		print("SETTINGS phase 2 start calm=", restored)
		print("SETTINGS PASS" if restored else "SETTINGS FAIL")
		DirAccess.remove_absolute(ProjectSettings.globalize_path(PROBE))
		get_tree().quit(0 if restored else 1)
	else:
		print("SETTINGS need --phase=1 or --phase=2")
		get_tree().quit(2)
