extends Node
## The one way server state reaches a screen. Session holds the latest validated view; the Ruleset turns it into a
## neutral model; Feed adds what only the client knows (the clock, the lock state, the connection) and announces it.
## Screens connect to `model_changed` / `status_changed` / `notice_raised` and read `models`, `player`; they never
## read Session, Net or a raw view.

## kind: lobby | round | reveal | end
signal model_changed(kind: String, model: Dictionary)
signal status_changed(status: Dictionary)
signal notice_raised(notice: Dictionary)

var models := {}                       # kind -> latest model
var player := TimelinePlayer.new()     # the reveal as a timeline; created once per round, never restarted
var _first_seconds := {}               # "room|round" -> the first seconds_left seen, the base of a timer ring


func _ready() -> void:
	Session.view_changed.connect(_on_view)
	Session.screen_changed.connect(func(_s): _emit_status())
	Session.notice.connect(_on_notice)
	Net.state_changed.connect(func(_s): refresh())


func reset() -> void:
	models = {}
	player.reset()
	_first_seconds = {}


func _on_view(v: Dictionary) -> void:
	var rs: Ruleset = Session.ruleset
	var kind: String = v.t
	var m: Dictionary
	match kind:
		"lobby":
			m = rs.lobby_model(v)
		"round":
			m = rs.round_model(v)
			var key := "%s|%s" % [Session.room_code, v.round]
			if not _first_seconds.has(key):
				_first_seconds[key] = float(v.seconds_left)
			m["timer"] = _timer_for(float(v.seconds_left), float(_first_seconds[key]))
			m["lock"] = _lock_now()
			player.later_round_arrived(int(v.round))
		"reveal":
			m = rs.reveal_model(v, Session.alias, Session.before_state_for(int(v.round)))
			m["timer"] = _timer_for(float(v.seconds_left), 0.0)
			player.offer(m, Session.room_code)
		"end":
			m = rs.end_model(v, Session.alias)
			player.later_round_arrived(1 << 30)
		_:
			return                     # upgrade_required and friends have no model; the status carries them
	models[kind] = m
	model_changed.emit(kind, m)
	_emit_status()


## The clock-derived timer fields. A ring draws fraction = remaining / total; "known" is false while the view is stale.
func _timer_for(seconds_left: float, first: float) -> Dictionary:
	return {"seconds_left": seconds_left, "received_msec": Session.view_msec,
		"deadline_msec": Session.view_msec + int(seconds_left * 1000.0),
		"total_s": maxf(first, seconds_left), "known": Session.timer_known()}


func _lock_now() -> Dictionary:
	return {"state": Session.lock_state(), "picker_open": Session.picker_open()}


## Re-derive the parts of the round model that change without a new view (an intent was sent, the network dropped).
func refresh() -> void:
	if models.has("round"):
		var m: Dictionary = models.round
		m["lock"] = _lock_now()
		if m.has("timer"):
			m.timer["known"] = Session.timer_known()
		model_changed.emit("round", m)
	_emit_status()


func seconds_left() -> int:
	return Session.seconds_left_now()


func status() -> Dictionary:
	return {"net": Net.state, "net_key": UiKeys.net_key(Net.state), "attempt": Net.attempt,
		"terminal": Session.terminal_reason, "awaiting_view": Session.awaiting_view, "screen": Session.screen,
		"has_seat": Session.token != "", "room_code": Session.room_code, "alias": Session.alias,
		"is_host": Session.host, "server_url": Session.server_url}


func _emit_status() -> void:
	status_changed.emit(status())


func _on_notice(kind: String, code: String, text: String) -> void:
	notice_raised.emit({"kind": kind, "code": code, "key": UiKeys.notice_key(kind, code), "text": text})
