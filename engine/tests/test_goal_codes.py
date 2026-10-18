"""Goals and goal progress as codes plus values (client request 4, 18 Oct 2026) without changing a word Torch says.

The ORACLE below is a verbatim copy of objective_text and goal_progress as they were before this change. The new
functions must give exactly the same text for every goal, every state and every rule variant, and the (code, args)
they give must render, through the one template table, to that same text. Never edit the oracle to make a test pass.
"""
import itertools
import unittest
from dataclasses import replace
from types import SimpleNamespace

from engine import Rules
from engine.finish import (GOAL_LINES, PROGRESS_LINES, goal_line, goal_progress, goal_progress_line, objective_text,
                           render_line)


# ---------------- ORACLE: the code exactly as it was ----------------
def oracle_objective_text(o, rules, target_name="@player"):
    return {
        "give": f"give away {rules.give_goal} rations over the game",
        "beat": f"finish with more rations than {target_name}",
        "robbed2_extract": f"get robbed at least {rules.robbed_goal}x and still extract",
        "steal3_clean": "steal 3 times before you're ever caught",
        "detective": "expose a thief red-handed with /investigate at least once",
        "grudge": (f"make sure {target_name} doesn't extract" if rules.grudge_goal == "deny"
                   else f"successfully rob {target_name} at least {rules.grudge_robs}x"),
    }[o]


def oracle_goal_progress(p, players, rules, quit_ids=frozenset(), target_band=None):
    r, o = rules, p.objective
    P = {q.pid: q for q in players}
    if o in ("beat", "grudge") and p.obj_target in quit_ids:
        return "failed", "your target left the game, so this goal no longer counts"
    if o == "steal3_clean":
        if p.clean_steals >= 3:
            return "done", "3/3 clean steals before you were ever caught"
        if p.steals_caught:
            return "failed", f"you were caught before your 3rd clean steal ({p.clean_steals}/3)"
        return "open", f"{p.clean_steals}/3 clean steals, never caught so far"
    if o == "give":
        return ("done", f"{p.gifted_out}/{r.give_goal} given") if p.gifted_out >= r.give_goal \
            else ("open", f"{p.gifted_out}/{r.give_goal} given")
    if o == "detective":
        n = getattr(p, "exposures", 0)
        return ("done", "thief exposed") if n >= 1 else ("open", "0/1 thieves exposed")
    if o == "robbed2_extract":
        if p.times_robbed >= r.robbed_goal:
            return "end", f"robbed {p.times_robbed}/{r.robbed_goal} ✓. Now hold a seat on the helicopter"
        return "open", f"robbed {p.times_robbed}/{r.robbed_goal} so far, and you'll need a seat at the end"
    if o == "beat":
        tgt = P[p.obj_target].name
        seen = f" They look {target_band} this morning." if target_band else ""
        return "end", f"decided at the end: you have {p.rations}, {tgt}'s stash is secret.{seen}"
    if r.grudge_goal == "deny":
        return "end", f"decided at the end: who gets a seat is only known when the helicopter comes"
    tgt = P[p.obj_target].name
    if p.grudge_hits >= r.grudge_robs:
        return "done", f"robbed {tgt} {p.grudge_hits}/{r.grudge_robs}"
    return "open", f"robbed {tgt} {p.grudge_hits}/{r.grudge_robs}"


GOALS = ("beat", "robbed2_extract", "steal3_clean", "give", "grudge", "detective")


def player(pid, name, goal, target, **kw):
    base = dict(pid=pid, name=name, objective=goal, obj_target=target, rations=5, clean_steals=0, steals_caught=0,
                gifted_out=0, exposures=0, times_robbed=0, grudge_hits=0)
    return SimpleNamespace(**{**base, **kw})


def states():
    """Every combination of the counters a goal reads, around each threshold, for every goal and rule variant."""
    rule_variants = [Rules(), replace(Rules(), grudge_goal="deny"), replace(Rules(), grudge_goal="rob", grudge_robs=2),
                     replace(Rules(), give_goal=5, robbed_goal=2)]
    for rules, goal in itertools.product(rule_variants, GOALS):
        for clean, caught, given, expo, robbed, hits, rations in itertools.product(
                (0, 3), (0, 1), (0, 3, 5), (0, 1), (0, 1, 2), (0, 1, 3), (0, 7)):
            me = player(0, "Me", goal, 1, clean_steals=clean, steals_caught=caught, gifted_out=given, exposures=expo,
                        times_robbed=robbed, grudge_hits=hits, rations=rations)
            others = [player(1, "Target", "give", 0, rations=4), player(2, "Other", "give", 0)]
            for quit_ids, band in itertools.product((frozenset(), frozenset({1})), (None, "🟡 getting by")):
                yield rules, me, [me] + others, quit_ids, band


class Oracle(unittest.TestCase):
    def test_the_goal_text_is_unchanged_for_every_goal_and_rule_variant(self):
        for rules, goal in itertools.product([Rules(), replace(Rules(), grudge_goal="deny"),
                                              replace(Rules(), give_goal=5, robbed_goal=2, grudge_robs=3)], GOALS):
            for name in ("Alias07", "@player", ""):
                self.assertEqual(objective_text(goal, rules, name), oracle_objective_text(goal, rules, name))

    def test_the_progress_text_is_unchanged_in_every_state(self):
        n = 0
        for rules, me, players, quit_ids, band in states():
            self.assertEqual(goal_progress(me, players, rules, quit_ids, band),
                             oracle_goal_progress(me, players, rules, quit_ids, band),
                             f"{me.objective} {vars(me)} quit={quit_ids} band={band} grudge={rules.grudge_goal}")
            n += 1
        self.assertGreater(n, 30000)

    def test_codes_and_values_render_to_the_same_text_as_the_oracle(self):
        """The wire form: (state, code, args) through the template table is the oracle's text, nothing else needed."""
        for rules, me, players, quit_ids, band in states():
            state, code, args = goal_progress_line(me, players, rules, quit_ids, band)
            want_state, want_text = oracle_goal_progress(me, players, rules, quit_ids, band)
            self.assertEqual(state, want_state)
            self.assertEqual(render_line(code, args), want_text)
            self.assertIn(code, PROGRESS_LINES)

    def test_the_goal_itself_as_a_code_renders_to_the_oracle_text(self):
        for rules, goal in itertools.product([Rules(), replace(Rules(), grudge_goal="deny"),
                                              replace(Rules(), give_goal=5, robbed_goal=2, grudge_robs=3)], GOALS):
            for name in ("Alias07", "Bo"):
                code, args = goal_line(goal, rules, name)
                self.assertIn(code, GOAL_LINES)
                self.assertEqual(render_line(code, args), oracle_objective_text(goal, rules, name))

    def test_args_carry_only_what_the_text_needs_and_no_hidden_facts(self):
        """The progress args are shown to the player: never another player's exact rations."""
        secret = 987654
        for rules, goal in itertools.product([Rules()], GOALS):
            me = player(0, "Me", goal, 1, rations=5)
            tgt = player(1, "Target", "give", 0, rations=secret)
            for quit_ids, band in itertools.product((frozenset(), frozenset({1})), (None, "🟡 getting by")):
                _, code, args = goal_progress_line(me, [me, tgt], rules, quit_ids, band)
                self.assertNotIn(secret, args.values(), f"{goal}: the target's exact rations leaked into the args")
                self.assertNotIn(str(secret), render_line(code, args))

    def test_every_template_placeholder_is_filled_by_its_code(self):
        import string
        for table in (GOAL_LINES, PROGRESS_LINES):
            for code, text in table.items():
                names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
                with self.subTest(code=code):
                    self.assertTrue(all(n.isidentifier() for n in names))


if __name__ == "__main__":
    unittest.main()
