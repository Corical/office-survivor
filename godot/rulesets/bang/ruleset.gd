class_name BangRuleset
extends Ruleset
## Bang! The Dice Game on the generic wire (server plug-in `bang`, docs/games/bang/PROTOCOL.md in the server worktree).
## One `view` frame carries every phase; this turns it into a neutral model the Bang screens draw, and never lets a hostile or
## odd frame show a role that is not public.

const S := TYPE_STRING
const I := TYPE_INT
const B := TYPE_BOOL
const ANY := Schema.ANY

const PHASES := {
	"lobby": {"screen": "lobby"},
	"roll": {"screen": "bang_table"},
	"resolve": {"screen": "bang_table"},
	"over": {"screen": "bang_end"},
}
const VIEW_TYPES := ["lobby", "view"]
## The server manifest's verbs (the client's copy). `keep` is a bit mask over the five dice: a set bit keeps that die.
const VERBS := {
	"roll": {},
	"reroll": {"keep": {"type": "int", "min": 0, "max": 31}},
	"stop": {},
	"target": {"at": {"type": "int", "min": 0, "max": 7}},
}
const SEAT_GONE_CODES := ["seat_gone", "room_gone", "bad_token"]
const SEAT_GONE_TEXTS := ["That seat no longer exists."]

const ROLES := ["sheriff", "deputy", "outlaw", "renegade"]
const FACES := ["arrow", "dynamite", "shoot1", "shoot2", "beer", "gatling"]
const TEAMS := ["sheriff", "outlaws", "renegade", "deputy", "outlaw", "abandoned"]
const MAX_SEATS := 8
const DICE := 5
const ALL_KEPT := 31
const NAME_MAX := 24                  # chosen: longer names are cut (the server's are "Player 3" / "Bot 2")
const LOG_SHOWN := 8                  # chosen: the newest events a phone screen has room for

const SCHEMAS := {
	"hello_ok": {"dict": {}},
	"upgrade_required": {"dict": {}},
	"error": {"dict": {"code": S, "?message": ANY}},
	"seat": {"dict": {"token": S, "room_code": S, "alias": S, "host": B}},
	"rooms": {"dict": {"?rooms": ANY}},
	"lobby": {"dict": {"room_code": S, "seats_taken": I, "seats_total": I, "host": B, "?seats": ANY}},
	"view": {"dict": {
		"game": S, "phase": S, "phase_id": S, "seq": I, "n": I,
		"you": {"dict": {"at": I, "role": S}},
		"players": {"list": {"dict": {"at": I, "name": S, "life": I, "max": I, "arrows": I, "alive": B, "away": B,
			"role": {"null": S}}}},
		"turn": {"null": I}, "pile": I, "rolls": I, "rolls_max": I,
		"dice": {"list": {"dict": {"face": S, "locked": B}}},
		"pending": {"null": {"dict": {"die": I, "face": S, "targets": {"list": I}}}},
		"assigned": {"list": {"dict": {"die": I, "face": S, "at": I}}},
		"can": {"dict": {"roll": B, "reroll": B, "stop": B, "target": {"null": {"list": I}}}},
		"log": {"list": ANY},
		"winner": {"null": {"dict": {"team": S, "ats": {"list": I}}}},
		"?deadline": ANY}},
}

## Every translation key this game emits (rulesets/bang/words.po carries all of them and nothing else).
const KEYS: Array[String] = [
	"bang.role.sheriff", "bang.role.deputy", "bang.role.outlaw", "bang.role.renegade", "bang.role.unknown",
	"bang.role_line", "bang.role_hint.sheriff", "bang.role_hint.deputy", "bang.role_hint.outlaw", "bang.role_hint.renegade",
	"bang.face.arrow", "bang.face.dynamite", "bang.face.shoot1", "bang.face.shoot2", "bang.face.beer", "bang.face.gatling",
	"bang.face.unknown", "bang.die_kept", "bang.die_locked", "bang.die_to",
	"bang.turn_yours", "bang.turn_of", "bang.turn_out", "bang.rolls", "bang.pile",
	"bang.seat_life", "bang.seat_arrows", "bang.seat_out", "bang.seat_away", "bang.seat_you", "bang.seat_turn",
	"bang.seat_sheriff", "bang.seat_unknown",
	"bang.act.roll", "bang.act.reroll", "bang.act.stop", "bang.wait", "bang.rolling_hint", "bang.target_prompt",
	"bang.target_wait", "bang.nothing",
	"bang.log_title", "bang.log_empty", "bang.log.rolled", "bang.log.arrow", "bang.log.indians", "bang.log.dynamite",
	"bang.log.shot", "bang.log.beer", "bang.log.gatling", "bang.log.out", "bang.log.turn", "bang.log.over",
	"bang.end.win", "bang.end.lose", "bang.end.roles", "bang.end.winners",
	"bang.team.sheriff", "bang.team.outlaws", "bang.team.renegade", "bang.team.deputy", "bang.team.outlaw",
	"bang.team.abandoned", "bang.team.unknown",
]


func view_types() -> Array:
	return VIEW_TYPES


func phases() -> Dictionary:
	return PHASES


func verbs() -> Dictionary:
	return VERBS


func seat_gone_codes() -> Array:
	return SEAT_GONE_CODES


func seat_gone_texts() -> Array:
	return SEAT_GONE_TEXTS


func words_path() -> String:
	return "res://rulesets/bang/words.po"


func all_keys() -> Array[String]:
	return KEYS


func validate(msg: Dictionary) -> String:
	var t := str(msg.get("t", ""))
	if not SCHEMAS.has(t):
		return ""
	if t == "view" and str(msg.get("game", "")) != "bang":
		return "view: not a bang view"
	return Schema.check(msg, SCHEMAS[t], t)


func lobby_model(view: Dictionary) -> Dictionary:
	return {"room_code": view.room_code, "seats_taken": view.seats_taken, "seats_total": view.seats_total,
		"is_host": view.host, "seats": _kick_seats(view.get("seats"), view.host == true)}


## The host's seat list, cleaned: [{id, connected}]. Guests never have one; anything that is not a clean entry is dropped.
static func _kick_seats(raw: Variant, is_host: bool) -> Array:
	var out: Array = []
	if not is_host or not (raw is Array):
		return out
	var seen := {}
	for e in raw:
		if out.size() >= MAX_SEATS * 2 or not (e is Dictionary):
			continue
		var id: Variant = e.get("id")
		if not (id is String) or id == "" or id.length() > 64 or seen.has(id):
			continue
		seen[id] = true
		out.append({"id": id, "connected": not (typeof(e.get("connected")) == TYPE_BOOL and not e.get("connected"))})
	return out


## The neutral model of a `view` frame. Seats come out sorted by table position, so every client lays the table out the same way.
func view_model(v: Dictionary) -> Dictionary:
	var me_at: int = int(v.you.at)
	var over: bool = str(v.phase) == "over"
	var seats := _seats(v, me_at, over)
	var by_at := {}
	for s in seats:
		by_at[s.at] = s
	var me: Dictionary = by_at.get(me_at, {})
	var alive: bool = bool(me.get("alive", false))
	var turn: int = int(v.turn) if v.turn != null else -1
	var my_turn: bool = alive and turn == me_at and not over and turn >= 0
	var can: Dictionary = v.can
	var targets: Array = []
	if my_turn and can.target is Array and str(v.phase) == "resolve":
		for a in can.target:
			if typeof(a) == TYPE_INT and by_at.has(a) and by_at[a].alive and not targets.has(a):
				targets.append(a)
	var dice: Array = []
	for i in mini(v.dice.size(), DICE):
		var d: Dictionary = v.dice[i]
		var face := str(d.face)
		dice.append({"index": i, "face": face if face in FACES else "unknown", "locked": bool(d.locked) or face == "dynamite"})
	var pending: Dictionary = {}
	if v.pending != null and str(v.phase) == "resolve":
		pending = {"die": int(v.pending.die), "face": str(v.pending.face) if str(v.pending.face) in FACES else "unknown"}
	var assigned: Array = []
	for a in v.assigned:
		assigned.append({"die": int(a.die), "face": str(a.face) if str(a.face) in FACES else "unknown", "at": int(a.at),
			"name": _name_of(by_at, int(a.at))})
	var winner: Dictionary = {}
	if v.winner != null:
		var team := str(v.winner.team)
		var ats: Array = []
		for a in v.winner.ats:
			ats.append(int(a))
		winner = {"team": team if team in TEAMS else "unknown", "ats": ats, "mine": me_at in ats}
	return {
		"phase": str(v.phase), "phase_id": str(v.phase_id), "seq": int(v.seq), "n": int(v.n), "over": over,
		"me": {"at": me_at, "role": _role_id(v.you.role), "alive": alive},
		"turn": turn, "turn_name": _name_of(by_at, turn) if turn >= 0 else "", "my_turn": my_turn,
		"pile": int(v.pile), "rolls": int(v.rolls), "rolls_max": int(v.rolls_max),
		"seats": seats, "dice": dice, "pending": pending, "assigned": assigned, "targets": targets,
		"can": {"roll": my_turn and bool(can.roll), "reroll": my_turn and bool(can.reroll), "stop": my_turn and bool(can.stop)},
		"log": _log(v.log, by_at), "winner": winner,
	}


## Seats by table position. A role is shown only when it is public: the Sheriff, an eliminated seat, any seat once the game is over,
## every seat in a 3-seat game, and my own. A frame that carries a role for any other seat is not believed.
func _seats(v: Dictionary, me_at: int, over: bool) -> Array:
	var out: Array = []
	var seen := {}
	for p in v.players:
		var at: int = int(p.at)
		if seen.has(at) or at < 0 or at >= MAX_SEATS or out.size() >= MAX_SEATS:
			continue
		seen[at] = true
		var role := ""
		var given: Variant = p.role
		if at == me_at:
			role = _role_id(v.you.role)
		elif given is String and (given == "sheriff" or not bool(p.alive) or over or int(v.n) == 3):
			role = _role_id(given)
		out.append({"at": at, "name": _clean_name(str(p.name), at), "life": maxi(0, int(p.life)), "max": maxi(1, int(p.max)),
			"arrows": maxi(0, int(p.arrows)), "alive": bool(p.alive), "away": bool(p.away), "role": role,
			"is_sheriff": role == "sheriff", "is_me": at == me_at, "is_turn": v.turn != null and int(v.turn) == at})
	out.sort_custom(func(a, b): return a.at < b.at)
	return out


static func _role_id(r: Variant) -> String:
	return str(r) if r is String and r in ROLES else ""


static func _clean_name(raw: String, at: int) -> String:
	var n := raw.strip_edges().replace("\n", " ")
	return n.left(NAME_MAX) if n != "" else "#%d" % (at + 1)


static func _name_of(by_at: Dictionary, at: int) -> String:
	return by_at[at].name if by_at.has(at) else "#%d" % (at + 1)


static func _int(d: Dictionary, k: String, dflt := -1) -> int:
	var x: Variant = d.get(k)
	if typeof(x) == TYPE_FLOAT and is_finite(x) and x == floorf(x) and absf(x) < 1000.0:
		return int(x)                         # nested JSON numbers can arrive as floats
	return int(x) if typeof(x) == TYPE_INT else dflt


static func _face_slot(f: Variant) -> Dictionary:
	return {"key": "bang.face." + (str(f) if f is String and f in FACES else "unknown")}


## The last events as {key, slots}, newest first. An event this client does not know, or one of the wrong shape, is dropped.
func _log(raw: Array, by_at: Dictionary) -> Array:
	var out: Array = []
	for i in range(raw.size() - 1, -1, -1):
		if out.size() >= LOG_SHOWN:
			break
		var e: Variant = raw[i]
		if not (e is Dictionary):
			continue
		var line := _line(e, by_at)
		if not line.is_empty():
			out.append(line)
	return out


func _line(e: Dictionary, by_at: Dictionary) -> Dictionary:
	var by := _name_of(by_at, _int(e, "by"))
	var at := _name_of(by_at, _int(e, "at"))
	match str(e.get("k")):
		"rolled":
			var faces: Variant = e.get("dice")
			if not (faces is Array) or faces.size() != DICE:
				return {}
			return {"key": "bang.log.rolled", "slots": {"by": by, "roll": _int(e, "roll", 0), "d1": _face_slot(faces[0]),
				"d2": _face_slot(faces[1]), "d3": _face_slot(faces[2]), "d4": _face_slot(faces[3]), "d5": _face_slot(faces[4])}}
		"arrow":
			return {"key": "bang.log.arrow", "slots": {"by": by}}
		"indians":
			var hits: Array[String] = []
			var raw: Variant = e.get("hits")
			if raw is Array:
				for h in raw:
					if h is Dictionary:
						hits.append("%s (-%d)" % [_name_of(by_at, _int(h, "at")), maxi(0, _int(h, "dmg", 0))])
			return {"key": "bang.log.indians", "slots": {"hits": {"list": hits}}}
		"dynamite":
			return {"key": "bang.log.dynamite", "slots": {"by": by}}
		"shot":
			return {"key": "bang.log.shot", "slots": {"by": by, "at": at}}
		"beer":
			return {"key": "bang.log.beer", "slots": {"by": by, "at": at}}
		"gatling":
			return {"key": "bang.log.gatling", "slots": {"by": by}}
		"out":
			var r := _role_id(e.get("role"))
			return {"key": "bang.log.out", "slots": {"at": at, "role": {"key": "bang.role." + (r if r != "" else "unknown")}}}
		"turn":
			return {"key": "bang.log.turn", "slots": {"at": at}}
		"over":
			return {"key": "bang.log.over", "slots": {}}
	return {}


# ---- what the table screen asks of the model (pure, so the tests can break them) ----

## The `keep` mask for a reroll: a set bit keeps that die. Every dynamite die is always kept (the server refuses a reroll without it),
## whatever the player tapped.
static func keep_mask(dice: Array, kept: Dictionary) -> int:
	var m := 0
	for d in dice:
		if bool(d.locked) or bool(kept.get(d.index, false)):
			m |= 1 << int(d.index)
	return m


## A reroll with every die kept rolls nothing (the server says nothing_to_reroll): the screen offers Stop instead.
static func can_send_reroll(model: Dictionary, kept: Dictionary) -> bool:
	return bool(model.can.reroll) and keep_mask(model.dice, kept) != ALL_KEPT


## Whether a tap on seat `at` may go out as a target now.
static func may_target(model: Dictionary, at: int) -> bool:
	return bool(model.my_turn) and str(model.phase) == "resolve" and not model.pending.is_empty() and at in model.targets
