"""docs/ARENA.md must say exactly what a live room does. Fails when the doc and the code disagree, in both directions.

Never edit this test to make it pass: fix the doc (or the code). Tables under `<!-- check:NAME -->` are compared with:
    settings          arena/room.py RoomSettings fields and defaults
    records           the record types arena/room.py writes (besides the core's)
    client-messages   the message types arena/server.py accepts
    server-messages   the message types arena/server.py and arena/views.py send
    limits            constants in arena/server.py
    refusals          every GameError text in arena/room.py and arena/server.py
"""
import ast
import dataclasses
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CORE_RECORDS = {"join", "start", "move", "quit", "radio", "night", "finish"}


def read(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def table(name):
    """Rows (lists of cells) of the table right under <!-- check:name --> in docs/ARENA.md."""
    text = read("docs/ARENA.md")
    m = re.search(rf"<!-- check:{re.escape(name)} -->\s*\n((?:\|.*\n)+)", text)
    if not m:
        raise AssertionError(f"docs/ARENA.md has no table under <!-- check:{name} -->")
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in m.group(1).strip().splitlines()]
    return rows[2:]                                   # skip header and the |---| line


def tick(cell):
    m = re.fullmatch(r"`(.*)`", cell.strip())
    return m.group(1) if m else cell.strip()


def string_of(node):
    """A string literal or f-string as text, with each {value} written as {name}."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                out.append(part.value)
            else:
                out.append("{" + ast.unparse(part.value) + "}")
        return "".join(out)
    return None


def game_errors(rel):
    out = set()
    for node in ast.walk(ast.parse(read(rel))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "GameError" and node.args:
            s = string_of(node.args[0])
            if s is not None:
                out.add(s)
    return out


class ArenaDoc(unittest.TestCase):
    def test_settings(self):
        from arena.room import RoomSettings
        code = {f.name: f.default for f in dataclasses.fields(RoomSettings)}
        doc = {tick(r[0]): ast.literal_eval(r[1]) for r in table("settings")}
        self.assertEqual(doc, code)

    def test_records(self):
        code = set(re.findall(r'"type": "(\w+)"', read("arena/room.py"))) - CORE_RECORDS
        doc = {tick(r[0]) for r in table("records")}
        self.assertEqual(doc, code)

    def test_client_messages(self):
        src = read("arena/server.py")
        code = set(re.findall(r'\bt == "(\w+)"', src)) | set(re.findall(r'msg\.get\("t"\) != "(\w+)"', src))
        doc = {tick(r[0]) for r in table("client-messages")}
        self.assertEqual(doc, code)

    def test_server_messages(self):
        code = set()
        for rel in ("arena/server.py", "arena/views.py"):
            code |= set(re.findall(r'"t": "(\w+)"', read(rel)))
        doc = {tick(r[0]) for r in table("server-messages")}
        self.assertEqual(doc, code)

    def test_limits(self):
        tree = ast.parse(read("arena/server.py"))
        consts = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if isinstance(node.targets[0], ast.Tuple):
                    for t, v in zip(node.targets[0].elts, node.value.elts):
                        consts[t.id] = ast.literal_eval(v)
                elif isinstance(node.targets[0], ast.Name):
                    try:
                        consts[node.targets[0].id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
        for r in table("limits"):
            with self.subTest(r[0]):
                self.assertEqual(consts.get(tick(r[0])), ast.literal_eval(r[1]))

    def test_refusals(self):
        code = game_errors("arena/room.py") | game_errors("arena/server.py")
        doc = {tick(r[0]) for r in table("refusals")}
        self.assertEqual(sorted(code - doc), [], "refusals in the code with no row in docs/ARENA.md")
        self.assertEqual(sorted(doc - code), [], "rows in docs/ARENA.md for refusals no longer in the code")


if __name__ == "__main__":
    unittest.main()
