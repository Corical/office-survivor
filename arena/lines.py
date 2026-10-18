"""What a player is told about a night, as codes and values instead of prose: [{"code": str, "args": {...}}].

The live rooms send these; a client turns each into words with the template table (LINES_EN here, the same table as
JSON in arena/lines_en.json for the Godot client). Rendered in English they are exactly Torch's lines
(bot/game.py news_lines and private_lines): arena/tests/test_lines.py proves that over many random games, so the two
can never drift apart unnoticed.

Wilderness events are the one exception: engine/events.py writes their story line itself, so it travels as the arg
`line` (code "event"). A second theme needs those out of the engine; see the plan, section 4.
"""
import json
import os

from engine.finish import GOAL_LINES, PROGRESS_LINES

LINES_EN = {
    # ---- private: what one player is told
    "idol_found": "🗿 You found a hidden idol. The next person to rob you gets nothing. Tell no one.",
    "idol_saved": "🗿 Your idol saved you: a thief left with nothing. The idol is spent.",
    "event": "{line}",
    "idol_blocked": "🗿 {target} had a hidden idol. You got nothing.",
    "scavenged_auto": "🥫 You didn't choose a move, so you scavenged automatically and found {found}.",
    "scavenged": "🥫 You scavenged and found {found}.",
    "guard_up_1": "🛡️ You're on guard for night {night}.",
    "guard_up_n": "🛡️ You're on guard for nights {nights}.",
    "stole": "🥷 You stole {amount} from {target}.",
    "steal_split": "🥷 You broke into {target}'s place, but someone beat you to it.",
    "steal_empty": "🥷 You broke into {target}'s place and found nothing.",
    "steal_caught": "🚨 {target} was guarding: you were caught and paid {paid}.",
    "robbed": "🥷 Someone stole {amount} from you.",
    "caught_thief_paid": "🚨 Your guard caught {thief} red-handed. They paid you {got}.",
    "caught_thief_paid_since": "🚨 Your guard (still up from night {since}) caught {thief} red-handed. They paid you {got}.",
    "caught_thief_broke": "🚨 Your guard caught {thief} red-handed, but they had nothing to pay you.",
    "caught_thief_broke_since": "🚨 Your guard (still up from night {since}) caught {thief} red-handed, but they had "
                                "nothing to pay you.",
    "watched": "🔍 You watched {target}: they chose {saw}.",
    "watched_target": "🔍 You watched {target}: they chose {saw} ({saw_target}).",
    "found_watching_1": "🔍 While watching, you found {found} ration.",
    "found_watching_n": "🔍 While watching, you found {found} rations.",
    "exposed_by_me": "🕵️ You exposed {thief}; they paid you {paid}.",
    "exposed_own_back": "🕵️ You also got your {back} back from {thief}, who robbed you.",
    "exposed_me": "🕵️ EXPOSED: an investigator saw you rob {victim}. You paid them {paid}.",
    "exposed_me_back": "🕵️ EXPOSED: an investigator saw you rob {victim}. You paid them {paid} and gave back the {back} "
                       "you stole.",
    "thief_exposed_for_me": "🕵️ An investigator caught the thief who robbed you: {thief}. You got your {back} back.",
    "gave": "🎁 You gave {receiver} {amount}.",
    "got_gift": "🎁 {giver} secretly gave you {amount}.",
    "got_gift_bonus": "🎁 {giver} secretly gave you {amount}, and gifts grow: you got {total}.",
    "became_bandit_me": "🏴‍☠️ You ran out of food. You're a bandit now: steal or investigate until you get back to 3.",
    "rejoined_me": "🎉 You've scraped together enough to rejoin the survivors.",
    "ate": "🍽️ You ate {amount}.",
    "feast": "🍽️ Feast night: you ate for free.",
    "now_have": "🥫 You now have {rations} rations.",
    # ---- news: what everyone is told
    "news_idol": "🗿 Someone tried to rob {player} and left empty-handed: {player} had a hidden idol.",
    "news_caught": "🚨 CAUGHT: {target} was guarding and caught {thief} red-handed. {thief} paid {paid}.",
    "news_exposed": "🕵️ EXPOSED: an investigator saw {thief} rob {victim}. {thief} pays them {paid}.",
    "news_exposed_back": "🕵️ EXPOSED: an investigator saw {thief} rob {victim}. {thief} pays them {paid} and gives "
                         "{victim} back the {back} they stole.",
    "news_bandit": "🏴‍☠️ {player} ran out of food. {player} is back... as a bandit.",
    "news_rejoined": "🎉 Bandit {player} has scraped together enough to rejoin the survivors.",
    "news_hit_1": "🥷 Someone hit {victim} overnight. {victim} is down {total}.",
    "news_hit_n": "🥷 {count} people hit {victim} overnight. {victim} is down {total}.",
    "news_break_in_empty": "🥷 Someone broke into {victim}'s place and found nothing.",
    "news_quiet": "🌙 A quiet night. Nobody lost anything.",
}


# The one table the client loads (arena/lines_en.json): the night's lines above, plus the goal and goal-progress
# wording, which lives in engine/finish.py so Torch's /status and the live rooms say exactly the same.
ALL_EN = {**LINES_EN, **GOAL_LINES, **PROGRESS_LINES}


def _l(code, **args):
    return {"code": code, "args": args}


def _event_line(e):
    """A wilderness story: the engine's finished sentence, plus the event id, who it hit (or the camp), so a client
    with its own words for that event can use them and fall back on the sentence. The story variant is not in the
    engine's log, so it cannot be sent (adding it would change every stored event record and break their replay)."""
    args = {"line": e["line"], "event": e["event"], "scope": e["scope"]}
    if e["scope"] == "player":
        args["who"] = e["player"]
    return _l("event", **args)


def _and(nums):
    """[3] -> '3'; [3, 4] -> '3 and 4'; [3, 4, 5] -> '3, 4 and 5' (Torch's guard span wording)."""
    nums = [str(n) for n in nums]
    return nums[0] if len(nums) == 1 else ", ".join(nums[:-1]) + " and " + nums[-1]


def render(line, table=None):
    """One line in words. A list arg is joined the English way ('3, 4 and 5')."""
    args = {k: _and(v) if isinstance(v, list) else v for k, v in line["args"].items()}
    return (table or ALL_EN)[line["code"]].format(**args)


def news_codes(events):
    """The public lines for a night, in the same order as Torch's news_lines. Empty for a quiet night."""
    out, wild_lines = [], []
    robbed = {}
    idol = {e["player"] for e in events if e["type"] == "event" and e.get("event") == "idol_used"}
    for e in events:
        if e["type"] == "event" and e.get("line"):
            wild_lines.append(_event_line(e))
        elif e["type"] == "event" and e.get("event") == "idol_used":
            out.append(_l("news_idol", player=e["player"]))
        elif e["type"] == "steal" and e["target"] in idol and e["outcome"] in ("success", "empty"):
            continue
        elif e["type"] == "steal" and e["outcome"] == "caught":
            out.append(_l("news_caught", target=e["target"], thief=e["thief"], paid=e["paid"]))
        elif e["type"] == "steal" and e["outcome"] in ("success", "empty"):
            robbed.setdefault(e["target"], []).append(e["amount"])
        elif e["type"] == "exposed":
            out.append(_l("news_exposed_back", thief=e["thief"], victim=e["victim"], paid=e["paid"], back=e["to_victim"])
                       if e.get("to_victim") else _l("news_exposed", thief=e["thief"], victim=e["victim"], paid=e["paid"]))
        elif e["type"] == "became_bandit":
            out.append(_l("news_bandit", player=e["player"]))
        elif e["type"] == "rejoined":
            out.append(_l("news_rejoined", player=e["player"]))
    for victim, amounts in robbed.items():
        total = sum(amounts)
        if not total:
            line = _l("news_break_in_empty", victim=victim)
        elif len(amounts) == 1:
            line = _l("news_hit_1", victim=victim, total=total)
        else:
            line = _l("news_hit_n", victim=victim, total=total, count=len(amounts))
        out.insert(0, line)
    return wild_lines + out


def private_codes(events, p, before, night=None, guard_nights=2):
    """What one player is told about their night, in the same order as Torch's private_lines."""
    me, out = p.name, []
    idol = {e["player"] for e in events if e["type"] == "event" and e.get("event") == "idol_used"}
    for e in events:
        t = e["type"]
        if t == "event" and e.get("player") == me:
            if e.get("event") == "idol":
                out.append(_l("idol_found"))
            elif e.get("event") == "idol_used":
                out.append(_l("idol_saved"))
            elif e.get("line"):
                out.append(_event_line(e))
        elif t == "event" and e.get("scope") == "camp" and e.get("line") and any(
                x["type"] == "ration" and x["player"] == me and x.get("detail") == e["event"] for x in events):
            out.append(_event_line(e))
        elif t == "steal" and e["thief"] == me and e["target"] in idol:
            out.append(_l("idol_blocked", target=e["target"]))
        elif t == "scavenge" and e["player"] == me:
            out.append(_l("scavenged_auto" if e.get("auto") else "scavenged", found=e["found"]))
        elif t == "guard_up" and e["player"] == me:
            first = night if night else e["until_night"]
            out.append(_l("guard_up_1", night=first) if first == e["until_night"]
                       else _l("guard_up_n", nights=list(range(first, e["until_night"] + 1))))
        elif t == "steal" and e["thief"] == me:
            if e["outcome"] == "success":
                out.append(_l("stole", amount=e["amount"], target=e["target"]))
            elif e["outcome"] == "empty":
                out.append(_l("steal_split" if e.get("split_with") else "steal_empty", target=e["target"]))
            else:
                out.append(_l("steal_caught", target=e["target"], paid=e["paid"]))
        elif t == "steal" and e["target"] == me and e["outcome"] == "success":
            out.append(_l("robbed", amount=e["amount"]))
        elif t == "steal" and e["target"] == me and e["outcome"] == "caught":
            got = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                      and x["reason"] == "guard_reward" and x.get("detail") == e["thief"])
            fresh = any(x["type"] == "guard_up" and x["player"] == me for x in events)
            since = None if fresh or not night else p.guard_until - guard_nights + 1
            code = ("caught_thief_paid" if got else "caught_thief_broke") + ("" if since is None else "_since")
            args = {"thief": e["thief"], **({"got": got} if got else {}), **({} if since is None else {"since": since})}
            out.append(_l(code, **args))
        elif t == "investigate" and e["investigator"] == me:
            out.append(_l("watched_target", target=e["target"], saw=e["saw_action"], saw_target=e["saw_target"])
                       if e["saw_target"] else _l("watched", target=e["target"], saw=e["saw_action"]))
            found = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                        and x["reason"] == "investigate_find")
            if found:
                out.append(_l("found_watching_n" if found > 1 else "found_watching_1", found=found))
        elif t == "exposed" and e["investigator"] == me:
            out.append(_l("exposed_by_me", thief=e["thief"], paid=e["paid"]))
            if e["victim"] == me and e.get("to_victim"):
                out.append(_l("exposed_own_back", back=e["to_victim"], thief=e["thief"]))
        elif t == "exposed" and e["thief"] == me:
            out.append(_l("exposed_me_back", victim=e["victim"], paid=e["paid"], back=e["to_victim"])
                       if e.get("to_victim") else _l("exposed_me", victim=e["victim"], paid=e["paid"]))
        elif t == "exposed" and e["victim"] == me and e.get("to_victim"):
            out.append(_l("thief_exposed_for_me", thief=e["thief"], back=e["to_victim"]))
        elif t == "gift" and e["giver"] == me:
            out.append(_l("gave", receiver=e["receiver"], amount=e["amount"]))
        elif t == "gift" and e["receiver"] == me:
            bonus = sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me
                        and x["reason"] == "gift_bonus" and x.get("detail") == e["giver"])
            out.append(_l("got_gift_bonus", giver=e["giver"], amount=e["amount"], total=e["amount"] + bonus)
                       if bonus else _l("got_gift", giver=e["giver"], amount=e["amount"]))
        elif t == "became_bandit" and e["player"] == me:
            out.append(_l("became_bandit_me"))
        elif t == "rejoined" and e["player"] == me:
            out.append(_l("rejoined_me"))
    ate = -sum(x["delta"] for x in events if x["type"] == "ration" and x["player"] == me and x["reason"] == "eat")
    if ate:
        out.append(_l("ate", amount=ate))
    elif any(e["type"] == "event" and e.get("event") == "feast" for e in events) and not p.bandit:
        out.append(_l("feast"))
    out.append(_l("now_have", rations=p.rations))
    return out


JSON_PATH = os.path.join(os.path.dirname(__file__), "lines_en.json")


def write_json(path=JSON_PATH):
    """Write the template table for the Godot client (a test keeps the file equal to LINES_EN)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ALL_EN, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    write_json()
    print("wrote", JSON_PATH)
