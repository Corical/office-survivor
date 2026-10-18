extends Node
## The one way server state reaches a screen. Session holds the latest validated view; the Ruleset turns it into a
## neutral model; Feed adds what only the client knows (the clock, the lock state, the connection) and announces it.
## Screens connect to `model_changed` / `status_changed` / `notice_raised` and read `models`, `player`; they never
## read Session, Net or a raw view.

## kind: lobby | round | reveal | end (Survivors) | view (the new wire) | rooms
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
	Session.rooms_changed.connect(_on_rooms)
	Session.games_changed.connect(_on_games)
	Session.room_game_decided.connect(_emit_status)


func reset() -> void:
	models = {}
	player.reset()
	_first_seconds = {}


## The open-camps list, as a neutral model: {supported, rooms: [{code, seats_taken, seats_total, age_s, name}], stale, loading}.
## `supported` is false until the server has answered a list request (and again when it stops answering), so a screen shows
## the list only when it is true, a quiet header while `loading`, and nothing otherwise.
func _on_rooms(m: Dictionary) -> void:
	models["rooms"] = m
	model_changed.emit("rooms", m)


## The games the server offers, as a neutral model: {games: [{id, name, seats_min, seats_max}], pick: bool}. `pick` is true only
## with more than one game: a lone game (or an old server that names none) has nothing to choose, and nothing new is drawn.
func games_model() -> Dictionary:
	return {"games": Session.games.duplicate(true), "pick": Session.games.size() > 1}


func _on_games() -> void:
	var m := games_model()
	models["games"] = m
	model_changed.emit("games", m)


## The name to show for a game id on a camp card: the server's name for it, "" for a lone-game server (no label at all), and the
## neutral "another game" key's text is the screen's to choose when the server did not list the id.
func game_label(id: Variant) -> Dictionary:
	if Session.games.size() < 2:
		return {}
	var e := Session.game_entry(id if id != null else RulesetRegistry.DEFAULT_ID)
	return {"name": e.name} if not e.is_empty() else {"unknown": true}


## The server's entry for the game of the room I am in ({} when none or not listed).
func room_game() -> Dictionary:
	return Session.room_game_entry()


func rooms_model() -> Dictionary:
	return models.get("rooms", {"supported": false, "rooms": [], "stale": false, "loading": false})


func _on_view(v: Dictionary) -> void:
	var rs: Ruleset = Session.ruleset
	var kind: String = v.t
	var m: Dictionary
	match kind:
		"lobby":
			m = rs.lobby_model(v)
			if Session.games.size() > 1:
				m["game"] = Session.room_game_entry()      # the room's game, for the seat range; a lone-game server adds nothing
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
		"view":
			m = rs.view_model(v)       # the new wire: any phase of any game, one model under one kind
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


## The screen ids the room's game draws (from its phases). The router shows a game screen only if the room's ruleset names it.
func game_screens() -> Array:
	var out: Array = []
	for p in Session.ruleset.phases().values():
		out.append(str(p.get("screen", "")))
	return out


func seconds_left() -> int:
	return Session.seconds_left_now()


func status() -> Dictionary:
	return {"net": Net.state, "net_key": UiKeys.net_key(Net.state), "attempt": Net.attempt,
		"terminal": Session.terminal_reason, "awaiting_view": Session.awaiting_view, "screen": Session.screen,
		"has_seat": Session.token != "", "room_code": Session.room_code, "alias": Session.alias,
		"is_host": Session.host, "server_url": Session.server_url, "entering": Session.entering_camp(),
		"unsupported_game": Session.unsupported_game}


func _emit_status() -> void:
	status_changed.emit(status())


func _on_notice(kind: String, code: String, text: String) -> void:
	notice_raised.emit({"kind": kind, "code": code, "key": UiKeys.notice_key(kind, code), "text": text})
