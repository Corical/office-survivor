extends Node
## What the client remembers and decides about the connection: the seat token (through a SessionStore), the latest
## validated view, the screen it implies, and which intents are in flight. Contract 5.3: draw only the latest view;
## after a reconnect, resume and wait for a fresh view. Frame shapes and seat-gone codes come from the Ruleset.

signal screen_changed(screen: String)
signal view_changed(view: Dictionary)
## kind: error | unknown | terminal | invalid. `code` is machine-readable; `text` is the server's fallback wording.
signal notice(kind: String, code: String, text: String)
## The OS back button / gesture. Screens decide what it means; the app never quits on it by itself.
signal back_requested

const ROUND_GUARDED := ["lock", "continue"]        # once per room+round
const SEAT_INTENTS := ["resume", "create_room", "join_room"]
const INTENT_TTL_MS := 10000                       # chosen: a Create/Join tap older than this is not replayed

var store: SessionStore
var clock: Clock = Clock.new()
var ruleset: Ruleset
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
## True from a (re)connect until the next view: the held view is stale, so the picker stays shut and the timer is
## unknown (contract 5.3, and the phone coming back from the background).
var awaiting_view := false

var _inflight := {}                   # guard key -> true
var _last_type := ""                  # the intent most recently sent: the one an `error` is taken to answer
var _last_key := ""


func _ready() -> void:
	if store == null:
		store = SessionStore.new()
	if ruleset == null:
		ruleset = RulesetRegistry.make()
	get_tree().quit_on_go_back = false           # Android: the back gesture must not close the game by itself
	load_store()
	Net.handshaken.connect(_on_handshaken)
	Net.message_received.connect(apply)
	Net.terminal.connect(_on_terminal)
	Net.probe_due.connect(_on_probe)
	Net.state_changed.connect(_on_net_state)


## Fresh state with the given store and clock (tests); nothing is read from or written to the player's files.
func reset(s: SessionStore = null, c: Clock = null) -> void:
	if s:
		store = s
	if c:
		clock = c
	ruleset = RulesetRegistry.make()
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
	awaiting_view = false
	_inflight = {}
	_last_type = ""
	_last_key = ""
	load_store()


static func valid_url(u: String) -> bool:
	return (u.begins_with("ws://") or u.begins_with("wss://")) and u.length() > 8 and not (" " in u)


# ---------------- intents ----------------

## Title screen: start fresh with Create or Join. The old seat is forgotten first, so the tap is never swallowed by a
## silent resume (review B1-2). Returns "" or a reason (no_server_url | <act reason>).
func begin(t: String, fields := {}) -> String:
	if not valid_url(server_url):
		Log.event("session", "bad_server_url", {"url": server_url}, "WARN")
		return "no_server_url"
	var had_seat := token != ""
	forget_seat()
	view = {}
	last_round_view = {}
	awaiting_view = false
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
	if not valid_url(server_url):
		Log.event("session", "bad_server_url", {"url": server_url}, "WARN")
		return false
	terminal_reason = ""
	awaiting_view = true
	Log.event("session", "resume_start", {"room": room_code})
	Net.connect_to(server_url)
	return true


## Send an intent once. Returns "" when sent, else why not: in_flight | locked | locked_round | radio_unavailable |
## <Net reason>.
func act(t: String, fields := {}) -> String:
	if locked_out:
		return "locked"
	if awaiting_view and t != "resume":
		# the held view is stale: after a reconnect the only first word is `resume` (found by the live two-human game,
		# where pick and radio went out ahead of it)
		Log.event("session", "intent_refused", {"t": t, "why": "awaiting_view"})
		return "awaiting_view"
	if t == "pick" and lock_state() != "open":
		Log.event("session", "intent_refused", {"t": t, "why": "round_locked"})
		return "locked_round"              # contract 5.3: after Lock the picker stays shut; never re-enabled locally
	if t == "radio" and not bool(view.get("radio_available", false)):
		return "radio_unavailable"
	var key := _guard_key(t, fields)
	if _inflight.has(key):
		Log.event("session", "intent_ignored", {"t": t, "why": "in_flight"})
		return "in_flight"
	var why: String = Net.send(t, fields)
	if why == "":
		_inflight[key] = true
		_last_type = t
		_last_key = key
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
	last_round_view = {}
	awaiting_view = false
	_inflight = {}
	terminal_reason = ""
	_go("title")


## Called by "Back to title" after a terminal reason.
func back_to_title() -> void:
	Net.close()
	view = {}
	_inflight = {}
	pending_intent = {}
	awaiting_view = false
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
	return screen == "round" and not locked_out and not awaiting_view and Net.state == "online" \
		and lock_state() == "open" and seconds_left_now() > 0


## False while the held view is stale (reconnecting, or back from the background): a ring should show "unknown".
func timer_known() -> bool:
	return not awaiting_view and Net.state == "online"


func seconds_left_now() -> int:
	if not view.has("seconds_left"):
		return 0
	var elapsed := (clock.now_msec() - view_msec) / 1000.0
	return maxi(0, ceili(float(view.seconds_left) - elapsed))


func before_state_for(r: int) -> Dictionary:
	return last_round_view if int(last_round_view.get("round", -1)) == r else {}


func expecting_seat() -> bool:
	for k in SEAT_INTENTS:
		if _inflight.has(k):
			return true
	return false


# ---------------- inbound ----------------

func apply(msg: Dictionary) -> void:
	var t: String = msg.t
	if locked_out:
		Log.event("session", "ignored_locked_out", {"t": t})
		return
	if Net.state == "offline":
		Log.event("session", "ignored_offline", {"t": t})      # a frame that outlived a deliberate close (N05)
		return
	var bad := ruleset.validate(msg)
	if bad != "":
		Log.event("session", "invalid_frame", {"t": t, "problem": bad}, "WARN")
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
			if not expecting_seat():
				Log.event("session", "unexpected_seat", {}, "WARN")      # N06: a seat nobody asked for changes nothing
				return
			if str(msg.room_code) != room_code:
				view = {}
				last_round_view = {}
			token = msg.token
			room_code = msg.room_code
			alias = msg.alias
			host = msg.host
			for k in SEAT_INTENTS:
				_inflight.erase(k)
				Net.ack(k)
			save_store()
			Log.event("session", "seat", {"room": room_code, "host": host})
		"error":
			_on_error(msg)
		_:
			if t in ruleset.view_types():
				_take_view(msg)
			else:
				Log.event("session", "unknown_type", {"t": t}, "WARN")
				notice.emit("unknown", t, "")


## Rank of a round-ish view so an older one can be told from a newer one: round n < reveal n < round n+1.
static func order_of(v: Dictionary) -> int:
	match v.get("t"):
		"round":
			return int(v.get("round", 0)) * 2
		"reveal":
			return int(v.get("round", 0)) * 2 + 1
	return -1


func _take_view(msg: Dictionary) -> void:
	var t: String = msg.t
	var old := order_of(view)
	var new := order_of(msg)
	if old >= 0 and new >= 0 and new < old:
		Log.event("session", "stale_view_ignored", {"got": t, "round": msg.get("round"), "have": view.get("round")}, "WARN")
		return
	if t == "lobby":
		host = msg.host
		room_code = msg.room_code
	var new_round := t == "round" and int(msg.round) != int(view.get("round", -1))
	if t == "round":
		last_round_view = msg
	view = msg
	view_msec = clock.now_msec()
	awaiting_view = false
	_clear_reply_guards()
	if new_round or t == "end":
		_drop_round_guards()
	# what this view answers (review N08): it ends the wait for every intent except a lock/continue it does not cover
	Net.ack_except(ROUND_GUARDED)
	if (t == "round" and bool(msg.my_locked)) or t == "reveal" or t == "end":
		Net.ack("lock")
	if new_round or t == "end":
		Net.ack("continue")
	if pending_intent and t != "lobby":
		pending_intent = {}
	Log.event("session", "view", {"t": t, "round": msg.get("round", "-")})
	_go(t)
	view_changed.emit(view)


func _on_error(msg: Dictionary) -> void:
	var code: String = msg.code
	var text := str(msg.get("message", ""))
	var was_resume := _inflight.has("resume")
	Log.event("session", "server_error", {"code": code, "resume": was_resume, "message": text}, "WARN")
	if code in ruleset.seat_gone_codes() or (code == "refused" and text in ruleset.seat_gone_texts()):
		_inflight = {}
		_seat_gone(code, text)
		return
	if code == "taken_over":
		return                        # Net also stops; _on_terminal handles the screen
	# an error answers the intent sent last; only that guard (and its wait) is released (review N07)
	if _last_key != "":
		_inflight.erase(_last_key)
		Net.ack(_last_type)
	if was_resume and not _inflight.has("resume"):
		# a refused resume that is not "that seat is gone" (rate limit, server_error): keep the seat, try again later
		notice.emit("error", code, text)
		Net.reconnect_later()
		return
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
			awaiting_view = false
			_go("title")


func _seat_gone(code: String, text: String) -> void:
	forget_seat()
	view = {}
	last_round_view = {}
	awaiting_view = false
	pending_intent = {}
	notice.emit("terminal", "seat_gone", text if text != "" else code)
	_go("title")


func _on_handshaken() -> void:
	_inflight = {}                    # after a reconnect the fresh view decides; keep nothing else
	if token != "":
		awaiting_view = true
		act("resume", {"token": token})
	elif pending_intent:
		var p := pending_intent
		pending_intent = {}
		if clock.now_msec() - int(p.at) > INTENT_TTL_MS:
			Log.event("session", "intent_expired", {"t": p.t})
			return
		act(p.t, p.fields)


## The moment the connection leaves "online" with a seat held, the view we hold is stale. Net says "online" a hair
## before it tells us the handshake finished; without this, a screen reacting to that state change could act on the
## stale picker before the resume goes out.
func _on_net_state(s: String) -> void:
	if s != "online" and token != "":
		awaiting_view = true


## Nothing heard for a while. `resume` on the live connection is a harmless ping: the server answers with the seat
## and the current view, and a dead path answers nothing, which the ack watchdog then catches.
func _on_probe() -> void:
	if token != "" and screen in ["lobby", "round", "reveal"] and not _inflight.has("resume"):
		act("resume", {"token": token})


# ---------------- app lifecycle (Android) ----------------

func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_PAUSED:
			Log.event("session", "app_paused")
		NOTIFICATION_APPLICATION_RESUMED:
			Log.event("session", "app_resumed", {"screen": screen})
			if token != "" and not locked_out and Net.state != "stopped":
				# the socket may have died in the background and the monotonic clock may have stopped: trust neither
				awaiting_view = true
				Net.reconnect_now()
		NOTIFICATION_WM_GO_BACK_REQUEST:
			back_requested.emit()


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
