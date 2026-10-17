"""Simulated colleagues for test games: who they are. How they play lives in bot/brain.py (the simulator's own AI).

A cast is dealt either balanced (one of each of the eight personalities before any repeats, see brain.balanced_pick)
or from the office mix (the simulator's weighted draw: a saint is only 8% of an office, so often missing).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "sim"))
from simbrain import OFFICE_MIX  # noqa: E402

from .brain import CASTS, balanced_pick  # noqa: E402,F401


def pick_personality(rng):
    return rng.choices(list(OFFICE_MIX), weights=list(OFFICE_MIX.values()))[0]
