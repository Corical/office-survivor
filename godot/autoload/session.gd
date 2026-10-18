extends Node
## What the client remembers and decides about the connection: the seat token (through a SessionStore), the latest
## validated view, the screen it implies, and which intents are in flight. Contract 5.3: draw only the latest view;
## after a reconnect, resume and wait for a fresh view.

signal screen_changed(screen: String)
signal view_changed(view: Dictionary)
## kind: error | unknown | terminal | invalid. `code` is machine-readable; `text` is the server's fallback wording.
signal notice(kind: String, code: String, text: String)

const VIEW_TYPES := ["lobby", "round", "reveal", "end"]
const NUM := -1                                   # "int or float" in SCHEMAS
const SCHEMAS := {
	"seat": {"token": TYPE_STRING, "room_code": TYPE_STRING, "alias": TYPE_STRING, "host": TYPE_BOOL},
	"lobby": {"room_code": TYPE_STRING, "seats_taken": TYPE_INT, "seats_total": TYPE_INT, "host": TYPE_BOOL},
	"round": {"round": TYPE_INT, "rounds": TYPE_INT, "seconds_left": NUM, "me": TYPE_DICTIONARY,
		"legal": TYPE_DICTIONARY, "gift_amounts": TYPE_ARRAY, "my_locked": TYPE_BOOL, "locked_count": TYPE_INT,
		"seats_total": TYPE_INT, "radio_available": TYPE_BOOL, "radio_phrases": TYPE_ARRAY, "aliases": TYPE_ARRAY},
	"round.me": {"alias": TYPE_STRING, "rations": TYPE_INT, "bandit": TYPE_BOOL},
	"reveal": {"round": TYPE_INT, "news": TYPE_ARRAY, "private": TYPE_ARRAY, "radio": TYPE_ARRAY,
		"seconds_left": NUM},
	"end": {"extracted": TYPE_ARRAY, "winners": TYPE_ARRAY, "results": TYPE_ARRAY},
	"error": {"code": TYPE_STRING},
	"upgrade_required": {},
	"hello_ok": {},
}
## Error codes that mean the stored seat is useless (requested in the brief). Any error answering `resume` counts too.
const SEAT_GONE_CODES := ["seat_gone", "room_gone", "bad_token"]
const ROUND_GUARDED := ["lock", "continue"]        # once per room+round
const INTENT_TTL_MS := 10000                       # chosen: a Create/Join tap older than this is not replayed

var store: SessionStore
var clock: Clock = Clock.new()
var server_url := "" if OS.has_feature("android") else "ws://127.0.0.1:8765"
var token := ""
var room_code := ""
var alias := ""
var host := false

var screen := "title"
var view := {}
var view_msec := 0
var last_round_view := {}             # the before-state for the next reveal
var locked_out := false               # true after upgrade_required: nothing the server says changes the screen
var terminal_reason := ""
var pending_intent := {}

var _inflight := {}                   # guard key -> true


func _ready() -> void:
	if store == null:
		store = SessionStore.new()
	load_store()
	Net.handshaken.connect(_on_handshaken)
	Net.message_received.connect(apply)
	Net.terminal.connect(_on_terminal)


## Fresh state with the given store and clock (tests); nothing is read from or written to the player's files.
func reset(s: SessionStore = null, c: Clock = null) -> void:
	if s:
		store = s
	if c:
		clock = c
	token = ""
	room_code = ""
	alias = ""
	host = false
	screen = "title"
	view = {}
	view_msec = 0
	last_round_view = {}
	locked_out = false
	terminal_reason = ""
	pending_intent = {}
	_inflight = {}
	load_store()


# ---------------- intents ----------------

## Title screen: start fresh with Create or Join. The old seat is forgotten first, so the tap is never swallowed by a
## silent resume (review B1-2); an open connection that carries the old seat is closed.
func begin(t: String, fields := {}) -> String:
	var had_seat := token != ""
	forget_seat()
	if had_seat and Net.state != "offline":
		Net.close()
	terminal_reason = ""
	if Net.handshake_done:
		return act(t, fields)
	pending_intent = {"t": t, "fields": fields, "at": clock.now_msec()}
	Log.event("session", "intent_pending", {"t": t})
	Net.connect_to(server_url)
	return ""


func resume_if_stored() -> bool:
	if token == "":
		return false
	terminal_reason = ""
	Log.event("session", "resume_start", {"room": room_code})
	Net.connect_to(server_url)
	return true


## Send an intent once. Returns "" when sent, else why not: in_flight | locked | <Net reason>.
func act(t: String, fields := {}) -> String:
	if locked_out:
		return "locked"
	var key := _guard_key(t, fields)
	if _inflight.has(key):
		Log.event("session", "intent_ignored", {"t": t, "why": "in_flight"})
		return "in_flight"
	var why: String = Net.send(t, fields)
	if why == "":
		_inflight[key] = true
	return why


func pick(kind: String, target: Variant, amount := 0) -> String:
	var fields := {"kind": kind, "target": target}
	if amount > 0:
		fields["amount"] = amount
	return act("pick", fields)


func leave() -> void:
	if Net.handshake_done:
		Net.send("leave")
	forget_seat()
	Net.close()
	view = {}
	_inflight = {}
	terminal_reason = ""
	_go("title")


## Called by "Back to title" after a terminal reason.
func back_to_title() -> void:
	Net.close()
	view = {}
	_inflight = {}
	pending_intent = {}
	if terminal_reason == "upgrade_required":
		return                    # nothing else to do until the app is updated
	_go("title")


# ---------------- what the round screen may show ----------------

## none | open | sent | locked: the one source for the Lock button and the picker (review B1-8).
func lock_state() -> String:
	if view.get("t") != "round":
		return "none"
	if bool(view.get("my_locked", false)):
		return "locked"
	if _inflight.has(_round_key("lock")):
		return "sent"
	return "open"


func picker_open() -> bool:
	return screen == "round" and not locked_out and Net.state == "online" and lock_state() == "open" \
		and seconds_left_now() > 0


func seconds_left_now() -> int:
	if not view.has("seconds_left"):
		return 0
	var elapsed := (clock.now_msec() - view_msec) / 1000.0
	return maxi(0, ceili(float(view.seconds_left) - elapsed))


func before_state_for(r: int) -> Dictionary:
	return last_round_view if int(last_round_view.get("round", -1)) == r else {}


# ---------------- inbound ----------------

func apply(msg: Dictionary) -> void:
	var t: String = msg.t
	if locked_out:
		Log.event("session", "ignored_locked_out", {"t": t})
		return
	if SCHEMAS.has(t):
		var bad := validate(msg)
		if bad != "":
			Log.event("session", "invalid_view", {"t": t, "problem": bad}, "WARN")
			notice.emit("invalid", "invalid_" + t, "")
			return
	match t:
		"hello_ok":
			pass
		"upgrade_required":
			locked_out = true
			terminal_reason = "upgrade_required"
			view = msg
			_inflight = {}
			_go("upgrade")
			view_changed.emit(view)
		"seat":
			token = msg.token
			room_code = msg.room_code
			alias = msg.alias
			host = msg.host
			_clear_reply_guards()
			save_store()
			Log.event("session", "seat", {"room": room_code, "host": host})
		"error":
			_on_error(msg)
		_:
			if t in VIEW_TYPES:
				_take_view(msg)
			else:
				Log.event("session", "unknown_type", {"t": t}, "WARN")
				notice.emit("unknown", t, "")


static func validate(msg: Dictionary) -> String:
	var t: String = msg.t
	var problem := _check(msg, SCHEMAS.get(t, {}))
	if problem == "" and t == "round":
		problem = _check(msg.me, SCHEMAS["round.me"])
		if problem != "":
			problem = "me." + problem
	return problem


static func _check(d: Dictionary, schema: Dictionary) -> String:
	for k in schema:
		if not d.has(k):
			return "%s missing" % k
		var want: int = schema[k]
		var got := typeof(d[k])
		if want == NUM:
			if got != TYPE_INT and got != TYPE_FLOAT:
				return "%s not a number" % k
		elif got != want:
			return "%s has the wrong type" % k
	return ""


func _take_view(msg: Dictionary) -> void:
	var t: String = msg.t
	if t == "lobby":
		host = msg.host
		room_code = msg.room_code
	var new_round := t == "round" and int(msg.round) != int(view.get("round", -1))
	if t == "round":
		last_round_view = msg
	view = msg
	view_msec = clock.now_msec()
	_clear_reply_guards()
	if new_round:
		_drop_round_guards()
	if pending_intent and t != "lobby":
		pending_intent = {}
	Log.event("session", "view", {"t": t, "round": msg.get("round", "-")})
	_go(t)
	view_changed.emit(view)


func _on_error(msg: Dictionary) -> void:
	var code: String = msg.code
	var text := str(msg.get("message", ""))
	var was_resume := _inflight.has(_guard_key("resume", {}))
	Log.event("session", "server_error", {"code": code, "resume": was_resume, "message": text}, "WARN")
	_inflight = {}                    # a refusal re-opens whatever it refused (a rejected lock re-opens the picker)
	if code in SEAT_GONE_CODES or was_resume:
		_seat_gone(code, text)
	elif code == "taken_over":
		pass                          # Net also stops; _on_terminal handles the screen
	else:
		notice.emit("error", code, text)


func _on_terminal(reason: String) -> void:
	terminal_reason = reason
	_inflight = {}
	pending_intent = {}
	match reason:
		"seat_gone":
			_seat_gone("seat_gone", "")
		"upgrade_required":
			if not locked_out:
				locked_out = true
				view = {"t": "upgrade_required"}
				_go("upgrade")
				view_changed.emit(view)
		_:
			notice.emit("terminal", reason, "")   # taken_over, too_big, flapping: the seat is kept; Title offers resume
			view = {}
			_go("title")


func _seat_gone(code: String, text: String) -> void:
	forget_seat()
	view = {}
	pending_intent = {}
	notice.emit("terminal", "seat_gone", text if text != "" else code)
	_go("title")


func _on_handshaken() -> void:
	_inflight = {}                    # after a reconnect the fresh view decides; keep nothing else
	if token != "":
		act("resume", {"token": token})
	elif pending_intent:
		var p := pending_intent
		pending_intent = {}
		if clock.now_msec() - int(p.at) > INTENT_TTL_MS:
			Log.event("session", "intent_expired", {"t": p.t})
			return
		act(p.t, p.fields)


# ---------------- storage ----------------

func forget_seat() -> void:
	token = ""
	room_code = ""
	alias = ""
	host = false
	pending_intent = {}
	save_store()


func load_store() -> void:
	var d := store.load_data() if store else {}
	token = str(d.get("token", ""))
	room_code = str(d.get("room_code", ""))
	alias = str(d.get("alias", ""))
	if str(d.get("server_url", "")) != "":
		server_url = str(d.server_url)


func save_store() -> void:
	if store:
		store.save_data({"token": token, "room_code": room_code, "alias": alias, "server_url": server_url})


# ---------------- helpers ----------------

func _guard_key(t: String, fields: Dictionary) -> String:
	if t in ROUND_GUARDED:
		return _round_key(t)
	if t == "pick":
		return "pick|%s" % JSON.stringify(fields)
	return t


func _round_key(t: String) -> String:
	return "%s|%s|%s" % [room_code, view.get("round", -1), t]


func _clear_reply_guards() -> void:
	for k in _inflight.keys():
		if not (k.ends_with("|lock") or k.ends_with("|continue")):
			_inflight.erase(k)


func _drop_round_guards() -> void:
	for k in _inflight.keys():
		if k.ends_with("|lock") or k.ends_with("|continue"):
			_inflight.erase(k)


func _go(s: String) -> void:
	if s != screen:
		Log.event("session", "screen", {"from": screen, "to": s})
		screen = s
		screen_changed.emit(s)
