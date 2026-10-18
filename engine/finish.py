"""End of game: helicopter seats, secret goals, points and the winner. Pure; randomness only for coin-flip ties."""


# The wording of each goal and of each line of goal progress, as templates ({name} is filled from the line's args).
# One table serves Torch's /status (rendered here, in English) and the live rooms (the code and values go to the client,
# which words them in its own theme). arena/tests and engine/tests/test_goal_codes.py hold the English to a frozen copy
# of what these lines said before they became templates.
GOAL_LINES = {
    "goal_give": "give away {n} rations over the game",
    "goal_beat": "finish with more rations than {target}",
    "goal_robbed2_extract": "get robbed at least {n}x and still extract",
    "goal_steal3_clean": "steal 3 times before you're ever caught",
    "goal_detective": "expose a thief red-handed with /investigate at least once",
    "goal_grudge_deny": "make sure {target} doesn't extract",
    "goal_grudge_rob": "successfully rob {target} at least {n}x",
}
PROGRESS_LINES = {
    "progress_target_left": "your target left the game, so this goal no longer counts",
    "progress_clean_done": "3/3 clean steals before you were ever caught",
    "progress_clean_failed": "you were caught before your 3rd clean steal ({have}/3)",
    "progress_clean_open": "{have}/3 clean steals, never caught so far",
    "progress_give": "{have}/{need} given",
    "progress_detective_done": "thief exposed",
    "progress_detective_open": "0/1 thieves exposed",
    "progress_robbed_end": "robbed {have}/{need} ✓. Now hold a seat on the helicopter",
    "progress_robbed_open": "robbed {have}/{need} so far, and you'll need a seat at the end",
    "progress_beat": "decided at the end: you have {rations}, {target}'s stash is secret.",
    "progress_beat_band": "decided at the end: you have {rations}, {target}'s stash is secret. They look {band} this morning.",
    "progress_grudge_deny": "decided at the end: who gets a seat is only known when the helicopter comes",
    "progress_grudge_rob": "robbed {target} {have}/{need}",
}


def render_line(code, args):
    """A goal or progress line in English from its code and values."""
    return {**GOAL_LINES, **PROGRESS_LINES}[code].format(**args)


def goal_line(o, rules, target_name="@player"):
    """(code, args) for a goal's wording: what the player's secret goal says."""
    if o == "give":
        return "goal_give", {"n": rules.give_goal}
    if o == "beat":
        return "goal_beat", {"target": target_name}
    if o == "robbed2_extract":
        return "goal_robbed2_extract", {"n": rules.robbed_goal}
    if o == "steal3_clean":
        return "goal_steal3_clean", {}
    if o == "detective":
        return "goal_detective", {}
    if rules.grudge_goal == "deny":                  # o == "grudge"
        return "goal_grudge_deny", {"target": target_name}
    return "goal_grudge_rob", {"target": target_name, "n": rules.grudge_robs}


def objective_text(o, rules, target_name="@player"):
    return render_line(*goal_line(o, rules, target_name))


def goal_progress_line(p, players, rules, quit_ids=frozenset(), target_band=None):
    """(state, code, args) for a goal's progress: state is 'done' (can no longer be lost), 'failed' (can no longer be
    met), 'open' or 'end' (only the reveal can tell). Uses the same counters `finish` scores with, and only facts the
    player may know: never another player's exact rations (`target_band` is passed only when ranges are public)."""
    r, o = rules, p.objective
    P = {q.pid: q for q in players}
    if o in ("beat", "grudge") and p.obj_target in quit_ids:
        return "failed", "progress_target_left", {}
    if o == "steal3_clean":                      # owner, 17 Oct 2026: 3 clean steals before a catch locks it in
        if p.clean_steals >= 3:
            return "done", "progress_clean_done", {}
        if p.steals_caught:
            return "failed", "progress_clean_failed", {"have": p.clean_steals}
        return "open", "progress_clean_open", {"have": p.clean_steals}
    if o == "give":
        return ("done" if p.gifted_out >= r.give_goal else "open"), "progress_give", \
            {"have": p.gifted_out, "need": r.give_goal}
    if o == "detective":
        return ("done", "progress_detective_done", {}) if getattr(p, "exposures", 0) >= 1 \
            else ("open", "progress_detective_open", {})
    if o == "robbed2_extract":
        args = {"have": p.times_robbed, "need": r.robbed_goal}
        return ("end", "progress_robbed_end", args) if p.times_robbed >= r.robbed_goal \
            else ("open", "progress_robbed_open", args)
    if o == "beat":
        args = {"rations": p.rations, "target": P[p.obj_target].name}
        if target_band:
            return "end", "progress_beat_band", {**args, "band": target_band}
        return "end", "progress_beat", args
    if r.grudge_goal == "deny":
        return "end", "progress_grudge_deny", {}
    return ("done" if p.grudge_hits >= r.grudge_robs else "open"), "progress_grudge_rob", \
        {"target": P[p.obj_target].name, "have": p.grudge_hits, "need": r.grudge_robs}


def goal_progress(p, players, rules, quit_ids=frozenset(), target_band=None):
    """(state, text) for /status mid-game: goal_progress_line, in English."""
    state, code, args = goal_progress_line(p, players, rules, quit_ids, target_band)
    return state, render_line(code, args)


def finish(players, rules, rng, emit=lambda _type, **f: None, quit_ids=frozenset()):
    """Seats, goals and scores. Sets extracted/survived/obj_done/score on each player; returns the summary."""
    r = rules
    P = {p.pid: p for p in players}
    seats = max(1, round(len(players) * r.seat_ratio))
    eligible = [p for p in players if (not p.bandit or r.bandit_can_extract) and p.pid not in quit_ids]
    rng.shuffle(eligible)                          # coin flips for whatever is still tied
    if r.tiebreak == "kindness":
        key = lambda p: (p.rations, p.gifted_out, -p.steals_caught)
    else:
        key = lambda p: (p.rations,)
    eligible.sort(key=key, reverse=True)
    extracted = eligible[:seats]
    coin_flip = (len(eligible) > seats and key(eligible[seats - 1]) == key(eligible[seats]))
    ext_ids = {p.pid for p in extracted}

    for p in players:
        p.extracted = p.pid in ext_ids
        p.survived = not p.bandit and p.pid not in quit_ids
        o = p.objective
        target_quit = p.obj_target in quit_ids
        if target_quit:
            done = False                           # owner decision: goals aimed at a quitter are void
        elif o == "beat":
            done = p.rations > P[p.obj_target].rations
        elif o == "robbed2_extract":
            done = p.times_robbed >= r.robbed_goal and p.extracted
        elif o == "steal3_clean":
            done = p.clean_steals >= 3
        elif o == "give":
            done = p.gifted_out >= r.give_goal
        elif o == "detective":
            done = getattr(p, "exposures", 0) >= 1
        elif r.grudge_goal == "deny":
            done = p.obj_target not in ext_ids
        else:  # rob
            done = p.grudge_hits >= r.grudge_robs
        p.obj_done = done
        p.score = (r.pts_extract if p.extracted else (r.pts_survive if p.survived else 0)) \
            + (r.pts_objective if done else 0)

    emit("extraction", seats=seats, extracted=[p.name for p in extracted],
         ranking=[{"player": p.name, "rations": p.rations, "gave_away": p.gifted_out} for p in eligible],
         tiebreak=r.tiebreak, decided_by_coin_flip=coin_flip, visibility="public")
    for p in players:
        tgt = P[p.obj_target].name if p.obj_target >= 0 else ""
        emit("result", player=p.name, rations=p.rations, survived=p.survived, extracted=p.extracted,
             objective=objective_text(p.objective, r, tgt), objective_done=p.obj_done, score=p.score,
             stole=p.rations_stolen, steals_ok=p.steals_ok, steals_caught=p.steals_caught,
             times_robbed=p.times_robbed, gave_away=p.gifted_out, visibility="public_at_reveal")
    top = max(p.score for p in players)
    winners = [p for p in players if p.score == top]
    if r.winner_tiebreak != "none":
        wkey = (lambda p: (p.gifted_out, p.rations)) if r.winner_tiebreak == "kindness" else (lambda p: (p.rations,))
        best = max(wkey(p) for p in winners)
        winners = [p for p in winners if wkey(p) == best]
    emit("game_end", winners=[p.name for p in winners], winner_tiebreak=r.winner_tiebreak, visibility="public")
    return dict(seats=seats, extracted=extracted, coin_flip=coin_flip, winners=winners,
                cutoff=extracted[-1].rations if extracted else 0, survivors=len(eligible))
