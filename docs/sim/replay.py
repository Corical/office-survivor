#!/usr/bin/env python3
"""
Replays a Survivors game from its log alone (JSONL, see LOG_FORMAT.md).

Works on simulator logs today and on the bot's logs later, as long as both
follow LOG_FORMAT.md.

  python3 sim/replay.py game.jsonl                   check the log, then tell the whole story night by night
  python3 sim/replay.py game.jsonl --player QuietBadger   one person's story
  python3 sim/replay.py game.jsonl --frames f.json   per-night state frames for building an animation
  python3 sim/replay.py game.jsonl --check           only check that the log rebuilds the game exactly

The check rebuilds every ration count from the ledger and compares it with the
night-by-night snapshots and the final results. If anything was left out of
the log, the check fails.
"""

import argparse
import json
import sys
from collections import defaultdict


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rebuild(events):
    """Rebuild state from the log. Returns (frames, problems)."""
    start = events[0]
    assert start["type"] == "game_start", "log must begin with game_start"
    rations = {p["name"]: p["start_rations"] for p in start["players"]}
    bandit = {name: False for name in rations}
    protected_until = defaultdict(int)
    problems = []
    frames = []
    night_events, night_actions, news = [], {}, []

    def say(e):
        t = e["type"]
        if t == "action":
            return None
        if t == "steal":
            if e["outcome"] == "caught":
                return f"{e['thief']} tried to rob {e['target']} but walked into a guard"
            if e["outcome"] == "empty":
                return f"{e['thief']} broke into {e['target']}'s place and found nothing"
            return f"{e['thief']} stole {e['amount']} from {e['target']}"
        if t == "guard_up":
            return f"{e['player']} set a guard (protected until night {e['until_night']}, guard #{e['guards_used']})"
        if t == "guard_wasted":
            return f"{e['player']} tried to guard while already protected"
        if t == "scavenge":
            return f"{e['player']} scavenged and found {e['found']}" + (" (missed the deadline)" if e["auto"] else "")
        if t == "gift":
            return f"{e['giver']} secretly gave {e['receiver']} {e['amount']}"
        if t == "investigate":
            saw = e["saw_action"] + (f" {e['saw_target']}" if e.get("saw_target") else "")
            return f"{e['investigator']} watched {e['target']} ({saw})"
        if t == "exposed":
            return f"{e['investigator']} exposed {e['thief']} for robbing {e['victim']}; paid {e['paid']}"
        if t == "radio":
            return f"#radio (secretly {e['author']}, {'true' if e['true'] else 'rumour'}): {e['text']}"
        if t == "became_bandit":
            return f"{e['player']} ran out of food and became a bandit"
        if t == "rejoined":
            return f"{e['player']} rejoined the survivors with {e['rations']}"
        if t == "event":
            return f"EVENT {e.get('event')}: {e.get('text', '')}"
        return None

    for e in events[1:]:
        t = e["type"]
        if t == "ration":
            name = e["player"]
            rations[name] += e["delta"]
            if rations[name] != e["balance"]:
                problems.append(f"seq {e['seq']}: {name} ledger says {e['balance']}, rebuilt {rations[name]}")
                rations[name] = e["balance"]
            continue
        if t == "action":
            night_actions[e["player"]] = {"action": e["action"], "target": e.get("target"), "auto": e.get("auto", False)}
        elif t == "guard_up":
            protected_until[e["player"]] = e["until_night"]
        elif t == "became_bandit":
            bandit[e["player"]] = True
        elif t == "rejoined":
            bandit[e["player"]] = False
        elif t == "news_post":
            news = list(e["lines"])
        line = say(e)
        if line:
            night_events.append(line)
        if t == "night_end":
            n = e["night"]
            for name, r in e["rations"].items():
                if rations[name] != r:
                    problems.append(f"night {n}: {name} has {rations[name]} rebuilt, snapshot says {r}")
            if sorted(k for k, v in bandit.items() if v) != sorted(e["bandits"]):
                problems.append(f"night {n}: bandit list differs from snapshot")
            frames.append({
                "night": n,
                "players": {name: {"rations": rations[name], "bandit": bandit[name],
                                   "protected": protected_until[name] >= n,
                                   **night_actions.get(name, {})} for name in rations},
                "what_happened": night_events,
                "news": news,
            })
            night_events, night_actions, news = [], {}, []
        if t == "result":
            if rations[e["player"]] != e["rations"]:
                problems.append(f"result: {e['player']} rebuilt {rations[e['player']]}, result says {e['rations']}")
    end = [e for e in events if e["type"] in ("extraction", "game_end")]
    results = [e for e in events if e["type"] == "result"]
    return frames, problems, end, results, start


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--player")
    ap.add_argument("--frames", metavar="OUT.json")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    events = load(a.log)
    frames, problems, end, results, start = rebuild(events)
    nights = len(frames)
    print(f"Log: {len(events)} events, {len(start['players'])} players, {nights} nights, seed {start['seed']}")
    if problems:
        print("REPLAY CHECK FAILED:")
        for p in problems[:20]:
            print(f"  - {p}")
        sys.exit(1)
    print("Replay check: every ration, bandit and result rebuilds exactly from the log.")
    if a.check:
        return
    if a.frames:
        with open(a.frames, "w", encoding="utf-8") as f:
            json.dump({"players": start["players"], "frames": frames,
                       "ending": end, "results": results}, f, indent=2, ensure_ascii=False)
        print(f"Frames written to {a.frames}")
        return

    for fr in frames:
        lines = fr["what_happened"]
        if a.player:
            lines = [l for l in lines if a.player in l]
            me = fr["players"][a.player]
            head = (f"Night {fr['night']}: {a.player} chose {me.get('action', '?')}"
                    + (f" {me['target']}" if me.get("target") else "")
                    + f", ends on {me['rations']}" + (" (bandit)" if me["bandit"] else ""))
            print("\n" + head)
        else:
            print(f"\n=== Night {fr['night']} ===")
        for l in lines:
            print(f"  {l}")
        if not a.player:
            standing = sorted(fr["players"].items(), key=lambda kv: -kv[1]["rations"])
            print("  rations: " + ", ".join(f"{n} {s['rations']}{' (B)' if s['bandit'] else ''}" for n, s in standing))
    print()
    for e in end:
        if e["type"] == "extraction":
            print(f"Helicopter ({e['seats']} seats): {', '.join(e['extracted'])}"
                  + (" (last seat by coin flip)" if e["decided_by_coin_flip"] else ""))
        else:
            print(f"Winner: {', '.join(e['winners'])}")
    if a.player:
        r = next(x for x in results if x["player"] == a.player)
        print(f"{a.player}: {r['score']} pts, goal '{r['objective']}' {'done' if r['objective_done'] else 'failed'}")


if __name__ == "__main__":
    main()
