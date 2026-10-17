#!/usr/bin/env python3
"""Strategy matrix: throw every kind of strategy mix at the OFFICIAL rules and look for anything weird.

    python -I docs/sim/tools/strategy_matrix.py bench
    python -I docs/sim/tools/strategy_matrix.py run   <experiment> [--games N] [--procs 4] [--tag NAME]
    python -I docs/sim/tools/strategy_matrix.py report

Experiments (letters follow the brief):
    A   monocultures: all players the same personality (N = 15, 9, 6, 25)
    B   monocultures of six pure-strategy stress archetypes (always-scavenge/steal/guard/investigate/gift, random legal)
    C   invasion matrix: one player of type X among N-1 of type Y (14 types x 14 residents + the office mix)
    D   50/50 pairs of all 14 types, plus a few chosen 3-way mixes
    E   random compositions (Dirichlet), 15 players, find the weirdest tables and what predicts what
    F   player counts 4, 6, 9, 15, 25 with the office mix
    (G, the anomaly sweep, runs inside every game of every experiment.)
    "nofeat" variants (A_nofeat, B_nofeat, C_nofeat) repeat a headline experiment with events off AND ranges off.

The "official" game = what Torch plays: docs/game.json rules, wilderness events "gentle" (1/night, top-biased, relative
rats), ranges 7/3/1 posted every morning, human memory (follows 3 players, fades the rest), and the AI that weighs
finds, bonuses and give-back (ai_exposure + ai_quiet). The no-feature variant switches off events and ranges+memory only.

The archetypes live ONLY in this file (registered into the in-process ARCH table at import; no game file is touched).
Every game is played with a replay log, so the books are checked in every game: no negative rations, no survivor at 0,
transfers net to zero each night, final rations = start + ledger, seats/extraction/score arithmetic, every night resolved.

Every game is a pure function of (spec, seed). Uses at most --procs processes (default 4) below normal priority.
Raw per-cell sums go to docs/sim/results/data/<tag>.json (mergeable accumulators: n, sum, sum of squares per metric).
"""
import argparse
import itertools
import json
import math
import os
import random
import statistics
import sys
import time
import traceback
from dataclasses import replace
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import survivors_sim as S  # noqa: E402
import visibility as V  # noqa: E402
from experiments import lower_priority  # noqa: E402

DATA = os.path.join(HERE, "..", "results", "data")
RESULTS = os.path.join(HERE, "..", "results")

# --------------------------------------------------------------------------
# The stress archetypes (opt-in, defined here only)
# --------------------------------------------------------------------------
ARCHETYPES = {
    "x_scav":   "always scavenge",
    "x_steal":  "always steal from whoever looks richest",
    "x_guard":  "always guard (scavenge when guarding is not legal)",
    "x_invest": "always investigate (the top suspect)",
    "x_gift":   "always give 1 to the poorest-looking, keeping at least 1 (scavenge when it can't)",
    "x_random": "uniformly random legal move, uniformly random target",
}
KIND = {"x_scav": "scavenge", "x_steal": "steal", "x_guard": "guard", "x_invest": "investigate",
        "x_gift": "gift", "x_random": "random"}
for _k, _v in ARCHETYPES.items():              # radio is only read for unexposed thefts (same 0.4 floor for everybody)
    S.ARCH[_k] = dict(w=(0, 0, 0, 0, 0), miss=0.0, final=0.0, radio=0.3, desc=_v)
PERSONALITIES = list(S.OFFICE_MIX)             # the 8 real ones
TYPES = PERSONALITIES + list(ARCHETYPES)       # 14
OFFICE = "office"                              # resident column meaning "the normal office mix"

GENTLE = {"events_per_night": 1.0, "events_bias": "top", "events_rats_relative": True}   # bot/game.py EVENT_MODES["gentle"]
CREATE = {"scavenge", "guard_income", "gift_bonus", "investigate_find", "event_found"}
DESTROY = {"eat", "fine", "event_lost"}
EXTRA_NAMES = [f"Extra{i}" for i in range(1, 41)]   # the sim only has 24 aliases; used only when players > 24


class XGame(S.Game):
    """The simulator's Game plus the stress archetypes. Everything else is untouched."""

    def _choose(self, p):
        kind = KIND.get(p.arch)
        if kind is None:
            return super()._choose(p)
        self._why, self._odds = [], None
        rng = self.rng
        if p.bandit:                                          # a bandit may only steal or investigate
            if kind == "investigate":
                bk = "investigate"
            elif kind == "steal":
                bk = "steal"
            elif kind == "random":
                bk = rng.choice(("steal", "investigate"))
            else:
                bk = "steal" if rng.random() < 0.85 else "investigate"   # the same rule the normal AI follows
            return self._act(p, bk)
        if kind == "random":
            legal = ["scavenge", "steal", "investigate"]
            if self.can_guard(p):
                legal.append("guard")
            if p.rations >= 2:
                legal.append("gift")
            return self._act(p, rng.choice(legal), uniform=True)
        if kind == "guard":
            return self._act(p, "guard" if self.can_guard(p) else "scavenge")
        if kind == "gift":
            return self._act(p, "gift" if p.rations >= 2 else "scavenge")
        return self._act(p, kind)

    def _act(self, p, kind, uniform=False):
        others = self.others(p)
        if kind == "steal":
            t = self.P(self.rng.choice(others).pid).pid if uniform else self.pick_steal_target(p)
            return ("steal", t, 0, False)
        if kind == "investigate":
            t = self.rng.choice(others).pid if uniform else self.pick_investigate_target(p)
            return ("investigate", t, 0, False)
        if kind == "gift":
            if uniform:
                t = self.rng.choice(others).pid
            else:                                             # the poorest-looking, no "pay back" memory: a pure rule
                t = min((self.perceived(p, q), q.pid) for q in others)[1]
            return ("gift", t, 1, False)
        return (kind, None, 0, False)


# --------------------------------------------------------------------------
# Specs and games
# --------------------------------------------------------------------------
# spec = dict(n, events, ranges, comp)   comp = list of [type, count] (explicit table), or
#                                        ["lone", X, resident]  one X among n-1 of resident (resident may be OFFICE)
#                                        None = the plain office mix
def rules_for(n, events):
    base = S.load_game_rules(S.DEFAULT_GAME)[0]
    return replace(base, players=n, **(GENTLE if events else {}))


def table(spec, seed):
    """The explicit list of personalities by seat for this game (None = leave it to the office mix), lone seat index."""
    n, comp = spec["n"], spec.get("comp")
    rr = random.Random(seed * 1000003 + 17)                   # seating draws never touch the game's own dice
    if comp is None:
        return None, None
    if comp[0] == "pair":                                     # 8/7, the bigger share alternates with the seed
        a, b = comp[1], comp[2]
        comp = [[a, 8], [b, 7]] if seed % 2 else [[a, 7], [b, 8]]
    elif comp[0] == "trio":
        comp = [[t, n // 3] for t in comp[1:]]
    if comp[0] == "lone":
        _, x, y = comp
        if y == OFFICE:
            return [x], rr.randrange(n)                       # seat 0 gets x, then swapped to a random seat in build()
        arr = [x] + [y] * (n - 1)
    else:
        arr = [t for t, c in comp for _ in range(c)]
        assert len(arr) == n, (comp, n)
    rr.shuffle(arr)
    return arr, None


def build(spec, seed):
    n = spec["n"]
    rules = rules_for(n, spec["events"])
    force, swap = table(spec, seed)
    ranges = spec["ranges"]
    names = S.NAMES
    if n > len(names):
        S.NAMES = names + EXTRA_NAMES                         # only for tables bigger than the alias pool
    try:
        g = XGame(rules, seed, force=force, log=True, vis="ranges" if ranges else "hidden",
                  memory=V.HumanMemory() if ranges else None, ai_exposure=True, ai_quiet=True)
    finally:
        S.NAMES = names
    if swap:
        a, b = g.players[0], g.players[swap]
        a.arch, b.arch = b.arch, a.arch                       # arch is only a label; names/goals stay per seat
    return g


def longest_run(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def fail(msg, g=None):
    raise AssertionError(msg)


def play(spec, seed):
    """-> (record dict of numbers, per-arch dict, per-goal dict). Raises on any broken invariant."""
    g = build(spec, seed)
    r = g.r
    n = r.players
    start = {p.name: r.start_rations for p in g.players}
    n5 = None
    for night in range(r.rounds):
        g.play_night()
        for p in g.players:
            if p.rations < 0:
                fail(f"negative rations {p.name}")
            if not p.bandit and p.rations <= 0:
                fail(f"survivor at 0 rations {p.name}")
        if night + 1 == 5:
            alive = [p for p in g.players if not p.bandit]
            if alive:
                top = max(p.rations for p in alive)
                n5 = {p.pid for p in alive if p.rations == top}
    if g.night != r.rounds or len(g.night_stats) != r.rounds:
        fail("a night was not resolved")
    res = g.finish()
    ext = {p.pid for p in res["extracted"]}
    wins = {p.pid for p in res["winners"]}
    # --- books ---
    net, held = {}, dict(start)
    made = {}
    destroyed = 0
    steal_ok = steal_empty = steal_caught = gifts = gift_amt = guards = radio = 0
    gifted_pairs, recip = set(), 0
    for e in g.events:
        t = e["type"]
        if t == "ration":
            held[e["player"]] += e["delta"]
            if e["reason"] in CREATE:
                made[e["reason"]] = made.get(e["reason"], 0) + e["delta"]
            elif e["reason"] in DESTROY:
                destroyed -= e["delta"]
            else:
                net[e["night"]] = net.get(e["night"], 0) + e["delta"]
        elif t == "steal":
            o = e["outcome"]
            steal_ok += o == "success"
            steal_empty += o == "empty"
            steal_caught += o == "caught"
        elif t == "gift":
            gifts += 1
            gift_amt += e["amount"]
            if (e["receiver"], e["giver"]) in gifted_pairs:
                recip += 1
            gifted_pairs.add((e["giver"], e["receiver"]))
        elif t == "guard_up":
            guards += 1
        elif t == "radio":
            radio += 1
    if any(v != 0 for v in net.values()):
        fail(f"transfers do not net to zero: {net}")
    for p in g.players:
        if held[p.name] != p.rations:
            fail(f"ledger does not match rations for {p.name}: {held[p.name]} vs {p.rations}")
        base = r.pts_extract if p.extracted else (r.pts_survive if p.survived else 0)
        if p.score != base + (r.pts_objective if p.obj_done else 0):
            fail(f"score arithmetic {p.name}")
        if p.extracted and p.bandit:
            fail(f"bandit extracted {p.name}")
    if len(res["extracted"]) > res["seats"]:
        fail("too many seats taken")
    left = [p for p in g.players if not p.bandit and p.pid not in ext]
    if res["extracted"] and left and max(p.rations for p in left) > min(p.rations for p in res["extracted"]):
        fail("a seat went to a lower ration count")
    if not res["winners"]:
        fail("no winner")

    # --- numbers ---
    ps = g.players
    scores = [p.score for p in ps]
    topscore = max(scores)
    total_r = sum(p.rations for p in ps)
    maxr = max(p.rations for p in ps)
    quiet = [s["quiet"] for s in g.night_stats]
    # nights each player spent as a survivor (not a bandit), from the bandit/rejoin lines in the log
    alive_n = {p.name: r.rounds for p in ps}
    out_since = {}
    for e in g.events:
        if e["type"] == "became_bandit":
            out_since[e["player"]] = e["night"]
        elif e["type"] == "rejoined" and e["player"] in out_since:
            alive_n[e["player"]] -= e["night"] - out_since.pop(e["player"])
    for name, nt in out_since.items():
        alive_n[name] -= r.rounds - nt                        # still a bandit at the end: nights nt+1..rounds lost
    ev = g.night_stats
    rec = dict(
        alive_end=sum(not p.bandit for p in ps), bandits_created=sum(p.deaths for p in ps),
        ever_bandit=sum(p.ever_bandit for p in ps), comebacks=sum(p.comebacks for p in ps),
        first_death_night=next((i + 1 for i, s in enumerate(ev) if s.get("death")), r.rounds + 1),
        nights_survived=statistics.mean(alive_n.values()),
        seats=res["seats"], extracted_n=len(ext), unfilled=max(0, res["seats"] - len(ext)),
        coin_flip=int(res["coin_flip"]), win_tie=int(len(res["winners"]) > 1),
        top_tie_n=sum(1 for s in scores if s == topscore), cutoff=res["cutoff"],
        score_mean=statistics.mean(scores), score_max=topscore, score_sd=statistics.pstdev(scores),
        max_rations=maxr, total_rations=total_r, runaway_share=(maxr / total_r) if total_r else 0.0,
        quiet_nights=sum(quiet), max_quiet_streak=longest_run(quiet),
        n5_leader_win=(len(n5 & wins) / len(n5)) if n5 else 0.0, n5_leader_seat=(len(n5 & ext) / len(n5)) if n5 else 0.0,
        steal_attempts=sum(p.actions["steal"] for p in ps), steal_landed=steal_ok, steal_empty=steal_empty,
        steal_caught=steal_caught, exposed=sum(s.get("exposed", 0) for s in ev),
        exposed_undone=sum(s.get("exposed_undone", 0) for s in ev), rations_stolen=sum(p.rations_stolen for p in ps),
        gifts=gifts, gift_amount=gift_amt, gift_reciprocal=recip, guards_up=guards,
        investigations=sum(p.actions["investigate"] for p in ps), scavenges=sum(p.actions["scavenge"] for p in ps),
        guard_actions=sum(p.actions["guard"] for p in ps), radio_lines=radio,
        food_created=sum(made.values()), food_destroyed=destroyed,
        food_scavenge=made.get("scavenge", 0), food_gift_bonus=made.get("gift_bonus", 0),
        food_investigate=made.get("investigate_find", 0), food_event=made.get("event_found", 0),
        events_fired=sum(v for k, v in g.event_tally.items() if k not in ("found", "lost", "fizzled")),
        pos0_win=(1 / len(wins)) if ps[0].pid in wins else 0.0, pos0_seat=int(ps[0].pid in ext),
    )
    rec["food_net"] = rec["food_created"] - rec["food_destroyed"]
    rec["anomaly"] = anomaly(rec, n, r.rounds)
    per_arch = {}
    for p in ps:
        a = per_arch.setdefault(p.arch, dict(cnt=0, win=0.0, seat=0, surv=0, score=0, ever_bandit=0, rations=0,
                                             steals_ok=0, caught=0, robbed=0, given=0, goal=0, stolen=0))
        a["cnt"] += 1
        a["win"] += (1 / len(wins)) if p.pid in wins else 0.0
        a["seat"] += p.pid in ext
        a["surv"] += p.survived
        a["score"] += p.score
        a["ever_bandit"] += p.ever_bandit
        a["rations"] += p.rations
        a["steals_ok"] += p.steals_ok
        a["caught"] += p.steals_caught
        a["robbed"] += p.times_robbed
        a["given"] += p.gifted_out
        a["goal"] += p.obj_done
        a["stolen"] += p.rations_stolen
    goals = {}
    for p in ps:
        d = goals.setdefault(p.objective, [0, 0])
        d[0] += 1
        d[1] += p.obj_done
    return rec, per_arch, goals


def anomaly(rec, n, rounds):
    """How weird one game is (higher = weirder). Documented in the report. Not comparable across player counts."""
    s = 4.0 * (n - rec["alive_end"]) / n                       # many dead at the end
    s += 6.0 * max(0.0, rec["runaway_share"] - 0.30)           # one player holds >30% of all food
    s += 3.0 * rec["win_tie"] + 1.5 * (rec["top_tie_n"] >= 3)  # winner tie even after kindness; 3+ tied on top
    s += 2.0 * rec["unfilled"] / max(1, rec["seats"])          # helicopter leaves with empty seats
    s += 2.0 * rec["max_quiet_streak"] / rounds                # long stretch of nights with nothing happening
    s += 1.0 * rec["coin_flip"]
    s += 3.0 * rec["bandits_created"] / n                      # lots of deaths
    s += 0.5 * rec["gift_reciprocal"] / 5                      # gift ping-pong
    return round(s, 3)


# --------------------------------------------------------------------------
# Accumulators
# --------------------------------------------------------------------------
class Acc:
    """key -> [n, sum, sum of squares], mergeable. Margins come from these."""

    def __init__(self):
        self.d = {}

    def add(self, k, v):
        x = self.d.get(k)
        if x is None:
            self.d[k] = [1, v, v * v]
        else:
            x[0] += 1
            x[1] += v
            x[2] += v * v

    def merge(self, other):
        for k, (n, s, s2) in other.items():
            x = self.d.get(k)
            if x is None:
                self.d[k] = [n, s, s2]
            else:
                x[0] += n
                x[1] += s
                x[2] += s2


def mean_moe(x):
    """(mean, 95% margin) from [n, s, s2]."""
    n, s, s2 = x
    m = s / n
    if n < 2:
        return m, 0.0
    var = max(0.0, (s2 - n * m * m) / (n - 1))
    return m, 1.96 * math.sqrt(var / n)


def run_chunk(job):
    """job = (cell_id, spec, seeds) -> (cell_id, acc dict, top anomalies, failures)."""
    cell, spec, seeds = job
    acc, top, fails = Acc(), [], []
    for seed in seeds:
        try:
            rec, per_arch, goals = play(spec, seed)
        except Exception as e:                                 # a crash or a broken invariant is a headline finding
            fails.append(dict(cell=cell, seed=seed, error=f"{type(e).__name__}: {e}",
                              trace="".join(traceback.format_exc().splitlines(True)[-4:])))
            continue
        for k, v in rec.items():
            acc.add(k, v)
        acc.add("games_ok", 1)
        for a, d in per_arch.items():
            c = d["cnt"]
            for k, v in d.items():
                acc.add(f"a:{a}:{k}", v / c if k != "cnt" else v)
        for o, (c, done) in goals.items():
            acc.add(f"goal:{o}:rate", done / c)
        top.append((rec["anomaly"], seed))
    top.sort(reverse=True)
    return cell, acc.d, top[:5], fails


def run_cells(cells, games, procs, label, chunk=100):
    """cells = {cell_id: spec}. Plays `games` games per cell (seeds 1..games, paired across cells). Returns merged results."""
    lower_priority()
    jobs = []
    for cid, spec in cells.items():
        ng = spec.get("games", games)
        s0 = spec.get("seed0", 0)
        seeds = list(range(s0 + 1, s0 + ng + 1))
        for i in range(0, ng, chunk):
            jobs.append((cid, spec, seeds[i:i + chunk]))
    total = sum(len(j[2]) for j in jobs)
    print(f"[{label}] {len(cells)} cells, {total} games, {procs} processes (below normal priority)", flush=True)
    t0 = time.time()
    merged = {cid: dict(acc=Acc(), top=[], fails=[], spec=spec) for cid, spec in cells.items()}
    done = 0
    with Pool(procs, initializer=lower_priority) as pool:
        for cid, d, top, fails in pool.imap_unordered(run_chunk, jobs):
            m = merged[cid]
            m["acc"].merge(d)
            m["top"] = sorted(m["top"] + top, reverse=True)[:5]
            m["fails"] += fails
    el = time.time() - t0
    nfail = sum(len(m["fails"]) for m in merged.values())
    print(f"[{label}] done in {el / 60:.1f} min, {total / el:.0f} games/s, failures: {nfail}", flush=True)
    return {cid: dict(spec=m["spec"], acc=m["acc"].d, top=m["top"], fails=m["fails"]) for cid, m in merged.items()}, el


def save(tag, data, meta):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"{tag}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(meta=meta, cells=data), f, separators=(",", ":"))
    print(f"wrote {os.path.normpath(path)} ({os.path.getsize(path) / 1e6:.2f} MB)", flush=True)


# --------------------------------------------------------------------------
# Experiment definitions
# --------------------------------------------------------------------------
def spec(n=15, comp=None, events=True, ranges=True, games=None):
    d = dict(n=n, comp=comp, events=events, ranges=ranges)
    if games:
        d["games"] = games
    return d


def mono(t, n):
    return [[t, n]]


def exp_cells(name, rr=None):
    """-> (cells, default games per cell, description)."""
    nofeat = name.endswith("_nofeat")
    base = name.replace("_nofeat", "")
    ev, rg = (not nofeat), (not nofeat)
    cells = {}
    if base == "A":
        for n in (15, 9, 6, 25):
            if nofeat and n != 15:
                continue
            for t in PERSONALITIES:
                cells[f"mono|{t}|{n}"] = spec(n, mono(t, n), ev, rg)
        return cells, 1000, "monocultures of the 8 personalities"
    if base == "B":
        for n in (15, 9, 6, 25):
            if nofeat and n != 15:
                continue
            for t in ARCHETYPES:
                cells[f"mono|{t}|{n}"] = spec(n, mono(t, n), ev, rg)
        return cells, 1000, "monocultures of the 6 pure archetypes"
    if base == "C":
        for x in TYPES:
            for y in TYPES + [OFFICE]:
                if x == y:
                    continue
                cells[f"inv|{x}|{y}"] = spec(15, ["lone", x, y], ev, rg)
        return cells, 1500, "invasion matrix: 1 invader x among 14 residents y"
    if base == "D":
        for a, b in itertools.combinations(TYPES, 2):
            cells[f"pair|{a}|{b}"] = spec(15, ["pair", a, b], ev, rg)
        for i, trio in enumerate(TRIOS):
            cells[f"trio|{'+'.join(trio)}"] = spec(15, ["trio"] + list(trio), ev, rg)
        return cells, 600, "50/50 pairs and chosen 3-way mixes"
    if base == "F":
        for n in (4, 6, 9, 15, 25):
            cells[f"office|{n}"] = spec(n, None, ev, rg)
        return cells, 2000, "office mix at several player counts"
    raise SystemExit(f"unknown experiment {name}")


TRIOS = [("shark", "saint", "detective"), ("opportunist", "paranoid", "x_guard"), ("casual", "shark", "x_steal"),
         ("farmer", "shark", "detective"), ("chaos", "x_random", "x_gift"), ("saint", "x_gift", "shark"),
         ("detective", "x_invest", "opportunist"), ("farmer", "x_scav", "x_steal")]


# --------------------------------------------------------------------------
# E: random compositions
# --------------------------------------------------------------------------
def random_table(i, base_seed=910000, n=15):
    """Dirichlet(1) weights over the 14 types -> integer counts by largest remainder. Fully determined by i."""
    rr = random.Random(base_seed + i)
    w = [rr.gammavariate(1.0, 1.0) for _ in TYPES]
    s = sum(w)
    w = [x / s for x in w]
    raw = [x * n for x in w]
    cnt = [int(x) for x in raw]
    for j in sorted(range(len(TYPES)), key=lambda j: raw[j] - cnt[j], reverse=True)[: n - sum(cnt)]:
        cnt[j] += 1
    return [[t, c] for t, c in zip(TYPES, cnt) if c]


def run_E(args):
    tables = args.tables
    cells = {}
    for i in range(tables):
        sp = spec(15, random_table(i), True, True, games=args.games or 40)
        sp["seed0"] = 100000 + i * 1000                            # each table plays its own seeds, not shared ones
        cells[f"rand|{i:04d}"] = sp
    return cells


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Loading, replay, recheck
# --------------------------------------------------------------------------
def load(tag):
    p = os.path.join(DATA, f"{tag}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def all_cells(exp, tables=600):
    if exp == "E":
        return {f"rand|{i:04d}": spec(15, random_table(i), True, True) for i in range(tables)}
    return exp_cells(exp)[0]


def cmd_replay(a):
    """Play ONE game of a cell and print it (and optionally write its replay log)."""
    cells = all_cells(a.exp)
    if a.cell not in cells:
        raise SystemExit(f"no cell '{a.cell}' in {a.exp}. Example ids: {list(cells)[:3]}")
    sp = cells[a.cell]
    g = build(sp, a.seed)
    res = g.run()
    for p in sorted(g.players, key=lambda p: -p.score):
        print(f"{p.score} pts {p.name:<13}{p.arch:<12}{'extracted' if p.extracted else ('survived' if p.survived else 'bandit'):<10}"
              f" rations {p.rations:<3} stole {p.rations_stolen} ({p.steals_ok} ok/{p.steals_caught} caught) robbed {p.times_robbed}x"
              f" gave {p.gifted_out} deaths {p.deaths}")
    print(f"winners: {[w.name for w in res['winners']]}  seats {res['seats']}  coin flip {res['coin_flip']}")
    rec, _, _ = play(sp, a.seed)
    print("record:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in rec.items()})
    if a.log:
        with open(a.log, "w", encoding="utf-8") as f:
            for e in g.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print("replay log written to", a.log)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
SHORT = dict(casual="cas", farmer="far", opportunist="opp", shark="shk", paranoid="par", saint="sai", detective="det",
             chaos="cha", x_scav="xSc", x_steal="xSt", x_guard="xGd", x_invest="xIv", x_gift="xGf", x_random="xRn",
             office="OFFICE")


def val(cell, key):
    x = cell["acc"].get(key)
    return mean_moe(x) if x else (float("nan"), 0.0)


def mval(cell, key):
    return val(cell, key)[0]


def mark(m, e, hi=1.25, lo=0.6):
    if m - e > hi:
        return "▲"
    if m + e < lo:
        return "▼"
    if m > hi:
        return "△"
    if m < lo:
        return "▽"
    return ""


def lone_stats(cell):
    """(win m,e ; seat m,e) of the invader, relative to a fair share. The invader is the only player of its type."""
    n = cell["spec"]["n"]
    x = cell["spec"]["comp"][1]
    seats = cell["acc"]["seats"][1] / cell["acc"]["seats"][0]
    w = val(cell, f"a:{x}:win")
    s = val(cell, f"a:{x}:seat")
    return (w[0] * n, w[1] * n), (s[0] / (seats / n), s[1] / (seats / n))


def is_marked(cell):
    (wm, we), (sm, se) = lone_stats(cell)
    return bool(mark(wm, we) in ("▲", "▼") or mark(sm, se) in ("▲", "▼"))


def cmd_recheck(a):
    """Re-run the surprising invasion cells (a margin-clear mark on win or seat share) with FRESH seeds."""
    d = load(a.exp)
    marked = [cid for cid, c in d["cells"].items() if cid.startswith("inv|") and is_marked(c)]
    def dev(cid):                                                  # distance of the win share from 1.00, in log terms
        return abs(math.log(max(lone_stats(d["cells"][cid])[0][0], 1e-3)))
    def margin(cid):                                               # how far inside the mark the cell is (small = borderline)
        (wm, we), (sm, se) = lone_stats(d["cells"][cid])
        best = []
        for m, e in ((wm, we), (sm, se)):
            if m - e > 1.25:
                best.append(m - e - 1.25)
            elif m + e < 0.6:
                best.append(0.6 - m - e)
        return min(best)
    if a.extreme or a.borderline:                                   # a sample of the marked cells, not all of them
        ext = sorted(marked, key=dev, reverse=True)[:a.extreme]
        bord = sorted([c for c in marked if c not in ext], key=margin)[:a.borderline]
        marked = ext + bord
    cells = {cid: dict(d["cells"][cid]["spec"], seed0=700000, games=a.games) for cid in marked}
    print(f"re-running {len(cells)} marked cells with {a.games} fresh games each (seeds 700001..)")
    data, el = run_cells(cells, a.games, a.procs, f"{a.exp}_recheck")
    save(f"{a.exp}_recheck", data, dict(exp=a.exp, games=a.games, minutes=round(el / 60, 2),
         command=" ".join(["python -I docs/sim/tools/strategy_matrix.py"] + sys.argv[1:])))


def f1(x, d=1):
    return "-" if x != x else f"{x:.{d}f}"


def pm(m, e, d=2):
    return f"{m:.{d}f}±{e:.{d}f}"


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def invasion_tables(C, recheck=None):
    """The matrix (win share, seat share) + dominance analysis. Returns (markdown, marked list)."""
    residents = TYPES + [OFFICE]
    rows_w, rows_s, marked = [], [], []
    rel_w, sig_up = {}, {}
    for x in TYPES:
        rw, rs = [], []
        for y in residents:
            cid = f"inv|{x}|{y}"
            if x == y:
                rw.append("(1.00)")
                rs.append("(1.00)")
                continue
            c = C["cells"][cid]
            (wm, we), (sm, se) = lone_stats(c)
            rel_w[(x, y)] = (wm, we)
            rw.append(f"{wm:.2f}±{we:.2f}{mark(wm, we)}")
            rs.append(f"{sm:.2f}±{se:.2f}{mark(sm, se)}")
            if mark(wm, we) or mark(sm, se):
                marked.append((x, y, wm, we, sm, se))
        rows_w.append([f"**{SHORT[x]}**"] + rw)
        rows_s.append([f"**{SHORT[x]}**"] + rs)
    head = ["invader \\ residents"] + [SHORT[y] for y in residents]
    out = ["### 3a. Win share of one invader, relative to a fair share (1.00 = fair, 1/15 of the wins)\n",
           md_table(head, rows_w), "\n### 3b. Helicopter-seat share of one invader, relative to a fair share\n",
           md_table(head, rows_s)]
    # dominance
    upsig = {(x, y) for (x, y), (m, e) in rel_w.items() if m - e > 1.0 and y != OFFICE}
    downsig = {(x, y) for (x, y), (m, e) in rel_w.items() if m + e < 1.0 and y != OFFICE}
    n_cells = len(rel_w)
    n_non = sum(1 for (x, y), (m, e) in rel_w.items() if (m - e > 1.0 or m + e < 1.0))
    out.append(f"\nCells whose win-share margin excludes 1.00 (either direction): {n_non} of {n_cells}. "
               f"Pure chance at the 95% level would give about {0.05 * n_cells:.0f}.\n")
    # row/col means
    rows = []
    for x in TYPES:
        vs = [rel_w[(x, y)][0] for y in TYPES if y != x]
        rows.append((x, statistics.mean(vs), min(vs), max(vs), rel_w[(x, OFFICE)][0],
                     sum((x, y) in upsig for y in TYPES if y != x), sum((x, y) in downsig for y in TYPES if y != x)))
    out.append("\n### 3c. Per invader: average over the 13 resident worlds\n")
    out.append(md_table(["invader", "mean win×", "worst world", "best world", "vs office", "worlds it clearly beats fair (of 13)",
                         "worlds it clearly loses (of 13)"],
                        [[SHORT[x], f"{m:.2f}", f"{lo:.2f}", f"{hi:.2f}", f"{o:.2f}", u, d] for x, m, lo, hi, o, u, d in
                         sorted(rows, key=lambda r: -r[1])]))
    # uninvadable residents, invadable
    rows = []
    for y in TYPES:
        vs = [rel_w[(x, y)] for x in TYPES if x != y]
        best = max(vs, key=lambda t: t[0])
        bx = [x for x in TYPES if x != y and rel_w[(x, y)] == best][0]
        rows.append((y, statistics.mean(m for m, e in vs), SHORT[bx], best, sum((x, y) in upsig for x in TYPES if x != y)))
    out.append("\n### 3d. Per resident world: how invadable is it (mean win× of a lone invader)\n")
    out.append(md_table(["resident world", "mean invader win×", "best invader", "its win×", "invaders clearly above fair (of 13)"],
                        [[SHORT[y], f"{m:.2f}", bx, pm(b[0], b[1]), k] for y, m, bx, b, k in sorted(rows, key=lambda r: -r[1])]))
    # cycles
    cyc = []
    for x, y, z in itertools.permutations(TYPES, 3):
        if x < y and x < z and (x, y) in upsig and (y, z) in upsig and (z, x) in upsig:
            cyc.append((x, y, z))
    mutual = sorted({tuple(sorted((x, y))) for (x, y) in upsig if (y, x) in upsig})
    out.append("\n### 3e. Cycles\n")
    out.append("Read 'X invades Y' as: a lone X among 14 Y does clearly better than fair. "
               f"Three-way cycles X→Y→Z→X among the 14 types: **{len(cyc)}**"
               + (": " + "; ".join(f"{SHORT[x]}→{SHORT[y]}→{SHORT[z]}→{SHORT[x]}" for x, y, z in cyc[:20]) if cyc else ".")
               + f"\n\nMutual invasion (each does clearly better than fair among the other, so neither world is stable): "
               f"**{len(mutual)}** pairs" + (": " + ", ".join(f"{SHORT[a]}/{SHORT[b]}" for a, b in mutual[:30]) if mutual else "."))
    unin = [y for y in TYPES if not any((x, y) in upsig for x in TYPES if x != y)]
    out.append(f"\n\nResident worlds nobody can clearly invade (no type beats fair as a lone invader): "
               f"{', '.join(SHORT[y] for y in unin) if unin else 'none'}.")
    # marked cells table with recheck
    out.append("\n### 3f. Marked cells (▲ above 1.25 / ▼ below 0.60, margin-clear), re-run with fresh seeds\n")
    rk = []
    for x, y, wm, we, sm, se in sorted(marked, key=lambda t: -abs(math.log(max(t[2], 1e-3)))):
        fresh = ""
        if recheck and f"inv|{x}|{y}" in recheck["cells"]:
            (fw, fe), (fs, fse) = lone_stats(recheck["cells"][f"inv|{x}|{y}"])
            same = ("holds" if (mark(fw, fe) in ("▲", "▼") or mark(fs, fse) in ("▲", "▼")) else "DOES NOT HOLD")
            fresh = f"{fw:.2f}±{fe:.2f} / {fs:.2f}±{fse:.2f}", same
        rk.append([SHORT[x], SHORT[y], pm(wm, we) + mark(wm, we), pm(sm, se) + mark(sm, se)]
                  + (list(fresh) if fresh else ["-", "-"]))
    out.append(md_table(["invader", "resident", "win× (orig)", "seat× (orig)", "fresh seeds win× / seat×", "verdict"], rk))
    return "\n".join(out), marked


FLAG_N = lambda c: c["spec"]["n"]


def mono_flags(c):
    n = c["spec"]["n"]
    r = 10
    m = lambda k: mval(c, k)
    fl = []
    if m("steal_attempts") < 1:
        fl.append("nobody steals")
    if m("scavenges") < 0.05 * n * r:
        fl.append("nobody scavenges")
    if m("alive_end") < 0.25 * n:
        fl.append(f"mass death ({m('alive_end'):.1f} of {n} alive at the end)")
    if m("runaway_share") > 0.25:
        fl.append(f"runaway leader (richest holds {m('runaway_share'):.0%} of all food)")
    if m("gifts") > 0.5 * n * r:
        fl.append(f"gift storm ({m('gifts'):.0f} gifts)")
    if m("win_tie") > 0.5:
        fl.append(f"joint win in {m('win_tie'):.0%} of games")
    if m("coin_flip") > 0.35:
        fl.append(f"seat decided by coin flip in {m('coin_flip'):.0%}")
    if m("unfilled") > 0.2:
        fl.append(f"{m('unfilled'):.1f} empty seats")
    if m("food_net") > 0.5 * n * 7:
        fl.append(f"food printing (+{m('food_net'):.0f} net)")
    return fl


def mono_tables(cells, n, title):
    types = [t for t in TYPES if f"mono|{t}|{n}" in cells]
    out = [f"#### {title}\n"]
    rows = []
    for t in types:
        c = cells[f"mono|{t}|{n}"]
        m = lambda k, d=1: f1(mval(c, k), d)
        rows.append([f"**{t}**", m("nights_survived"), m("bandits_created"), m("alive_end"), m("comebacks"), m("seats", 0) + "/" + m("extracted_n"),
                     m("unfilled", 2), m("score_mean", 2), m("score_max", 1), m("score_sd", 2),
                     f"{mval(c, 'win_tie'):.0%}", f"{mval(c, 'top_tie_n'):.1f}", f"{mval(c, 'coin_flip'):.0%}",
                     m("runaway_share", 2), m("quiet_nights"), m("anomaly", 2)])
    out.append(md_table(["monoculture", "nights alive/player", "bandits created", "alive at end", "comebacks", "seats/taken",
                         "empty seats", "pts mean", "pts max", "pts sd", "joint win", "tied on top", "coin flip seat",
                         "richest's food share", "quiet nights", "anomaly"], rows))
    rows = []
    for t in types:
        c = cells[f"mono|{t}|{n}"]
        m = lambda k, d=1: f1(mval(c, k), d)
        rows.append([f"**{t}**", m("steal_attempts"), m("steal_landed"), m("steal_empty"), m("steal_caught"), m("exposed", 2),
                     m("exposed_undone", 2), m("gifts"), m("gift_reciprocal"), m("guards_up", 2), m("investigations"),
                     m("scavenges"), m("radio_lines", 2), m("food_created"), m("food_destroyed"), m("food_net"),
                     m("food_gift_bonus"), m("food_investigate"), m("events_fired", 1)])
    out.append("\n" + md_table(["monoculture", "steals tried", "landed", "empty", "caught", "exposed", "exposures undone", "gifts",
                                "gift ping-pong", "guards raised", "investigations", "scavenges", "radio lines", "food created",
                                "food destroyed", "net", "of which gift bonus", "of which investigate find", "events fired"], rows))
    goals = ["beat", "robbed2_extract", "steal3_clean", "give", "grudge"]
    rows = [[f"**{t}**"] + [f"{mval(cells[f'mono|{t}|{n}'], f'goal:{g}:rate'):.0%}" for g in goals] for t in types]
    out.append("\n" + md_table(["monoculture"] + ["goal: " + g for g in goals], rows))
    fl = [[f"**{t}**", "; ".join(mono_flags(cells[f"mono|{t}|{n}"])) or "-"] for t in types]
    out.append("\nDegenerate-world flags:\n\n" + md_table(["monoculture", "flags"], fl))
    return "\n".join(out)


def pair_tables(D):
    cells = D["cells"]
    rel = {}
    for cid, c in cells.items():
        if not cid.startswith("pair|"):
            continue
        _, a, b = cid.split("|")
        n = c["spec"]["n"]
        rel[(a, b)] = tuple(v * n for v in val(c, f"a:{a}:win"))
        rel[(b, a)] = tuple(v * n for v in val(c, f"a:{b}:win"))
    rows = []
    for a in TYPES:
        row = [f"**{SHORT[a]}**"]
        for b in TYPES:
            if a == b:
                row.append("-")
            else:
                m, e = rel[(a, b)]
                row.append(f"{m:.2f}±{e:.2f}{mark(m, e)}")
        rows.append(row)
    out = ["### 5a. Win share per player of the ROW type in a 50/50 table with the COLUMN type (8 vs 7 players, alternating; 1.00 = fair)\n",
           md_table(["row \\ column"] + [SHORT[b] for b in TYPES], rows)]
    sysrows = []
    for cid, c in sorted(cells.items()):
        if not cid.startswith("pair|"):
            continue
        _, a, b = cid.split("|")
        sysrows.append((cid, mval(c, "bandits_created"), mval(c, "alive_end"), mval(c, "food_net"), mval(c, "gifts"),
                        mval(c, "steal_attempts"), mval(c, "max_quiet_streak"), mval(c, "anomaly"), a, b))
    def top(idx, rev, k=6):
        return sorted(sysrows, key=lambda r: r[idx], reverse=rev)[:k]
    out.append("\n### 5b. System outcomes: the extreme 50/50 tables\n")
    for idx, label, rev in ((1, "most bandits created", True), (1, "fewest bandits created", False), (3, "most net food", True),
                            (3, "least net food (worst food drain)", False), (4, "most gifts", True), (6, "longest quiet streak", True)):
        out.append(f"\n**{label}**\n")
        out.append(md_table(["pair", "bandits created", "alive at end", "net food", "gifts", "steals tried", "longest quiet streak"],
                            [[f"{SHORT[r[8]]}+{SHORT[r[9]]}", f1(r[1]), f1(r[2]), f1(r[3]), f1(r[4]), f1(r[5]), f1(r[6])]
                             for r in top(idx, rev)]))
    # 3-way
    trows = []
    for cid, c in cells.items():
        if cid.startswith("trio|"):
            ts = cid.split("|")[1].split("+")
            n = c["spec"]["n"]
            trows.append([cid.split("|")[1].replace("+", " + ")] + [pm(*(v * n for v in val(c, f"a:{t}:win"))) for t in ts]
                         + [f1(mval(c, "bandits_created")), f1(mval(c, "alive_end")), f1(mval(c, "food_net")),
                            f1(mval(c, "gifts"))])
    out.append("\n### 5c. Chosen 3-way mixes (5/5/5): win× of each type in the order listed\n")
    out.append(md_table(["mix", "type 1 win×", "type 2 win×", "type 3 win×", "bandits created", "alive at end", "net food", "gifts"], trows))
    return "\n".join(out), rel


def solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[piv] = M[piv], M[i]
        d = M[i][i]
        for j in range(i, n + 1):
            M[i][j] /= d
        for r in range(n):
            if r != i and M[r][i]:
                f = M[r][i]
                for j in range(i, n + 1):
                    M[r][j] -= f * M[i][j]
    return [M[i][n] for i in range(n)]


def invert(A):
    n = len(A)
    cols = []
    for i in range(n):
        e = [0.0] * n
        e[i] = 1.0
        cols.append(solve(A, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def ols(X, y):
    """No-intercept least squares (the fractions sum to 1, so they carry the intercept). -> beta, se, r2."""
    k = len(X[0])
    XtX = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    Xty = [sum(r[i] * yy for r, yy in zip(X, y)) for i in range(k)]
    beta = solve(XtX, Xty)
    resid = [yy - sum(b * v for b, v in zip(beta, r)) for r, yy in zip(X, y)]
    dof = max(1, len(y) - k)
    s2 = sum(e * e for e in resid) / dof
    inv = invert(XtX)
    se = [math.sqrt(max(0.0, s2 * inv[i][i])) for i in range(k)]
    my = statistics.mean(y)
    ss_tot = sum((v - my) ** 2 for v in y)
    return beta, se, (1 - sum(e * e for e in resid) / ss_tot) if ss_tot else 0.0


def random_tables(E):
    cells = E["cells"]
    ids = sorted(cells)
    X, rows = [], []
    for cid in ids:
        c = cells[cid]
        cnt = {t: 0 for t in TYPES}
        for t, k in c["spec"]["comp"]:
            cnt[t] = k
        X.append([cnt[t] / 15 for t in TYPES])
        rows.append(c)
    outcomes = [("bandits_created", "bandits created"), ("alive_end", "alive at end"), ("gifts", "gifts"),
                ("max_quiet_streak", "longest quiet streak"), ("n5_leader_win", "N5 leader wins"), ("food_net", "net food"),
                ("steal_attempts", "steals tried"), ("win_tie", "joint-win share"), ("unfilled", "empty seats"),
                ("score_sd", "points spread (sd)")]
    out = [f"{len(ids)} random tables of 15 players: weights drawn Dirichlet(1,...,1) over the 14 types, turned into whole "
           f"players by largest remainder; {rows[0]['spec'].get('games')} games per table, each table on its own seeds.\n"]
    ys = {k: [mval(c, k) for c in rows] for k, _ in outcomes}
    reg = {}
    for k, label in outcomes:
        beta, se, r2 = ols(X, ys[k])
        reg[k] = (beta, se, r2)
    out.append("### 6a. What predicts what: effect of swapping ONE average player for one of this type "
               "(regression of the table's mean outcome on the type fractions; `*` = |t| > 2)\n")
    hdr = ["outcome (table mean)", "R²", "mean"] + [SHORT[t] for t in TYPES]
    rowsm = []
    nstar = 0
    for k, label in outcomes:
        beta, se, r2 = reg[k]
        row = [label, f"{r2:.2f}", f1(statistics.mean(ys[k]), 2)]
        for i, t in enumerate(TYPES):
            others = [beta[j] for j in range(len(TYPES)) if j != i]
            d = (beta[i] - statistics.mean(others)) / 15
            # se of the contrast, treating the others' mean as fixed noise-free (approximation)
            t_ = (beta[i] - statistics.mean(others)) / se[i] if se[i] else 0
            star = "*" if abs(t_) > 2 else ""
            nstar += bool(star)
            row.append(f"{d:+.2f}{star}")
        rowsm.append(row)
    out.append(md_table(hdr, rowsm))
    out.append(f"\n{nstar} of {len(outcomes) * len(TYPES)} effects carry a `*`. Pure chance would flag about "
               f"{0.05 * len(outcomes) * len(TYPES):.0f}. The t-value uses the standard error of the type's own coefficient "
               f"(an approximation of the contrast's), so read stars as hints and R² as the honest size of the story: "
               f"an outcome with R² under about 0.1 is mostly noise in the composition.\n")
    # weirdest tables
    def z(k):
        m, s = statistics.mean(ys[k]), statistics.pstdev(ys[k]) or 1
        return [(v - m) / s for v in ys[k]]
    keys = ["bandits_created", "max_quiet_streak", "gifts", "n5_leader_win", "food_net"]
    zs = {k: z(k) for k in keys}
    weird = sorted(range(len(ids)), key=lambda i: -sum(abs(zs[k][i]) for k in keys))
    def comp_text(c):
        return ", ".join(f"{k} {t}" for t, k in c["spec"]["comp"])
    def replay_line(cid, c):
        return f"`python -I docs/sim/tools/strategy_matrix.py replay E \"{cid}\" <seed {c['spec']['seed0'] + 1}..{c['spec']['seed0'] + c['spec']['games']}>`"
    out.append("### 6b. The 10 weirdest tables (sum of |z| over bandits, quiet streak, gifts, leader hold, net food)\n")
    wr = []
    for i in weird[:10]:
        c = rows[i]
        wr.append([ids[i], comp_text(c), f1(ys["bandits_created"][i]), f1(ys["alive_end"][i]), f1(ys["max_quiet_streak"][i]),
                   f1(ys["gifts"][i]), f"{ys['n5_leader_win'][i]:.0%}", f1(ys["food_net"][i]),
                   f"{c['spec']['seed0'] + 1}..{c['spec']['seed0'] + c['spec']['games']}"])
    out.append(md_table(["table", "exact composition (counts)", "bandits created", "alive end", "quiet streak", "gifts",
                         "N5 leader wins", "net food", "seeds"], wr))
    out.append("\nReplay any table game with: `python -I docs/sim/tools/strategy_matrix.py replay E \"rand|NNNN\" <seed>`.\n")
    out.append("### 6c. Extremes by single outcome\n")
    for k, label, rev in (("bandits_created", "most bandits", True), ("max_quiet_streak", "longest stalemates", True),
                          ("gifts", "most gifts", True), ("gifts", "fewest gifts", False),
                          ("n5_leader_win", "highest leader hold (N5 leader wins)", True),
                          ("n5_leader_win", "lowest leader hold", False)):
        order = sorted(range(len(ids)), key=lambda i: ys[k][i], reverse=rev)[:3]
        out.append(f"\n**{label}**\n")
        out.append(md_table(["table", "value", "composition"],
                            [[ids[i], f1(ys[k][i], 2), comp_text(rows[i])] for i in order]))
    # simple correlations of the 5 headline outcomes
    return "\n".join(out), reg


def count_table(F):
    rows = []
    for n in (4, 6, 9, 15, 25):
        c = F["cells"].get(f"office|{n}")
        if not c:
            continue
        m = lambda k, d=1: f1(mval(c, k), d)
        rows.append([n, int(mval(c, 'games_ok') and c['acc']['games_ok'][0]), len(c["fails"]), m("seats", 0), m("extracted_n"), m("unfilled", 2),
                     m("score_mean", 2), m("score_max", 2), m("score_sd", 2), m("bandits_created"), m("alive_end"),
                     m("comebacks"), m("nights_survived"), f"{mval(c, 'win_tie'):.0%}", f"{mval(c, 'coin_flip'):.0%}",
                     f"{mval(c, 'n5_leader_win'):.0%}", m("steal_attempts"), m("gifts"), m("food_net"), m("anomaly", 2)])
    return md_table(["players", "games ok", "crashes/invariant fails", "seats", "taken", "empty seats", "pts mean", "pts max", "pts sd",
                     "bandits created", "alive end", "comebacks", "nights alive/player", "joint win", "coin flip seat", "N5 leader wins",
                     "steals tried", "gifts", "net food", "anomaly"], rows)


def collect_anomalies(datasets, predicate):
    rows = []
    for tag, D in datasets.items():
        for cid, c in D["cells"].items():
            if not predicate(cid, c):
                continue
            for s, seed in c["top"]:
                rows.append((s, tag, cid, seed))
    rows.sort(reverse=True)
    return rows


def main_report(a):
    tags = ["A", "B", "C", "D", "E", "F", "A_nofeat", "B_nofeat", "C_nofeat", "C_recheck", "A_N_more"]
    D = {t: load(t) for t in tags}
    D = {t: v for t, v in D.items() if v}
    head = open(a.head, encoding="utf-8").read() if a.head else "## 1) TL;DR\n\n(hand-written part not supplied)\n"
    tail = open(a.tail, encoding="utf-8").read() if a.tail else "## 8) What I would test next\n\n(hand-written part not supplied)\n"
    parts = [head]
    # --- totals / failures ---
    total_games = sum(c["acc"].get("games_ok", [0])[0] for v in D.values() for c in v["cells"].values()
                      if v.get("meta", {}).get("exp") != "C_recheck" and not str(v.get("meta", {}).get("exp", "")).endswith("recheck"))
    total_fail = sum(len(c["fails"]) for v in D.values() for c in v["cells"].values())
    fails = [(tag, cid, f) for tag, v in D.items() for cid, c in v["cells"].items() for f in c["fails"]]
    parts.append(f"### 2z. Anomaly sweep (G) and the weirdest single games\n\n**Anomaly sweep (G).** {total_games:,} games were played with the full book-keeping check inside every game "
                 f"(negative rations, survivor at 0, per-night transfers netting to zero, final rations = start + ledger, "
                 f"score arithmetic, seats, bandit extraction, every night resolved). Crashes or broken invariants: **{total_fail}**.\n")
    if fails:
        parts.append(md_table(["experiment", "cell", "seed", "error"], [[t, cid, f["seed"], f["error"][:120]] for t, cid, f in fails[:30]]))
    # anomalies
    for title, pred in (("non-monoculture tables with 15 players", lambda cid, c: not cid.startswith("mono|") and c["spec"]["n"] == 15),
                        ("all cells with 15 players (monocultures included)", lambda cid, c: c["spec"]["n"] == 15)):
        rows = collect_anomalies({k: v for k, v in D.items() if not k.endswith("recheck")}, pred)[:10]
        parts.append(f"\n**The 10 weirdest single games: {title}** (anomaly score, see method)\n")
        parts.append(md_table(["score", "experiment", "cell", "seed", "replay"],
                              [[f"{s:.2f}", t, cid, seed, f"`python -I docs/sim/tools/strategy_matrix.py replay {t if t != 'C_nofeat' else 'C_nofeat'} \"{cid}\" {seed}`"]
                               for s, t, cid, seed in rows]))
    if "C" in D:
        parts.append("\n## 3) The invasion matrix\n")
        txt, marked = invasion_tables(D["C"], D.get("C_recheck"))
        parts.append(txt)
    parts.append("\n## 4) Monocultures\n")
    for tag, label in (("A", "personalities"), ("B", "pure-strategy archetypes")):
        if tag in D:
            for n in (15, 9, 6, 25):
                if any(cid.endswith(f"|{n}") for cid in D[tag]["cells"]):
                    parts.append(mono_tables(D[tag]["cells"], n, f"4. {label}, {n} players (official rules)") + "\n")
    both = {}
    for tag in ("A", "B"):
        if tag in D:
            both.update(D[tag]["cells"])
    nof = {}
    for tag in ("A_nofeat", "B_nofeat"):
        if tag in D:
            nof.update(D[tag]["cells"])
    if nof:
        parts.append("### 4x. Same monocultures with events OFF and ranges/memory OFF (15 players)\n")
        parts.append(mono_tables(nof, 15, "personalities and archetypes, no events, no ranges"))
        # side by side deltas
        rows = []
        feat = {}
        for tag in ("A", "B"):
            if tag in D:
                feat.update(D[tag]["cells"])
        for t in TYPES:
            k = f"mono|{t}|15"
            if k in nof and k in feat:
                rows.append([t] + [f"{mval(feat[k], m):.1f} → {mval(nof[k], m):.1f}"
                                   for m in ("alive_end", "bandits_created", "steal_attempts", "gifts", "food_net", "unfilled")])
        parts.append("\nOfficial → no-features, same seeds:\n\n" + md_table(
            ["monoculture", "alive end", "bandits created", "steals tried", "gifts", "net food", "empty seats"], rows))
    if "C_nofeat" in D and "C" in D:
        parts.append("\n### 3x. Invasion matrix with events OFF and ranges/memory OFF\n")
        txt, _ = invasion_tables(D["C_nofeat"])
        parts.append(txt.replace("### 3", "### 3x."))
    if "D" in D:
        parts.append("\n## 5) Pairs and mixes\n")
        parts.append(pair_tables(D["D"])[0])
    if "E" in D:
        parts.append("\n## 6) Random compositions\n")
        parts.append(random_tables(D["E"])[0])
    if "F" in D:
        parts.append("\n## 7) Player-count sanity (office mix)\n")
        parts.append(count_table(D["F"]))
    parts.append(tail)
    path = os.path.join(RESULTS, "strategy_matrix.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))
    print("wrote", os.path.normpath(path))


def _seat_job(job):
    feat, seeds = job
    sp = spec(15, None, feat, feat)
    win, seat, rat, dead = [0.0] * 15, [0] * 15, [0] * 15, [0] * 15
    for sd in seeds:
        g = build(sp, sd)
        res = g.run()
        wins = {p.pid for p in res["winners"]}
        for p in g.players:
            win[p.pid] += (1 / len(wins)) if p.pid in wins else 0
            seat[p.pid] += p.extracted
            rat[p.pid] += p.rations
            dead[p.pid] += p.deaths
    return win, seat, rat, dead


def cmd_seatorder(a):
    """Does the seat number matter? Office mix, 15 players, results per seat (seeds 900001..)."""
    lower_priority()
    for feat, label, n in ((True, "official", a.games), (False, "events off, ranges off", a.games * 2 // 3)):
        jobs = [(feat, list(range(900001 + i, 900001 + min(i + 150, n)))) for i in range(0, n, 150)]
        W, S_, R, B = [0.0] * 15, [0] * 15, [0] * 15, [0] * 15
        with Pool(a.procs, initializer=lower_priority) as pool:
            for w, s_, r_, b in pool.imap_unordered(_seat_job, jobs):
                for i in range(15):
                    W[i] += w[i]; S_[i] += s_[i]; R[i] += r_[i]; B[i] += b[i]
        print(f"{label}: {n} games")
        print(" seat  win x   seat x  mean end rations  deaths/game")
        for i in range(15):
            print(f" {i:>3}  {W[i] / n * 15:.3f}  {S_[i] / n / (5 / 15):.3f}  {R[i] / n:.2f}   {B[i] / n:.3f}")


def cmd_ledger(a):
    """Where does a lone archetype's food come from? Ledger per game by reason, lone player among the office mix."""
    for x in a.types:
        sp = spec(15, ["lone", x, OFFICE], True, True)
        tot = {}
        for sd in range(1, a.games + 1):
            g = build(sp, sd)
            g.run()
            me = next(p for p in g.players if p.arch == x)
            for e in g.events:
                if e["type"] == "ration" and e["player"] == me.name:
                    tot[e["reason"]] = tot.get(e["reason"], 0) + e["delta"]
        print(x, {k: round(v / a.games, 2) for k, v in sorted(tot.items())}, "net", round(sum(tot.values()) / a.games, 2))


def cmd_bench(a):
    sp = spec(15, None, True, True)
    t0 = time.time()
    for s in range(1, 41):
        play(sp, s)
    print(f"events+ranges+log, 15 players: {(time.time() - t0) / 40 * 1000:.1f} ms/game")
    sp = spec(15, None, False, False)
    t0 = time.time()
    for s in range(1, 41):
        play(sp, s)
    print(f"no features,       15 players: {(time.time() - t0) / 40 * 1000:.1f} ms/game")
    for n in (4, 25):
        sp = spec(n, None, True, True)
        t0 = time.time()
        for s in range(1, 21):
            play(sp, s)
        print(f"events+ranges+log, {n} players: {(time.time() - t0) / 20 * 1000:.1f} ms/game")


def cmd_run(a):
    if a.exp == "E":
        cells = run_E(a)
        games = a.games
    else:
        cells, dg, _ = exp_cells(a.exp)
        games = a.games or dg
    if a.only:
        cells = {k: v for k, v in cells.items() if a.only in k}
    tag = a.tag or a.exp
    data, el = run_cells(cells, games, a.procs, tag)
    meta = dict(exp=a.exp, games=games, procs=a.procs, minutes=round(el / 60, 2),
                command=" ".join(["python -I docs/sim/tools/strategy_matrix.py"] + sys.argv[1:]))
    save(tag, data, meta)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bench")
    r = sub.add_parser("run")
    r.add_argument("exp")
    r.add_argument("--games", type=int, default=0)
    r.add_argument("--tables", type=int, default=400)
    r.add_argument("--procs", type=int, default=4)
    r.add_argument("--tag", default="")
    r.add_argument("--only", default="")
    rp = sub.add_parser("report")
    rp.add_argument("--head", default="")
    rp.add_argument("--tail", default="")
    rc = sub.add_parser("recheck")
    rc.add_argument("exp")
    rc.add_argument("--games", type=int, default=6000)
    rc.add_argument("--procs", type=int, default=4)
    rc.add_argument("--extreme", type=int, default=0)
    rc.add_argument("--borderline", type=int, default=0)
    so = sub.add_parser("seatorder")
    so.add_argument("--games", type=int, default=9000)
    so.add_argument("--procs", type=int, default=4)
    lg = sub.add_parser("ledger")
    lg.add_argument("types", nargs="+")
    lg.add_argument("--games", type=int, default=400)
    rl = sub.add_parser("replay")
    rl.add_argument("exp")
    rl.add_argument("cell")
    rl.add_argument("seed", type=int)
    rl.add_argument("--log", default="")
    a = ap.parse_args()
    if a.cmd == "bench":
        cmd_bench(a)
    elif a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "seatorder":
        cmd_seatorder(a)
    elif a.cmd == "ledger":
        cmd_ledger(a)
    elif a.cmd == "recheck":
        cmd_recheck(a)
    elif a.cmd == "replay":
        cmd_replay(a)
    else:
        main_report(a)


if __name__ == "__main__":
    main()
