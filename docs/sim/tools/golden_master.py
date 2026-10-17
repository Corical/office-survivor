"""Golden master for the engine extraction: record what the simulator does now, check it does exactly the same later.

    python tools/golden_master.py record DIR    # before changing the engine
    python tools/golden_master.py check DIR     # after: every log and report must match byte for byte

Covers: full replay logs (every event, ration and news line) for 20 seeds with the rules players and 10 with
the adaptive learning players, plus the 300-game batch report on the current rules. Single process.
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import survivors_sim as S  # noqa: E402
import brains  # noqa: E402

RULES = S.load_game_rules(S.DEFAULT_GAME)[0]


def outputs():
    """name -> text for everything the golden master compares."""
    out = {}
    for seed in range(1, 21):
        g = S.Game(RULES, seed, log=True)
        g.run()
        out[f"reel_rules_seed{seed:02d}.jsonl"] = "".join(json.dumps(e, sort_keys=True) + "\n" for e in g.events)
    for seed in range(1, 11):
        g = S.Game(RULES, seed, log=True, brain=brains.make_brain_factory("adaptive", S.ARCH)())
        g.run()
        out[f"reel_adaptive_seed{seed:02d}.jsonl"] = "".join(json.dumps(e, sort_keys=True) + "\n" for e in g.events)
    buf = io.StringIO()
    with redirect_stdout(buf):
        S.report(RULES, 300, 7)
    out["batch_300_seed7.txt"] = buf.getvalue()
    return out


if __name__ == "__main__":
    mode, d = sys.argv[1], sys.argv[2]
    got = outputs()
    if mode == "record":
        os.makedirs(d, exist_ok=True)
        for name, text in got.items():
            open(os.path.join(d, name), "w", encoding="utf-8", newline="\n").write(text)
        print(f"recorded {len(got)} files in {d}")
    else:
        bad = [n for n, t in got.items() if open(os.path.join(d, n), encoding="utf-8").read() != t]
        print(f"{len(got) - len(bad)} of {len(got)} identical" + (f"; DIFFERENT: {bad}" if bad else ""))
        sys.exit(1 if bad else 0)
