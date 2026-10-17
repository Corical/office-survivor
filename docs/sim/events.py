"""Wilderness events: a library of small random things that happen to the camp at the start of a night.

PROTOTYPE, simulator only. Switched on by two rule knobs (both default off, see engine/rules.py):

    events_per_night   average number of events per night, camp-wide (0 = events off, nothing here is called)
    events_bias        "random": every eligible player is equally likely to be hit
                       "trailing": good events go to players below the median 3 times as often as to the rest,
                                   bad events go to players above the median 3 times as often as to the rest

The library below is plain data. To add an event, add one entry; to change how common it is, change `weight`.
Each entry:
    id, name, emoji   what it is called
    text              the #news line ({who} = the player it happened to)
    public            True = posted in #news; False = only the player is told (a hidden idol stays hidden)
    good              True = a lucky event (trailing bias sends it to the poor); False = unlucky (sent to the rich)
    scope             "player" = happens to one player; "camp" = happens to everyone
    effect            {"op": ..., ...}, see OPS
    weight            relative chance of being drawn (a design choice, not a measurement)

Every ration change is booked as a `ration` ledger line with reason `event_found` (food appears) or `event_lost`
(food disappears), so the books still balance: check_invariants.py and conservation_check.py count those two as
created / destroyed. Storm and feast change no balance directly (they act inside the night, see engine/resolve.py).

The events use their OWN random stream, seeded from (game seed, night), so switching events on never moves a dice
roll in the main game, and switching them off gives back exactly the old game.
"""
import random
import statistics

TRAILING_FAVOUR = 3       # a favoured player is this many times as likely to be picked as an unfavoured one

EVENTS = [
    dict(id="bananas", name="Bananas", emoji="\U0001F34C", good=True, scope="player", public=True, weight=10,
         text="{who} found a pile of bananas. +1 ration.",
         effect={"op": "find", "amount": 1}),
    dict(id="coconut", name="Coconut", emoji="\U0001F965", good=True, scope="player", public=True, weight=10,
         text="{who} cracked open a fallen coconut. +1 ration.",
         effect={"op": "find", "amount": 1}),
    dict(id="cache", name="Supply cache", emoji="\U0001F392", good=True, scope="player", public=True, weight=3,
         text="{who} stumbled on a buried supply cache. +2 rations.",
         effect={"op": "find", "amount": 2}),
    dict(id="idol", name="Hidden idol", emoji="\U0001F5FF", good=True, scope="player", public=False, weight=5,
         text="You found a hidden idol. The next person to rob you gets nothing.",
         effect={"op": "idol"}),
    dict(id="snake", name="Snake bite", emoji="\U0001F40D", good=False, scope="player", public=True, weight=8,
         text="{who} was bitten by a snake. -1 ration.",
         effect={"op": "lose", "amount": 1, "floor": 1}),
    dict(id="rain", name="Rain on the stash", emoji="\U0001F327️", good=False, scope="player", public=True,
         weight=8, text="Rain soaked {who}'s stash. -1 ration.",
         effect={"op": "lose", "amount": 1, "floor": 1}),
    dict(id="shelter", name="Shelter collapse", emoji="\U0001F3DA️", good=False, scope="player", public=True,
         weight=4, text="{who}'s shelter collapsed in the night. Their guard is gone.",
         effect={"op": "drop_guard"}),
    dict(id="rats", name="Rats in the stores", emoji="\U0001F400", good=False, scope="camp", public=True, weight=3,
         text="Rats got into the stores. Everyone holding 7 or more rations lost 1.",
         effect={"op": "tax", "at_least": 7, "amount": 1}),
    dict(id="storm", name="Storm night", emoji="⛈️", good=False, scope="camp", public=True, weight=4,
         text="A storm rolled in. Nobody finds any food tonight.",
         effect={"op": "flag", "flag": "storm"}),
    dict(id="feast", name="Feast night", emoji="\U0001F356", good=True, scope="camp", public=True, weight=4,
         text="A feast night. Nobody eats tonight.",
         effect={"op": "flag", "flag": "feast"}),
]
BY_ID = {e["id"]: e for e in EVENTS}

# Same effect, different story (owner, 17 Oct 2026: "it's not always just snake bite, snake bite"). One is picked per
# occurrence from its own dice (event, player, night), so variations never move the balance results.
VARIANTS = {
    "bananas": [
        ("\U0001F34C", "{who} found a pile of bananas. +1 ration."),
        ("\U0001FAD0", "{who} found a bush heavy with wild berries. +1 ration."),
        ("\U0001F96D", "A ripe mango dropped right at {who}'s feet. +1 ration."),
        ("\U0001F344", "{who} found mushrooms. The safe kind, apparently. +1 ration."),
        ("\U0001F36F", "{who} raided a wild beehive and lived. +1 ration."),
        ("\U0001F95A", "{who} found a nest of eggs nobody was guarding. +1 ration."),
        ("\U0001F360", "{who} dug up a sweet potato. +1 ration."),
    ],
    "coconut": [
        ("\U0001F965", "{who} cracked open a fallen coconut. +1 ration."),
        ("\U0001F41F", "{who} caught a fish with their bare hands. +1 ration."),
        ("\U0001F980", "{who} grabbed a crab before it got away. +1 ration."),
        ("\U0001F95C", "{who} found a squirrel's hidden stash of nuts. +1 ration."),
        ("\U0001F96B", "A tin of beans washed up on the beach. {who} got there first. +1 ration."),
        ("\U0001F36B", "{who} found a chocolate bar in an old jacket pocket. +1 ration."),
        ("\U0001F33D", "{who} found a patch of wild corn. +1 ration."),
    ],
    "cache": [
        ("\U0001F392", "{who} stumbled on a buried supply cache. +2 rations."),
        ("\U0001F6F6", "A crate washed ashore and {who} dragged it home. +2 rations."),
        ("\U0001FA82", "A supply drop landed near {who}'s shelter. +2 rations."),
    ],
    "snake": [
        ("\U0001F40D", "{who} was bitten by a snake and spent a ration recovering. -1 ration."),
        ("\U0001F98D", "A gorilla raided {who}'s stash and ran off with a ration. -1 ration."),
        ("\U0001F412", "A monkey snatched a ration from {who} and laughed about it. -1 ration."),
        ("\U0001F99D", "Something with a striped tail got into {who}'s food overnight. -1 ration."),
        ("\U0001F426", "A seagull swooped down and took {who}'s lunch. -1 ration."),
        ("\U0001F417", "A wild boar trampled through {who}'s camp. -1 ration."),
        ("\U0001F577️", "{who} was bitten by a spider and lost a ration's worth of energy. -1 ration."),
    ],
    "rain": [
        ("\U0001F327️", "Rain soaked {who}'s stash. -1 ration."),
        ("\U0001F30A", "The tide came in further than {who} expected. -1 ration."),
        ("\U0001F41C", "Ants found {who}'s food before {who} did. -1 ration."),
        ("\U0001F92E", "{who} ate something that disagreed with them. -1 ration."),
        ("\U0001F525", "{who}'s cooking fire got out of hand. -1 ration."),
        ("\U0001F573️", "{who} dropped a ration down a hole and it's not coming back. -1 ration."),
        ("\U0001F9A0", "Mould got into {who}'s stash. -1 ration."),
    ],
}


def flavour(ev, game_seed, occurrence):
    """(emoji, text template) for the n-th occurrence (0-based) of `ev` in a game. Each event's variations are a
    deck shuffled once per game: all of them come up before any repeats. Own dice: never touches any game rng."""
    options = list(VARIANTS.get(ev["id"]) or [(ev["emoji"], ev["text"])])
    random.Random(f"flavour:{ev['id']}:{game_seed}").shuffle(options)
    return options[occurrence % len(options)]


def rng_for(seed, night):
    """The events' own dice for one night of one game. A string seed is hashed, so it is stable across runs."""
    return random.Random(f"wilderness-events:{seed}:{night}")


def _eligible(game, ev):
    """Players this player-scope event could happen to. Bandits are left out: events never touch them."""
    op, eff = ev["effect"]["op"], ev["effect"]
    out = []
    for p in game.players:
        if p.bandit:
            continue
        if op == "lose" and p.rations <= eff["floor"]:
            continue                       # never below the floor, so an event can never create a bandit
        if op == "idol" and p.idol:
            continue
        if op == "drop_guard" and p.guard_until < game.night:
            continue
        out.append(p)
    return out


def _pick(game, ev, pool, rng):
    if game.r.events_bias == "random" or len(pool) == 1:
        return rng.choice(pool)
    if game.r.events_bias != "trailing":
        raise ValueError(f"events_bias must be 'random' or 'trailing', not {game.r.events_bias!r}")
    median = statistics.median(p.rations for p in game.players if not p.bandit)
    # lucky events favour whoever is below the median, unlucky ones whoever is above it
    weights = [TRAILING_FAVOUR if (p.rations < median if ev["good"] else p.rations > median) else 1 for p in pool]
    return rng.choices(pool, weights=weights)[0]


def _book(game, p, delta, reason, ev):
    p.rations += delta
    game.ledger(p, delta, reason, p.rations, detail=ev["id"])
    game.event_tally["found" if delta > 0 else "lost"] += abs(delta)


def _apply(game, ev, rng, flags, news):
    eff, tally = ev["effect"], game.event_tally
    if ev["scope"] == "camp":
        who = None
        if eff["op"] == "flag":
            flags.add(eff["flag"])
        elif eff["op"] == "tax":
            for p in game.players:
                if not p.bandit and p.rations >= eff["at_least"]:
                    _book(game, p, -eff["amount"], "event_lost", ev)
        game.L("event", event=ev["id"], scope="camp", visibility="public")
        news.append(f"{ev['emoji']} {ev['text']}")
        tally[ev["id"]] += 1
        return
    pool = _eligible(game, ev)
    if not pool:
        tally["fizzled"] += 1              # nobody it could happen to (e.g. everyone is at the floor)
        return
    p = _pick(game, ev, pool, rng)
    op = eff["op"]
    if op == "find":
        _book(game, p, eff["amount"], "event_found", ev)
    elif op == "lose":
        _book(game, p, -min(eff["amount"], p.rations - eff["floor"]), "event_lost", ev)
    elif op == "idol":
        p.idol = True
    elif op == "drop_guard":
        p.guard_until = game.night - 1
    game.L("event", event=ev["id"], scope="player", player=p.name, visibility="public" if ev["public"] else "private")
    emoji, text = flavour(ev, game.seed, tally[ev["id"]])
    p.notes.append(f"Night {game.night}: {text.format(who=p.name)}")
    if ev["public"]:
        news.append(f"{emoji} {text.format(who=p.name)}")
        if op in ("find", "lose"):         # the camp can read the news, so their guess at this player's stash moves
            game.public_delta[p.pid] += eff["amount"] if op == "find" else -eff["amount"]
    tally[ev["id"]] += 1


def run_night_events(game, rng):
    """The start-of-night phase. Returns (flags for resolve_night, #news lines). Uses only `rng`, never game.rng."""
    x = game.r.events_per_night
    count = int(x) + (1 if rng.random() < x - int(x) else 0)
    flags, news = set(), []
    for _ in range(count):
        ev = rng.choices(EVENTS, weights=[e["weight"] for e in EVENTS])[0]
        _apply(game, ev, rng, flags, news)
    return frozenset(flags), news
