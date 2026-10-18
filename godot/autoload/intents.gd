extends Node
## Taps back to the server. Screens call these with the ids the models carry (`server_id`, a phrase's `server_id`);
## they never build wire messages or touch Session / Net. Every method returns "" when the intent went out, else a short
## reason (in_flight | locked | locked_round | radio_unavailable | no_server_url | not_connected | ...) the screen can show.


func create_room() -> String:
	return _done(Session.begin("create_room"))


func join_room(code: String) -> String:
	return _done(Session.begin("join_room", {"code": code.strip_edges().to_upper()}))


## Resume a stored seat on launch. False when there is none (or no usable server address).
func resume() -> bool:
	return Session.resume_if_stored()


func start() -> String:
	return _done(Session.act("start"))


func pick(server_id: String, target: Variant = null, amount := 0) -> String:
	return _done(Session.pick(server_id, target, amount))


func lock() -> String:
	return _done(Session.act("lock"))


func radio(phrase_server_id: String, about: Variant = null) -> String:
	return _done(Session.act("radio", {"phrase": phrase_server_id, "about": about}))


func proceed() -> String:
	return _done(Session.act("continue"))


func leave() -> void:
	Session.leave()
	Feed.reset()
	Feed.refresh()


## "Back to title" after a terminal reason (taken over, flapping, seat gone).
func back_to_title() -> void:
	Session.back_to_title()
	Feed.reset()
	Feed.refresh()


func set_server_url(url: String) -> void:
	Session.server_url = url.strip_edges()
	Session.save_store()
	Feed.refresh()


func _done(reason: String) -> String:
	Feed.refresh()
	return reason
