class_name SurvivorsAdapter
extends RefCounted
## The only place that knows the Survivors protocol: contract field names, line codes, move ids, bands, goal codes.
## It turns server views into NEUTRAL models (what screens consume) and line codes into atomic beats (what the Stage
## animates). Output carries translation keys and typed slots, never sentences, colours or asset paths.
##
## Pure functions: no nodes, no engine singletons except Log (unknown inputs are logged once each).

const OFFSTAGE := "@offstage"          # an unnamed actor, or the world: animates from the screen edge, never a home
const ME := "@me"
const LINES_PATH := "res://rulesets/survivors/lines_en.json"
const MOVES := ["scavenge", "guard", "steal", "investigate", "gift"]
const UNTARGETED := ["scavenge", "guard"]     # legal[kind] == [] is ambiguous; the server has no flag yet (note 6)
const BANDS := ["well_fed", "getting_by", "starving", "bandit"]
const GOALS := ["beat", "robbed2_extract", "steal3_clean", "give", "grudge", "detective"]
const RADIO := ["saw", "trust", "lying", "guarding", "easy", "innocent", "watch", "me"]
## Arg name -> how a theme must treat it. Everything not listed passes through as a plain value.
const SLOT_TYPES := {"saw": "move", "nights": "list"}
const END_COLUMNS := [
	{"id": "score", "highlight": true}, {"id": "rations", "highlight": true}, {"id": "stole", "highlight": true},
	{"id": "gave_away", "highlight": true},
	{"id": "times_robbed", "highlight": false},     # owner: praise only; shown, never ranked or highlighted
]
const SYNTH_QUIET := "news_quiet"     # the server sends news: [] for a quiet night
const GOAL_STATES := ["open", "done", "failed", "end"]
const UNKNOWN_LOG_CAP := 64           # chosen: distinct unknown values logged per run, so a hostile server cannot flood
## Every beat kind the adapter can emit; the Stage must handle each (a test checks both directions).
const BEAT_KINDS := ["move_resource", "shield_on", "shield_off", "blocked", "empty", "learn", "marked", "status", "camp",
	"charm", "total", "quiet", "event", "unknown"]
## Wilderness events (MECHANICS section 5; the server sends the id, the scope and who it hit beside the sentence).
const EVENT_FIND := {"bananas": 1, "coconut": 1, "cache": 2}        # one player finds food (created)
const EVENT_LOSE := {"snake": 1, "rain": 1, "raid": 2}              # one player loses food (destroyed)
const EVENT_CAMP := ["storm", "feast", "rats", "rats_top"]          # happens to the whole camp
const EVENT_CAMP_TAKES := {"rats": 1, "rats_top": 1}                # what a camp event takes from each player it hits

static var _seen_unknown := {}
static var _codes: Dictionary = {}


# ---------------- vocabulary ----------------

static func line_codes() -> Array:
	if _codes.is_empty():
		var data: Variant = SafeJson.parse(FileAccess.get_file_as_string(LINES_PATH))
		_codes = data if data is Dictionary else {}
	return _codes.keys()


## Every translation key this adapter can ever emit. The theme completeness test compares a theme against this.
static func all_keys() -> Array[String]:
	var out: Array[String] = ["line.unknown", "line.now_have.one", "list.and", "resource.ration", "status.outcast",
		"status.shield", "move.unknown", "move.unknown.choice", "move.unknown.help", "band.unknown", "goal.unknown",
		"radio.unknown", "goal.state.unknown"]
	for c in line_codes():
		out.append("line." + c)
	for s in GOAL_STATES:
		out.append("goal.state." + s)
	for col in END_COLUMNS:
		out.append("column." + col.id)
	for m in MOVES:
		out.append_array(["move." + m, "move.%s.choice" % m, "move.%s.help" % m])
	for b in BANDS:
		out.append("band." + b)
	for g in GOALS:
		out.append("goal." + g)
	for r in RADIO:
		out.append("radio." + r)
	return out


static func _unknown(kind: String, value: String) -> void:
	var k := kind + ":" + value
	if _seen_unknown.has(k):
		return
	if _seen_unknown.size() >= UNKNOWN_LOG_CAP:
		if _seen_unknown.size() == UNKNOWN_LOG_CAP:
			_seen_unknown["@capped"] = true
			Log.event("adapter", "unknown_log_capped", {"cap": UNKNOWN_LOG_CAP}, "WARN")
		return
	_seen_unknown[k] = true
	Log.event("adapter", "unknown_" + kind, {"value": value}, "WARN")


static func forget_unknowns() -> void:
	_seen_unknown = {}


# ---------------- beats ----------------

static func _beat(kind: String, from_ := OFFSTAGE, to := OFFSTAGE, style := "") -> Dictionary:
	return {"kind": kind, "from": from_, "to": to, "amount_out": 0, "amount_in": 0, "style": style, "detail": ""}


static func _mv(from_: String, to: String, out_: int, in_ := -1, style := "") -> Dictionary:
	var b := _beat("move_resource", from_, to, style)
	b.amount_out = out_
	b.amount_in = out_ if in_ < 0 else in_
	return b


## Args come from the network: any key may be missing, null or the wrong type. These never raise.
static func _n(a: Dictionary, k: String) -> int:
	var v: Variant = a.get(k)
	match typeof(v):
		TYPE_INT:
			return v
		TYPE_FLOAT:
			return int(v) if is_finite(v) else 0
		TYPE_STRING:
			return v.to_int() if v.is_valid_int() else 0
	return 0


static func _s(a: Dictionary, k: String) -> String:
	var v: Variant = a.get(k)
	return "" if v == null else str(v)


## A wilderness event as one beat. The sentence travels along as `detail` so a theme with no words of its own for the
## event can still show it. An event the client does not know, or one with no `who`, is the generic event beat.
static func _event_beat(a: Dictionary) -> Dictionary:
	var ev := _s(a, "event")
	var who := _s(a, "who")
	var b: Dictionary
	if ev in EVENT_FIND and who != "":
		b = _mv(OFFSTAGE, who, EVENT_FIND[ev], -1, ev)
	elif ev in EVENT_LOSE and who != "":
		b = _mv(who, OFFSTAGE, EVENT_LOSE[ev], -1, ev)
	elif ev == "shelter" and who != "":
		b = _beat("shield_off", who, who, ev)
	elif ev in EVENT_CAMP:
		b = _beat("camp", OFFSTAGE, OFFSTAGE, ev)
	else:
		b = _beat("event", OFFSTAGE, OFFSTAGE, ev)
	b.detail = plain_sentence(_s(a, "line"))
	return b


## One server line becomes one or more atomic beats. `a` is the line's args.
static func beats_for(code: String, a: Dictionary) -> Array:
	match code:
		"scavenged":
			return [_mv(OFFSTAGE, ME, _n(a, "found"), -1, "scavenge")]
		"scavenged_auto":
			return [_mv(OFFSTAGE, ME, _n(a, "found"), -1, "scavenge_auto")]
		"found_watching_1", "found_watching_n":
			return [_mv(OFFSTAGE, ME, _n(a, "found"), -1, "watch")]
		"ate":
			return [_mv(ME, OFFSTAGE, _n(a, "amount"), -1, "eat")]
		"feast":
			return [_beat("camp", OFFSTAGE, OFFSTAGE, "feast")]
		"now_have":
			var t := _beat("total", OFFSTAGE, ME)
			t.amount_in = _n(a, "rations")
			return [t]
		"guard_up_1", "guard_up_n":
			return [_beat("shield_on", ME, ME)]
		"stole":
			return [_mv(_s(a, "target"), ME, _n(a, "amount"), -1, "steal")]
		"steal_empty":
			return [_beat("empty", ME, _s(a, "target"))]
		"steal_split":
			return [_beat("empty", ME, _s(a, "target"), "split")]
		"steal_caught":
			return [_beat("blocked", ME, _s(a, "target"), "guard"), _mv(ME, _s(a, "target"), _n(a, "paid"), -1, "fine")]
		"robbed":
			return [_mv(ME, OFFSTAGE, _n(a, "amount"), -1, "robbed")]
		"caught_thief_paid", "caught_thief_paid_since":
			return [_beat("blocked", _s(a, "thief"), ME, "guard"), _mv(_s(a, "thief"), ME, _n(a, "got"), -1, "fine")]
		"caught_thief_broke", "caught_thief_broke_since":
			return [_beat("blocked", _s(a, "thief"), ME, "guard")]
		"watched", "watched_target":
			var w := _beat("learn", ME, _s(a, "target"), _s(a, "saw"))
			w.detail = _s(a, "saw_target")
			return [w]
		"exposed_by_me":
			return [_beat("marked", ME, _s(a, "thief"), "exposed"), _mv(_s(a, "thief"), ME, _n(a, "paid"), -1, "bounty")]
		"exposed_me":
			return [_beat("marked", OFFSTAGE, ME, "exposed"), _mv(ME, OFFSTAGE, _n(a, "paid"), -1, "bounty")]
		"exposed_me_back":
			return [_beat("marked", OFFSTAGE, ME, "exposed"), _mv(ME, OFFSTAGE, _n(a, "paid"), -1, "bounty"),
				_mv(ME, _s(a, "victim"), _n(a, "back"), -1, "return")]
		"exposed_own_back":
			return [_mv(_s(a, "thief"), ME, _n(a, "back"), -1, "return")]
		"thief_exposed_for_me":
			return [_beat("marked", OFFSTAGE, _s(a, "thief"), "exposed"),
				_mv(_s(a, "thief"), ME, _n(a, "back"), -1, "return")]
		"gave":
			return [_mv(ME, _s(a, "receiver"), _n(a, "amount"), -1, "gift")]
		"got_gift":
			return [_mv(_s(a, "giver"), ME, _n(a, "amount"), -1, "gift")]
		"got_gift_bonus":
			return [_mv(_s(a, "giver"), ME, _n(a, "amount"), _n(a, "total"), "gift")]
		"became_bandit_me":
			return [_beat("status", ME, ME, "enter")]
		"rejoined_me":
			return [_beat("status", ME, ME, "exit")]
		"idol_found":
			return [_beat("charm", ME, ME)]
		"idol_saved":
			return [_beat("blocked", OFFSTAGE, ME, "idol")]
		"idol_blocked":
			return [_beat("blocked", ME, _s(a, "target"), "idol")]
		"event":
			return [_event_beat(a)]
		"news_hit_1", "news_hit_n":
			return [_mv(_s(a, "victim"), OFFSTAGE, _n(a, "total"), -1, "hit")]
		"news_break_in_empty":
			return [_beat("empty", OFFSTAGE, _s(a, "victim"))]
		"news_caught":
			return [_beat("blocked", _s(a, "thief"), _s(a, "target"), "guard"),
				_mv(_s(a, "thief"), _s(a, "target"), _n(a, "paid"), -1, "fine")]
		"news_exposed":
			return [_beat("marked", OFFSTAGE, _s(a, "thief"), "exposed"),
				_mv(_s(a, "thief"), OFFSTAGE, _n(a, "paid"), -1, "bounty")]
		"news_exposed_back":
			return [_beat("marked", OFFSTAGE, _s(a, "thief"), "exposed"),
				_mv(_s(a, "thief"), OFFSTAGE, _n(a, "paid"), -1, "bounty"),
				_mv(_s(a, "thief"), _s(a, "victim"), _n(a, "back"), -1, "return")]
		"news_bandit":
			return [_beat("status", _s(a, "player"), _s(a, "player"), "enter")]
		"news_rejoined":
			return [_beat("status", _s(a, "player"), _s(a, "player"), "exit")]
		"news_idol":
			return [_beat("blocked", OFFSTAGE, _s(a, "player"), "idol")]
		"news_quiet":
			return [_beat("quiet")]
	return [_beat("unknown")]


## One server line -> {code, key, slots, beats, source}. Unknown codes degrade to a neutral line + an unknown beat.
static func line(code: String, args: Dictionary, source := "private") -> Dictionary:
	var known := code in line_codes()
	if not known:
		_unknown("line_code", code)
	var slots := slots_for(args)
	var key := ("line." + code) if known else "line.unknown"
	if code == "now_have" and _n(args, "rations") == 1:
		key = "line.now_have.one"          # "1 ration", not "1 rations"
	var beats: Array = beats_for(code, args) if known else [_beat("unknown")]
	if known and is_text_only(code):
		beats = []                          # goal and progress wording is text for a card, never something that happens
	# a camp event that took food from EVERY holder reaches me in my private lines only when it took from me
	if known and code == "event" and source == "private" and _s(args, "scope") == "camp":
		var takes: int = EVENT_CAMP_TAKES.get(_s(args, "event"), 0)
		if takes > 0:
			beats.append(_mv(ME, OFFSTAGE, takes, -1, _s(args, "event")))
	return {"code": code, "key": key, "slots": slots, "beats": beats, "source": source, "covered": false}


## The server's table also holds the wording of goals and goal progress (`goal_*`, `progress_*`). They are worded onto
## a card, not played in a reveal, so they have no beats.
static func is_text_only(code: String) -> bool:
	return code.begins_with("goal_") or code.begins_with("progress_")


## The server's own sentences (wilderness events) start with an emoji. Fonts differ and icons belong to the theme, so
## the fallback sentence is shown without it (a real window drew it as an empty box).
static func plain_sentence(s: String) -> String:
	var i := 0
	while i < s.length() and s.unicode_at(i) > 127:
		i += 1
	return s.substr(i).strip_edges()


## Typed slots for a line's args (a move becomes a translated word, a list is joined the theme's way).
static func slots_for(args: Dictionary) -> Dictionary:
	var slots := {}
	for k in args:
		if k == "line" and args[k] is String:
			slots[k] = plain_sentence(args[k])
			continue
		match SLOT_TYPES.get(k, ""):
			"move":
				var mv := str(args[k])
				if mv not in MOVES:
					_unknown("move", mv)
					mv = "unknown"
				slots[k] = {"key": "move.%s.choice" % mv}
			"list":
				slots[k] = {"list": args[k] if args[k] is Array else [args[k]]}
			_:
				slots[k] = args[k]
	return slots


## A goal or progress shown from the server's code + values when it sent them and we have words for the code;
## otherwise from the older contract-id key with the server's English as the slot.
static func _goal_text(line_ref: Variant, fallback_key: String, fallback_slots: Dictionary) -> Dictionary:
	if line_ref is Dictionary:
		var code := str(line_ref.get("code", ""))
		if code in line_codes():
			var args: Dictionary = line_ref.get("args") if line_ref.get("args") is Dictionary else {}
			return {"key": "line." + code, "slots": slots_for(args), "from_code": true}
		_unknown("goal_line", code)
	return {"key": fallback_key, "slots": fallback_slots, "from_code": false}


# ---------------- reveal: merge, dedupe, order ----------------

## Ordered log lines for a reveal. Order: news events, then my private lines (already in night order), then the rest
## of the news. A news line whose outcome one of my private lines already shows keeps its text but loses its beats,
## so one theft is one animation (review P3b). `me` is my alias.
static func reveal_lines(view: Dictionary, me: String) -> Array:
	var news: Array = view.get("news", [])
	var priv: Array = view.get("private", [])
	var private_events := {}
	var stole_from := {}
	var exposed_by_me := {}
	for l in priv:
		var a: Dictionary = l.get("args", {})
		match l.code:
			"event":
				private_events[_s(a, "line")] = true
			"stole":
				stole_from[_s(a, "target")] = true
			"exposed_by_me":
				exposed_by_me[_s(a, "thief")] = true
	var lines: Array = []
	var news_rest: Array = []
	if news.is_empty():
		lines.append(line(SYNTH_QUIET, {}, "news"))
	for l in news:
		var a: Dictionary = l.get("args", {})
		if l.code == "event":
			if private_events.has(_s(a, "line")):
				continue                 # the same sentence is in my private lines: show it once, there
			lines.append(line(l.code, a, "news"))
		else:
			news_rest.append(l)
	for l in priv:
		lines.append(line(l.code, l.get("args", {}), "private"))
	# The server resolves in seat order, so same-kind public lines arrive in seat order; showing them that way would let
	# a viewer infer who joined before whom, i.e. who is a human (review N14). Order by content instead.
	news_rest.sort_custom(func(x, y): return _line_key(x) < _line_key(y))
	for l in news_rest:
		var a: Dictionary = l.get("args", {})
		var ln := line(l.code, a, "news")
		ln.covered = _covered(l.code, a, me, stole_from, exposed_by_me)
		if ln.covered:
			ln.beats = []
		lines.append(ln)
	return lines


static func _line_key(l: Dictionary) -> String:
	return str(l.get("code", "")) + "|" + JSON.stringify(l.get("args", {}), "", true)


## Does one of my private lines already show this news line's outcome? With no known `me` nothing is covered: a
## missing argument ("") must never be mistaken for me (review N26).
static func _covered(code: String, a: Dictionary, me: String, stole_from: Dictionary, exposed_by_me: Dictionary) -> bool:
	var mine := me != ""
	match code:
		"news_hit_1", "news_hit_n":
			return (mine and _s(a, "victim") == me) or stole_from.has(_s(a, "victim"))
		"news_caught":
			return mine and me in [_s(a, "target"), _s(a, "thief")]
		"news_exposed", "news_exposed_back":
			return (mine and me in [_s(a, "thief"), _s(a, "victim")]) or exposed_by_me.has(_s(a, "thief"))
		"news_bandit", "news_rejoined", "news_idol":
			return mine and _s(a, "player") == me
	return false


# ---------------- models ----------------

static func lobby_model(view: Dictionary) -> Dictionary:
	return {"room_code": view.room_code, "seats_taken": view.seats_taken, "seats_total": view.seats_total,
		"is_host": view.host}


static func band_id(band: Variant) -> String:
	var b := str(band)
	if b in BANDS:
		return "band." + b
	_unknown("band", b)
	return "band.unknown"


## Everyone's home, sorted by alias (never by list order, which could reveal join order). Others' band comes from the
## board only; null when ranges are off.
## `board_before` (the previous morning's board) lets the Stage show a band change; "" when unknown.
static func roster(me: String, others: Array, board: Variant, board_before: Variant = null) -> Array:
	var bands := {}
	if board is Array:
		for e in board:
			bands[str(e.get("alias"))] = band_id(e.get("band"))
	var bands_before := {}
	if board_before is Array:
		for e in board_before:
			bands_before[str(e.get("alias"))] = band_id(e.get("band"))
	var names: Array = others.duplicate()
	if me != "":
		names.append(me)
	names = names.filter(func(n): return n != "")
	names.sort()
	var out: Array = []
	for n in names:
		out.append({"alias": n, "is_me": n == me, "band": bands.get(n, ""), "band_before": bands_before.get(n, "")})
	return out


static func _goal_slots(goal: Dictionary) -> Dictionary:
	return {"text": str(goal.get("text", "")), "target": str(goal.get("target") if goal.get("target") != null else "")}


## The goal card: worded from the server's code + values when it sent them (`goal.line`), else from the goal id with
## the server's English as the slot. `progress` is the same for how it is going; `state` says open/done/failed/end.
static func goal_card(goal: Dictionary, gcode: String, progress: Dictionary, gstate: String) -> Dictionary:
	var fallback_key := ("goal." + gcode) if gcode in GOALS else "goal.unknown"
	var text := _goal_text(goal.get("line"), fallback_key, _goal_slots(goal))
	var state_key := ("goal.state." + gstate) if gstate in GOAL_STATES else "goal.state.unknown"
	var prog := _goal_text(progress.get("line"), state_key, {"text": str(progress.get("text", ""))})
	return {"key": text.key, "slots": text.slots, "from_code": text.from_code,
		"state": gstate if gstate in GOAL_STATES else "unknown", "state_key": state_key,
		"progress": {"key": prog.key, "slots": prog.slots, "from_code": prog.from_code},
		"progress_text": str(progress.get("text", ""))}


static func round_model(view: Dictionary) -> Dictionary:
	var me: Dictionary = view.me
	var pickers: Array = []
	var kinds: Array = view.legal.keys()
	kinds.sort()
	for kind in kinds:
		var known: bool = kind in MOVES
		if not known:
			_unknown("move", str(kind))
		var targets: Array = view.legal[kind].duplicate()
		targets.sort()
		var mid: String = kind if known else "unknown"
		pickers.append({"move_id": mid, "server_id": kind, "targets": targets,
			"key": "move." + mid, "help_key": "move.%s.help" % mid, "choice_key": "move.%s.choice" % mid,
			"amounts": view.gift_amounts.duplicate() if kind == "gift" else [],
			"takes_target": (kind not in UNTARGETED) if known else not targets.is_empty()})
	var goal: Dictionary = me.get("goal") if me.get("goal") is Dictionary else {}
	var gcode := str(goal.get("code", ""))
	if gcode not in GOALS:
		_unknown("goal", gcode)
	var progress: Dictionary = me.get("goal_progress") if me.get("goal_progress") is Dictionary else {}
	var gstate := str(progress.get("state", ""))
	if gstate not in GOAL_STATES:
		_unknown("goal_state", gstate)
	var pick: Variant = null
	if view.get("my_pick") is Dictionary:
		var p: Dictionary = view.my_pick
		pick = {"move_id": p.kind, "target": p.get("target"), "amount": int(p.get("amount", 0))}
	var phrases: Array = []
	for ph in view.radio_phrases:
		if str(ph.key) not in RADIO:
			_unknown("radio", str(ph.key))
		phrases.append({"key": ("radio." + ph.key) if ph.key in RADIO else "radio.unknown",
			"server_id": ph.key, "needs_player": ph.needs_player})
	return {
		"round": view.round, "rounds": view.rounds,
		"timer": {"seconds_left": view.seconds_left},
		"me": {"alias": me.alias,
			"resources": [{"id": "resource.ration", "amount": me.rations}],
			"statuses": [{"id": "status.outcast", "on": me.bandit}, {"id": "status.shield", "on": me.get("guarded") == true}],
			"shields_left": me.get("guards_left")},
		"goal": goal_card(goal, gcode, progress, gstate),
		"pickers": pickers, "my_pick": pick,
		"locked": view.my_locked, "locked_count": view.locked_count, "seats_total": view.seats_total,
		"radio": {"available": view.radio_available, "phrases": phrases},
		"roster": roster(str(me.alias), view.aliases, view.get("board")),
	}


## `before` is the last round view (the only source of who is in the game when ranges are off); {} if unknown.
static func reveal_model(view: Dictionary, me_arg: String, before: Dictionary) -> Dictionary:
	var before_me: Dictionary = before.get("me") if before.get("me") is Dictionary else {}
	var me := me_arg if me_arg != "" else str(before_me.get("alias", ""))      # one source of "who am I" (N26)
	var lines := reveal_lines(view, me)
	var beats: Array = []
	for i in lines.size():
		for b in lines[i].beats:
			var bb: Dictionary = b.duplicate()
			bb["line_index"] = i
			# A public line names me by alias; the Stage and the arithmetic know me as ME. One name for one person,
			# or my food is counted twice and the conservation sum is wrong (found by mutation M04).
			if me != "":
				if bb.from == me:
					bb.from = ME
				if bb.to == me:
					bb.to = ME
			beats.append(bb)
	# The lines do not always add up to the night's real change (wilderness events and guard income carry no amount),
	# so the animation would end on the wrong number. Make up the difference with one explicit beat.
	var total_before := int(before_me.rations) if before_me.has("rations") else -1
	var total_after := -1
	var total_at := -1
	for i in beats.size():
		if beats[i].kind == "total":
			total_after = int(beats[i].amount_in)
			total_at = i
	var residual := 0
	if total_before >= 0 and total_after >= 0:
		residual = (total_after - total_before) - net_for_me(beats)
		if residual != 0:
			var rb := _mv(OFFSTAGE, ME, residual, -1, "other") if residual > 0 else _mv(ME, OFFSTAGE, -residual, -1, "other")
			rb["line_index"] = beats[total_at].line_index
			beats.insert(total_at, rb)
	var radio: Array = []
	for r in view.get("radio", []):
		var ph = r.get("phrase")
		if ph == null or str(ph) not in RADIO:
			if ph != null:
				_unknown("radio", str(ph))
			radio.append({"key": "radio.unknown", "slots": {}})
		else:
			radio.append({"key": "radio." + ph, "slots": {"a": str(r.get("about") if r.get("about") != null else "")}})
	var others: Array = before.get("aliases", []).duplicate()      # a copy: never write into the caller's view
	if others.is_empty() and view.get("board") is Array:
		for e in view.board:
			if e.alias != me:
				others.append(e.alias)
	return {"round": view.round, "lines": lines, "beats": beats, "radio": radio,
		"timer": {"seconds_left": view.seconds_left},
		"totals": {"before": total_before if total_before >= 0 else null, "after": total_after if total_after >= 0 else null,
			"residual": residual},
		"roster": roster(me, others, view.get("board"), before.get("board")),
		"roster_known": not others.is_empty(), "has_before_state": not before.is_empty()}


## What my beats add up to: everything arriving at me minus everything leaving me.
static func net_for_me(beats: Array) -> int:
	var n := 0
	for b in beats:
		if b.kind != "move_resource":
			continue
		if b.to == ME:
			n += b.amount_in
		if b.from == ME:
			n -= b.amount_out
	return n


static func end_model(view: Dictionary, me: String) -> Dictionary:
	var rows: Array = []
	for r in view.results:
		var g: Dictionary = r.get("goal") if r.get("goal") is Dictionary else {}
		var gcode := str(g.get("code", ""))
		if gcode not in GOALS:
			_unknown("goal", gcode)
		var gt := _goal_text(g.get("line"), ("goal." + gcode) if gcode in GOALS else "goal.unknown", _goal_slots(g))
		rows.append({"alias": r.alias, "is_me": r.alias == me, "is_winner": r.alias in view.winners,
			"has_seat": r.seat,
			"cells": {"score": r.score, "rations": r.rations, "stole": r.stole, "gave_away": r.gave_away,
				"times_robbed": r.times_robbed},
			"goal": {"key": gt.key, "slots": gt.slots, "done": r.goal_done}})
	var columns: Array = []
	for c in END_COLUMNS:
		var cc: Dictionary = c.duplicate()
		cc["key"] = "column." + c.id
		columns.append(cc)
	return {"winners": view.winners.duplicate(), "extracted": view.extracted.duplicate(), "rows": rows,
		"columns": columns}
