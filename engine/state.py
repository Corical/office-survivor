"""What the game itself knows about a player. Anything that only steers simulated players lives in the simulator."""
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class PlayerState:
    pid: int
    name: str
    rations: int
    objective: str = ""
    obj_target: int = -1
    bandit: bool = False
    ever_bandit: bool = False
    robbed_last: bool = False
    guard_until: int = 0
    guards_used: int = 0
    next_guard_night: int = 0
    # counted facts used by objectives, tiebreaks and the reveal
    times_robbed: int = 0
    steals_ok: int = 0
    steals_caught: int = 0
    clean_steals: int = 0          # successful steals before the first catch (the clean-thief goal counts these)
    idol: bool = False             # a wilderness-event shield: the next theft against this player fails
    rations_stolen: int = 0
    gifted_out: int = 0
    grudge_hits: int = 0
    deaths: int = 0
    comebacks: int = 0
    died_unrobbed: int = 0
    missed: int = 0
    exposures: int = 0                 # thieves this player exposed with investigate (the Detective goal)
    actions: Counter = field(default_factory=Counter)
