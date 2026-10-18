class_name Transport
extends RefCounted
## The transport port. Net talks only to this: WsTransport is the default, tests/fake_transport.gd the double.

signal opened
signal closed(code: int, reason: String)
signal text_received(text: String)
signal binary_received(size: int)


func open(_url: String) -> Error:
	return ERR_UNAVAILABLE


func send_text(_text: String) -> Error:
	return ERR_UNAVAILABLE


func close() -> void:
	pass


func is_open() -> bool:
	return false


func poll() -> void:
	pass
