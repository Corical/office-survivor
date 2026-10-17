"""docs/MECHANICS.md must say exactly what the game does. This test fails when the doc and the game disagree.

Owner's rule (17 October 2026): the mechanics doc is the first point of reference, so every game change updates it
in the same commit. Never edit this test to make it pass: fix the doc (or the code).

How it works. Tables in the doc that sit right under a line `<!-- check:NAME -->` are parsed and compared with the
code:

    rules             every engine.Rules field and its default (a new field without a row fails)
    constants         numbers that are typed into the code (gift sizes, delays, limits...)
    seats             seats for every possible player count
    phases            the numbered phases of engine/resolve.py
    modes, events, variants       wilderness events (bot/game.py EVENT_MODES, engine/events.py)
    bands             engine/visibility.py band edges and labels
    goals             engine/deal.py GOALS and engine/finish.py objective_text wording
    radio             bot/game.py RADIO_PHRASES
    ledger            every ration "reason" the engine books, and whether it creates, destroys or moves food
    commands          every slash command in bot/discord_app.py, its options and its description
    reveal-columns, awards        bot/reveal_image.py
    hall-awards, hall-columns     bot/hall.py and bot/hall_image.py (the /gm hall-of-fame awards and picture)
    lines             player-facing text: each line's fixed words must still exist in the named source file, and
                      every refusal / news line / DM line in the code must have a row

It reads the working tree. Source files are read with `ast` (never imported) where importing would need Discord.
Limit: a ration reason built from a variable (not a string typed at the call) is only seen when a random game in
`_runtime_reasons` happens to book it; add the rule option to STRING_OPTIONS when a new one appears.
"""
import ast
import dataclasses
import json
import math
import os
import random
import re
import unittest
from collections import Counter

from engine import PlayerState, Rules, resolve_night
from engine import deal as deal_mod
from engine import events as wild
from engine import finish as finish_mod
from engine import moves as moves_mod
from engine import visibility as vis_mod

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC_REL = "docs/MECHANICS.md"
DOC_FIX = "Edit " + DOC_REL + " (and keep it that way: the doc is the first point of reference)."

# Rule options the random games try, so ration reasons that only appear under a non-default option are seen.
STRING_OPTIONS = {"exposure_undo": ("none", "split", "full"), "events_bias": ("random", "trailing", "top"),
                  "tiebreak": ("kindness", "coin"), "grudge_goal": ("rob", "deny")}


def read(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def S(x):
    """Text that is safe to print on any console (non-ASCII shown as escapes)."""
    x = str(x)
    return x if x.isascii() else ascii(x)[1:-1]


def parse_value(text):
    """A doc cell as a Python value: numbers, True/False, "strings", and simple fractions like 1/3."""
    text = text.strip()
    try:
        node = ast.parse(text, mode="eval").body
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return ast.literal_eval(node.left) / ast.literal_eval(node.right)
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return text


def same(a, b):
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return a == b


def cell(text):
    """A table cell without surrounding whitespace and one pair of backticks."""
    text = text.strip()
    if len(text) >= 2 and text[0] == "`" and text[-1] == "`" and text.count("`") == 2:
        return text[1:-1]
    return text


def kwargs(text, where):
    """`a=1, b="x"` -> {"a": 1, "b": "x"}; `-` or empty -> {}."""
    text = cell(text)
    if text in ("-", ""):
        return {}
    try:
        call = ast.parse(f"dict({text})", mode="eval").body
        return {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    except (SyntaxError, ValueError):
        raise AssertionError(f"{where}: cannot read '{S(text)}' as 'name=value, name=value' (or '-' for none).")


def render(node):
    """A string literal as text, with {} where an f-string has an expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(p.value if isinstance(p, ast.Constant) else "{}" for p in node.values)
    return None


def strings_in(node):
    """The message text(s) an expression can produce: a literal, an f-string, or either branch of `a if c else b`."""
    if isinstance(node, ast.IfExp):
        return strings_in(node.body) + strings_in(node.orelse)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):        # "text" + ("a" if x else "b")
        return [a + b for a in strings_in(node.left) for b in strings_in(node.right)]
    text = render(node)
    return [text] if text is not None else []


def norm(text):
    """Placeholders {anything} all become {}, so '{n}' in the doc matches '{e['x']}' in the code."""
    return re.sub(r"\{[^{}]*\}", "{}", text)


class MechanicsDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = read(DOC_REL)

    # ------------------------------------------------------------------ helpers
    def table(self, name, what):
        """Rows (dicts by header) of the table right under <!-- check:name -->."""
        m = re.search(rf"^<!-- check:{re.escape(name)} -->[ \t]*$", self.doc, re.M)
        if not m:
            self.fail(f"{DOC_REL} has no line '<!-- check:{name} -->'. Put it on its own line directly above the "
                      f"{what} table.")
        lines = []
        for line in self.doc[m.end():].lstrip("\n").split("\n"):
            if not line.startswith("|"):
                break
            lines.append(line)
        if len(lines) < 3:
            self.fail(f"{DOC_REL}: the {what} table under '<!-- check:{name} -->' is missing or empty.")
        split = lambda ln: [c.strip() for c in ln.strip()[1:-1].split("|")]      # noqa: E731
        head = split(lines[0])
        rows = []
        for ln in lines[2:]:
            cells = split(ln)
            if len(cells) != len(head):
                self.fail(f"{DOC_REL}: in the {what} table a row has {len(cells)} cells but the header has "
                          f"{len(head)} (a stray '|' inside a cell?): {S(ln[:100])}")
            rows.append(dict(zip(head, cells)))
        return rows

    def verdict(self, problems):
        if problems:
            self.fail("\n" + DOC_REL + " and the game disagree:\n  - " + "\n  - ".join(problems) + "\n" + DOC_FIX)

    def ast_assign(self, rel, name):
        """The literal value of a module-level `name = ...` in a source file (read, never imported)."""
        for node in ast.parse(read(rel)).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
        self.fail(f"Cannot find a plain `{name} = ...` in {rel}. The test reads it with ast; if it was moved or "
                  f"made dynamic, point this test at its new home.")

    def alias_pool_size(self):
        """How many distinct aliases Torch can hand out (bot/config.py: game.json lists, topped up from the sim)."""
        pres = json.loads(read("docs/game.json")).get("presentation", {})
        aliases = [a for k in ("alias_pool", "example_names") if isinstance(pres.get(k), list) for a in pres[k]]
        if len(aliases) < 20:
            aliases = list(dict.fromkeys(aliases + self.ast_assign("docs/sim/survivors_sim.py", "NAMES")))
        return len(dict.fromkeys(aliases))

    # ------------------------------------------------------------------ section 2: numbers
    def test_rules_table_has_every_rules_field_with_its_default(self):
        rows = self.table("rules", "Rules fields (section 2)")
        doc = {}
        for r in rows:
            doc[cell(r["Rules field"])] = parse_value(cell(r["Default"]))
        defaults = Rules()
        problems = []
        for f in dataclasses.fields(Rules):
            want = getattr(defaults, f.name)
            if f.name not in doc:
                problems.append(f"Rules has a field `{f.name}` (default {S(repr(want))}) with no row. Add to the "
                                f"check:rules table: | `{f.name}` | `{S(repr(want))}` | `{S(repr(want))}` (the live "
                                f"value from docs/game.json) | what it does |")
            elif not same(doc[f.name], want):
                problems.append(f"`{f.name}`: the doc says default {S(repr(doc[f.name]))} but engine/rules.py says "
                                f"{S(repr(want))}. Fix the Default cell (or the code).")
        for name in doc:
            if name not in {f.name for f in dataclasses.fields(Rules)}:
                problems.append(f"check:rules has a row for `{name}` but Rules has no such field. Delete the row.")
        self.verdict(problems)

    def test_live_column_is_what_the_game_really_plays_with(self):
        """docs/game.json is what Torch loads (bot/config.py): it overrides the defaults. The Live column says so."""
        game = json.loads(read("docs/game.json")).get("rules", {})
        defaults, names = Rules(), {f.name for f in dataclasses.fields(Rules)}
        doc = {cell(r["Rules field"]): parse_value(cell(r["Live"])) for r in self.table("rules", "Rules fields (section 2)")}
        problems = []
        for key in game:
            if key not in names:
                problems.append(f"docs/game.json rules.{key} is not a Rules field, so Torch ignores it. Remove it "
                                f"from game.json (or add the field to engine/rules.py).")
        for name in sorted(names):
            live = game[name] if name in game else getattr(defaults, name)
            if name in doc and not same(doc[name], live):
                where = "docs/game.json sets" if name in game else "no override in docs/game.json, so the default is"
                problems.append(f"`{name}`: the Live cell says {S(repr(doc[name]))} but {where} {S(repr(live))}. "
                                f"Fix the Live cell (the game plays with this value).")
        self.verdict(problems)

    def test_constants_typed_into_the_code(self):
        rows = self.table("constants", "constants (section 2)")
        pool = self.alias_pool_size()
        app, gamepy, finishpy = read("bot/discord_app.py"), read("bot/game.py"), read("engine/finish.py")

        def find(text, pattern, last=False, where=""):
            hits = re.findall(pattern, text)
            if not hits:
                self.fail(f"The test cannot find /{pattern}/ in {where}. The code was reworded: update the "
                          f"resolver for this constant in test_mechanics_doc.py.")
            if not last and len(set(hits)) > 1:
                self.fail(f"/{pattern}/ matches different values {sorted(set(hits))} in {where}: one number is "
                          f"typed in more than one place and they disagree. Make them agree, then update the doc.")
            return parse_value(hits[-1 if last else 0])

        ranges = set(re.findall(r"day_minutes: app_commands\.Range\[float, (\d+), (\d+)\] = ([\d.]+)", app))
        self.assertEqual(len(ranges), 1, f"bot/discord_app.py: /gm start and /gm pilot must declare the same "
                                         f"day_minutes Range[...] = default (found {sorted(ranges)}). Fix the code, "
                                         f"then the doc.")
        rng = ranges.pop()
        resolvers = {
            "KINDS": lambda: ", ".join(moves_mod.KINDS),
            "GIFT_MIN": lambda: moves_mod.GIFT_MIN,
            "GIFT_MAX": lambda: moves_mod.GIFT_MAX,
            "TRAILING_FAVOUR": lambda: wild.TRAILING_FAVOUR,
            "CLEAN_STEALS_NEEDED": lambda: find(finishpy, r"clean_steals >= (\d+)", where="engine/finish.py"),
            "MIN_PLAYERS_TO_START": lambda: find(gamepy, r"len\(self\.joined\) < (\d+)", where="bot/game.py"),
            "ALIAS_POOL_SIZE": lambda: pool,
            "REAL_DAY_HOURS": lambda: find(gamepy, r"day_seconds >= (\d+) \* 3600", where="bot/game.py"),
            "GM_DAY_MINUTES_MIN": lambda: parse_value(rng[0]),
            "GM_DAY_MINUTES_MAX": lambda: parse_value(rng[1]),
            "GM_DAY_MINUTES_DEFAULT": lambda: parse_value(rng[2]),
            "GM_PILOT_SIMS_DEFAULT": lambda: find(app, r"sims: app_commands\.Range\[int, 1, \d+\] = (\d+)",
                                                  where="bot/discord_app.py"),
            "FINAL_STRETCH": lambda: find(gamepy, r"FINAL_STRETCH = (\d+)", where="bot/game.py"),
            "HISTORY_ROWS_SHOWN": lambda: find(app, r"for r in rows\[:(\d+)\]", where="bot/discord_app.py"),
            "HALL_TOTALS": lambda: ", ".join(self.ast_assign("bot/hall.py", "TOTALS")),
            "GM_NEWS_DELAY_SECONDS": lambda: find(app, r"news_delay=(\d+)", where="bot/discord_app.py"),
            "GM_ADD_SIMS_MAX": lambda: find(app, r"count: app_commands\.Range\[int, 1, (\d+)\]",
                                            where="bot/discord_app.py"),
            "HEARTBEAT_SECONDS": lambda: find(app, r"asyncio\.sleep\((\d+)\)", last=True, where="bot/discord_app.py"),
            "PICKER_MAX_NAMES": lambda: 25 if 25 in {int(x) for x in re.findall(r"\[:(\d+)\]", app)} else None,
            "MESSAGE_CUT": lambda: 1990 if 1990 in {int(x) for x in re.findall(r"\[:(\d+)\]", app)} else None,
        }
        doc = {cell(r["Name"]): parse_value(cell(r["Value"])) for r in rows}
        problems = []
        for name, get in resolvers.items():
            have = get()
            if name not in doc:
                problems.append(f"The code has constant {name} = {S(repr(have))} but check:constants has no row. "
                                f"Add: | `{name}` | `{S(have)}` | what it is |")
            elif not same(doc[name], have):
                problems.append(f"{name}: the doc says {S(repr(doc[name]))} but the code has {S(repr(have))}. "
                                f"Fix the Value cell.")
        for name in doc:
            if name not in resolvers:
                problems.append(f"check:constants has a row `{name}` that the test does not know. Either delete the "
                                f"row or add a resolver for it in test_mechanics_doc.py.")
        self.verdict(problems)

    def test_seats_for_every_player_count(self):
        rows = self.table("seats", "seats by player count (section 1)")
        ratio = Rules().seat_ratio
        doc = {int(cell(r["Players"])): int(cell(r["Seats"])) for r in rows}
        problems = []
        for n in range(2, self.alias_pool_size() + 1):          # every head count the game can have
            want = max(1, round(n * ratio))
            if n not in doc:
                problems.append(f"No seats row for {n} players. Add: | {n} | {want} |")
            elif doc[n] != want:
                problems.append(f"{n} players: the doc says {doc[n]} seats but max(1, round({n} x seat_ratio)) is "
                                f"{want}. Fix the row.")
        self.verdict(problems)

    # ------------------------------------------------------------------ section 4: the night
    def test_phase_numbers_match_resolve_night(self):
        rows = self.table("phases", "night phases (section 4)")
        in_code = [int(n) for n in re.findall(r"^\s*# (\d+)\. ", read("engine/resolve.py"), re.M)]
        in_doc = [int(cell(r["Phase"])) for r in rows]
        self.verdict([] if in_code == in_doc else [
            f"engine/resolve.py has numbered phases {in_code} but the check:phases table has {in_doc}. Add, remove "
            f"or renumber rows (and rewrite the 'in detail' text for any phase that changed)."])

    # ------------------------------------------------------------------ section 5: events
    def test_event_modes(self):
        rows = self.table("modes", "event modes (section 5)")
        code = self.ast_assign("bot/game.py", "EVENT_MODES")
        doc = {cell(r["Mode"]): kwargs(r["Settings"], f"check:modes row {r['Mode']}") for r in rows}
        problems = []
        for mode, settings in code.items():
            if mode not in doc:
                problems.append(f"EVENT_MODES has mode `{mode}` ({S(settings)}) with no row in check:modes.")
            elif doc[mode] != settings:
                problems.append(f"Mode `{mode}`: the doc says {S(doc[mode])} but bot/game.py EVENT_MODES has "
                                f"{S(settings)}. Fix the Settings cell.")
        problems += [f"check:modes lists mode `{m}` that EVENT_MODES does not have." for m in doc if m not in code]
        choices = set(re.findall(r'Choice\(name="(\w+)", value="\1"\)', read("bot/discord_app.py")))
        if choices != set(code):
            problems.append(f"/gm start offers the events choices {sorted(choices)} but EVENT_MODES has "
                            f"{sorted(code)}. They must match, then fix the doc.")
        self.verdict(problems)

    def test_event_library(self):
        rows = self.table("events", "wilderness events (section 5)")
        gentle = Rules(**self.ast_assign("bot/game.py", "EVENT_MODES")["gentle"])
        weights = {e["id"]: wild._weight(e, gentle) for e in wild.EVENTS}
        total = sum(weights.values())
        doc = {cell(r["Event"]): r for r in rows}
        yn = lambda b: "yes" if b else "no"                                        # noqa: E731
        problems = []
        for e in wild.EVENTS:
            eid = e["id"]
            if eid not in doc:
                problems.append(f"engine/events.py has event `{eid}` with no row in check:events. Add: | `{eid}` | "
                                f"{e['scope']} | {yn(e['good'])} | {yn(e['public'])} | {e['weight']} | "
                                f"{weights[eid]:g} | {100 * weights[eid] / total:.1f}% | {e['effect']['op']} | "
                                f"`{', '.join(f'{k}={v!r}' for k, v in e['effect'].items() if k != 'op') or '-'}` | what happens |")
                continue
            r = doc[eid]
            params = {k: v for k, v in e["effect"].items() if k != "op"}
            checks = [("Scope", cell(r["Scope"]), e["scope"]), ("Lucky", cell(r["Lucky"]), yn(e["good"])),
                      ("Public", cell(r["Public"]), yn(e["public"])), ("Op", cell(r["Op"]), e["effect"]["op"])]
            for col, got, want in checks:
                if got != want:
                    problems.append(f"Event `{eid}`, column {col}: the doc says '{got}' but the code has '{want}'.")
            for col, got, want in (("Library weight", parse_value(cell(r["Library weight"])), e["weight"]),
                                   ("Gentle weight", parse_value(cell(r["Gentle weight"])), weights[eid])):
                if not same(got, want):
                    problems.append(f"Event `{eid}`, column {col}: the doc says {got} but the code has {want:g}.")
            chance = f"{100 * weights[eid] / total:.1f}%"
            if cell(r["Chance per draw (gentle)"]) != chance:
                problems.append(f"Event `{eid}`, column 'Chance per draw (gentle)': the doc says "
                                f"'{cell(r['Chance per draw (gentle)'])}' but weight {weights[eid]:g} of a total "
                                f"{total:g} is {chance}.")
            doc_params = kwargs(r["Parameters"], f"check:events row {eid}")
            if doc_params != params:
                problems.append(f"Event `{eid}`, column Parameters: the doc says {S(doc_params)} but the effect has "
                                f"{S(params)}.")
        problems += [f"check:events has a row `{x}` but engine/events.py has no such event. Delete it." for x in doc
                     if x not in weights]
        self.verdict(problems)

    def test_event_stories(self):
        rows = self.table("variants", "event story variants (section 5)")
        doc = {}
        for r in rows:
            doc.setdefault(cell(r["Event"]), []).append((cell(r["Emoji"]), cell(r["Text"])))
        problems = []
        for e in wild.EVENTS:
            want = list(wild.VARIANTS.get(e["id"]) or [(e["emoji"], e["text"])])
            have = doc.get(e["id"], [])
            if Counter(have) != Counter(want):
                missing = [w for w in want if w not in have]
                extra = [h for h in have if h not in want]
                problems.append(f"Event `{e['id']}` stories differ. Rows to add to check:variants: {S(missing)}. "
                                f"Rows to delete or fix: {S(extra)}. (Generate the table from engine/events.py "
                                f"VARIANTS: one row per telling: | `id` | emoji | `text` |)")
        problems += [f"check:variants has rows for `{x}` which is not an event." for x in doc
                     if x not in {e['id'] for e in wild.EVENTS}]
        self.verdict(problems)

    # ------------------------------------------------------------------ section 6: ranges
    def test_ration_bands(self):
        rows = self.table("bands", "ration bands (section 6)")
        labels = tuple(cell(r["Label"]) for r in rows)
        edges = tuple(parse_value(cell(r["Lowest rations in the band"])) for r in rows[:-1])
        problems = []
        if labels != tuple(vis_mod.BAND_LABELS):
            problems.append(f"Band labels: the doc has {S(labels)} but engine/visibility.py BAND_LABELS is "
                            f"{S(tuple(vis_mod.BAND_LABELS))}. Fix the Label cells (one row per label, richest first, "
                            f"bandit last).")
        if edges != tuple(vis_mod.BAND_EDGES):
            problems.append(f"Band edges: the doc has {edges} but BAND_EDGES is {tuple(vis_mod.BAND_EDGES)}. Fix the "
                            f"'Lowest rations in the band' cells; the bandit row says `-`.")
        if cell(rows[-1]["Lowest rations in the band"]) != "-":
            problems.append("The last bands row (bandit) must say `-` for its lowest rations.")
        self.verdict(problems)

    # ------------------------------------------------------------------ section 7: goals
    def test_goals(self):
        rows = self.table("goals", "secret goals (section 7)")
        doc = {cell(r["Goal id"]): r for r in rows}
        rules = Rules()
        problems = []
        for goal in deal_mod.GOALS:
            try:
                want = finish_mod.objective_text(goal, rules, "@player")
            except KeyError:
                problems.append(f"engine/deal.py GOALS has `{goal}` but engine/finish.py objective_text has no "
                                f"wording for it (the game would crash at /status). Fix the code first.")
                continue
            if goal not in doc:
                problems.append(f"engine/deal.py GOALS has `{goal}` with no row in check:goals. Add: | `{goal}` | "
                                f"{'yes' if goal in deal_mod.TARGETED else 'no'} | `{want}` | done when... |")
                continue
            r = doc[goal]
            if cell(r["Exact wording (placeholder @player)"]) != want:
                problems.append(f"Goal `{goal}` wording: the doc says '{S(cell(r['Exact wording (placeholder @player)']))}'"
                                f" but objective_text says '{S(want)}'.")
            hunter = "yes" if goal in deal_mod.TARGETED else "no"
            if cell(r["Has a target"]) != hunter:
                problems.append(f"Goal `{goal}`: 'Has a target' should be {hunter} (engine/deal.py TARGETED).")
        problems += [f"check:goals has `{g}` which engine/deal.py GOALS does not have." for g in doc
                     if g not in deal_mod.GOALS]
        self.verdict(problems)

    # ------------------------------------------------------------------ section 9: what players see
    def test_radio_phrases(self):
        rows = self.table("radio", "radio phrases (section 9)")
        code = self.ast_assign("bot/game.py", "RADIO_PHRASES")
        doc = {cell(r["Key"]): cell(r["Line"]) for r in rows}
        problems = []
        for key, text in code.items():
            if key not in doc:
                problems.append(f"RADIO_PHRASES has `{key}` ('{S(text)}') with no row. Add: | `{key}` | `{S(text)}` |")
            elif doc[key] != text:
                problems.append(f"Radio `{key}`: the doc says '{S(doc[key])}' but the code says '{S(text)}'.")
        problems += [f"check:radio has `{k}` which RADIO_PHRASES does not have. Delete it." for k in doc
                     if k not in code]
        self.verdict(problems)

    def test_slash_commands(self):
        rows = self.table("commands", "slash commands (section 9)")
        code = {}
        for node in ast.walk(ast.parse(read("bot/discord_app.py"))):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in node.decorator_list:
                if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "command"
                        and isinstance(d.func.value, ast.Name) and d.func.value.id in ("tree", "gm")):
                    kw = {k.arg: ast.literal_eval(k.value) for k in d.keywords if k.arg in ("name", "description")}
                    name = ("/gm " if d.func.value.id == "gm" else "/") + kw.get("name", node.name)
                    code[name] = ([a.arg for a in node.args.args[1:]], kw.get("description", ""))
        doc = {cell(r["Command"]): r for r in rows}
        problems = []
        for name, (opts, desc) in code.items():
            if name not in doc:
                problems.append(f"bot/discord_app.py has the command `{name}` with no row in check:commands. Add: | "
                                f"`{name}` | `{', '.join(opts) or '-'}` | {S(desc)} | who |")
                continue
            r = doc[name]
            doc_opts = [] if cell(r["Options"]) == "-" else [o.strip() for o in cell(r["Options"]).split(",")]
            if doc_opts != opts:
                problems.append(f"`{name}` options: the doc says {doc_opts} but the code has {opts}.")
            if r["Description (as players see it)"] != desc:
                problems.append(f"`{name}` description: the doc says '{S(r['Description (as players see it)'])}' but the "
                                f"code says '{S(desc)}'.")
        problems += [f"check:commands lists `{n}` which bot/discord_app.py does not define. Delete the row."
                     for n in doc if n not in code]
        self.verdict(problems)

    def test_reveal_picture(self):
        cols = self.ast_assign("bot/reveal_image.py", "COLUMNS")
        awards = self.ast_assign("bot/reveal_image.py", "AWARDS")
        got_cols = [(cell(r["Column"]), cell(r["Key"]), cell(r["Top of the column highlighted"]) == "yes")
                    for r in self.table("reveal-columns", "reveal picture columns (section 8)")]
        want_cols = [(h, k, bool(hi)) for h, k, _num, hi in cols]
        got_awards = [(cell(r["Award"]), cell(r["Emoji"]), cell(r["Stat key"]))
                      for r in self.table("awards", "reveal award cards (section 8)")]
        want_awards = [(title, emoji, key) for emoji, title, key in awards]
        problems = []
        if got_cols != want_cols:
            problems.append(f"Reveal columns: the doc has {S(got_cols)} but bot/reveal_image.py COLUMNS gives "
                            f"{S(want_cols)} (header, key, highlighted).")
        if got_awards != want_awards:
            problems.append(f"Reveal awards: the doc has {S(got_awards)} but bot/reveal_image.py AWARDS gives "
                            f"{S(want_awards)} (title, emoji, key).")
        self.verdict(problems)

    def test_hall_of_fame_awards(self):
        got = [(cell(r["Award"]), cell(r["Emoji"]), cell(r["Meaning"]), cell(r["Stat"]))
               for r in self.table("hall-awards", "Hall of Fame awards (section 9)")]
        want = [(title, emoji, meaning, field) for emoji, title, meaning, field in
                self.ast_assign("bot/hall.py", "AWARDS")]
        self.verdict([] if got == want else [
            f"Hall of Fame awards: the doc has {S(got)} but bot/hall.py AWARDS gives {S(want)} (title, emoji, "
            f"meaning, stat). One row per award, in this order."])

    def test_hall_of_fame_picture_columns(self):
        got = [(cell(r["Column"]), cell(r["Key"]), cell(r["Top of the column highlighted"]) == "yes")
               for r in self.table("hall-columns", "Hall of Fame picture columns (section 9)")]
        want = [(head, key, bool(numeric) and key != "games")
                for head, key, numeric in self.ast_assign("bot/hall_image.py", "COLUMNS")]
        self.verdict([] if got == want else [
            f"Hall of Fame picture columns: the doc has {S(got)} but bot/hall_image.py COLUMNS gives {S(want)} "
            f"(header, key, top highlighted: every numeric column except games)."])

    # ------------------------------------------------------------------ player-facing lines
    def test_every_documented_line_still_exists_and_every_message_is_documented(self):
        rows = self.table("lines", "player-facing lines (section 9)")
        literals = {}                                           # file -> set of normalised string literals
        problems = []

        def literals_of(rel):
            if rel not in literals:
                out = set()
                for node in ast.walk(ast.parse(read(rel))):
                    text = render(node)
                    if text is not None:
                        out.add(norm(text))
                    elif isinstance(node, (ast.BinOp, ast.IfExp)):         # "a" + ("b" if x else "c")
                        out.update(norm(t) for t in strings_in(node))
                literals[rel] = out
            return literals[rel]

        documented = []
        for r in rows:
            line, rel = norm(cell(r["Line"])), cell(r["File"])
            documented.append(line)
            if not os.path.exists(os.path.join(ROOT, *rel.split("/"))):
                problems.append(f"check:lines row '{S(line)}' names the file {rel}, which does not exist.")
            elif not any(line in lit for lit in literals_of(rel)):
                problems.append(f"The line '{S(cell(r['Line']))}' (where: {r['Where']}) is no longer in {rel}. "
                                f"Update the row to the new wording, or delete it if the line is gone.")
        # the other way round: every refusal and every news / DM line typed in the code needs a row
        found = []
        game_tree = ast.parse(read("bot/game.py"))
        for node in ast.walk(game_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "endgame_note":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        found += [(t, "bot/game.py endgame_note") for t in strings_in(sub.value)]
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "GameError"
                    and node.args):
                found += [(t, "bot/game.py GameError") for t in strings_in(node.args[0])]
            if isinstance(node, ast.FunctionDef) and node.name in ("news_lines", "private_lines"):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr in ("append", "insert") and sub.args):
                        found += [(t, f"bot/game.py {node.name}") for t in strings_in(sub.args[-1])]
        for node in ast.walk(ast.parse(read("engine/moves.py"))):
            if isinstance(node, ast.FunctionDef) and node.name == "validate":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        found += [(t, "engine/moves.py validate") for t in strings_in(sub.value)]
        for text, origin in found:
            n = norm(text)
            if len(n.strip()) < 8 or n.strip("{} ") == "":
                continue
            if n not in documented:
                problems.append(f"{origin} can say '{S(text)}' ({{}} = a value filled in) and no row in check:lines "
                                f"covers it. Add a row: | where | who sees it | `the line, with the values written "
                                f"as {{name}}` | `{origin.split()[0]}` |")
        self.verdict(problems)

    # ------------------------------------------------------------------ section 10: the ledger
    def test_ledger_reasons(self):
        rows = self.table("ledger", "ration ledger reasons (section 10)")
        doc = {cell(r["Reason"]): cell(r["Effect on the food supply"]) for r in rows}
        created = set(self.ast_assign("docs/sim/check_invariants.py", "CREATE"))
        destroyed = set(self.ast_assign("docs/sim/check_invariants.py", "DESTROY"))
        static, runtime = _static_reasons(), _runtime_reasons()
        code = static | runtime
        problems = []
        for reason in sorted(code):
            effect = "creates" if reason in created else "destroys" if reason in destroyed else "transfer"
            verb = {"creates": "creates", "destroys": "destroys", "transfer": "only moves"}[effect]
            seen = "typed in the code" if reason in static else "booked in a random game"
            if reason not in doc:
                problems.append(f"The engine books the ration reason `{reason}` ({seen}; it {verb} food) with no "
                                f"row. Add to check:ledger: | `{reason}` | {effect} | phase | notes |")
            elif doc[reason] != effect:
                problems.append(f"Ledger `{reason}`: the doc says '{doc[reason]}' but check_invariants.py "
                                f"CREATE/DESTROY says it {verb} food ('{effect}'). Fix the row (or the sets).")
        problems += [f"check:ledger has `{r}` but no code books that reason. Delete the row." for r in doc
                     if r not in code]
        if (created | destroyed) - code:
            problems.append(f"docs/sim/check_invariants.py lists reasons the engine never books: "
                            f"{sorted((created | destroyed) - code)}.")
        self.verdict(problems)

    def test_every_check_marker_in_the_doc_is_tested(self):
        known = {"seats", "rules", "constants", "phases", "modes", "events", "variants", "bands", "goals", "radio",
                 "commands", "reveal-columns", "awards", "hall-awards", "hall-columns", "lines", "ledger"}
        used = set(re.findall(r"^<!-- check:([\w-]+) -->", self.doc, re.M))
        self.verdict([f"The doc has '<!-- check:{u} -->' but no test reads it. Rename it or add a test."
                      for u in sorted(used - known)]
                     + [f"This test expects '<!-- check:{k} -->' in the doc and it is gone. Put it back above its "
                        f"table (a table with no marker is not checked)." for k in sorted(known - used)])


# ---------------------------------------------------------------------- ledger scanning
def _static_reasons():
    """Reasons typed as string literals at ledger(...), move(...) and _book(...) calls in the engine."""
    where = {"ledger": (2,), "move": (3, 4), "_book": (3,)}
    out = set()
    for rel in ("engine/resolve.py", "engine/events.py"):
        for node in ast.walk(ast.parse(read(rel))):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            for i in where.get(name, ()):
                if i < len(node.args) and isinstance(node.args[i], ast.Constant) and isinstance(node.args[i].value, str):
                    out.add(node.args[i].value)
    return out


class _P(PlayerState):
    idol = False            # Torch's PlayerState has no `idol`; the simulator's players do, and the event reads it


class _Camp:
    """What engine/events.py needs from a game."""

    def __init__(self, players, rules, night, seed, book):
        self.players, self.r, self.night, self.seed = players, rules, night, seed
        self.event_tally = Counter()
        self.L = lambda *a, **k: None
        self.ledger = lambda p, delta, reason, balance, detail="": book(reason)


def _runtime_reasons():
    """Every ration reason booked while playing random nights under several rule sets (events included)."""
    names = {f.name for f in dataclasses.fields(Rules)}
    variants = [Rules(), Rules(caught_penalty=3, guard_reward=1, guard_income_max=1, gift_bonus=1, guard_cooldown=1),
                Rules(events_per_night=3.0, events_bias="trailing", events_raid=1.0),
                Rules(events_per_night=2.0, events_bias="top", events_rats_relative=True)]
    for field, options in STRING_OPTIONS.items():
        if field in names:
            variants += [Rules(**{field: o}) for o in options]
    seen, rng = set(), random.Random(20261017)
    book = seen.add
    for rules in variants:
        for night in range(1, 70):
            players = [_P(pid=i, name=f"P{i}", rations=rng.randint(0, 9)) for i in range(rng.randint(4, 9))]
            for p in players:
                p.bandit = p.rations == 0 or rng.random() < 0.15
                p.guard_until = night + rng.choice([-2, -1, 0, 1])
                p.guards_used = rng.randint(0, 2)
            flags = frozenset()
            if rules.events_per_night > 0:
                camp = _Camp(players, rules, night, "doc-test", book)
                flags, _ = wild.run_night_events(camp, wild.rng_for("doc-test", night))
            moves = {}
            for p in players:
                legal = moves_mod.legal_moves(players, p.pid, rules, night)
                amounts = legal.pop("gift_amounts", [])
                kind = rng.choice(sorted(legal))
                target = rng.choice(legal[kind]) if legal[kind] else None
                moves[p.pid] = (kind, target, rng.choice(amounts) if kind == "gift" else 0, False)
            resolve_night(players, moves, rules, random.Random(rng.random()), night,
                          emit=lambda t, **f: book(f["reason"]) if t == "ration" else None, flags=flags)
    return seen


if __name__ == "__main__":
    unittest.main()
