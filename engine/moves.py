"""Which moves a player may make tonight. The server checks every move with `validate`, whatever the client sent.

A move is (kind, target_id | None, amount, auto). Kinds: scavenge, steal, guard, investigate, gift.
Owner decisions (17 Oct 2026): gifts are 1 or 2 and the giver keeps at least 1; quitters can't be targeted.
"""
KINDS = ("scavenge", "steal", "guard", "investigate", "gift")
TARGETED = ("steal", "investigate", "gift")
GIFT_MIN, GIFT_MAX = 1, 2


def can_guard(p, rules, night):
    """Same rule as the simulator: not already protected tonight, guards left, past any cooldown."""
    if p.guard_until >= night:
        return False
    if rules.guard_limit and p.guards_used >= rules.guard_limit:
        return False
    return night >= p.next_guard_night


def legal_moves(players, pid, rules, night, quit_ids=frozenset()):
    """What this player may do tonight, as {kind: [target ids]} ({kind: []} for untargeted kinds), plus the legal gift
    amounts under the key 'gift_amounts'. Built from `validate` itself, so a menu can never offer what the server
    would refuse."""
    others = [p.pid for p in players if p.pid != pid and p.pid not in quit_ids]
    out = {}
    for kind in KINDS:
        if kind in TARGETED:
            amt = GIFT_MIN if kind == "gift" else 0
            ok = [t for t in others if validate(players, pid, (kind, t, amt, False), rules, night, quit_ids) is None]
            if ok:
                out[kind] = ok
        elif validate(players, pid, (kind, None, 0, False), rules, night, quit_ids) is None:
            out[kind] = []
    if "gift" in out:
        t = out["gift"][0]
        out["gift_amounts"] = [a for a in range(GIFT_MIN, GIFT_MAX + 1)
                               if validate(players, pid, ("gift", t, a, False), rules, night, quit_ids) is None]
    return out


def validate(players, pid, move, rules, night, quit_ids=frozenset()):
    """None if the move is allowed, else a short reason a player can read."""
    P = {p.pid: p for p in players}
    if pid not in P or pid in quit_ids:
        return "You're not in this game."
    p = P[pid]
    kind, target, amount = move[0], move[1], move[2]
    if kind not in KINDS:
        return f"Unknown move '{kind}'."
    if p.bandit and kind not in ("steal", "investigate"):
        return "Bandits can only steal or investigate."
    if kind in TARGETED:
        if target is None or target not in P or target in quit_ids:
            return "Pick a player who is still in the game."
        if target == pid:
            return "You can't target yourself."
    elif target is not None:
        return f"'{kind}' doesn't take a target."
    if kind == "guard" and not can_guard(p, rules, night):
        if p.guard_until >= night:
            return "You're already protected tonight."
        if rules.guard_limit and p.guards_used >= rules.guard_limit:
            return f"You've used all {rules.guard_limit} guards."
        return "You can't guard again yet."
    if kind == "gift":
        if not isinstance(amount, int) or not GIFT_MIN <= amount <= GIFT_MAX:
            return f"Gifts are {GIFT_MIN} or {GIFT_MAX} rations."
        if p.rations - amount < 1:
            return "You must keep at least 1 ration."
    elif amount not in (0, None):
        return f"'{kind}' doesn't take an amount."
    return None
