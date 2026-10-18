"""Generate godot/themes/placeholder/words.po from the server's line table plus the UI words.

    python godot/tools/gen_placeholder_words.py

The placeholder theme is plain English with no emoji (icons come from the theme's icon set, not from text). Line
templates are the server's own English (arena/lines_en.json) minus the leading emoji, so a code the server adds
shows up here the next time this runs and the completeness test tells you which key is new.
Also copies arena/lines_en.json to godot/rulesets/survivors/lines_en.json (the drift test compares the two).
"""
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GODOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.abspath(os.path.join(GODOT, "..", "arena", "lines_en.json"))
DST_LINES = os.path.join(GODOT, "rulesets", "survivors", "lines_en.json")
OUT = os.path.join(GODOT, "themes", "placeholder", "words.po")

RADIO = {
    "saw": "I saw {a} sneaking around last night.",
    "trust": "Don't trust {a}.",
    "lying": "{a} is lying about their rations.",
    "guarding": "{a} is guarding. Don't waste your night on them.",
    "easy": "{a} looks like an easy target.",
    "innocent": "{a} is innocent. Leave them alone.",
    "watch": "Someone should watch {a}'s back tonight.",
    "me": "I'm innocent. Leave me alone.",
}
UI = {
    "line.unknown": "Something happened.",
    "list.and": "and",
    "resource.ration": "Rations",
    "status.outcast": "Bandit",
    "status.shield": "On guard",
    "move.scavenge": "Scavenge", "move.guard": "Guard", "move.steal": "Steal",
    "move.investigate": "Investigate", "move.gift": "Gift", "move.unknown": "Other move",
    "move.scavenge.choice": "scavenge", "move.guard.choice": "guard", "move.steal.choice": "steal",
    "move.investigate.choice": "investigate", "move.gift.choice": "gift", "move.unknown.choice": "something",
    "move.scavenge.help": "Look for food.", "move.guard.help": "Protect yourself for two nights.",
    "move.steal.help": "Take food from someone.", "move.investigate.help": "See what someone does tonight.",
    "move.gift.help": "Give someone food.", "move.unknown.help": "No description.",
    "band.well_fed": "Well fed", "band.getting_by": "Getting by", "band.starving": "Starving",
    "band.bandit": "Bandit", "band.unknown": "Unknown",
    "goal.beat": "{text}", "goal.robbed2_extract": "{text}", "goal.steal3_clean": "{text}", "goal.give": "{text}",
    "goal.grudge": "{text}", "goal.detective": "{text}", "goal.unknown": "{text}",
    "radio.unknown": "Unclear message.",
}
for k, v in RADIO.items():
    UI["radio." + k] = v
UI.update({
    "line.now_have.one": "You now have {rations} ration.",
    "goal.state.open": "In progress", "goal.state.done": "Done", "goal.state.failed": "Lost",
    "goal.state.end": "Decided at the end", "goal.state.unknown": "Unknown",
    "column.score": "Points", "column.rations": "Rations", "column.stole": "Stole",
    "column.gave_away": "Gave away", "column.times_robbed": "Robbed",
    # ruleset-neutral words (core/ui_keys.gd)
    "ui.app_name": "Arena", "ui.create_room": "Create room", "ui.join_room": "Join room", "ui.enter_code": "Room code",
    "ui.server_address": "Server address", "ui.resume": "Resume game", "ui.start": "Start game", "ui.lock": "Lock in",
    "ui.locked": "Locked in", "ui.locking": "Locking in...", "ui.continue": "Continue", "ui.leave": "Leave game",
    "ui.back_to_title": "Back to title", "ui.new_game": "New game", "ui.settings": "Settings",
    "ui.room_code": "Room {code}", "ui.seats": "{taken} of {total} seats taken", "ui.you_are": "You are {alias}",
    "ui.locked_count": "{locked} of {total} locked in", "ui.round_of": "Round {round} of {rounds}", "ui.radio": "Radio",
    "ui.goal": "Your goal", "ui.winners": "Winners", "ui.results": "Results", "ui.theme": "Theme",
    "ui.timer_unknown": "Waiting for the server", "ui.waiting_for_host": "Waiting for the host to start",
    "ui.copy": "Copy",
    "ui.pick_a_move": "Pick a move", "ui.pick_a_target": "Pick a target", "ui.pick_an_amount": "Pick an amount",
    "ui.your_pick": "Your pick: {pick}", "ui.radio_pick_player": "About whom?", "ui.seconds": "{n} s",
    "ui.roster": "Everyone", "ui.you_mark": "(you)", "ui.winner_mark": "winner", "ui.seat_mark": "seat",
    "ui.goal_met": "goal met", "ui.goal_missed": "goal missed", "ui.reveal_title": "What happened",
    "ui.radio_heard": "On the radio", "ui.nothing_to_show": "Nothing yet.", "ui.close": "Close",
    "ui.hide_settings": "Hide settings", "ui.skip": "Skip",
    "ui.reduced_motion": "Reduced motion", "ui.on": "On", "ui.off": "Off", "ui.rank": "#{n}",
    "ui.fullscreen": "Full screen (F11)",
    "ui.open_camps": "Open camps", "ui.no_open_camps": "No open camps. Create one.", "ui.camp_just_now": "just now",
    "ui.camp_min_ago": "{n} min ago", "ui.camp_hours_ago": "{n} h ago", "ui.camp_days_ago": "{n} d ago",
    "ui.camp_seats": "{taken} of {total}", "ui.create_sheet_title": "New camp", "ui.camp_name_hint": "Camp name (optional)",
    "ui.public": "Public", "ui.private": "Private",
    "ui.public_help": "Anyone who opens the app can see this camp and join it.",
    "ui.private_help": "Not listed. Only people you give the code to can join.",
    "ui.create_go": "Create", "ui.cancel": "Cancel", "ui.you_are_prefix": "You are", "ui.pick_prompt": "Pick a move!",
    # --- round screen ---
    # --- round pick hints ---
    "ui.hint_pick_move": "Pick a move first", "ui.hint_pick_target": "Pick a target first",
    "ui.hint_pick_amount": "Pick an amount first", "ui.hint_sending": "Sending your pick...",
    "ui.hint_closed": "Waiting for the next night", "ui.move_off": "Closed",
    # --- end round pick hints ---
    "ui.goal_tap_more": "Tap for details", "ui.goal_tap_less": "Tap to hide",
    "ui.move_unavailable": "{move} is not available tonight.",
    "ui.goal_seat_note": "A seat is a place on the helicopter. Only a few are free; the players with the most rations at the end get them.",
    "notice.camp_unavailable": "That camp filled up or closed first. Here is the fresh list.",
    "notice.room_full": "That camp is full.", "notice.room_started": "That camp has already started.",
    "notice.room_gone": "No camp with that code. Check it and try again.",
    "ui.resume_code": "Resume game {code}",
    # --- kick (host removes a seat that dropped off) ---
    "notice.kicked": "The host removed you from this game. You can join again with a code.",
    "ui.kick": "Remove", "ui.kick_confirm": "Remove this player?",
    "ui.seat_n": "Seat {n}", "ui.seat_here": "Here", "ui.seat_dropped": "Not connected",
    "ui.kick_help": "A seat that dropped off stays taken. Remove it to free the seat.",
    "ui.net.connecting": "Connecting...", "ui.net.online": "Connected", "ui.net.reconnecting": "Reconnecting...",
    "ui.net.unreachable": "Can't reach the server", "ui.net.offline": "Offline", "ui.net.stopped": "Disconnected",
    "notice.seat_gone": "Your seat is gone: the game ended or the host removed you. You can join again with a code.",
    "notice.taken_over": "This game was opened on another device. Resume here to take it back.",
    "notice.too_big": "The server sent something too large.",
    "notice.flapping": "The connection keeps dropping. Another device may have your seat.",
    "notice.upgrade_required": "Please update the app to play.",
    "notice.invalid": "The server sent something this app could not read.",
    "notice.unknown": "The server sent something this app doesn't know.",
    "notice.generic": "{text}", "notice.no_server_url": "Enter the server address first.",
    "notice.locked": "Your move is locked in.", "notice.in_flight": "Already sent.",
    # --- end/lobby/title ---
    "ui.best_legend": "[ ] = the most in the group",
    "ui.code_caption": "Room code",
    "ui.copied": "Copied",
    "ui.bots_fill": "Empty seats are filled by bots when you start.",
    "ui.advanced": "Advanced", "ui.hide_advanced": "Hide advanced",
    "ui.advanced_hint": "Only change this if you were given an address.",
    # --- lobby away count ---
    "ui.seats_away": "{here} here, {away} away",
    # --- reveal/stage ---
    "ui.reveal_waiting": "Waiting for the others, {n} s",
})
UI["column.gave_away"] = "Given"       # one short word: a header must fit its column on one line


def strip_emoji(text):
    # drop leading non-ASCII symbols (emoji, joiners, variation selectors) and the space after them
    return re.sub(r"^[^\x00-\x7f\ufe0f\u200d]+[\ufe0f\u200d]*[^\x00-\x7f]*\s*", "", text, count=1).lstrip() \
        if ord(text[0]) > 127 else text


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main():
    lines = json.load(open(SRC, encoding="utf-8"))
    os.makedirs(os.path.dirname(DST_LINES), exist_ok=True)
    shutil.copyfile(SRC, DST_LINES)
    entries = {}
    for code, tpl in lines.items():
        text = strip_emoji(tpl).replace("✓", "(done)")      # the placeholder theme carries no symbols at all
        entries["line." + code] = text
    entries.update(UI)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: en\\n"\n\n')
        for key in sorted(entries):
            f.write('msgid "%s"\nmsgstr "%s"\n\n' % (esc(key), esc(entries[key])))
    print("%d lines from the server, %d keys written to %s" % (len(lines), len(entries), OUT))
    for k in sorted(entries):
        if k.startswith("line.") and not entries[k][:1].isalnum() and not entries[k].startswith("{"):
            print("  check emoji strip:", k, repr(entries[k][:40]))


if __name__ == "__main__":
    main()
