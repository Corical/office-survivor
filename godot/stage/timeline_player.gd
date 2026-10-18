class_name TimelinePlayer
extends RefCounted
## Owns the current Timeline and decides when a new reveal view starts one. The server pushes the same reveal many
## times (once per action), so the rule is: a round's timeline is created once and never restarted.

var timeline: Timeline


## A reveal model arrived. Same round again -> keep the running timeline. New round -> a new one, snapped to its end
## when there is no before-state to animate from.
func offer(model: Dictionary) -> Timeline:
	if timeline != null and int(model.round) <= timeline.round:
		if int(model.round) < timeline.round:
			Log.event("stage", "stale_reveal_ignored", {"got": model.round, "have": timeline.round}, "WARN")
		return timeline                   # same round again (never restart) or an older one (never go back)
	timeline = Timeline.new(int(model.round), model.beats, not bool(model.has_before_state))
	return timeline


## A view for a later round arrived while a reveal is playing: finish it instantly so the screens can move on.
func later_round_arrived(round_number: int) -> void:
	if timeline != null and round_number > timeline.round:
		timeline.snap_to_end()
