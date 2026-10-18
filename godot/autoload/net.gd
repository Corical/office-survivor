extends Node
## One connection to the server: open, hello handshake, JSON in and out, reconnect with backoff, and the watchdogs
## that notice a dead socket. Net knows nothing about screens or the game; Session decides what a message means.

signal handshaken
signal message_received(msg: Dictionary)
signal state_changed(state: String)
## The connection ended for a reason reconnecting cannot fix: seat_gone | upgrade_required | taken_over | too_big | flapping
signal terminal(reason: String)
## Nothing has arrived for a while on an idle connection: the owner of the seat should probe it (an idle half-open
## socket otherwise looks alive for ever, because the server only speaks when something changes).
signal probe_due
## After every watchdog pass (every frame; directly by tests with a fake clock). Timers owned elsewhere (the open-camps poll)
## ride on it so one clock drives everything.
signal ticked

const PROTO := 1
const BACKOFF := [1.0, 2.0, 4.0, 8.0]   # seconds; chosen
const HELLO_TIMEOUT_MS := 5000           # chosen: open but no hello_ok -> try again
const ACK_TIMEOUT_MS := 8000             # chosen: the server answers every accepted intent; silence = dead
const PROBE_MS := 30000                  # chosen: idle this long -> probe (a round is 180 s of silence otherwise)
const TOO_BIG_TRIES := 2                 # chosen: oversize frames before we give up
const MAX_TEXT := 64 * 1024              # chosen: bytes; the engine's own buffer limit proved looser than its name
const STABLE_MS := 10000                 # chosen: a connection that lived this long was healthy; backoff restarts
const FLAP_LIMIT := 4                    # chosen: short-lived connections in a row before we stop and say so
const UNREACHABLE_AFTER := 4             # attempts before the banner says "can't reach the server"
## Close codes the server sends after a terminal message (requested in the brief); the message itself may be lost.
const CLOSE_CODES := {4001: "seat_gone", 4002: "upgrade_required", 4003: "taken_over", 4004: "kicked", 1009: "too_big"}
## The server knows who we are from the connection. An intent that names a seat is a bug, never sent.
const FORBIDDEN_KEYS := ["seat", "pid", "player", "player_id", "seat_id"]
## Intents that get no reply (the server answers leave by dropping us). `list_rooms` is here because an old server may
## never answer it, and a missing answer must not look like a dead socket: the open-camps list has its own 3 s rule.
const NO_REPLY := ["hello", "leave", "list_rooms", "kick"]       # kick: the server answers it only with a fresh lobby (or a refusal)

var transport: Transport
var clock: Clock = Clock.new()
var url := ""
## offline | connecting | online | reconnecting | unreachable | stopped (terminal)
var state := "offline"
var handshake_done := false
## `features` from the latest hello_ok (null when the server sent none). Set right before `handshaken` fires, so whoever
## handles that signal reads this connection's value, never a previous connection's.
var server_features: Variant = null
## `games` from the latest hello_ok, as the server sent it (null when it sent none: the old server, Survivors only). Cleaned by
## RoomsWatch.sanitize_games, never trusted here. Set right before `handshaken` fires, like `server_features`.
var server_games: Variant = null
var attempt := 0
var probe_ms := PROBE_MS
var log_payloads := OS.is_debug_build()

var _want := false
var _retry_at := -1
var _hello_deadline := -1
var _acks := {}                # intent type -> deadline (ms); one per kind of intent in flight (review N08)
var _too_big := 0
var _up_since := -1            # when the current connection got hello_ok
var _short_lives := 0          # connections in a row that ended within STABLE_MS of hello_ok
var _last_rx := 0


func _ready() -> void:
	use_transport(WsTransport.new())


func use_transport(t: Transport) -> void:
	if transport:
		for s in [["opened", _on_opened], ["closed", _on_closed], ["text_received", _on_text],
				["binary_received", _on_binary]]:
			if transport.is_connected(s[0], s[1]):
				transport.disconnect(s[0], s[1])
	transport = t
	transport.opened.connect(_on_opened)
	transport.closed.connect(_on_closed)
	transport.text_received.connect(_on_text)
	transport.binary_received.connect(_on_binary)


## Back to a fresh state (tests; also "Back to title" after a terminal reason).
func reset() -> void:
	_want = false
	_retry_at = -1
	_hello_deadline = -1
	_acks.clear()
	_too_big = 0
	_up_since = -1
	_short_lives = 0
	attempt = 0
	handshake_done = false
	server_games = null
	url = ""
	probe_ms = PROBE_MS
	if transport:
		transport.close()
	_set_state("offline")


func connect_to(server_url: String) -> void:
	if server_url == url and state in ["connecting", "online", "reconnecting", "unreachable"]:
		Log.event("net", "connect_ignored", {"state": state})
		return
	if state != "offline":
		transport.close()
	url = server_url
	_want = true
	attempt = 0
	_too_big = 0
	_short_lives = 0
	_up_since = -1
	_open()


func close() -> void:
	_want = false
	_retry_at = -1
	_hello_deadline = -1
	_acks.clear()
	handshake_done = false
	transport.close()
	_set_state("offline")


## Send one intent. Returns "" when sent, else a reason: forbidden_key | not_connected | send_failed.
## `ack_ms`: how long to wait for the server's answer before the line is called dead. The default is ACK_TIMEOUT_MS; an intent the
## server answers late on purpose (Continue waits for the others) says how long its answer may take.
func send(t: String, fields := {}, ack_ms := -1) -> String:
	for k in fields:
		# the ONE exception: a kick carries the opaque handle of the seat to remove, in a field the server calls `seat`
		# (the handle comes from the latest lobby; it is not a seat id or a player id and means nothing to anyone else)
		if t == "kick" and str(k) == "seat" and fields[k] is String:
			continue
		if str(k).to_lower() in FORBIDDEN_KEYS:
			Log.event("net", "refused_seat_field", {"t": t, "key": k}, "ERROR")
			return "forbidden_key"
	if not handshake_done:
		Log.event("net", "dropped_offline", {"t": t, "state": state}, "WARN")
		return "not_connected"
	var msg: Dictionary = fields.duplicate()
	msg["t"] = t
	if not _send_raw(msg):
		return "send_failed"
	if not t in NO_REPLY:
		_acks[t] = clock.now_msec() + (ack_ms if ack_ms > 0 else ACK_TIMEOUT_MS)
	return ""


## The reply to intent `t` arrived: stop waiting for it.
func ack(t: String) -> void:
	_acks.erase(t)


## Stop waiting for every intent except those named.
func ack_except(keep: Array) -> void:
	for k in _acks.keys():
		if not k in keep:
			_acks.erase(k)


## Drop this connection and open a new one after the next backoff step (a rate-limited resume, say).
func reconnect_later() -> void:
	if _want:
		_drop_and_retry()


## Drop this connection and open a new one now (the app came back from the background).
func reconnect_now() -> void:
	if not _want:
		return
	transport.close()
	handshake_done = false
	_hello_deadline = -1
	_acks.clear()
	_retry_at = clock.now_msec()
	_set_state("reconnecting")


func _process(_delta: float) -> void:
	if transport:
		transport.poll()
	tick()


## Watchdogs and retry timer; called every frame, and directly by tests with a fake clock.
func tick() -> void:
	_watchdogs()
	ticked.emit()


func _watchdogs() -> void:
	var now := clock.now_msec()
	if _retry_at >= 0 and now >= _retry_at:
		_retry_at = -1
		_open()
	if _hello_deadline >= 0 and now >= _hello_deadline:
		_hello_deadline = -1
		Log.event("net", "hello_timeout", {"url": url}, "WARN")
		_drop_and_retry()
		return
	for k in _acks.keys():
		if now >= _acks[k]:
			Log.event("net", "ack_timeout", {"intent": k, "url": url}, "WARN")
			_drop_and_retry()
			return
	if handshake_done and probe_ms > 0 and now - _last_rx >= probe_ms and _acks.is_empty():
		_last_rx = now
		Log.event("net", "probe_due", {"idle_ms": probe_ms})
		probe_due.emit()


func _open() -> void:
	handshake_done = false
	_set_state("connecting" if attempt == 0 else ("unreachable" if attempt >= UNREACHABLE_AFTER else "reconnecting"))
	var err: int = transport.open(url)
	if err != OK:
		Log.event("net", "open_failed", {"url": url, "error": err}, "ERROR")
		_schedule_retry()
		return
	_hello_deadline = clock.now_msec() + HELLO_TIMEOUT_MS


func _drop_and_retry() -> void:
	handshake_done = false
	_hello_deadline = -1
	_acks.clear()
	transport.close()
	_schedule_retry()


func _schedule_retry() -> void:
	if not _want:
		return
	var wait: float = BACKOFF[mini(attempt, BACKOFF.size() - 1)]
	attempt += 1
	_retry_at = clock.now_msec() + int(wait * 1000)
	_set_state("unreachable" if attempt >= UNREACHABLE_AFTER else "reconnecting")
	Log.event("net", "retry_scheduled", {"attempt": attempt, "in_s": wait})


func _stop(reason: String) -> void:
	_want = false
	_retry_at = -1
	_hello_deadline = -1
	_acks.clear()
	handshake_done = false
	transport.close()
	_set_state("stopped")
	Log.event("net", "terminal", {"reason": reason}, "WARN")
	terminal.emit(reason)


func _on_opened() -> void:
	Log.event("net", "open", {"url": url})
	_last_rx = clock.now_msec()
	_send_raw({"t": "hello", "proto": PROTO, "client_build": str(ProjectSettings.get_setting(
		"application/config/version"))})


func _on_closed(code: int, reason: String) -> void:
	if state == "stopped":
		return
	var lived := clock.now_msec() - _up_since if _up_since >= 0 else -1
	_up_since = -1
	handshake_done = false
	_hello_deadline = -1
	_acks.clear()
	if lived >= STABLE_MS:
		attempt = 0
		_short_lives = 0
	elif lived >= 0:
		_short_lives += 1              # up, then dropped quickly: the signature of two devices fighting for a seat
		if _short_lives >= FLAP_LIMIT:
			Log.event("net", "flapping", {"short_lives": _short_lives, "code": code}, "WARN")
			_stop("flapping")
			return
	var why: String = CLOSE_CODES.get(code, "")
	if why == "too_big":
		_too_big += 1
		Log.event("net", "frame_too_big", {"tries": _too_big}, "WARN")
		if _too_big >= TOO_BIG_TRIES:
			_stop("too_big")
			return
	elif why != "":
		_stop(why)
		return
	if _want:
		Log.event("net", "lost", {"code": code, "reason": reason}, "WARN")
		_schedule_retry()
	else:
		Log.event("net", "closed", {"code": code})
		_set_state("offline")


func _on_binary(size: int) -> void:
	Log.event("net", "dropped_binary", {"bytes": size}, "WARN")


func _on_text(text: String) -> void:
	if state == "stopped" or not _want:
		# a frame that was already on its way when we closed on purpose must not move the game (review N05)
		Log.event("net", "dropped_unwanted", {"bytes": text.length(), "state": state})
		return
	if text.length() > MAX_TEXT / 4 and text.to_utf8_buffer().size() > MAX_TEXT:
		_too_big += 1
		Log.event("net", "frame_too_big", {"bytes": text.to_utf8_buffer().size(), "tries": _too_big}, "WARN")
		if _too_big >= TOO_BIG_TRIES:
			_stop("too_big")
		else:
			_drop_and_retry()
		return
	var data: Variant = SafeJson.parse(text)
	if not (data is Dictionary) or typeof(data.get("t")) != TYPE_STRING:
		Log.event("net", "dropped_not_a_message", {"bytes": text.length(), "head": text.left(60)}, "WARN")
		return
	var msg: Dictionary = normalize(data)
	_last_rx = clock.now_msec()
	if msg.t != "hello_ok":
		_too_big = 0              # a real message got through, so the size problem was one-off
	Log.event("net", "rx", {"t": msg.t, "bytes": text.length()})
	if log_payloads:
		Log.event("net", "rx_payload", {"json": JSON.stringify(redact(msg))})
	match msg.t:
		"hello_ok":
			if handshake_done:
				Log.event("net", "duplicate_hello_ok", {}, "WARN")      # review N06: never re-fire the handshake
				return
			handshake_done = true
			server_features = msg.get("features")
			server_games = msg.get("games")
			_hello_deadline = -1
			_up_since = clock.now_msec()      # attempt is NOT reset here: only a connection that stays up earns that
			_set_state("online")
			handshaken.emit()
		"upgrade_required":
			message_received.emit(msg)
			_stop("upgrade_required")
			return
		"error":
			if msg.get("code") == "taken_over":
				message_received.emit(msg)
				_stop("taken_over")      # reconnecting would take the seat back from the other device
				return
			if msg.get("code") == "kicked":
				message_received.emit(msg)
				_stop("kicked")          # the host removed this seat: reconnecting would only be refused (seat_gone)
				return
	message_received.emit(msg)


func _send_raw(msg: Dictionary) -> bool:
	var err: int = transport.send_text(JSON.stringify(msg))
	if err != OK:
		Log.event("net", "send_failed", {"t": msg.t, "error": err}, "WARN")
		return false
	Log.event("net", "tx", {"t": msg.t})
	return true


func _set_state(s: String) -> void:
	if s != state:
		Log.event("net", "state", {"from": state, "to": s})
		state = s
		state_changed.emit(s)


static func redact(msg: Dictionary) -> Dictionary:
	var out := msg.duplicate(true)
	if out.has("token"):
		out["token"] = "<redacted>"
	return out


## JSON gives every number as a float; whole numbers become ints so `amount == 2` and "5 rations" read right.
static func normalize(v: Variant) -> Variant:
	match typeof(v):
		TYPE_FLOAT:
			return int(v) if is_finite(v) and v == floor(v) and absf(v) < 1e15 else v
		TYPE_DICTIONARY:
			var d := {}
			for k in v:
				d[k] = normalize(v[k])
			return d
		TYPE_ARRAY:
			var a := []
			for x in v:
				a.append(normalize(x))
			return a
	return v
