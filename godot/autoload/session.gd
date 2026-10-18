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
## The open-camps list changed (or was hidden): the model Feed publishes as "rooms".
signal rooms_changed(model: Dictionary)

const ROUND_GUARDED := ["lock", "continue"]        # once per room+round
const SEAT_INTENTS := ["resume", "create_room", "join_room"]
const INTENT_TTL_MS := 10000                       # chosen: a Create/Join tap older than this is not replayed

var store: SessionStore
var clock: Clock = Clock.new()
var ruleset: Ruleset
var server_url := "wss://raspberrypi.tail87b476.ts.net:8470"      # the arena server on the Pi (tailnet only); Settings can change it
## Old defaults that earlier builds saved to disk as if the player had chosen them. A saved copy of one of these is not a
## choice, so it is dropped on load and the current default applies (an address the player typed is always kept).
const RETIRED_DEFAULT_URLS: Array[String] = ["ws://127.0.0.1:8765"]
const CONTINUE_ACK_MARGIN_MS := 10000          # after the reveal's own clock runs out, the next view should come within this
const CONTINUE_ACK_MAX_MS := 120000            # chosen: no reveal waits longer than two minutes, whatever the server says
## The exact words the server uses when a kick targets a seat that is no longer in the room (docs/arena/GODOT_FOUNDATION.md).
const KICK_SEAT_GONE_TEXT := "That seat is not in the room any more."
## What the server answers a join_room with when the camp cannot be joined (rooms listing and typed codes alike).
const JOIN_REFUSAL_CODES: Array[String] = ["room_full", "room_started", "room_gone"]
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
## True from the moment the seat of a Create / Join arrives until the first view of that camp: the screen is about to change,
## so the title must not re-lay itself out (a "Rejoin camp" button flashed in at exactly this point).
var seat_pending_view := false

## The open-camps list (see core/rooms_watch.gd). It runs only while a screen has asked for it (rooms_watch) and only on the
## title screen, never while an intent is waiting for its answer, and it stops when a game starts.
var rooms := RoomsWatch.new()
const URL_SETTLE_MS := 1000           # chosen: after the server address is edited, wait this long before reconnecting for the list
var _watchers := 0                    # screens that asked for the list; a count, so a rebuilt screen cannot switch it off by leaving late
var _watch_reconnect_at := -1
var _wire := 0                        # counts what was sent, to tell which request an `error` is answering
var _list_wire := 0
var _intent_wire := 0
var _join_from_list := false          # the join in flight was a tap on a listed camp: a refusal gets the neutral wording

var _inflight := {}                   # guard key -> true
var _locked_seen := {}                # "room|round|lock" -> true once a view said my_locked for that round
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
	Net.ticked.connect(_rooms_tick)


## Fresh state with the given store and clock (tests); nothing is read from or written to the player's files.
func reset(s: SessionStore = null, c: Clock = null) -> void:
	if s:
		store = s
	if c:
		clock = c
	ruleset = RulesetRegistry.make()
	seat_pending_view = false
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
	_locked_seen = {}
	_last_type = ""
	_last_key = ""
	rooms = RoomsWatch.new()
	_watchers = 0
	_watch_reconnect_at = -1
	_wire = 0
	_list_wire = 0
	_intent_wire = 0
	_join_from_list = false
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
	if Net.handshake_done and Net.state == "online":
		act("resume", {"token": token})          # the line is already up (the open-camps list opened it): just resume on it
		return true
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
	if (t == "pick" or t == "lock") and lock_state() == "locked":
		return "locked_round"                  # the server said this round is locked: nothing more goes out for it
	if t == "pick" and lock_state() != "open":
		Log.event("session", "intent_refused", {"t": t, "why": "round_locked"})
		return "locked_round"              # contract 5.3: after Lock the picker stays shut; never re-enabled locally
	if t == "radio" and not bool(view.get("radio_available", false)):
		return "radio_unavailable"
	var key := _guard_key(t, fields)
	if _inflight.has(key):
		Log.event("session", "intent_ignored", {"t": t, "why": "in_flight"})
		return "in_flight"
	var why: String = Net.send(t, fields, _ack_ms_for(t))
	if why == "":
		_inflight[key] = true
		_last_type = t
		_last_key = key
		_wire += 1
		_intent_wire = _wire
	return why


## The host removes a seat that dropped off. `handle` must be one of the seats in the LATEST lobby (a handle changes when a seat
## changes hands, so an older one is refused by the server and could never hit the next person; we refuse it here first).
## Returns "" when sent, else not_host | not_in_lobby | unknown_seat | in_flight | <a connection reason>.
func kick(handle: String) -> String:
	if view.get("t") != "lobby":
		return "not_in_lobby"
	if not host:
		return "not_host"
	var known := false
	for s in ruleset.lobby_model(view).get("seats", []):                # the cleaned list the host's screen shows, not the raw frame
		if str(s.get("id", "")) == handle and handle != "":
			known = true
	if not known:
		Log.event("session", "kick_refused", {"why": "unknown_seat"})
		return "unknown_seat"
	return act("kick", {"seat": handle})


## How long the server may take to answer `t` before the line is called dead. Almost everything is answered at once. Continue is
## not: the server answers it when the reveal ends (or everyone has tapped), so a tap 6 s into a 20 s reveal is rightly silent
## for 14 s. Waiting only 8 s dropped a healthy line and showed "Signal lost" (stranger pass 2, N3). The wait is the reveal's own
## remaining time plus a margin, bounded so a hostile countdown cannot buy an endless wait; -1 = the normal deadline.
func _ack_ms_for(t: String) -> int:
	if t != "continue" or view.get("t") != "reveal":
		return -1
	var left_s: Variant = view.get("seconds_left", 0)
	var left_ms := 0.0
	if left_s is int or left_s is float:
		left_ms = float(left_s) * 1000.0 - float(clock.now_msec() - view_msec)
	if is_nan(left_ms) or left_ms < 0.0:
		left_ms = 0.0
	return int(clampf(maxf(left_ms + CONTINUE_ACK_MARGIN_MS, Net.ACK_TIMEOUT_MS), Net.ACK_TIMEOUT_MS, CONTINUE_ACK_MAX_MS))


func pick(kind: String, target: Variant, amount := 0) -> String:
	var fields := {"kind": kind, "target": target}
	if amount > 0:
		fields["amount"] = amount
	return act("pick", fields)


func leave() -> void:
	seat_pending_view = false
	if Net.handshake_done:
		Net.send("leave")
	forget_seat()
	Net.close()
	view = {}
	last_round_view = {}
	awaiting_view = false
	_inflight = {}
	_locked_seen = {}
	terminal_reason = ""
	_go("title")


## Called by "Back to title" after a terminal reason.
## True while a Create / Join is on its way into a camp: the tap is waiting for the server, or the seat has arrived and the
## camp's first view has not. The title reads this to stay still (read-only: nothing else changes behaviour on it).
func entering_camp() -> bool:
	if _inflight.has("create_room") or _inflight.has("join_room") or seat_pending_view:
		return true
	return pending_intent.get("t", "") in ["create_room", "join_room"]


func back_to_title() -> void:
	seat_pending_view = false
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
	# once the server has said this round is locked it stays locked here, whatever a later view claims
	# (contract 5.3: never re-enable the picker locally)
	if bool(view.get("my_locked", false)) or _locked_seen.has(_round_key("lock")):
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
			pass                      # features are read in _on_handshaken, before the first list request
		"upgrade_required":
			locked_out = true
			terminal_reason = "upgrade_required"
			view = msg
			_inflight = {}
			_go("upgrade")
			view_changed.emit(view)
		"seat":
			if not expecting_seat():
				# The server answers the idle probe's `resume` with the view FIRST and the seat after it, so by the time the
				# seat arrives the resume looks answered. A seat for the very seat we hold is that echo: harmless, not a
				# warning (stranger pass: one WARN per client every 30 s). Any other seat is still ignored, and still a WARN.
				if token != "" and str(msg.get("token")) == token and str(msg.get("room_code")) == room_code:
					Log.event("session", "seat_echo", {})
				else:
					Log.event("session", "unexpected_seat", {}, "WARN")      # N06: a seat nobody asked for changes nothing
				return
			if str(msg.room_code) != room_code:
				view = {}
				last_round_view = {}
			token = msg.token
			room_code = msg.room_code
			alias = msg.alias
			host = msg.host
			seat_pending_view = _inflight.has("create_room") or _inflight.has("join_room")
			for k in SEAT_INTENTS:
				_inflight.erase(k)
				Net.ack(k)
			save_store()
			Log.event("session", "seat", {"room": room_code, "host": host})
		"error":
			_on_error(msg)
		"rooms":
			_on_rooms(msg)
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
	if t == "round" and bool(msg.my_locked):
		_locked_seen[_round_key("lock")] = true
	view_msec = clock.now_msec()
	awaiting_view = false
	seat_pending_view = false
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
	# An error answers the request sent last. If that was the list request, it says "no lists here" (or "slow down"),
	# and it is not something to tell the player about.
	if rooms.awaiting() and _list_wire > _intent_wire:
		if rooms.on_error(code, clock.now_msec()):
			rooms_changed.emit(rooms.model())
		Log.event("session", "list_rooms_error", {"code": code})
		return
	# A tap on a listed camp that was refused: the camp filled, started or vanished first, or anything else. One neutral
	# wording for all of it, and the list is refreshed at once.
	if _join_from_list and _last_key == "join_room" and _inflight.has("join_room"):
		_join_from_list = false
		_inflight.erase("join_room")
		Net.ack("join_room")
		Log.event("session", "listed_camp_refused", {"code": code, "message": text}, "WARN")
		notice.emit("error", "camp_unavailable", text)
		rooms.refresh_now(clock.now_msec())
		return
	# A typed join that was refused because the camp is full, started or gone: that is about THIS join, not about a seat we
	# hold (room_gone is also a seat-gone code, but only for a refused resume). Say so in its own words and stay on the title.
	if _last_key == "join_room" and _inflight.has("join_room") and code in JOIN_REFUSAL_CODES:
		_inflight.erase("join_room")
		pending_intent = {}
		Net.ack("join_room")
		Log.event("session", "join_refused", {"code": code, "message": text}, "WARN")
		notice.emit("error", code, text)
		return
	var was_resume := _inflight.has("resume")
	Log.event("session", "server_error", {"code": code, "resume": was_resume, "message": text}, "WARN")
	if code in ruleset.seat_gone_codes() or (code == "refused" and text in ruleset.seat_gone_texts()):
		_inflight = {}
		_seat_gone(code, text)
		return
	if code == "taken_over" or code == "kicked":
		return                        # Net also stops; _on_terminal handles the screen
	# A kick the server refused because that seat left first: the list changed under the host and a fresh lobby is on its way.
	# Nothing to tell them; just release the guard so the next kick can go.
	if _last_key == "kick" and text == KICK_SEAT_GONE_TEXT:
		_inflight.erase("kick")
		Log.event("session", "kick_target_already_gone", {})
		return
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
	seat_pending_view = false
	terminal_reason = reason
	_inflight = {}
	pending_intent = {}
	match reason:
		"seat_gone":
			_seat_gone("seat_gone", "")
		"kicked":
			# The host removed this seat (error `kicked` and/or close 4004: either one alone is enough). The seat is dead on the
			# server, so forget it, say who did it, and go to the title. The player can join again by code (there is no ban).
			forget_seat()
			view = {}
			last_round_view = {}
			awaiting_view = false
			_locked_seen = {}
			notice.emit("terminal", "kicked", "")
			_go("title")
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
	rooms.on_features(Net.server_features)          # before the first list_rooms: a server that said no is never asked
	rooms.on_connected(clock.now_msec())
	rooms_changed.emit(rooms.model())
	_rooms_tick()                     # (re)connected with the list showing: ask for it now, do not wait for the next beat
	if token != "" and not _watch_only():
		awaiting_view = true
		act("resume", {"token": token})
	elif token != "":
		pass                          # on the title screen with a stored seat and the camps list open: Resume is the player's choice
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
	if s != "online" and rooms.connected:
		rooms.on_disconnected()                  # the list we hold is the last one we had; polling resumes with the handshake
		rooms_changed.emit(rooms.model())


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
	seat_pending_view = false
	save_store()


func load_store() -> void:
	var d := store.load_data() if store else {}
	token = str(d.get("token", ""))
	room_code = str(d.get("room_code", ""))
	alias = str(d.get("alias", ""))
	var saved := str(d.get("server_url", "")).strip_edges()
	if saved != "" and not RETIRED_DEFAULT_URLS.has(saved):
		server_url = saved


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
		if s != "title":
			_join_from_list = false
			if rooms.watching:                   # a game started (or the app locked): the list is over, whatever the screen says
				_watchers = 0
				rooms.stop()
				rooms_changed.emit(rooms.model())
		screen_changed.emit(s)


# ---------------- the open-camps list ----------------

## A screen wants the list (true) or no longer does (false). Counted, so a screen that is rebuilt (its replacement asks
## before the old one has left) never switches the list off by leaving late. Only the title screen shows it.
func rooms_watch(on: bool) -> void:
	if on:
		if screen != "title" or locked_out:
			return
		_watchers += 1
		if _watchers > 1:
			return                               # the list is already running for another screen
		rooms.start(clock.now_msec())
		rooms_changed.emit(rooms.model())
		_watch_connect()
		return
	if _watchers == 0:
		return
	_watchers -= 1
	if _watchers > 0:
		return
	rooms.stop()
	rooms_changed.emit(rooms.model())
	# nothing else is using the line (no seat, nothing waiting for a reply): do not keep it open just for a closed list
	if token == "" and pending_intent.is_empty() and _inflight.is_empty() and screen == "title" and Net.state != "offline":
		Net.close()


## Ask for the list now (a camp filled first; the player pressed refresh). "" when asked, else why not.
func rooms_refresh() -> String:
	if not rooms.watching:
		return "not_watching"
	rooms.refresh_now(clock.now_msec())
	_rooms_tick()
	return "" if rooms.awaiting() or Net.handshake_done else "not_connected"


## The server address was edited while the list is open: the line to the old address is dropped and a new one is made once
## the typing has settled (so every keystroke of a half-typed address is not a connection attempt).
func url_changed() -> void:
	if _watchers == 0 or token != "" or Net.url == server_url:
		return
	Net.close()
	rooms.on_disconnected()
	rooms_changed.emit(rooms.model())
	_watch_reconnect_at = clock.now_msec() + URL_SETTLE_MS


func _watch_only() -> bool:
	return rooms.watching and screen == "title" and pending_intent.is_empty()


func _watch_connect() -> void:
	if not valid_url(server_url) or locked_out:
		return
	if Net.handshake_done and Net.state == "online":
		rooms.refresh_now(clock.now_msec())
		_rooms_tick()
		return
	if Net.state in ["connecting", "reconnecting", "unreachable"]:
		return                                   # already trying
	Net.connect_to(server_url)


## Driven by Net's tick (every frame, or by tests with a fake clock): the settle timer, the 3 s silence rule, the poll.
func _rooms_tick() -> void:
	var now := clock.now_msec()
	if _watch_reconnect_at >= 0 and now >= _watch_reconnect_at:
		_watch_reconnect_at = -1
		_watch_connect()
	if rooms.tick(now):
		Log.event("session", "rooms_hidden_silence", {})
		rooms_changed.emit(rooms.model())
	if not rooms.poll_due(now):
		return
	# never while something waits for its answer (an error would be taken for the wrong request), nor off the title screen
	if screen != "title" or locked_out or not _inflight.is_empty() or not pending_intent.is_empty() or not Net.handshake_done:
		return
	if Net.send("list_rooms") == "":
		_wire += 1
		_list_wire = _wire
		rooms.sent(now)
		rooms_changed.emit(rooms.model())


func _on_rooms(msg: Dictionary) -> void:
	if rooms.on_reply(msg.get("rooms")):
		rooms_changed.emit(rooms.model())


# ---------------- create and join with the list ----------------

## Create a camp. `visibility` ("public" | "private") and `name` go out ONLY once a valid `rooms` reply has shown that this
## server knows them: an old server might reject unknown fields. Returns "" or a reason, like begin().
func create_camp(visibility := "", camp_name := "") -> String:
	var fields := {}
	if rooms.create_fields_ok():
		var vis := RoomsWatch.clean_visibility(visibility)
		if vis != "":
			fields["visibility"] = vis
		var nm := RoomsWatch.clean_name(camp_name)
		if nm != "":
			fields["name"] = nm
	return begin("create_room", fields)


## Join a camp by code. `from_list`: the player tapped a card, so a refusal is worded neutrally (it filled or closed first).
func join_camp(code: String, from_list := false) -> String:
	_join_from_list = from_list
	var why := begin("join_room", {"code": code.strip_edges().to_upper()})
	if why != "":
		_join_from_list = false
	return why
