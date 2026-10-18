class_name Stage
extends Control
## The reveal as a picture: one home per player on a ring (me at the bottom), and the night's beats played on it by the
## pure Timeline. Knows beat kinds and endpoints only: no game words, no colours (all from the theme's "Stage" type),
## no ordering that could say who joined when (homes are placed from the alias-sorted roster).
##
## Privacy by construction: another player's food is never drawn as a number (a band word, from the model), and an
## unnamed actor (@offstage) comes in from outside the ring, belonging to no home.

const ME := "@me"                       # the adapter's markers for "I" and "someone unnamed" (a test keeps these equal)
const OFFSTAGE := "@offstage"

var _roster: Array = []
var _beats: Array = []
var _timeline: Timeline
var _model: Dictionary = {}
var _pos := {}                          # alias -> Vector2, and ME -> my position
var _food_mine := 0
var _applied := 0                       # how many beats' effects are already in _food_mine / _shields
var _shields := {}
var _out := {}                          # aliases currently marked as outcasts by a finished status beat


func _ready() -> void:
	custom_minimum_size = Vector2(0, 390)
	resized.connect(_layout)
	Feed.model_changed.connect(_on_model)
	_load()


func _on_model(kind: String, _m: Dictionary) -> void:
	if kind == "reveal":
		_load()


func _load() -> void:
	_model = Feed.models.get("reveal", {})
	if _model.is_empty():
		return
	_roster = _model.roster
	_beats = _model.beats
	_timeline = Feed.player.timeline
	_shields = {}
	_out = {}
	_applied = 0
	var t: Dictionary = _model.totals
	var animated := _timeline != null and not _timeline.finished and t.before != null
	_food_mine = int(t.before) if animated else int(t.after if t.after != null else (t.before if t.before != null else 0))
	if _timeline != null and (_timeline.finished or t.before == null):
		_applied = _beats.size()                  # snapped: effects are already in the final numbers
	_layout()
	queue_redraw()


func _layout() -> void:
	_pos = {}
	var c := size / 2.0 + Vector2(0, 26)                   # room above the ring for the caption
	var r := minf(size.x, size.y) * 0.30
	var others: Array = _roster.filter(func(e): return not e.is_me)
	for e in _roster:
		if e.is_me:
			_pos[e.alias] = c + Vector2(0, r)
			_pos[ME] = c + Vector2(0, r)
	for i in others.size():
		var angle := PI / 2.0 + TAU * float(i + 1) / float(others.size() + 1)
		_pos[others[i].alias] = c + Vector2(cos(angle), sin(angle)) * r
	set_meta("centre", c)
	set_meta("radius", r)


func _process(delta: float) -> void:
	if _timeline == null or _model.is_empty():
		return
	_timeline.advance(delta * 1000.0)
	_apply_done()
	queue_redraw()


## Fold the effects of every beat that has finished into what is drawn (my food, shields, outcasts).
func _apply_done() -> void:
	var upto: int = _beats.size() if _timeline.finished else _timeline.index
	while _applied < upto:
		var b: Dictionary = _beats[_applied]
		match b.kind:
			"move_resource":
				if b.to == ME:
					_food_mine += int(b.amount_in)
				if b.from == ME:
					_food_mine -= int(b.amount_out)
			"total":
				_food_mine = int(b.amount_in)
			"shield_on":
				_shields[b.to] = true
			"shield_off":
				_shields.erase(b.to)
			"status":
				if b.style == "enter":
					_out[b.to] = true
				else:
					_out.erase(b.to)
		_applied += 1


## What the Stage is showing, for tests: the current beat and my displayed food.
func describe() -> Dictionary:
	var cur: Dictionary = _timeline.current() if _timeline != null else {}
	return {"beat": cur.get("kind", ""), "from": cur.get("from", ""), "to": cur.get("to", ""), "my_food": _food_mine,
		"finished": _timeline == null or _timeline.finished, "applied": _applied}


func where(endpoint: String, toward: String = "") -> Vector2:
	if endpoint == OFFSTAGE:
		var c: Vector2 = get_meta("centre", size / 2.0)
		var dir := ((_pos.get(toward, c) as Vector2) - c).normalized()
		if dir == Vector2.ZERO:
			dir = Vector2.UP
		return c + dir * float(get_meta("radius", 100.0)) * 2.4          # outside the ring, belonging to nobody
	return _pos.get(endpoint, size / 2.0)


func _draw() -> void:
	if _model.is_empty():
		return
	var font := get_theme_default_font()
	var fs := get_theme_default_font_size()
	var col_text := get_theme_color("text", "Stage")
	var col_home := get_theme_color("home", "Stage")
	var col_me := get_theme_color("home_me", "Stage")
	var col_food := get_theme_color("food", "Stage")
	var col_loss := get_theme_color("loss", "Stage")
	var col_shield := get_theme_color("shield", "Stage")
	var col_mark := get_theme_color("marked", "Stage")
	var cur: Dictionary = _timeline.current() if _timeline != null else {}
	var p: float = _timeline.beat_progress() if _timeline != null else 1.0
	var radius_home := 26.0

	if cur.get("kind") == "camp":
		var tint := col_mark
		tint.a = 0.18 * sin(p * PI)
		draw_rect(Rect2(Vector2.ZERO, size), tint)
	for e in _roster:
		var at: Vector2 = _pos[e.alias]
		draw_circle(at, radius_home, col_me if e.is_me else col_home)
		if _shields.has(e.alias) or _shields.has(ME) and e.is_me:
			draw_arc(at, radius_home + 6, 0, TAU, 40, col_shield, 3.0)
		if _out.has(e.alias) or (_out.has(ME) and e.is_me):
			draw_arc(at, radius_home + 12, 0, TAU, 40, col_loss, 2.0)
		var label: String = e.alias
		if e.is_me:
			label += "  " + str(_food_mine)
		elif e.band != "":
			label += "  " + Words.render(e.band)
		draw_string(font, at + Vector2(-70, radius_home + 22), label, HORIZONTAL_ALIGNMENT_CENTER, 140, fs - 4, col_text)

	if cur.is_empty():
		return
	var to_pos := where(cur.to, cur.from)
	var from_pos := where(cur.from, cur.to)
	var eased := p * p * (3.0 - 2.0 * p)
	match cur.kind:
		"move_resource":
			var at := from_pos.lerp(to_pos, eased)
			draw_circle(at, 10.0, col_food)
			var amt: int = int(cur.amount_in) if cur.to == ME or cur.from == OFFSTAGE else int(cur.amount_out)
			draw_string(font, at + Vector2(12, -8), "%d" % amt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col_text)
		"blocked":
			draw_arc(to_pos, radius_home + 8, 0, TAU, 40, col_shield, 4.0)
			draw_line(to_pos + Vector2(-14, -14), to_pos + Vector2(14, 14), col_loss, 4.0)
			draw_line(to_pos + Vector2(-14, 14), to_pos + Vector2(14, -14), col_loss, 4.0)
		"empty":
			draw_arc(to_pos, radius_home - 6, 0, TAU, 32, col_text, 2.0)
		"learn":
			draw_line(from_pos, to_pos, col_text, 2.0)
		"marked":
			draw_arc(to_pos, radius_home + 10, 0, TAU, 40, col_mark, 4.0 + 2.0 * sin(p * PI))
		"status":
			draw_arc(to_pos, radius_home + 12, 0, TAU, 40, col_loss, 3.0)
		"shield_on", "shield_off":
			draw_arc(to_pos, radius_home + 6 + 6.0 * p, 0, TAU, 40, col_shield, 3.0)
		"charm":
			var d := 10.0
			draw_colored_polygon(PackedVector2Array([to_pos + Vector2(0, -d), to_pos + Vector2(d, 0), to_pos + Vector2(0, d),
				to_pos + Vector2(-d, 0)]), col_mark)
		"total":
			draw_arc(_pos.get(ME, size / 2.0), radius_home + 4, 0, TAU, 40, col_food, 3.0)
	# the line being played, in the theme's words (also what a screen reader would read)
	var li: int = int(cur.get("line_index", -1))
	if li >= 0 and li < _model.lines.size():
		var ln: Dictionary = _model.lines[li]
		draw_multiline_string(font, Vector2(8, 20), Words.render(ln.key, ln.slots), HORIZONTAL_ALIGNMENT_LEFT, size.x - 16, fs - 3, 2, col_text)
