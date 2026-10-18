class_name UiKeys
extends RefCounted
## The ruleset-neutral words every game's screens need: navigation, connection states, notices. A theme must cover
## these AND the active ruleset's keys; nothing else may be in its translation file (the stale-key test).

const ALL: Array[String] = [
	"ui.app_name", "ui.create_room", "ui.join_room", "ui.enter_code", "ui.server_address", "ui.resume", "ui.start",
	"ui.lock", "ui.locked", "ui.locking", "ui.continue", "ui.leave", "ui.back_to_title", "ui.new_game", "ui.settings",
	"ui.room_code", "ui.seats", "ui.you_are", "ui.locked_count", "ui.round_of", "ui.radio", "ui.goal", "ui.winners",
	"ui.results", "ui.theme", "ui.timer_unknown", "ui.waiting_for_host", "ui.copy",
	"ui.pick_a_move", "ui.pick_a_target", "ui.pick_an_amount", "ui.your_pick", "ui.radio_pick_player", "ui.seconds",
	"ui.roster", "ui.you_mark", "ui.winner_mark", "ui.seat_mark", "ui.goal_met", "ui.goal_missed", "ui.reveal_title",
	"ui.radio_heard", "ui.nothing_to_show", "ui.close", "ui.hide_settings", "ui.skip",
	"ui.reduced_motion", "ui.on", "ui.off", "ui.rank", "ui.fullscreen",
	"ui.open_camps", "ui.no_open_camps", "ui.camp_just_now", "ui.camp_min_ago", "ui.camp_hours_ago", "ui.camp_days_ago",
	"ui.camp_seats", "ui.create_sheet_title", "ui.camp_name_hint", "ui.public", "ui.private", "ui.public_help",
	"ui.private_help", "ui.create_go", "ui.cancel", "ui.you_are_prefix", "ui.pick_prompt", "ui.goal_seat_note", "ui.move_unavailable", "ui.goal_tap_more", "ui.goal_tap_less",
	"ui.net.connecting", "ui.net.online", "ui.net.reconnecting", "ui.net.unreachable", "ui.net.offline", "ui.net.stopped",
	"notice.seat_gone", "notice.taken_over", "notice.too_big", "notice.flapping", "notice.upgrade_required",
	"notice.invalid", "notice.unknown", "notice.generic", "notice.no_server_url", "notice.locked", "notice.in_flight",
	"notice.camp_unavailable", "notice.room_full", "notice.room_started", "notice.room_gone", "ui.resume_code",
	"notice.kicked", "ui.kick", "ui.kick_confirm", "ui.seat_n", "ui.seat_here", "ui.seat_dropped", "ui.kick_help",
	# --- end/lobby/title ---
	"ui.best_legend", "ui.code_caption", "ui.copied", "ui.bots_fill", "ui.advanced", "ui.hide_advanced",
	"ui.advanced_hint",
	# --- reveal/stage ---
	"ui.reveal_waiting",
]

## Notice codes the client itself raises that have a word of their own; everything else uses `notice.generic` with the
## server's own text as a fallback.
const NOTICE_CODES := ["seat_gone", "taken_over", "too_big", "flapping", "upgrade_required", "no_server_url", "locked",
	"in_flight", "camp_unavailable", "room_full", "room_started", "room_gone", "kicked"]


## The translation key for a notice (kind, code): a specific one when we have it.
static func notice_key(kind: String, code: String) -> String:
	if code in NOTICE_CODES:
		return "notice." + code
	if kind == "invalid" or code.begins_with("invalid_"):
		return "notice.invalid"
	if kind == "unknown":
		return "notice.unknown"
	return "notice.generic"


static func net_key(state: String) -> String:
	return "ui.net." + state if ("ui.net." + state) in ALL else "ui.net.offline"
