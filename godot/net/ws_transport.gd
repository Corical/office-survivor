class_name WsTransport
extends Transport
## The default transport: one WebSocketPeer per open().

const MAX_FRAME := 64 * 1024        # chosen: a real view is a few hundred bytes; a bigger frame closes with 1009
const HEARTBEAT := 10.0             # chosen: seconds between pings, so the server notices a dead phone

var _peer: WebSocketPeer
var _state := WebSocketPeer.STATE_CLOSED


func open(url: String) -> Error:
	if _peer:
		_peer.close()                  # never orphan a previous peer
	_peer = WebSocketPeer.new()
	_peer.inbound_buffer_size = MAX_FRAME
	_peer.heartbeat_interval = HEARTBEAT
	var err := _peer.connect_to_url(url)
	_state = WebSocketPeer.STATE_CONNECTING if err == OK else WebSocketPeer.STATE_CLOSED
	return err


func send_text(text: String) -> Error:
	if not is_open():
		return ERR_UNAVAILABLE
	return _peer.send_text(text)


func close() -> void:
	if _peer:
		_peer.close(1000, "client closed")


func is_open() -> bool:
	return _peer != null and _peer.get_ready_state() == WebSocketPeer.STATE_OPEN


func poll() -> void:
	if _peer == null:
		return
	_peer.poll()
	var state := _peer.get_ready_state()
	# drain before reporting a close, so anything that did arrive is delivered first
	while _peer.get_available_packet_count() > 0:
		var pkt := _peer.get_packet()
		if _peer.was_string_packet():
			text_received.emit(pkt.get_string_from_utf8())
		else:
			binary_received.emit(pkt.size())
	if state != _state:
		var was := _state
		_state = state
		if state == WebSocketPeer.STATE_OPEN:
			opened.emit()
		elif state == WebSocketPeer.STATE_CLOSED and was != WebSocketPeer.STATE_CLOSED:
			closed.emit(_peer.get_close_code(), _peer.get_close_reason())
