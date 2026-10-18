class_name BaseTest
extends Node
## Base for tests: a fresh Net + Session wired to a fake transport, fake clock and in-memory store. Nothing a test does
## touches the player's session file.

var failures: Array[String] = []
var clock: FakeClock
var fake: FakeTransport
var store: MemorySessionStore
var notices: Array = []
var mark := 0


func setup() -> void:
	clock = FakeClock.new()
	fake = FakeTransport.new()
	store = MemorySessionStore.new()
	Net.reset()
	Net.use_transport(fake)
	Net.clock = clock
	Net.log_payloads = false
	Session.reset(store, clock)
	Session.server_url = "ws://test"
	notices.clear()
	if not Session.notice.is_connected(_on_notice):
		Session.notice.connect(_on_notice)
	mark = Log.mark()


func teardown() -> void:
	if Session.notice.is_connected(_on_notice):
		Session.notice.disconnect(_on_notice)


func _on_notice(kind: String, code: String, text: String) -> void:
	notices.append({"kind": kind, "code": code, "text": text})


# ---- assertions ----

func check(cond: bool, msg := "check failed") -> void:
	if not cond:
		failures.append(msg)


func eq(got: Variant, want: Variant, msg := "") -> void:
	if typeof(got) != typeof(want) or got != want:
		failures.append("%s: got %s, wanted %s" % [msg, str(got), str(want)])


func no_errors() -> void:
	var bad := Log.since(mark, "ERROR")
	if not bad.is_empty():
		failures.append("unexpected ERROR lines: " + str(bad))


# ---- scenario helpers ----

func go_online() -> void:
	Net.connect_to("ws://test")
	fake.server_open()
	fake.server_send({"t": "hello_ok", "proto": 1})


func give_seat(tok := "tok-secret-1", room := "ABCD", is_host := true) -> void:
	fake.server_send({"t": "seat", "token": tok, "room_code": room, "alias": "Mango", "host": is_host})


func round_view(n := 1, locked := false, secs := 180, locked_count := 0) -> Dictionary:
	return {"t": "round", "round": n, "rounds": 10, "seconds_left": secs,
		"me": {"alias": "Mango", "rations": 7, "bandit": false, "guards_left": 3, "guarded": false,
			"goal": {"code": "give", "target": null, "text": "give away 3 rations over the game"},
			"goal_progress": {"state": "open", "text": "0/3 given"}},
		"legal": {"scavenge": [], "guard": [], "steal": ["Fig", "Kiwi"], "gift": ["Fig", "Kiwi"]},
		"gift_amounts": [1, 2], "my_pick": null, "my_locked": locked, "locked_count": locked_count,
		"seats_total": 4, "radio_available": true, "radio_phrases": [], "aliases": ["Fig", "Kiwi", "Plum"],
		"board": null}


func in_round(n := 1) -> void:
	go_online()
	give_seat()
	fake.server_send(round_view(n))
