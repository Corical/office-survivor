class_name RoomsWatch
extends RefCounted
## The "open camps" list: what the client knows about the server's `rooms` replies, when to ask again, and when to give
## up. This is the ONE place that knows the proposal in docs/arena/GODOT_FOUNDATION.md ("18 Oct 2026 13:59"), so a
## change of the server's mind is a change here:
##   client -> server  list_rooms                      (no fields)
##   server -> client  rooms {rooms: [{code, seats_taken, seats_total, age_s, name?}]}   newest first, at most 20
##   create_room may carry visibility ("public" | "private") and name (<= 24 chars), only once a valid `rooms` reply
##   has proven the server understands them.
## Assumptions where the proposal is silent (all easy to change below): codes are letters and digits; a room with no free
## seat is not a joinable camp and is dropped; an entry without a usable `age_s` is dropped; `age_s` above a week is
## shown as a week; replies carry no request id, so they are matched by order and a late reply after `stop()` is ignored.
##
## Pure logic: no nodes, no clock of its own (every time is passed in, in milliseconds) and nothing from the engine
## except Log, so tests drive it with numbers.

const POLL_MS := 3000                 # ask again this often while the list is showing (the proposal's "about every 3 s")
const SLOW_POLL_MS := 15000           # chosen: once the list was hidden (no usable answer), ask this rarely, in case the server upgrades
const SILENCE_MS := 3000              # no `rooms` reply this long after a request: hide the list (the proposal)
const MAX_ROOMS := 20                 # the proposal's max_rooms
const MAX_RAW := 200                  # chosen: entries looked at, however long the list is, so a hostile frame costs a bounded time
const MAX_NAME := 24                  # the proposal
const MAX_CODE := 12                  # chosen: real codes are 4 letters; anything longer is not a code
const MAX_SEATS := 12                 # chosen: a camp bigger than this is not one this client can draw
const MAX_AGE_S := 604800             # chosen: a week; "absurd" ages are shown as this
const VISIBILITIES := ["public", "private"]

var watching := false
var connected := false
var supported := false                # a valid `rooms` reply has been seen on this connection
var rooms: Array = []                 # clean entries: {code, seats_taken, seats_total, age_s, name}
var stale := false                    # the connection dropped: this is the last list we had
var loading := false                  # asked, never answered yet (the list shows its quiet header, not its rows)
var requests := 0                     # how many list_rooms went out (tests)
var replies := 0                      # how many were taken in (tests)

var _next_poll_ms := 0
var _awaiting_since := -1
var _hidden := false                  # we gave up on this server: poll slowly


func model() -> Dictionary:
	return {"supported": supported, "rooms": rooms.duplicate(true), "stale": stale, "loading": loading}


func awaiting() -> bool:
	return _awaiting_since >= 0


## The list screen asked for the list. Rooms already known stay (a screen rebuilt a moment later should not flash empty).
func start(now: int) -> void:
	if watching:
		return
	watching = true
	_next_poll_ms = now
	loading = not supported


## The list screen is gone (or a game started). A reply that arrives after this is ignored.
func stop() -> void:
	watching = false
	_awaiting_since = -1
	loading = false


## Handshake done: the server may be a different build from last time, so it must prove itself again.
func on_connected(now: int) -> void:
	connected = true
	supported = false
	_hidden = false
	_awaiting_since = -1
	_next_poll_ms = now
	loading = watching
	stale = false


func on_disconnected() -> void:
	connected = false
	_awaiting_since = -1
	loading = false
	stale = not rooms.is_empty()


## Ask again at the next opportunity (a camp filled or vanished first; the player pressed refresh).
func refresh_now(now: int) -> void:
	_next_poll_ms = now


func poll_due(now: int) -> bool:
	return watching and connected and now >= _next_poll_ms


## A list_rooms went out.
func sent(now: int) -> void:
	requests += 1
	_next_poll_ms = now + (SLOW_POLL_MS if _hidden else POLL_MS)
	if _awaiting_since < 0:
		_awaiting_since = now                 # the clock runs from the OLDEST unanswered request
	if not supported and not _hidden:
		loading = true                            # a list we gave up on is not "loading" again at every slow poll


## True when this call changed what the screen shows (silence hid the list).
func tick(now: int) -> bool:
	if watching and _awaiting_since >= 0 and now - _awaiting_since >= SILENCE_MS:
		_hide(now)
		return true
	return false


## A `rooms` frame. Returns true when the shown list changed. Ignored while nobody is watching, and ignored when its
## `rooms` is not a list at all (then it counts as no answer, and silence will hide the list).
func on_reply(raw: Variant) -> bool:
	if not watching:
		Log.event("rooms", "late_reply_ignored", {})
		return false
	var clean: Variant = sanitize(raw)
	if clean == null:
		Log.event("rooms", "bad_reply", {"type": typeof(raw)}, "WARN")
		return false
	replies += 1
	supported = true
	_hidden = false
	loading = false
	stale = false
	_awaiting_since = -1
	rooms = clean
	return true


## An `error` that answers list_rooms. `rate_limited` is an answer ("the list you have is current"); anything else means
## this server does not do lists.
func on_error(code: String, now: int) -> bool:
	if not watching:
		return false
	_awaiting_since = -1
	if code == "rate_limited":
		loading = false
		return false
	_hide(now)
	return true


func _hide(now: int) -> void:
	supported = false
	rooms = []
	stale = false
	loading = false
	_hidden = true
	_awaiting_since = -1
	_next_poll_ms = now + SLOW_POLL_MS            # having given up, ask rarely, not at the very next beat


# ---------------- hostile input ----------------

## The clean list for a `rooms` value: at most MAX_ROOMS entries, each one checked and cleaned, bad ones dropped, a
## repeated code kept once (the first, the newest). Null when `raw` is not a list.
static func sanitize(raw: Variant) -> Variant:
	if not (raw is Array):
		return null
	var out: Array = []
	var seen := {}
	var looked := 0
	for e in raw:
		looked += 1
		if looked > MAX_RAW:
			break
		var r := _entry(e)
		if r.is_empty() or seen.has(r.code):
			continue
		seen[r.code] = true
		out.append(r)
		if out.size() >= MAX_ROOMS:
			break
	return out


static func _entry(e: Variant) -> Dictionary:
	if not (e is Dictionary):
		return {}
	var code := _code(e.get("code"))
	var taken: Variant = _whole(e.get("seats_taken"))
	var total: Variant = _whole(e.get("seats_total"))
	if code == "" or taken == null or total == null:
		return {}
	if int(taken) < 0 or int(total) < 1 or int(total) > MAX_SEATS or int(taken) >= int(total):
		return {}                                   # negative, absurd, or no free seat: not a camp anyone can join
	var age: Variant = e.get("age_s")
	if not (typeof(age) == TYPE_INT or typeof(age) == TYPE_FLOAT) or not is_finite(float(age)) or float(age) < 0.0:
		return {}
	return {"code": code, "seats_taken": int(taken), "seats_total": int(total),
		"age_s": int(minf(float(age), float(MAX_AGE_S))), "name": clean_name(e.get("name"))}


static func _code(v: Variant) -> String:
	if not (v is String):
		return ""
	var s: String = (v as String).strip_edges().to_upper()
	if s.length() < 1 or s.length() > MAX_CODE:
		return ""
	for i in s.length():
		var c := s.unicode_at(i)
		if not ((c >= 48 and c <= 57) or (c >= 65 and c <= 90)):
			return ""
	return s


## An integer, or null: a whole number only (a float with a fraction, a bool, a string, a huge value are all "not a count").
static func _whole(v: Variant) -> Variant:
	match typeof(v):
		TYPE_INT:
			return v if absi(v) < 1000000 else null
		TYPE_FLOAT:
			return int(v) if is_finite(v) and v == floorf(v) and absf(v) < 1000000.0 else null
	return null


## A camp name made safe to show: text only, control and direction-changing characters removed, runs of spaces made one,
## trimmed, at most MAX_NAME characters. Anything that is not text becomes "". Used for names coming IN and going OUT.
static func clean_name(v: Variant) -> String:
	if not (v is String):
		return ""
	var s: String = v
	var out := ""
	var last_space := true
	var looked := 0
	for i in s.length():
		looked += 1
		if looked > 400 or out.length() >= MAX_NAME + 1:
			break                                       # a 10 000 character name is cut before it costs anything
		var c := s.unicode_at(i)
		var blank := c == 32 or c == 9 or c == 10 or c == 13 or c == 0xA0 or c == 0x3000       # tab and line breaks read as a space
		var junk := (c < 32 and not blank) or (c >= 127 and c < 160) or (c >= 0x200B and c <= 0x200F) or (c >= 0x202A and c <= 0x202E) \
			or (c >= 0x2060 and c <= 0x2069) or c == 0xFEFF or c == 0xFFFC or c == 0xFFFD or (c >= 0xD800 and c <= 0xDFFF)
		if junk:
			continue
		if blank:
			if last_space:
				continue
			last_space = true
			out += " "
		else:
			last_space = false
			out += char(c)
	return out.strip_edges().left(MAX_NAME).strip_edges()


## "public" or "private" when `v` is one of them, else "".
static func clean_visibility(v: Variant) -> String:
	return v if (v is String and (v as String) in VISIBILITIES) else ""
