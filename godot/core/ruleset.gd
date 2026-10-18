class_name Ruleset
extends RefCounted
## What the client core needs to know about a game, and nothing more. Session validates frames and routes seat errors
## through this; Feed asks it for neutral models. A new game is a new subclass in rulesets/<id>/ plus one line in
## rulesets/registry.gd; core never names a game.

## Message types that are screens' views (the rest are control frames).
func view_types() -> Array:
	return []


## Error codes after which the stored seat is useless.
func seat_gone_codes() -> Array:
	return []


## Server wordings that mean the same, for servers that do not send a distinct code yet.
func seat_gone_texts() -> Array:
	return []


## "" when the frame is well-formed for its type (unknown types are accepted: Session reports them), else a reason.
func validate(_msg: Dictionary) -> String:
	return ""


func lobby_model(_view: Dictionary) -> Dictionary:
	return {}


func round_model(_view: Dictionary) -> Dictionary:
	return {}


## `me` is my alias (may be ""); `before` is the last round view, or {} when unknown.
func reveal_model(_view: Dictionary, _me: String, _before: Dictionary) -> Dictionary:
	return {}


func end_model(_view: Dictionary, _me: String) -> Dictionary:
	return {}


## This game's phases: {phase_id: {"screen": screen id}}. A view whose phase is not listed gets the neutral phase screen.
func phases() -> Dictionary:
	return {}


## This game's verbs, the client's copy of the server manifest: {verb: {arg: spec}}. A spec is {"type": "int" | "str" | "bool"}
## plus any of "optional", "nullable", "min", "max", "max_len", "choices". Intents.act refuses anything outside it before it is sent.
func verbs() -> Dictionary:
	return {}


## The neutral model of a `view` frame (the new wire's one frame, any phase). {} for a game that draws nothing from it.
func view_model(_view: Dictionary) -> Dictionary:
	return {}


## A .po file of this game's own words ("" when the theme's file carries them). Asked after the theme's, so a theme can still override.
func words_path() -> String:
	return ""


## Every translation key this ruleset can emit (a theme must cover them all).
func all_keys() -> Array[String]:
	return []
