"""Dealing secret goals fairly (owner, 17 Oct 2026): like a deck, not independent dice.

- Goal types are dealt as evenly as possible (with 15 players and 6 types: 2 or 3 of each).
- Targeted goals (beat, grudge) are dealt as a chain: every player is the target of at most one goal,
  nobody targets themselves, and no two players target each other.
Measured with the old independent dealing: 66% of games had someone targeted 2+ times, 11% 3+.
"""
GOALS = ("beat", "robbed2_extract", "steal3_clean", "give", "grudge", "detective")
TARGETED = ("beat", "grudge")


def deal(pids, rng, goals=GOALS, tries=200):
    """pid -> (goal, target_pid or -1). Deterministic for a given rng state."""
    pids = list(pids)
    n = len(pids)
    deck = [goals[i % len(goals)] for i in range(n)]
    rng.shuffle(deck)
    hand = dict(zip(pids, deck))
    hunters = [p for p in pids if hand[p] in TARGETED]
    for _ in range(tries):
        targets = list(pids)
        rng.shuffle(targets)
        pick, used, ok = {}, set(), True
        for h in hunters:
            choice = next((t for t in targets if t != h and t not in used and pick.get(t) != h), None)
            if choice is None:
                ok = False
                break
            pick[h] = choice
            used.add(choice)
        if ok:
            return {p: (hand[p], pick.get(p, -1)) for p in pids}
    # tiny rosters (2 players, both hunters) can't avoid a mutual pair: give one of them an untargeted goal
    for h in hunters[1:]:
        hand[h] = "give"
    return deal_fixed(pids, hand, rng)


def deal_fixed(pids, hand, rng):
    hunters = [p for p in pids if hand[p] in TARGETED]
    out = {}
    for h in hunters:
        others = [p for p in pids if p != h]
        out[h] = (hand[h], rng.choice(others))
    return {p: out.get(p, (hand[p], -1)) for p in pids}
