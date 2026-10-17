"""Mutation check: break the engine on purpose and confirm the tests notice. Restores the file afterwards.

    python engine/tests/mutants.py
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET = os.path.join(ROOT, "engine", "resolve.py")
MUTANTS = [
    ("arrival order", "    moves = dict(sorted(moves.items()))", "    moves = dict(moves)"),
    ("loot stealable again", "    can_lose = dict(bal)", "    can_lose = bal"),
    ("gift takes the last ration", "amt = min(a[2], max(0, giver.rations - 1))", "amt = min(a[2], giver.rations)"),
    ("caught thief overpays", "can_pay = min(r.caught_penalty, bal[th])", "can_pay = r.caught_penalty"),
    ("bandit eats", "        if not p.bandit:\n            before = p.rations", "        if True:\n            before = p.rations"),
]

original = open(TARGET, encoding="utf-8").read()
backup = TARGET + ".bak"
shutil.copy2(TARGET, backup)
survived = []
try:
    for name, old, new in MUTANTS:
        if original.count(old) != 1:
            sys.exit(f"mutant '{name}': pattern not found exactly once")
        open(TARGET, "w", encoding="utf-8").write(original.replace(old, new))
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "engine/tests", "-t", "."],
                           cwd=ROOT, capture_output=True, text=True)
        caught = r.returncode != 0
        print(f"{'caught  ' if caught else 'SURVIVED'} {name}")
        if not caught:
            survived.append(name)
finally:
    shutil.copy2(backup, TARGET)
    os.remove(backup)
sys.exit(1 if survived else 0)
