class_name Timeline
extends RefCounted
## The reveal as a pure state machine over beats. The Stage reads current() and tweens visuals; nothing here uses
## Tween, Timer or engine time, so tests drive it with advance(ms).

const DEFAULT_MS := 1000       # chosen: one beat on screen
const SHORT_MS := 400          # chosen: bookkeeping beats ("you now have N")
const QUIET_MS := 800          # chosen

var round := -1
var beats: Array = []
var index := 0
var elapsed_ms := 0.0
var finished := false


## `snap` = start already finished (no before-state, or we resumed late): the end state is shown, nothing invented.
func _init(r: int, b: Array, snap := false) -> void:
	round = r
	beats = b
	finished = snap or b.is_empty()
	if finished:
		index = beats.size()


static func duration_ms(beat: Dictionary) -> float:
	match beat.get("kind"):
		"total":
			return SHORT_MS
		"quiet":
			return QUIET_MS
	return DEFAULT_MS


func current() -> Dictionary:
	return {} if finished else beats[index]


func advance(dt_ms: float) -> void:
	if finished:
		return
	elapsed_ms += dt_ms
	while not finished and elapsed_ms >= duration_ms(beats[index]):
		elapsed_ms -= duration_ms(beats[index])
		_next()


func skip() -> void:
	if not finished:
		elapsed_ms = 0.0
		_next()


func snap_to_end() -> void:
	index = beats.size()
	elapsed_ms = 0.0
	finished = true


## 0..1 within the current beat, for the Stage to ease with.
func beat_progress() -> float:
	return 1.0 if finished else clampf(elapsed_ms / duration_ms(beats[index]), 0.0, 1.0)


func _next() -> void:
	index += 1
	if index >= beats.size():
		index = beats.size()
		finished = true
