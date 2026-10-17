"""The game's rule knobs. Values come from game.json's "rules" block; the defaults are the v2 rules doc."""
from dataclasses import dataclass


@dataclass
class Rules:
    """Defaults = the rules doc as currently written (v2, tuned 16 Oct 2026)."""
    players: int = 15
    rounds: int = 10              # weekday nights
    start_rations: int = 7
    eat: int = 1                  # cost per night for survivors
    scavenge_min: int = 0
    scavenge_max: int = 2
    steal_amount: int = 2
    caught_penalty: int = 2       # a thief caught by a guard loses this
    guard_reward: int = 2         # a guard gains this per thief caught
    guard_income_max: int = 0     # guards still scavenge 0..this
    guard_nights: int = 2         # a guard stays up for this many nights
    guard_limit: int = 3          # max guards per player per game (0 = unlimited)
    guard_cooldown: int = 0       # nights you must wait after a guard ends before guarding again
    missed_scavenge_max: int = -1 # missed deadline scavenges 0..this (-1 = same as a normal scavenge)
    investigate_bounty: int = 1   # catching a thief by investigation exposes them and they pay this
    exposure_undo: str = "none"   # what an exposure does to the theft itself: "none" (the theft stands, today),
                                  # "split" (loot taken back from the thief: half to the victim, rounded UP, the rest
                                  # to the investigator) or "full" (all the loot back to the victim). Either way the
                                  # thief also pays investigate_bounty, loot first, then the bounty, from what they hold
    investigate_find: int = 0     # an investigator also finds 0..this new rations (uniform) in phase 6; 0 = off, no dice drawn
    gift_bonus: int = 0          # extra rations the receiver gets on top of each gift
    winner_tiebreak: str = "kindness"  # tied top scores: "none" (shared win), "rations", or "kindness"
    tiebreak: str = "kindness"    # last-seat ties: "coin" or "kindness" (most given away, then fewest caught)
    give_goal: int = 3            # threshold for the give-away objective
    grudge_goal: str = "rob"      # "deny" (@player doesn't extract) or "rob" (rob @player N times)
    grudge_robs: int = 1          # N for the "rob" grudge objective
    robbed_goal: int = 1          # times robbed for the robbed-and-extract objective
    bandit_steal_amount: int = 1
    bandit_rejoin: int = 3        # a bandit with this many rations rejoins
    bandit_can_extract: bool = False
    seat_ratio: float = 1 / 3     # extraction seats as a share of players
    miss_scale: float = 1.0       # multiplies everyone's chance of missing the deadline
    pts_extract: int = 3
    pts_objective: int = 2
    pts_survive: int = 1
    # wilderness events (prototype, simulator only; 0 = off, and then nothing below is read)
    events_per_night: float = 0.0  # average events per night, camp-wide
    events_bias: str = "random"    # "random", "trailing" (good events lean below the median, bad above), or
                                   # "top" (bad player-events only hit the top third, good ones only the bottom third)
    events_raid: float = 0.0       # how many times its library weight the "raid" event is drawn (0 = no raids)
    events_rats_relative: bool = False  # rats tax everyone within 1 of the richest, instead of a fixed 7 or more

    def __post_init__(self):
        if self.exposure_undo not in EXPOSURE_UNDO:      # a typo must not silently mean "none"
            raise ValueError(f"exposure_undo must be one of {EXPOSURE_UNDO}, not {self.exposure_undo!r}")


EXPOSURE_UNDO = ("none", "split", "full")
