extends Node
## One connection to the server: open, hello handshake, JSON in and out, reconnect with backoff, and the watchdogs
## that notice a dead socket. Net knows nothing about screens or the game; Session decides what a message means.

signal handshaken
signal message_received(msg: Dictionary)
signal state_changed(state: String)
## The connection ended for a reason reconnecting cannot fix: seat_gone | upgrade_required | taken_over | too_big
signal terminal(reason: String)

const PROTO := 1
const BACKOFF := [1.0, 2.0, 4.0, 8.0]   # seconds; chosen
const HELLO_TIMEOUT_MS := 5000           # chosen: open but no hello_ok -> try again
const ACK_TIMEOUT_MS := 8000             # chosen: the server answers every accepted intent with a view; silence = dead
const TOO_BIG_TRIES := 2                 # chosen: 1009 closes before we give up
const UNREACHABLE_AFTER := 4             # attempts before the banner says "can't reach the server"
## Close codes the server sends after a terminal message (requested in the brief); the message itself may be lost.
const CLOSE_CODES := {4001: "seat_gone", 4002: "upgrade_required", 4003: "taken_over", 1009: "too_big"}
## The server knows who we are from the connection. An intent that names a seat is a bug, never sent.
const FORBIDDEN_KEYS := ["seat", "pid", "player", "player_id", "seat_id"]
## Intents that get no view back (the server answers leave by dropping us).
const NO_REPLY := ["hello", "leave"]

var transport: Transport
var clock: Clock = Clock.new()
var url := ""
## offline | connecting | online | reconnecting | unreachable | stopped (terminal)
var state := "offline"
var handshake_done := false
var attempt := 0
var log_payloads := OS.is_debug_build()

var _want := false
var _retry_at := -1
var _hello_deadline := -1
var _ack_deadline := -1
var _too_big := 0


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
	_ack_deadline = -1
	_too_big = 0
	attempt = 0
	handshake_done = false
	url = ""
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
	_open()


func close() -> void:
	_want = false
	_retry_at = -1
	_hello_deadline = -1
	_ack_deadline = -1
	handshake_done = false
	transport.close()
	_set_state("offline")


## Send one intent. Returns "" when sent, else a reason: forbidden_key | not_connected | send_failed.
func send(t: String, fields := {}) -> String:
	for k in fields:
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
		_ack_deadline = clock.now_msec() + ACK_TIMEOUT_MS
	return ""


func _process(_delta: float) -> void:
	if transport:
		transport.poll()
	tick()


## Watchdogs and retry timer; called every frame, and directly by tests with a fake clock.
func tick() -> void:
	var now := clock.now_msec()
	if _retry_at >= 0 and now >= _retry_at:
		_retry_at = -1
		_open()
	if _hello_deadline >= 0 and now >= _hello_deadline:
		_hello_deadline = -1
		Log.event("net", "hello_timeout", {"url": url}, "WARN")
		_drop_and_retry()
	if _ack_deadline >= 0 and now >= _ack_deadline:
		_ack_deadline = -1
		Log.event("net", "ack_timeout", {"url": url}, "WARN")
		_drop_and_retry()


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
	_ack_deadline = -1
	handshake_done = false
	transport.close()
	_set_state("stopped")
	Log.event("net", "terminal", {"reason": reason}, "WARN")
	terminal.emit(reason)


func _on_opened() -> void:
	Log.event("net", "open", {"url": url})
	_send_raw({"t": "hello", "proto": PROTO, "client_build": str(ProjectSettings.get_setting(
		"application/config/version"))})


func _on_closed(code: int, reason: String) -> void:
	if state == "stopped":
		return
	handshake_done = false
	_hello_deadline = -1
	_ack_deadline = -1
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
	if state == "stopped":
		Log.event("net", "dropped_after_stop", {"bytes": text.length()})
		return
	var data: Variant = SafeJson.parse(text)
	if not (data is Dictionary) or typeof(data.get("t")) != TYPE_STRING:
		Log.event("net", "dropped_not_a_message", {"bytes": text.length(), "head": text.left(60)}, "WARN")
		return
	var msg: Dictionary = normalize(data)
	_ack_deadline = -1
	if msg.t != "hello_ok":
		_too_big = 0              # a real message got through, so the size problem was one-off
	Log.event("net", "rx", {"t": msg.t, "bytes": text.length()})
	if log_payloads:
		Log.event("net", "rx_payload", {"json": JSON.stringify(redact(msg))})
	match msg.t:
		"hello_ok":
			handshake_done = true
			_hello_deadline = -1
			attempt = 0
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
