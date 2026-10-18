class_name FakeTransport
extends Transport
## A transport the test plays the server on. `sent` holds what the client sent, parsed.

var sent: Array = []
var open_urls: Array = []
var closes := 0
var _open := false


func open(url: String) -> Error:
	open_urls.append(url)
	return OK


func send_text(text: String) -> Error:
	if not _open:
		return ERR_UNAVAILABLE
	sent.append(SafeJson.parse(text))
	return OK


func close() -> void:
	closes += 1
	_open = false


func is_open() -> bool:
	return _open


# ---- the server's side ----

func server_open() -> void:
	_open = true
	opened.emit()


func server_send(d: Dictionary) -> void:
	text_received.emit(JSON.stringify(d))


func server_raw(s: String) -> void:
	text_received.emit(s)


func server_close(code: int, reason := "") -> void:
	_open = false
	closed.emit(code, reason)


func types() -> Array:
	return sent.map(func(m): return m.t)


func count(t: String) -> int:
	return types().count(t)


func last(t: String) -> Dictionary:
	for i in range(sent.size() - 1, -1, -1):
		if sent[i].t == t:
			return sent[i]
	return {}
