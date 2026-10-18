extends Node
## Every push_error, push_warning, engine error, network problem and inbound/outbound message goes to a log file
## (and stdout for our own lines), so a test run or the autopilot can read and classify them.
## The engine's own errors arrive through a Logger registered with OS.add_logger; they already print to stderr, so
## the sink only writes the file. Path: `user://client.log`, or `--log=<path>` after `--` on the command line
## (tests use their own file so they never wipe the player's log).

const DEFAULT_PATH := "user://client.log"
const KEEP := 2000                     # chosen: lines held in memory for tests

var path := DEFAULT_PATH
var lines: Array[String] = []
var counts := {"INFO": 0, "WARN": 0, "ERROR": 0}
var total := 0                         # lines ever written, so a mark survives the ring buffer dropping old lines

var _file: FileAccess
var _mutex := Mutex.new()
var _sink: _Sink


class _Sink extends Logger:
	var log_node

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
		var level := "WARN" if error_type == ERROR_TYPE_WARNING else "ERROR"
		var what := rationale if rationale != "" else code
		log_node.write_line(level, "engine", "%s (%s:%d in %s)" % [what, file, line, function], false)

	func _log_message(_message: String, _error: bool) -> void:
		pass


func _init() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--log="):
			path = a.substr(6)
	_file = FileAccess.open(path, FileAccess.WRITE)     # one log per run
	_sink = _Sink.new()
	_sink.log_node = self
	OS.add_logger(_sink)
	event("log", "start", {"build": ProjectSettings.get_setting("application/config/version"),
		"debug": OS.is_debug_build(), "os": OS.get_name(), "path": path})


func _exit_tree() -> void:
	OS.remove_logger(_sink)


## Structured line: `name key=value key=value`. Values are written with str(); strings with spaces are quoted.
func event(tag: String, name: String, fields := {}, level := "INFO") -> void:
	var parts := [name]
	for k in fields:
		var v := str(fields[k])
		parts.append("%s=%s" % [k, ('"%s"' % v) if " " in v else v])
	write_line(level, tag, " ".join(parts))


func info(tag: String, msg: String) -> void:
	write_line("INFO", tag, msg)


func warn(tag: String, msg: String) -> void:
	write_line("WARN", tag, msg)


func error(tag: String, msg: String) -> void:
	write_line("ERROR", tag, msg)


func write_line(level: String, tag: String, msg: String, echo := true) -> void:
	var t := Time.get_datetime_string_from_system()
	var text := "%s.%03d %s [%s] %s" % [t, Time.get_ticks_msec() % 1000, level, tag, msg]
	_mutex.lock()
	lines.append(text)
	if lines.size() > KEEP:
		lines.remove_at(0)
	total += 1
	counts[level] = counts.get(level, 0) + 1
	if _file:
		_file.store_line(text)
		_file.flush()
	_mutex.unlock()
	if echo:
		if level == "INFO":
			print(text)
		else:
			printerr(text)


## A mark for `since`: the number of lines written so far.
func mark() -> int:
	return total


## Lines at `level` (or all) written after `mark`, as far back as the ring buffer still holds.
func since(m: int, level := "") -> Array[String]:
	var out: Array[String] = []
	_mutex.lock()
	var first := total - lines.size()
	for i in range(maxi(m, first), total):
		var s := lines[i - first]
		if level == "" or (" %s [" % level) in s:
			out.append(s)
	_mutex.unlock()
	return out
