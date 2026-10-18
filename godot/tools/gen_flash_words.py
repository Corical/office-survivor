"""Generate godot/themes/flash/words.po: the placeholder's keys, in the voice of a camp on a dark island.

    python godot/tools/gen_flash_words.py

Every key of themes/placeholder/words.po is copied; OVERRIDES replaces the text. A key not in OVERRIDES keeps the
placeholder wording on purpose (it is already plain and carries a rule number, or it is a pass-through such as {text}).
The script fails if a replaced text drops, adds or renames a {slot}, or contains a non-ASCII character (no emoji,
icons are textures), so a reword can never break a sentence or a rule. Rule numbers (3 clean steals, back to 3, the
2 and 1 of a theft) stay exactly as the placeholder states them.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GODOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(GODOT, "themes", "placeholder", "words.po")
OUT = os.path.join(GODOT, "themes", "flash", "words.po")

OVERRIDES = {
    # ---- bands, goals, columns
    "goal.state.open": "Still on",
    "goal.state.end": "Settled when the helicopter comes",
    # ---- the night, as the player reads it
    "line.ate": "You ate {amount}. One more night survived.",
    "line.became_bandit_me": "The stores are empty. You're a bandit now: steal or stake out until you're back up to 3.",
    "line.caught_thief_broke": "Your watch caught {thief} red-handed, but they had nothing to pay you.",
    "line.caught_thief_broke_since": "Your watch (still up from night {since}) caught {thief} red-handed, but they had nothing to pay you.",
    "line.caught_thief_paid": "Your watch caught {thief} red-handed. They paid you {got}.",
    "line.caught_thief_paid_since": "Your watch (still up from night {since}) caught {thief} red-handed. They paid you {got}.",
    "line.exposed_by_me": "Your stake-out exposed {thief}; they paid you {paid}.",
    "line.exposed_me": "EXPOSED: someone was watching in the dark. They saw you rob {victim}. You paid them {paid}.",
    "line.exposed_me_back": "EXPOSED: someone was watching in the dark. They saw you rob {victim}. You paid them {paid} and gave back the {back} you stole.",
    "line.feast": "Feast night: you ate for free.",
    "line.found_watching_1": "While staking out, you found {found} ration.",
    "line.found_watching_n": "While staking out, you found {found} rations.",
    "line.goal_detective": "expose a thief red-handed by staking out at least once",
    "line.goal_grudge_deny": "make sure {target} doesn't get a seat on the helicopter",
    "line.goal_robbed2_extract": "get robbed at least {n}x and still get a seat on the helicopter",
    "line.got_gift": "{giver} slipped you {amount} in secret.",
    "line.got_gift_bonus": "{giver} slipped you {amount} in secret, and gifts grow: you got {total}.",
    "line.news_bandit": "{player} ran out of food and has turned bandit.",
    "line.news_break_in_empty": "Someone broke into {victim}'s shelter and found nothing.",
    "line.news_caught": "CAUGHT: {target} was on guard and caught {thief} red-handed. {thief} paid {paid}.",
    "line.news_exposed": "EXPOSED: someone was watching and saw {thief} rob {victim}. {thief} pays them {paid}.",
    "line.news_exposed_back": "EXPOSED: someone was watching and saw {thief} rob {victim}. {thief} pays them {paid} and gives {victim} back the {back} they stole.",
    "line.news_hit_1": "Someone hit {victim} in the dark. {victim} is down {total}.",
    "line.news_hit_n": "{count} people hit {victim} in the dark. {victim} is down {total}.",
    "line.news_idol": "Someone tried to rob {player} in the dark and left empty-handed: {player} had a hidden idol.",
    "line.news_quiet": "A quiet night. Nobody lost anything.",
    "line.robbed": "Someone took {amount} from you in the dark.",
    "line.scavenged": "You foraged in the dark and found {found}.",
    "line.scavenged_auto": "You didn't choose a move, so you foraged automatically and found {found}.",
    "line.steal_caught": "{target} was on guard: you were caught and paid {paid}.",
    "line.steal_empty": "You crept into {target}'s shelter and found nothing.",
    "line.steal_split": "You crept into {target}'s shelter, but someone beat you to it.",
    "line.thief_exposed_for_me": "Someone was watching and caught the thief who robbed you: {thief}. You got your {back} back.",
    "line.watched": "You staked out {target}: they chose {saw}.",
    "line.watched_target": "You staked out {target}: they chose {saw} ({saw_target}).",
    # ---- the five moves
    "move.scavenge": "Forage",
    "move.scavenge.choice": "forage",
    "move.scavenge.help": "Search the dark for food.",
    "move.guard": "Keep watch",
    "move.guard.choice": "keep watch",
    "move.guard.help": "Shield yourself for two nights.",
    "move.steal.help": "Take food from someone's stash.",
    "move.investigate": "Stake out",
    "move.investigate.choice": "stake out",
    "move.investigate.help": "Find out what someone does tonight.",
    "move.gift": "Give",
    "move.gift.choice": "give",
    "move.gift.help": "Give someone food, quietly.",
    # ---- notices
    "notice.flapping": "The line keeps dropping. Another device may have your seat.",
    # ---- the radio
    "radio.easy": "{a} looks like an easy mark.",
    "radio.guarding": "{a} is on guard. Don't waste your night on them.",
    "radio.saw": "I saw {a} creeping around last night.",
    # ---- screens
    "ui.app_name": "Long Night",
    "ui.back_to_title": "Back to the fire",
    "ui.create_room": "Create camp",
    "ui.join_room": "Join camp",
    "ui.enter_code": "Camp code",
    "ui.goal": "YOUR SECRET GOAL",
    "ui.leave": "Leave camp",
    "ui.lock": "Lock in for the night",
    "ui.net.reconnecting": "Signal lost. Reconnecting...",
    "ui.net.unreachable": "No signal: can't reach the server",
    "ui.nothing_to_show": "Quiet out here. Nothing yet.",
    "ui.pick_a_move": "PICK YOUR MOVE FOR TONIGHT",
    "ui.reduced_motion": "Calm mode (less motion)",
    "ui.open_camps": "OPEN CAMPS",
    "ui.create_sheet_title": "Light a new fire",
    "ui.public_help": "Anyone who opens the app can see this camp and sit down by the fire.",
    "ui.private_help": "Not listed. Only people you give the code to can find it.",
    "ui.pick_a_target": "PICK A TARGET",
    "ui.pick_an_amount": "PICK AN AMOUNT",
    "ui.radio_heard": "ON THE RADIO",
    "ui.radio_pick_player": "ABOUT WHOM?",
    "ui.results": "RESULTS",
    "ui.resume": "Rejoin camp",
    "ui.resume_code": "Rejoin camp {code}",
    "notice.taken_over": "Your camp was opened on another device. Rejoin here to take it back.",
    "ui.reveal_title": "What happened in the night",
    "ui.room_code": "Camp {code}",
    "ui.roster": "AROUND THE FIRE",
    "ui.round_of": "Night {round} of {rounds}",
    "ui.seats": "{taken} of {total} places by the fire",
    "ui.server_address": "SERVER ADDRESS",
    "ui.start": "Start the first night",
    "ui.waiting_for_host": "Waiting for the host to begin",
    # --- end/lobby/title ---
    "ui.best_legend": "[ ] = the most around the fire",
    "ui.code_caption": "Camp code",
    "ui.bots_fill": "Empty places by the fire are taken by bots when you start.",
}

SLOT = re.compile(r"\{(\w+)\}")


def parse(path):
    out, key = {}, None
    for line in open(path, encoding="utf-8").read().split("\n"):
        if line.startswith("msgid "):
            key = line[7:-1]
        elif line.startswith("msgstr ") and key is not None:
            out[key] = line[8:-1].replace('\\"', '"').replace("\\\\", "\\")
    return out


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main():
    base = parse(SRC)
    unknown = [k for k in OVERRIDES if k not in base]
    if unknown:
        print("FAIL: overrides for keys the placeholder does not have:", unknown)
        return 1
    problems = []
    final = {}
    for k, v in base.items():
        if k == "":
            continue
        t = OVERRIDES.get(k, v)
        if set(SLOT.findall(t)) != set(SLOT.findall(v)):
            problems.append("%s: slots %s != placeholder %s" % (k, SLOT.findall(t), SLOT.findall(v)))
        if any(ord(c) > 126 for c in t):
            problems.append("%s: non-ASCII character in %r" % (k, t))
        final[k] = t
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: en\\n"\n\n')
        for k in sorted(final):
            f.write('msgid "%s"\nmsgstr "%s"\n\n' % (esc(k), esc(final[k])))
    same = [k for k in final if k not in OVERRIDES]
    print("%d keys written to %s; %d reworded, %d kept as the placeholder words them" % (len(final), OUT, len(OVERRIDES), len(same)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
