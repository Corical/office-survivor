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
        text = strip_emoji(tpl)
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
