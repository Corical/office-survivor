"""End of game: helicopter seats, secret goals, points and the winner. Pure; randomness only for coin-flip ties."""


def objective_text(o, rules, target_name="@player"):
    return {
        "give": f"give away {rules.give_goal} rations over the game",
        "beat": f"finish with more rations than {target_name}",
        "robbed2_extract": f"get robbed at least {rules.robbed_goal}x and still extract",
        "steal3_clean": "steal at least 3 times without ever being caught",
        "detective": "expose a thief red-handed with /investigate at least once",
        "grudge": (f"make sure {target_name} doesn't extract" if rules.grudge_goal == "deny"
                   else f"successfully rob {target_name} at least {rules.grudge_robs}x"),
    }[o]


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
            done = p.steals_ok >= 3 and p.steals_caught == 0
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
