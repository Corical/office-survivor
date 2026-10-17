"""Simulated colleagues for test games: the simulator's office personalities, playing through the real rules.

Each sim picks a move from its personality's weights (scavenge, steal, guard, investigate, gift), sometimes misses
the deadline, and never makes a move the engine would refuse.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "sim"))
from survivors_sim import ARCH, OFFICE_MIX  # noqa: E402

from engine.moves import can_guard, validate  # noqa: E402

KINDS = ("scavenge", "steal", "guard", "investigate", "gift")


def pick_personality(rng):
    return rng.choices(list(OFFICE_MIX), weights=list(OFFICE_MIX.values()))[0]


def decide(p, arch, players, rules, night, rng, quit_ids=frozenset()):
    """A legal move for sim player p, or None when it 'missed the deadline' (auto-scavenge)."""
    a = ARCH[arch]
    if not p.bandit and rng.random() < a["miss"] * rules.miss_scale:
        return None
    others = [q.pid for q in players if q.pid != p.pid and q.pid not in quit_ids]
    weights = dict(zip(KINDS, a["w"]))
    if p.bandit:
        weights = {"steal": 0.85, "investigate": 0.15}
    if not can_guard(p, rules, night):
        weights.pop("guard", None)
    if p.rations < 2:
        weights.pop("gift", None)
    for _ in range(8):
        kinds = [k for k, w in weights.items() if w > 0]
        kind = rng.choices(kinds, weights=[weights[k] for k in kinds])[0]
        tgt = rng.choice(others) if kind in ("steal", "investigate", "gift") and others else None
        amt = (2 if p.rations >= 7 else 1) if kind == "gift" else 0
        move = (kind, tgt, amt, False)
        if validate(players, p.pid, move, rules, night, quit_ids) is None:
            return move
    return ("steal", others[0], 0, False) if p.bandit and others else ("scavenge", None, 0, False)
