extends Node
## Taps back to the server. Screens call these with the ids the models carry (`server_id`, a phrase's `server_id`);
## they never build wire messages or touch Session / Net. Every method returns "" when the intent went out, else a short
## reason (in_flight | locked | locked_round | radio_unavailable | no_server_url | not_connected | ...) the screen can show.


## Create a camp. `visibility` ("public" | "private") and `name` (at most 24 characters) are optional and are sent only
## when the server has shown it understands them; with neither, this is the plain create_room it always was.
func create_room(visibility := "", camp_name := "", game := "") -> String:
	return _done(Session.create_camp(visibility, camp_name, game))


## Join by code. `from_list`: the player tapped a camp in the open-camps list (a refusal then gets the neutral wording).
func join_room(code: String, from_list := false) -> String:
	return _done(Session.join_camp(code, from_list))


## The open-camps list is showing (true) or no longer is (false). While it is, the client keeps a line open and asks
## about every 3 s; when it stops, so does the asking. Calls must be paired (one true, one false per screen).
func rooms_watch(on: bool) -> void:
	Session.rooms_watch(on)


## Ask for the list right now ("" when asked).
func list_rooms() -> String:
	return Session.rooms_refresh()


## The host removes a seat that dropped off (`handle` is a seat's `id` from the lobby model; see Feed.models.lobby.seats).
func kick(handle: String) -> String:
	return _done(Session.kick(handle))


## Full screen on a desktop window (a phone is always full screen: then there is nothing to offer).
func can_fullscreen() -> bool:
	return WindowModes.available()


func toggle_fullscreen() -> void:
	WindowModes.toggle()


## Resume a stored seat on launch. False when there is none (or no usable server address).
func resume() -> bool:
	return Session.resume_if_stored()


## Where copied text goes. The real clipboard by default; a test swaps it so it never touches the machine's clipboard.
var clipboard_set: Callable = func(text: String): DisplayServer.clipboard_set(text)
const COPY_MAX := 64                      # chosen: a camp code is 4 letters; nothing longer is ever worth copying


## Put text (a camp code) on the clipboard. "" when copied, else why not (empty).
func copy_text(text: String) -> String:
	var clean := text.strip_edges().left(COPY_MAX)
	if clean == "":
		return "empty"
	clipboard_set.call(clean)
	return ""


## One verb of the room's game on the generic wire. `args` is what the verb's table in the ruleset allows and nothing else; the
## phase and the act id are added here, never by the caller. "" when sent, else why not (unknown_verb | bad_args | forbidden_arg |
## no_phase | in_flight | ...). Nothing calls this yet but the tests: no Survivors screen is moved onto it.
func act(verb: Variant, args: Variant = {}) -> String:
	return _done(Session.act_verb(verb, args))


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
	Session.url_changed()
	Feed.refresh()


func _done(reason: String) -> String:
	Feed.refresh()
	return reason
