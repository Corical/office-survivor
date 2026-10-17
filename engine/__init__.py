"""The Survivors game engine: rules, player facts and the night resolution. No I/O; shared by the simulator and Torch."""
from .resolve import NightResult, Observer, resolve_night
from .rules import Rules
from .state import PlayerState

ENGINE_VERSION = "1"

__all__ = ["ENGINE_VERSION", "NightResult", "Observer", "PlayerState", "Rules", "resolve_night"]
