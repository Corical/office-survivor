extends Node
## Headless test runner. Run (after `godot --headless --path godot --import`):
##   godot --headless --path godot res://tests/runner.tscn -- --log=<scratch>/test.log [--only=test_session]
## Discovers tests/test_*.gd (classes extending BaseTest), runs every `test_*` method (each may await), and exits 0 on
## success, 1 on any failure or any engine-level error in the log. Per-test timeout 5 s, whole run 90 s (both chosen).

const TEST_TIMEOUT_MS := 5000
const RUN_TIMEOUT_MS := 90000

var passed := 0
var failed := 0


func _ready() -> void:
	var only := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--only="):
			only = a.substr(7)
	await get_tree().process_frame           # autoloads finish _ready before the first test
	var started := Time.get_ticks_msec()
	var files: Array[String] = []
	var dir := DirAccess.open("res://tests")
	for f in dir.get_files():
		if f.begins_with("test_") and f.ends_with(".gd") and (only == "" or f.begins_with(only)):
			files.append(f)
	files.sort()
	var log_mark := Log.mark()
	for f in files:
		var script: GDScript = load("res://tests/" + f)
		var inst: BaseTest = script.new()
		inst.name = f
		add_child(inst)
		var names: Array[String] = []
		for m in script.get_script_method_list():
			if str(m.name).begins_with("test_"):
				names.append(m.name)
		names.sort()
		for n in names:
			if Time.get_ticks_msec() - started > RUN_TIMEOUT_MS:
				_fail(f, n, ["run timeout"])
				continue
			inst.failures.clear()
			inst.setup()
			await _run_one(inst, n)
			inst.teardown()
			if inst.failures.is_empty():
				passed += 1
				print("PASS  %s::%s" % [f, n])
			else:
				_fail(f, n, inst.failures)
		inst.queue_free()
	var engine_errors: Array[String] = []
	for l in Log.since(log_mark, "ERROR"):
		if "[engine]" in l:
			engine_errors.append(l)
	if not engine_errors.is_empty():
		failed += 1
		print("FAIL  engine errors during the run:")
		for l in engine_errors:
			print("      " + l)
	print("\n%d passed, %d failed" % [passed, failed])
	get_tree().quit(0 if failed == 0 else 1)


func _run_one(inst: BaseTest, n: String) -> void:
	var done := [false]
	var go := func():
		await inst.call(n)
		done[0] = true
	go.call()
	var t0 := Time.get_ticks_msec()
	while not done[0] and Time.get_ticks_msec() - t0 < TEST_TIMEOUT_MS:
		await get_tree().process_frame
	if not done[0]:
		inst.failures.append("timed out after %d ms" % TEST_TIMEOUT_MS)


func _fail(f: String, n: String, why: Array) -> void:
	failed += 1
	print("FAIL  %s::%s" % [f, n])
	for w in why:
		print("      " + str(w))
