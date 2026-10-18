class_name SurvivorsRuleset
extends Ruleset
## The Survivors protocol: frame shapes, view types, seat-gone codes. Model building lives in adapter.gd.

const A = preload("res://rulesets/survivors/adapter.gd")

const S := TYPE_STRING
const I := TYPE_INT
const B := TYPE_BOOL
const NUM := Schema.NUM
const ANY := Schema.ANY

const VIEW_TYPES := ["lobby", "round", "reveal", "end"]
const SEAT_GONE_CODES := ["seat_gone", "room_gone", "bad_token"]
const SEAT_GONE_TEXTS := ["That seat no longer exists."]       # today's wording, until the server sends seat_gone

const LINE := {"dict": {"code": S, "?args": TYPE_DICTIONARY}}
const BOARD := {"null": {"list": {"dict": {"alias": S, "?band": ANY}}}}
const LINE_REF := {"null": {"dict": {"code": S, "?args": TYPE_DICTIONARY}}}      # a goal / progress line: code + values
const GOAL := {"null": {"dict": {"?code": ANY, "?target": ANY, "?text": ANY, "?line": LINE_REF}}}

const SCHEMAS := {
	"hello_ok": {"dict": {}},
	"upgrade_required": {"dict": {}},
	"error": {"dict": {"code": S, "?message": ANY}},
	"seat": {"dict": {"token": S, "room_code": S, "alias": S, "host": B}},
	# the open-camps list: the frame itself only has to be an object; every entry is checked and cleaned one by one by
	# RoomsWatch.sanitize, so one bad entry (or a hostile list) never costs the whole frame or raises a "bad frame" notice
	"rooms": {"dict": {"?rooms": ANY}},
	"lobby": {"dict": {"room_code": S, "seats_taken": I, "seats_total": I, "host": B}},
	"round": {"dict": {
		"round": I, "rounds": I, "seconds_left": NUM,
		"me": {"dict": {"alias": S, "rations": I, "bandit": B, "?guards_left": ANY, "?guarded": ANY,
			"?goal": GOAL, "?goal_progress": GOAL}},
		"legal": {"map": {"list": S}}, "gift_amounts": {"list": I},
		"?my_pick": {"null": {"dict": {"kind": S, "?target": ANY, "?amount": ANY}}},
		"my_locked": B, "locked_count": I, "seats_total": I, "radio_available": B,
		"radio_phrases": {"list": {"dict": {"key": S, "needs_player": B}}},
		"aliases": {"list": S}, "?board": BOARD}},
	"reveal": {"dict": {
		"round": I, "seconds_left": NUM, "news": {"list": LINE}, "private": {"list": LINE},
		"radio": {"list": {"dict": {"?phrase": ANY, "?about": ANY}}}, "?board": BOARD}},
	"end": {"dict": {
		"extracted": {"list": S}, "winners": {"list": S},
		"results": {"list": {"dict": {"alias": S, "score": I, "rations": I, "seat": B, "goal_done": B, "stole": I,
			"times_robbed": I, "gave_away": I, "?goal": GOAL}}}}},
}


func view_types() -> Array:
	return VIEW_TYPES


func seat_gone_codes() -> Array:
	return SEAT_GONE_CODES


func seat_gone_texts() -> Array:
	return SEAT_GONE_TEXTS


func validate(msg: Dictionary) -> String:
	var t := str(msg.get("t", ""))
	if not SCHEMAS.has(t):
		return ""
	return Schema.check(msg, SCHEMAS[t], t)


func lobby_model(view: Dictionary) -> Dictionary:
	return A.lobby_model(view)


func round_model(view: Dictionary) -> Dictionary:
	return A.round_model(view)


func reveal_model(view: Dictionary, me: String, before: Dictionary) -> Dictionary:
	return A.reveal_model(view, me, before)


func end_model(view: Dictionary, me: String) -> Dictionary:
	return A.end_model(view, me)


func all_keys() -> Array[String]:
	return A.all_keys()
