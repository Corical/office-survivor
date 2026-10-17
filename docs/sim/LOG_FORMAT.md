# Survivors replay log format (version 1)

Everything that happens in a game is logged, so the whole game can be checked, replayed and animated afterwards. The simulator writes this format today (`python3 sim/survivors_sim.py reel --log game.jsonl`). The Discord bot must write the same format, so tools built on simulated games work unchanged on the real one.

## Rules

1. **JSON Lines:** one event per line, in order, append-only. Never edit or delete a line; a correction is a new event.
2. **Every event has** `seq` (1, 2, 3… with no gaps), `night` (0 = setup), `type`, and `visibility` (who could see it when it happened).
3. **Every change to anyone's rations is a `ration` event** with `delta`, `reason` and `balance` (the amount after). Adding them up must rebuild every player's rations exactly. `replay.py --check` enforces this.
4. **Each night ends with a `night_end` snapshot** of everyone's rations and status, so a replay can jump straight to any night.
5. **Players are named in events.** `game_start` lists every name with its id.
6. **The bot adds a `ts` timestamp** (ISO 8601, Africa/Johannesburg) to every event. The simulator has no clock and leaves it out.
7. **Randomness is logged.** The bot writes every roll as an `rng` event, so any outcome can be audited.

## Events the simulator writes

| type | When | Main fields | visibility |
| --- | --- | --- | --- |
| `game_start` | Setup | `seed`, `log_format`, `rules` (every rule value), `seats`, `players` (`id`, `name`, `start_rations`, plus `personality` and `smart` in the simulator) | public |
| `objective` | Setup, one per player | `player`, `objective`, `target`, `text` | private |
| `action` | Each night, one per player (final choice) | `player`, `action`, `target`, `amount`, `auto` (missed deadline), `as_bandit`, `rations_before`, `decided_by` (simulator brain), `decision` (Jev's pick and probability) | private |
| `guard_up` | A new guard is set | `player`, `until_night`, `guards_used` | private |
| `guard_wasted` | Guarding while already protected | `player`, `protected_until` | private |
| `steal` | Each theft attempt | `thief`, `target`, `outcome` (`success`, `empty` or `caught`), `amount`, `split_with`, `paid` (caught only: what the thief actually handed over) | victim sees the amount only; caught thieves are public |
| `scavenge` | Each scavenge | `player`, `found`, `auto` | private |
| `gift` | Each gift | `giver`, `receiver`, `amount` | giver and receiver |
| `investigate` | Each investigation | `investigator`, `target`, `saw_action`, `saw_target` | private |
| `exposed` | An investigation catches a thief | `thief`, `investigator`, `victim`, `paid` | public, without the investigator's name |
| `radio` | Each #radio post | `author`, `text`, `kind` (`accusation` or `rumour`), `true` | public, anonymous |
| `ration` | Every change to anyone's rations | `player`, `delta`, `reason`, `balance`, `detail` (who or why), `requested` (when a payment was capped by what they had) | private |
| `became_bandit` | Someone hits 0 | `player` | public |
| `rejoined` | A bandit gets back to the rejoin level | `player`, `rations` | public |
| `news_post` | The morning #news post | `channel`, `lines` | public |
| `night_end` | End of each night | `rations` (everyone), `bandits`, `guarded_until`, `guards_used` | Game Master only |
| `extraction` | After the last night | `seats`, `extracted`, `ranking`, `tiebreak`, `decided_by_coin_flip` | public |
| `result` | After the last night, one per player | `player`, `rations`, `survived`, `extracted`, `objective`, `objective_done`, `score`, `stole`, `steals_ok`, `steals_caught`, `times_robbed`, `gave_away` | public at the reveal |
| `game_end` | The very end | `winners`, `winner_tiebreak` | public |

Ration `reason` values: `robbed`, `stole`, `caught_penalty`, `guard_reward`, `fine`, `scavenge`, `guard_income`, `gift_out`, `gift_in`, `gift_bonus`, `bounty_paid`, `bounty_received`, `eat`, and (wilderness events, off by default) `event_found` and `event_lost`. Events also write an `event` line (`event`, `scope`, `player`).

**The books must balance.** Food is only created by `scavenge`, `guard_income`, `gift_bonus` and `event_found`, and only destroyed by `eat`, `fine` and `event_lost`. Every other reason is one side of a transfer between two players, so within a night those deltas must add up to exactly zero. A transfer moves only what the payer actually has, and the receiver gets exactly that. `check_invariants.py` enforces this on every logged game.

## Extra events only the bot writes

The real game has things the simulator doesn't, and all of them get logged:

| type | What |
| --- | --- |
| `player_joined`, `player_quit` | Opt-in and opt-out, with the Discord user id |
| `command` | Every slash command anyone runs, including `/status`, with its exact arguments |
| `action_changed` | Every change of mind before the deadline, with time (great replay material: "changed their mind four times, then stole") |
| `deadline_locked` | Actions locked for the night |
| `dm_sent` | The exact text of every private message the bot sends |
| `rng` | Every random roll: what it was for and the result |
| `event` | Random events (the apparition, lucky finds, rats, items, supply drops, storms): who, what, effect, private or public |
| `luck_change` | Changes to a player's luck across seasons, including beginner's luck |
| `admin` | Every Game Master action (pause, fix, radio-log read), with who did it |
| `chat_message` | #town-square messages, only if players are told up front that open chat is part of the replay |
| `season_start`, `season_end` | Season boundaries, for luck carry-over and titles |

## Tools

```
python3 sim/replay.py game.jsonl --check          rebuilds every ration from the ledger; fails if anything is missing
python3 sim/replay.py game.jsonl                  the whole story, night by night, including what was secret
python3 sim/replay.py game.jsonl --player QuietBadger  one person's story
python3 sim/replay.py game.jsonl --frames f.json  per-night state frames: the input for a replay animation
```

The frames file holds `players`, then one frame per night (each player's rations, bandit status, protection, action and target, plus that night's happenings and #news lines), then the ending and results. A season-recap animation can be built straight from it, using the same avatars, tins and icons as the explainer video.
