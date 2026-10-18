"""Drift check: the Godot adapter's lists against the server's own definitions.

    cd <repo root> && python godot/tools/check_drift.py

Compares, by value: move kinds, goal codes, ration bands, radio phrase keys, the protocol number and the line-code
table (arena/lines_en.json vs the copy in godot/rulesets/survivors/). Exits 1 on any difference. This is the check
that fails loudly when the server adds a move, a goal or a band and the client has not caught up.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.getcwd())

from arena import views  # noqa: E402
from bot.core import RADIO_PHRASES  # noqa: E402
from engine.deal import GOALS  # noqa: E402
from engine.moves import KINDS  # noqa: E402

ADAPTER = os.path.join("godot", "rulesets", "survivors", "adapter.gd")
COPY = os.path.join("godot", "rulesets", "survivors", "lines_en.json")
SERVER_LINES = os.path.join("arena", "lines_en.json")


def gd_list(src, name):
    m = re.search(r"const %s := \[(.*?)\]" % name, src, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else None


def main():
    src = open(ADAPTER, encoding="utf-8").read()
    checks = [
        ("MOVES", gd_list(src, "MOVES"), list(KINDS)),
        ("GOALS", gd_list(src, "GOALS"), list(GOALS)),
        ("BANDS", gd_list(src, "BANDS"), list(views.BANDS)),
        ("RADIO", gd_list(src, "RADIO"), list(RADIO_PHRASES)),
    ]
    bad = 0
    for name, client, server in checks:
        same = client is not None and sorted(client) == sorted(server)
        print("%-6s %s" % (name, "ok" if same else "DIFFERENT: client=%s server=%s" % (client, server)))
        bad += not same
    a = json.load(open(COPY, encoding="utf-8"))
    b = json.load(open(SERVER_LINES, encoding="utf-8"))
    same = a == b
    print("LINES  %s" % ("ok (%d codes)" % len(b) if same else "DIFFERENT: only client=%s only server=%s" % (
        sorted(set(a) - set(b)), sorted(set(b) - set(a)))))
    bad += not same
    proto = re.search(r"const PROTO := (\d+)", open(os.path.join("godot", "autoload", "net.gd"), encoding="utf-8").read())
    same = proto is not None and int(proto.group(1)) == views.PROTO
    print("PROTO  %s" % ("ok (%d)" % views.PROTO if same else "DIFFERENT: client=%s server=%d" % (
        proto.group(1) if proto else None, views.PROTO)))
    bad += not same
    print("\ndrift:", "NONE" if not bad else "%d difference(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
