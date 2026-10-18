# Survivors: how the game works

**This is the first point of reference for every question about how the game works.** Read it before the code. Go to the code only to change the game, or when this file does not answer (then add the answer here).

Last checked against the code: 17 October 2026, at commit 4ecdb0f. It describes the game Torch plays (the code in `engine/` and `bot/`). The older files `docs/docs/rules.md` and `docs/HANDOVER.md` are design history: where they disagree with this file, this file is right.

**The rule:** every change to game behaviour (rules, numbers, goals, events, ranges, messages, commands, phase order, scoring) updates this file in the same commit. `engine/tests/test_mechanics_doc.py` fails when this file and the game disagree.

**Live rooms (the Godot client)** play these same rules; what a room adds (4 seats, timed rounds, lock-in, early advance, reconnects, the protocol) is in `docs/ARENA.md`, kept true by `arena/tests/test_arena_doc.py`.

## How this file is checked

Tables that follow a line like `<!-- check:rules -->` are read by the test. The first column or the backticked cells must match the code exactly. If you add a Rules field, a goal, an event, a radio phrase, a ledger reason, a command or a player-facing line, the test names the table and the row to add. Prose is not checked, so keep it short and keep it true.

## Contents

1. Setup
2. The numbers
3. Moves and what is allowed
4. The night, phase by phase
5. Wilderness events
6. Morning ration ranges
7. Secret goals
8. Scoring and the end
9. What players see
10. The ration ledger
11. Known problems and quirks
12. Change log

## 1. Setup

### Players and aliases

| Fact | How it works |
| --- | --- |
| Joining | `/join` before the game starts. After the start, joining is closed ("The game has already started; joining is closed."). |
| Minimum to start | The Game Master can only start with at least `MIN_PLAYERS_TO_START` players (see constants). |
| Maximum | One player per alias in the pool. The pool is the four example names in `docs/game.json` plus the simulator's name list, without repeats: `ALIAS_POOL_SIZE` names. When all are taken: "The game is full." |
| Alias | Torch picks a random free alias for you. You never choose it. A new season avoids every alias used in the newest archived season (so nobody is handed last game's name and mistakes it for their own); those names are used only if no other is free. |
| Why aliases (owner decision 17) | Betrayals cannot be pinned on a person. Torch assigns the names because a familiar handle would give its owner away. Everything public (#news, #radio, the reveal) uses aliases only. The link from Discord account to alias is kept in a separate file (`identity.json`), never in the game log. |
| Real names | Nothing official ever confirms who an alias is during a season. #town-square is normal chat where people may say what they like. After a season has ended, the Game Master can see who played which alias (`/gm history`, `/gm hall-of-fame`, section 9). Never during a game. |

### Start

`/gm start` (Game Master only) deals the secret goals and gives everyone `start_rations` rations. The game then runs on its own clock. The Game Master chooses:

| Option | Values | Default |
| --- | --- | --- |
| `day_minutes` | 1 to 1440 (`GM_DAY_MINUTES_MIN` to `GM_DAY_MINUTES_MAX`) | 5 (`GM_DAY_MINUTES_DEFAULT`) |
| `events` | `off` or `gentle` (section 5) | `off` |
| `ranges` | on or off (section 6) | off |

Start announcements: #news gets "The game has begun" (with extra sentences when events or ranges are on). Every human player gets a DM. Simulated colleagues get nothing.

**Rules are frozen at the start.** The rules in force (section 2, "Live" column) are written into the start record. A running game is played, and replayed after a restart, under those rules, never under today's file. Changing `docs/game.json` only affects games started afterwards. A rule field that is newer than the saved game takes its default for that game.

### The one-step pilot

`/gm pilot` (Game Master only) does it all at once: archives the last season if it was started (a running game needs `confirm: True`, and is archived unfinished), makes you join, adds simulated colleagues, and starts the game.

| Option | Values | Default |
| --- | --- | --- |
| `sims` | 1 to `GM_ADD_SIMS_MAX` | 8 (`GM_PILOT_SIMS_DEFAULT`) |
| `day_minutes` | as for `/gm start` | 5 |
| `events` | `gentle` or `off` | `gentle` |
| `ranges` | on or off | on |
| `confirm` | needed only if a game is still running | off |
| `cast` | `balanced` or `office` (see "Simulated colleagues") | `balanced` |

Note the defaults differ from `/gm start` (events and ranges are on here). A season that has not started keeps whoever already joined.

### Seats

Seats on the helicopter = `max(1, round(players x seat_ratio))`. "Players" means everyone dealt in at the start, including anyone who later quit. With `seat_ratio` = 1/3:

<!-- check:seats -->
| Players | Seats |
| --- | --- |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 3 |
| 9 | 3 |
| 10 | 3 |
| 11 | 4 |
| 12 | 4 |
| 13 | 4 |
| 14 | 5 |
| 15 | 5 |
| 16 | 5 |
| 17 | 6 |
| 18 | 6 |
| 19 | 6 |
| 20 | 7 |
| 21 | 7 |
| 22 | 7 |
| 23 | 8 |
| 24 | 8 |

### Rounds, deadlines and the clock

| Fact | How it works |
| --- | --- |
| Length | `rounds` nights (10). Night 1 is the first night after the start. |
| Deadline | Night N closes at the start time + N x one day. A day is `day_minutes` long. No weekends are skipped: the nights are back to back. |
| Pilot days | 5 minutes each (the default). Night 1 closes 5 minutes after `/gm start`. A 10-night pilot takes 50 minutes. |
| Real days | `day_minutes` = 1440 is a 24-hour day. Start the game at the time of day you want the deadline to be. |
| Resolution | At the deadline the night is resolved. Torch checks the clock every `HEARTBEAT_SECONDS` seconds, so it lands within a few seconds. |
| News | Posted `GM_NEWS_DELAY_SECONDS` seconds after the deadline. DMs go out with it. |
| Night labels | A day shorter than `REAL_DAY_HOURS` hours: "Night 6 (closes 08:34)" while open, "Night 6 (closed 08:34)" in news and results (SAST, UTC+2, no daylight saving). A real day: "Night 6 (Tue)", the weekday the night closes on (one minute before the deadline). |
| Changing your mind | You may send a new move any time before the deadline. The last valid one counts. |
| The end | After night `rounds` has resolved and its news is posted, Torch scores the game and posts the reveal (section 8). |
| Late bot | If Torch was down, it catches up one night per clock check. A night with no moves sent in time is all auto-scavenge. |

### Missing the deadline

If you have no valid move when the night resolves, you scavenge automatically (a "missed" scavenge). It finds the same 0 to 2 as a normal one (`missed_scavenge_max` is -1, meaning "same as normal"). Your DM says you did not choose a move. A bandit who misses gets nothing (bandits cannot scavenge). A move that has become illegal by the deadline (for example you aimed at a player who then quit) is treated as no move.

### Quitting

`/quit` (any time):

- Your food goes to 0 and leaves the game (it is not booked in the ledger).
- Your move for tonight is dropped. You are removed from the night, the ranges board, `/play` lists and the radio list.
- #news says "{alias} has left the game. Their food goes with them."
- You cannot be targeted by steal, investigate or gift.
- Anyone whose goal aimed at you ("beat" or "grudge") has that goal voided (counted as not done).
- You score no survival point and cannot get a seat. See section 11 for what else follows from quitting.

### Simulated colleagues

`/gm add-sims` (1 to `GM_ADD_SIMS_MAX`, before the start) adds computer players for test games. They have the simulator's office personalities (casual, farmer, opportunist, shark, paranoid, saint, detective, chaos) and play through the same rules. They never receive DMs.

**Cast (`cast` option on `/gm add-sims` and `/gm pilot`, default `balanced`).** `balanced` deals one of each of the eight personalities before any repeats, in a shuffled order, and carries on the cycle when sims are added in several batches (8 sims = all eight, 16 = two of each). `office` draws each sim from the simulator's office mix (casual 25%, farmer 20%, opportunist 15%, paranoid 10%, saint 8%, detective 8%, shark 7%, chaos 7%), so a saint is often missing. The personality is stored in the sim's join record.

**How a sim decides (`bot/brain.py`, `docs/sim/simbrain.py`).** It is the simulator's own AI, the same code, not a copy: it rolls a move from its personality's odds (and sometimes misses the deadline, chance depends on the personality, times `miss_scale`), nudged by its secret goal, being short of food, being robbed last night, the last night, and having been caught or exposed (it then steals less). It picks targets by what it believes about people, with some noise. It gives food back to whoever gave to it. Investigating and gifting are weighed up for the food they bring (`investigate_find`, `gift_bonus`).

What a sim knows is only what a player in its seat knows: its own state, its own private night results (what it saw when watching someone, who gave it food, who its guard caught; never who robbed it), the public #news facts (robberies, catches, exposures, bandits, events), and the morning ration ranges when the game has them (otherwise it estimates from the start rations and what #news said). Like a human it forgets: it follows about three people closely and its guesses about the rest drift to the camp average. It does not listen to #radio.

**Restarts.** A sim's knowledge is never saved. It is rebuilt from the log: every night is re-resolved on load, and the same code that resolves a night updates the sims' beliefs, live or replayed. Each night's choices use dice seeded by season and night, so a restarted Torch decides exactly what an uninterrupted one would.

**Sim radio.** Each sim may post at most one radio line a day, from the fixed phrases (section 9), never about itself when the line names someone. It is decided at the night's deadline from what the sim knew then (its own dice, season and night), written through the same path as a player's radio (a `radio` record, the text in the text store) and goes out with that morning's news. The chance a sim posts on a given day is `RADIO_RATE` in `bot/brain.py` (casual 3%, farmer 8%, opportunist 15%, paranoid 20%, saint 20%, shark 40%, chaos 45%; a detective 90% when it has something true to say). A full cast of eight averages about 1.7 lines a night.

| Personality | What it says |
| --- | --- |
| shark | "Don't trust X" or "X is lying about their rations", about whoever it thinks is richest |
| opportunist | "X is guarding. Don't waste your night on them." about whoever it thinks is richest (a bluff to keep rivals off its own mark) |
| paranoid | "I'm innocent. Leave me alone." |
| saint | "Someone should watch X's back tonight" about someone robbed last night, else "X is innocent" about whoever looks worst off |
| farmer | "Someone should watch X's back tonight" about someone robbed last night, else "I'm innocent" |
| casual | rarely: "I'm innocent" or "X is innocent" about a random person |
| detective | only what it watched: "I saw X sneaking around last night" when it watched X steal last night, later "Don't trust X" about a thief it watched earlier. Never lies. |
| chaos | any line, any target (bluffs and rumours) |

## 2. The numbers

**Default** is the value in `engine/rules.py`. **Live** is what the game really plays with: `docs/game.json` ("rules" block) overrides the default, and a game freezes its rules when it starts (section 1). Both columns are checked against the code. Values are in code notation: `1/3` is one third.

<!-- check:rules -->
| Rules field | Default | Live | What it does |
| --- | --- | --- | --- |
| `players` | `15` | `15` | Not used by the rules. Torch counts whoever joined; this is only copied into the start record. |
| `rounds` | `10` | `10` | Number of nights. |
| `start_rations` | `7` | `7` | Rations each player starts with. |
| `eat` | `1` | `1` | What each survivor (not a bandit) eats at the end of every night. |
| `scavenge_min` | `0` | `0` | Lowest a scavenge can find. |
| `scavenge_max` | `2` | `2` | Highest a scavenge can find. Each whole number from min to max is equally likely. |
| `steal_amount` | `2` | `2` | What one thief tries to take. |
| `caught_penalty` | `2` | `2` | What a thief caught by a guard pays (at most what they hold). |
| `guard_reward` | `2` | `2` | The most of that payment the guard keeps. Anything above it is a fine that leaves the game. |
| `guard_income_max` | `0` | `0` | A guard also finds 0 to this many rations. 0 means guards find nothing. |
| `guard_nights` | `2` | `2` | How many nights one guard covers (the night you set it, and the next). |
| `guard_limit` | `3` | `3` | Most guards one player may set in a game. 0 means no limit. |
| `guard_cooldown` | `0` | `0` | Nights you must wait after a guard ends before guarding again. |
| `missed_scavenge_max` | `-1` | `-1` | Highest a missed-deadline scavenge finds. -1 means the same as a normal scavenge. |
| `investigate_bounty` | `1` | `1` | What an exposed thief pays the investigator (at most what they hold). |
| `exposure_undo` | `"none"` | `"full"` | What an exposure does to the theft itself. `"none"`: the theft stands. `"full"`: the exposed thief hands back what they took tonight to the victim (then pays the bounty). `"split"`: half of it (rounded up) to the victim, the rest to the investigator. Live rule: `"full"`. |
| `investigate_find` | `0` | `2` | Every investigator also finds a random whole number from 0 to this many new rations in phase 6 (created food). 0 means off, and then no dice are drawn. Live: 0, 1 or 2, each equally likely. |
| `gift_bonus` | `0` | `1` | Extra rations created for the receiver of each gift. Live: every gift is worth 1 more to the receiver than it costs the giver. |
| `winner_tiebreak` | `"kindness"` | `"kindness"` | Tied top scores: `"kindness"` (most given away, then most rations), `"rations"`, or `"none"` (shared win). |
| `tiebreak` | `"kindness"` | `"kindness"` | Helicopter seat ties: `"kindness"` (most rations, then most given away, then fewest times caught) or `"coin"` (rations only). A coin flip settles anything still tied. |
| `give_goal` | `3` | `3` | Rations to give away for the "give" goal. |
| `grudge_goal` | `"rob"` | `"rob"` | `"rob"` (rob the target) or `"deny"` (the target must not get a seat). |
| `grudge_robs` | `1` | `1` | Successful robberies of the target needed for the "rob" grudge. |
| `robbed_goal` | `1` | `1` | Nights you must be robbed for the "robbed and extract" goal. |
| `bandit_steal_amount` | `1` | `1` | What a bandit tries to take per steal. |
| `bandit_rejoin` | `3` | `3` | A bandit holding this many rations at the end of a night rejoins the survivors. |
| `bandit_can_extract` | `False` | `False` | Whether a bandit can take a helicopter seat. |
| `seat_ratio` | `1/3` | `0.3333333333` | Share of players who get a seat. |
| `miss_scale` | `1.0` | `1.0` | Multiplies how often simulated colleagues miss the deadline. Real players are not affected. |
| `pts_extract` | `3` | `3` | Points for a helicopter seat. |
| `pts_objective` | `2` | `2` | Points for a completed secret goal. |
| `pts_survive` | `1` | `1` | Points for surviving without a seat. |
| `events_per_night` | `0.0` | `0.0` | Average wilderness events per night. 0 means events are off. |
| `events_bias` | `"random"` | `"random"` | Who events hit: `"random"`, `"trailing"` or `"top"`. Torch only uses `"top"` (in gentle mode). |
| `events_raid` | `0.0` | `0.0` | Times its library weight the raid event is drawn. 0 means no raids. |
| `events_rats_relative` | `False` | `False` | True: rats tax everyone within 1 of the richest. False: everyone holding 7 or more. |

Other fixed numbers (hard-coded in the code, so listed here):

<!-- check:constants -->
| Name | Value | What it is |
| --- | --- | --- |
| `KINDS` | `scavenge, steal, guard, investigate, gift` | The five moves. |
| `GIFT_MIN` | `1` | Smallest gift. |
| `GIFT_MAX` | `2` | Largest gift. |
| `CLEAN_STEALS_NEEDED` | `3` | Successful steals before your first catch that complete the clean-thief goal. |
| `TRAILING_FAVOUR` | `3` | In "trailing" bias, how many times likelier the favoured players are (not used by Torch). |
| `MIN_PLAYERS_TO_START` | `2` | Fewest players `/gm start` accepts. |
| `ALIAS_POOL_SIZE` | `24` | Number of distinct aliases, so the most players. |
| `REAL_DAY_HOURS` | `20` | A day at least this long counts as a real day for labels. |
| `GM_DAY_MINUTES_DEFAULT` | `5.0` | Default `day_minutes`. |
| `GM_DAY_MINUTES_MIN` | `1` | Smallest `day_minutes`. |
| `GM_DAY_MINUTES_MAX` | `1440` | Largest `day_minutes`. |
| `GM_NEWS_DELAY_SECONDS` | `10` | Seconds from the deadline to the news. |
| `GM_PILOT_SIMS_DEFAULT` | `8` | Default number of sims for `/gm pilot`. |
| `FINAL_STRETCH` | `3` | The last this-many nights show a countdown. |
| `HISTORY_ROWS_SHOWN` | `40` | Most rows `/gm history` shows. |
| `HALL_TOTALS` | `games, won, seat, points, stolen, exposed, guarded, given, goal` | What `/gm hall-of-fame` adds up per person. |
| `GM_ADD_SIMS_MAX` | `20` | Most sims added per `/gm add-sims`. |
| `HEARTBEAT_SECONDS` | `5` | How often Torch checks the clock and delivers messages. |
| `PICKER_MAX_NAMES` | `25` | Names a Discord picker can list (Discord's limit). |
| `MESSAGE_CUT` | `1990` | Longer messages are cut to this many characters. |

## 3. Moves and what is allowed

One move per player per night. Nobody sees your move. Every move is checked when you send it and again when the night resolves, so a menu can never offer what the server would refuse.

| Move | Needs a target | What it does |
| --- | --- | --- |
| Scavenge | No | Find 0 to 2 rations (`scavenge_min` to `scavenge_max`). |
| Steal | Yes | Try to take `steal_amount` (a bandit: `bandit_steal_amount`) from the target. |
| Guard | No | Protect yourself tonight and tomorrow night (`guard_nights`). You find nothing that night. |
| Investigate | Yes | Learn what the target chose tonight. If they chose steal, they are exposed and pay you `investigate_bounty`. |
| Gift | Yes, plus 1 or 2 | Give rations. You always keep at least 1. |

### What is refused

| Rule | Detail |
| --- | --- |
| Joined and open | You must have joined, the game must have started and not finished, and the deadline must not have passed. |
| Target | Must be a player still in the game, not yourself. Untargeted moves (scavenge, guard) take no target. Only gift takes an amount. |
| Guard | You cannot guard while already protected. You cannot guard once you have used `guard_limit` guards. You cannot guard before `guard_cooldown` nights have passed since the last one ended. With the defaults: guard on night N covers N and N+1, you can guard again on N+2, three times in a game. |
| Gift | Amount 1 or 2, and your rations minus the amount must stay at least 1. So you need 2 rations to give 1, 3 to give 2. |
| Bandit | Only steal or investigate. |

### Who you may target

Steal and investigate: any other player still in the game, including bandits and players with nothing. Gift: the same, if you have at least 2 rations.

### Radio

One anonymous message a day, picked from fixed phrases (section 9). It is not a move: you still make tonight's move.

## 4. The night, phase by phase

Everything below happens when the deadline passes, in this order. Players are handled in internal join order (invisible to players); this only matters where noted.

### Phase 0: before the engine

1. Every player with no valid move gets an automatic scavenge (see "Missing the deadline"). Simulated players choose theirs.
2. If events are on, the night's wilderness events happen first (section 5). They change rations before the night starts, so "start of night" below means after the events.

<!-- check:phases -->
| Phase | Name | What happens |
| --- | --- | --- |
| 1 | Guards go up | Each guard sets protection through night + `guard_nights` - 1. `guards_used` goes up. A guard who is already protected wastes nothing and uses no guard (cannot happen through the menus). Bandits never count as guarding. |
| 2 | Thieves who hit a guard pay | Each thief who targeted a protected player is caught and pays `caught_penalty` (at most what they hold). The guard receives up to `guard_reward` of it. Anything above that is a fine that leaves the game. Caught thieves steal nothing. |
| 3 | Other thefts | Thefts against unprotected targets are shared out from a fixed snapshot (below). |
| 4 | Scavenging | Every scavenger who is not a bandit finds a random amount. A guard also finds 0 to `guard_income_max`. This is the main way food is created (the others: `gift_bonus` in phase 5, `investigate_find` in phase 6, and events). |
| 5 | Gifts | Gifts go through, capped so the giver keeps 1. |
| 6 | Investigations | Each investigator learns the target's move. If it was a steal, the thief is exposed: they hand back what they took tonight (live rule `exposure_undo` = "full") and pay the bounty. |
| 7 | Eating, bandits, comebacks | Survivors eat. Anyone on 0 becomes a bandit. Bandits with enough rations rejoin. |

### Phase 2 in detail: guards

- Guarded targets are handled in the order of their lowest-numbered thief. Each thief pays from what they hold at that moment, so a thief who was already paid as a guard earlier in this phase can pay from it.
- A caught thief who holds less than `caught_penalty` pays what they have. The guard gets what was paid, up to `guard_reward`.
- Each caught thief counts one "caught" (used by the clean-thief goal and the seat tiebreak). #news names the thief. The guard gets a private line.
- An idol on a guarded player is not used up: the thieves are caught first.

### Phase 3 in detail: thefts

1. **Snapshot.** Each victim can lose at most what they hold after phase 2. This is fixed before any theft lands, so the order between thieves cannot matter and tonight's loot cannot be stolen again tonight.
2. **What thieves want.** `steal_amount` each (`bandit_steal_amount` for a bandit).
3. **Total taken from a victim** = the smaller of (their snapshot rations) and (all thieves' wants added up). If the victim holds a hidden idol, the total is 0 and the idol is spent.
4. **Splitting.** The thieves are put in a random order (from the night's dice). Rations are handed out one at a time round and round: first thief, second thief, and so on, skipping anyone who has what they wanted, until the total is gone. So with 3 thieves who want 2 each and a victim holding 4: shares are 2, 1, 1 (the first in the random order gets the extra). With a victim holding 1 and 2 thieves: one random thief gets 1 and the other finds the place empty.
5. **Each thief's result.** Got more than 0: "success" (counts a successful steal; counts a clean steal if never caught; counts toward a grudge on their target; adds to "stole"). Got 0: "empty".
6. **The victim.** If the total taken is more than 0, the victim is "robbed" once that night (counts once, however many thieves), and the news says someone hit them and how much they are down. If it is 0, the news says someone broke in and found nothing (or the idol line).

### Phase 4 in detail: scavenging

- Found = a random whole number from `scavenge_min` to `scavenge_max`, each equally likely (the default 0, 1, 2: one third each, average 1).
- A missed-deadline scavenge uses `missed_scavenge_max` if it is 0 or more.
- On a storm night everyone finds 0 (the roll is still drawn).
- Loot from phase 3 is already in the books but could not be stolen (snapshot). Scavenging happens after thefts, so a robbed player still finds food.

### Phase 5 in detail: gifts

- Handled in join order. The giver's rations at this point (after thefts and scavenging) are used: the gift is `min(amount, rations - 1)`. If that is 0 or less, nothing happens and nobody is told.
- The gift is counted in the giver's "gave away" total (used by the give goal, the seat tiebreak and the reveal).
- `gift_bonus` rations (default 0, live 1) are created for the receiver on top. The giver is not charged for them and they do not count towards "gave away". The receiver's DM says the total they got.
- A gift cannot be stolen the night it is given (gifts come after thefts).

### Phase 6 in detail: investigations

- The investigator learns what the target chose tonight (the move kind, and the target's target if any), even if the move failed or was an automatic scavenge. They are not told whether it was automatic.
- If the target chose **steal** (any steal, even one that was caught or found nothing), the thief is exposed. Three things can follow, in this order, each limited to what the thief holds at that moment (after thefts, scavenging and gifts):
  1. **Loot back** (`exposure_undo`, live value "full"). What this thief took tonight goes back to the victim: all of it with "full"; with "split", half (rounded up) to the victim and the rest to the investigator; with "none", nothing. Only this thief's own share, only once (a second investigator on the same thief finds nothing left to take back), and only what they still hold. A thief who hit a guard or an idol took nothing, so has nothing to hand back. The theft still counts as a successful steal for goals and for the victim's "robbed" count.
  2. **The bounty.** The thief pays `investigate_bounty` to the investigator, at most what they hold after step 1.
  3. The exposure is public in #news (the thief and victim are named, the investigator is not).
- A thief with nothing to pay still counts as exposed (the Detective goal counts it).
- Two investigators watching the same thief each get the bounty (in join order), if the thief still has rations. Each exposure gets its own news line.
- A thief caught by a guard **and** exposed pays the guard and the investigator.
- **Finding food while watching** (`investigate_find`, off at 0). After each investigation is settled, if the number is above 0 the investigator finds a random whole number from 0 to it (equally likely) and that food is created. The die is drawn for every investigator, so turning it on also changes the dice later in the night.
- Everything in this phase happens before eating.

### Phase 7 in detail: eating, bandits, comebacks

- A survivor eats `eat` (1). On a feast night nobody eats.
- If a survivor ends the night on 0 rations they become a bandit that night (even on a feast night). The news says so. They stay a bandit until they rejoin.
- Bandits do not eat. They can only steal or investigate, and take `bandit_steal_amount` per steal.
- A player who was already a bandit when the night began and ends it with `bandit_rejoin` or more rations rejoins the survivors. They do not eat that night. A player who becomes a bandit tonight cannot rejoin tonight.
- With `eat` at 1, a survivor with exactly 1 ration at the end of phase 6 eats it and becomes a bandit the same night.

### Tie and order summary

| Question | Answer |
| --- | --- |
| Who goes first among thieves on one target? | Nobody: the random order only decides who gets the odd extra ration. |
| Can I be robbed of what I find tonight? | No. Thefts use a snapshot taken before scavenging. |
| Can I be robbed of a gift I receive tonight? | No. Gifts come after thefts. |
| Can I give away what I am robbed of? | The gift uses what you hold after being robbed, keeping 1. |
| Does the order of players ever matter? | Phase 2 (a guard who is also a thief paying out of a reward), phase 5 (chained gifts) and phase 6 (who is paid first when the thief runs short). |

## 5. Wilderness events

Small random things that happen to the camp at the start of a night, before phase 1. Off unless the Game Master starts the game with `events: gentle`.

### Modes

<!-- check:modes -->
| Mode | Settings | What it means |
| --- | --- | --- |
| `off` | `-` | No events. The game is exactly the plain game. |
| `gentle` | `events_per_night=1.0, events_bias="top", events_rats_relative=True` | Exactly one event a night. Bad events can only hit the top third by rations; good events can only reach the bottom third. Rats tax the richest. No raids. |

Engine options that Torch cannot select: bias `"random"` and `"trailing"`, and `events_raid`. Count per night is the whole number part of `events_per_night`, plus one more with the leftover as the chance (so 1.0 is always exactly one).

### How an event is chosen and aimed

1. Draw one event from the library by weight (gentle weights below; zero-weight events are never drawn).
2. Camp events (storm, feast, rats, rats_top) happen to everyone. Player events pick one player.
3. Eligible players: never a bandit; a "lose" event needs the player to keep at least the floor (so an event can never create a bandit); a raid needs the top quarter by rations; the idol needs someone without one; the shelter collapse needs someone whose guard is currently up.
4. Gentle aiming ("top"): the top third is every non-bandit whose rations are at or above the k-th richest non-bandit, where k is (non-bandit players / 3) rounded up, and at least 1; the bottom third likewise from the poor end. Ties at the edge are all in. A bad event picks at random among eligible players in the top third; a good event among eligible players in the bottom third. A bad event with nobody there fizzles (nothing happens, no news). A good event with nobody there goes to any eligible player.
5. If no one is eligible the event fizzles. Fizzled events are not counted for the story decks.

### The events

<!-- check:events -->
| Event | Scope | Lucky | Public | Library weight | Gentle weight | Chance per draw (gentle) | Op | Parameters | What happens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bananas` | player | yes | yes | 10 | 10 | 16.9% | find | `amount=1` | One player finds 1 ration (created). |
| `coconut` | player | yes | yes | 10 | 10 | 16.9% | find | `amount=1` | One player finds 1 ration (created). |
| `cache` | player | yes | yes | 3 | 3 | 5.1% | find | `amount=2` | One player finds 2 rations (created). |
| `idol` | player | yes | no | 5 | 5 | 8.5% | idol | `-` | One player gets a hidden idol: the next time anyone robs them, the thieves get nothing and the idol is spent. Only they are told. |
| `snake` | player | no | yes | 8 | 8 | 13.6% | lose | `amount=1, floor=1` | One player loses 1 ration (destroyed). Needs at least 2 rations. |
| `rain` | player | no | yes | 8 | 8 | 13.6% | lose | `amount=1, floor=1` | Same effect as snake, different story. |
| `shelter` | player | no | yes | 4 | 4 | 6.8% | drop_guard | `-` | One player whose guard is up loses it for tonight. The guard still counts as used and cannot be set again until it would have ended. |
| `rats` | camp | no | yes | 3 | 0 | 0.0% | tax | `at_least=7, amount=1` | Everyone holding 7 or more loses 1. Only used when `events_rats_relative` is False, so never in Torch. |
| `storm` | camp | no | yes | 4 | 4 | 6.8% | flag | `flag="storm"` | Nobody finds food scavenging tonight (phase 4). |
| `feast` | camp | yes | yes | 4 | 4 | 6.8% | flag | `flag="feast"` | Nobody eats tonight (phase 7). |
| `raid` | player | no | yes | 4 | 0 | 0.0% | lose | `amount=2, floor=1, top_quartile=True` | One player in the top quarter loses 2 (needs at least 3). Drawn only when `events_raid` is above 0, so never in Torch. |
| `rats_top` | camp | no | yes | 3 | 3 | 5.1% | tax | `relative=True, within=1, amount=1, floor=1` | Every non-bandit within 1 of the richest, and holding at least 2, loses 1. If nobody qualifies it fizzles. The news names them. |

Floors: "floor 1" means the event never takes a player below 1 ration. Total gentle weight is 59.

### Stories (no repeats)

Each event has several tellings of the same effect. For each event, the tellings are shuffled once per game (their own dice, from the game and the event) and used in that order; all of them come up before any repeats. The count of earlier occurrences carries across nights, including after a restart. Variants never change the rations. Events with one telling (`idol`, `shelter`, `rats`) always use their base text.

<!-- check:variants -->
| Event | Emoji | Text |
| --- | --- | --- |
| `bananas` | 🍌 | `{who} found a pile of bananas. +1 ration.` |
| `bananas` | 🫐 | `{who} found a bush heavy with wild berries. +1 ration.` |
| `bananas` | 🥭 | `A ripe mango dropped right at {who}'s feet. +1 ration.` |
| `bananas` | 🍄 | `{who} found mushrooms. The safe kind, apparently. +1 ration.` |
| `bananas` | 🍯 | `{who} raided a wild beehive and lived. +1 ration.` |
| `bananas` | 🥚 | `{who} found a nest of eggs nobody was guarding. +1 ration.` |
| `bananas` | 🍠 | `{who} dug up a sweet potato. +1 ration.` |
| `coconut` | 🥥 | `{who} cracked open a fallen coconut. +1 ration.` |
| `coconut` | 🐟 | `{who} caught a fish with their bare hands. +1 ration.` |
| `coconut` | 🦀 | `{who} grabbed a crab before it got away. +1 ration.` |
| `coconut` | 🥜 | `{who} found a squirrel's hidden stash of nuts. +1 ration.` |
| `coconut` | 🥫 | `A tin of beans washed up on the beach. {who} got there first. +1 ration.` |
| `coconut` | 🍫 | `{who} found a chocolate bar in an old jacket pocket. +1 ration.` |
| `coconut` | 🌽 | `{who} found a patch of wild corn. +1 ration.` |
| `cache` | 🎒 | `{who} stumbled on a buried supply cache. +2 rations.` |
| `cache` | 🛶 | `A crate washed ashore and {who} dragged it home. +2 rations.` |
| `cache` | 🪂 | `A supply drop landed near {who}'s shelter. +2 rations.` |
| `idol` | 🗿 | `You found a hidden idol. The next person to rob you gets nothing.` |
| `snake` | 🐍 | `{who} was bitten by a snake and spent a ration recovering. -1 ration.` |
| `snake` | 🦍 | `A gorilla raided {who}'s stash and ran off with a ration. -1 ration.` |
| `snake` | 🐒 | `A monkey snatched a ration from {who} and laughed about it. -1 ration.` |
| `snake` | 🦝 | `Something with a striped tail got into {who}'s food overnight. -1 ration.` |
| `snake` | 🐦 | `A seagull swooped down and took {who}'s lunch. -1 ration.` |
| `snake` | 🐗 | `A wild boar trampled through {who}'s camp. -1 ration.` |
| `snake` | 🕷️ | `{who} was bitten by a spider and lost a ration's worth of energy. -1 ration.` |
| `rain` | 🌧️ | `Rain soaked {who}'s stash. -1 ration.` |
| `rain` | 🌊 | `The tide came in further than {who} expected. -1 ration.` |
| `rain` | 🐜 | `Ants found {who}'s food before {who} did. -1 ration.` |
| `rain` | 🤮 | `{who} ate something that disagreed with them. -1 ration.` |
| `rain` | 🔥 | `{who}'s cooking fire got out of hand. -1 ration.` |
| `rain` | 🕳️ | `{who} dropped a ration down a hole and it's not coming back. -1 ration.` |
| `rain` | 🦠 | `Mould got into {who}'s stash. -1 ration.` |
| `shelter` | 🏚️ | `{who}'s shelter collapsed in the night. Their guard is gone.` |
| `rats` | 🐀 | `Rats got into the stores. Everyone holding 7 or more rations lost 1.` |
| `storm` | ⛈️ | `A storm rolled in. Nobody finds any food tonight.` |
| `storm` | 🌫️ | `Thick fog all night. Nobody finds any food tonight.` |
| `storm` | 🌪️ | `A whirlwind tore through the island. Nobody finds any food tonight.` |
| `storm` | 🌊 | `A storm surge flooded the foraging grounds. Nobody finds any food tonight.` |
| `feast` | 🍖 | `A feast night. Nobody eats tonight.` |
| `feast` | 🔥 | `Someone got a big fire going and everybody shared. Nobody eats tonight.` |
| `feast` | 🐠 | `The fish practically jumped into camp. Nobody eats tonight.` |
| `feast` | 🥥 | `The palms dropped coconuts all evening. Nobody eats tonight.` |
| `raid` | 🐒 | `A troop of monkeys raided {who}'s stash and made off with two rations. -2 rations.` |
| `raid` | 🐻 | `A bear tore open {who}'s food store. -2 rations.` |
| `raid` | 🌊 | `A freak wave swept away half of {who}'s stash. -2 rations.` |
| `raid` | 🐺 | `Wolves got into {who}'s shelter overnight. -2 rations.` |
| `raid` | 🔥 | `A brush fire ran through {who}'s corner of the camp. -2 rations.` |
| `raid` | 🐊 | `A crocodile dragged off {who}'s supplies. -2 rations.` |
| `rats_top` | 🐀 | `Rats got into the biggest stashes: {who}. -1 ration each.` |
| `rats_top` | 🐁 | `Mice chewed through the fullest stores: {who}. -1 ration each.` |
| `rats_top` | 🦝 | `Raccoons went for the best-stocked camps: {who}. -1 ration each.` |
| `rats_top` | 🐦 | `Crows picked over the biggest piles: {who}. -1 ration each.` |
| `rats_top` | 🐜 | `Ants marched on the fullest stashes: {who}. -1 ration each.` |

### Events and the main dice

Events use their own random stream, seeded from the game and the night, so turning events on never moves a roll in the plain game, and a night replayed after a restart gives identical events.

### What events do to the books

Every ration change is booked: `event_found` creates food, `event_lost` destroys it. Storm and feast change no balance directly. See section 10.

## 6. Morning ration ranges

When the Game Master starts with `ranges` on, each morning's #news ends with a block showing a band per player, never a count. Bandit status wins over rations.

<!-- check:bands -->
| Band | Label | Lowest rations in the band |
| --- | --- | --- |
| 0 | `🟢 well fed` | 7 |
| 1 | `🟡 getting by` | 3 |
| 2 | `🔴 starving` | 1 |
| 3 | `🏴‍☠️ bandit` | - |

- Order inside the post: richest band first. Names inside a band are alphabetical, so the list cannot leak a ranking.
- Quitters are not listed. A band with nobody in it is left out.
- A player on 0 who is still a survivor never shows: they become a bandit first.
- `/status` adds "The camp sees you as {band}." when ranges are on, and a "beat" goal shows how the target looks this morning.
- The text that announces ranges at the start ("🟢 7+ · 🟡 3-6 · 🔴 1-2") is typed by hand in the code and does not follow the band numbers if they change (section 11).

## 7. Secret goals

### The deal

Every player gets one secret goal at the start. The deal is like a deck, not independent dice:

1. There are 6 goal types. The deck holds the types in turn (beat, robbed2_extract, steal3_clean, give, grudge, detective, then again), as many cards as players, shuffled. With 15 players that is 3 each of the first three and 2 each of the last three. Extra cards from an uneven count go to the types earlier in that list.
2. Goals with a target (beat, grudge) are dealt as a chain: every player is the target of at most one goal, nobody targets themselves, and no two players target each other. Up to 200 tries; with a tiny roster that cannot avoid a mutual pair, all but one of the players holding a target goal get a "give" goal instead.
3. Targets are chosen among everyone dealt in, including simulated players.

### The goals

<!-- check:goals -->
| Goal id | Has a target | Exact wording (placeholder @player) | Done when (checked at the end) |
| --- | --- | --- | --- |
| `beat` | yes | `finish with more rations than @player` | Your final rations are more than the target's (a tie is not enough). The target may be a bandit. |
| `robbed2_extract` | no | `get robbed at least 1x and still extract` | You were robbed on at least `robbed_goal` nights (the name is old; the number is now 1) and you hold a helicopter seat. |
| `steal3_clean` | no | `steal 3 times before you're ever caught` | You made `CLEAN_STEALS_NEEDED` successful steals (each took more than 0) before the first time a guard caught you. Once you reach 3 it is locked in: a later catch does not undo it. Being exposed by an investigator is not a catch. |
| `give` | no | `give away 3 rations over the game` | You gave away at least `give_goal` rations in total (what was actually delivered). |
| `grudge` | yes | `successfully rob @player at least 1x` | You took more than 0 from the target on at least `grudge_robs` nights. (If `grudge_goal` were "deny" the wording is "make sure @player doesn't extract" and it is done when the target holds no seat.) |
| `detective` | no | `expose a thief red-handed with /investigate at least once` | You exposed at least one thief (investigated someone who chose steal that night). |

A goal aimed at a player who quit is never done. Goals are public only at the reveal.

### What /status shows mid-game

Progress states: **done** (can no longer be lost), **failed** (can no longer be met), **open** (still possible), **end** (only the helicopter can tell). Only facts the player may know are used. Other players' exact rations are never shown.

| Goal | Open | Done | Failed | End |
| --- | --- | --- | --- | --- |
| Any with a target, target quit | - | - | "your target left the game, so this goal no longer counts" | - |
| `steal3_clean` | "{n}/3 clean steals, never caught so far" | "3/3 clean steals before you were ever caught" | "you were caught before your 3rd clean steal ({n}/3)" | - |
| `give` | "{n}/3 given" | "{n}/3 given" | - | - |
| `detective` | "0/1 thieves exposed" | "thief exposed" | - | - |
| `robbed2_extract` | "robbed {n}/1 so far, and you'll need a seat at the end" | - | - | "robbed {n}/1 ✓. Now hold a seat on the helicopter" once robbed enough |
| `beat` | - | - | - | "decided at the end: you have {n}, {target}'s stash is secret." (plus "They look {band} this morning." when ranges are on) |
| `grudge` (rob) | "robbed {target} {n}/1" | "robbed {target} {n}/1" (same words, once enough) | - | - |
| `grudge` (deny) | - | - | - | "decided at the end: who gets a seat is only known when the helicopter comes" |

The `/status` marks: "✅ **Goal met:**" for done, "❌ **Goal lost:**" for failed, "🎯 **Progress:**" for open, "⏳ **Progress:**" for end.

## 8. Scoring and the end

### Order of events at the end

1. After night `rounds` resolves and its news is posted, Torch runs the final scoring.
2. **Seats.** Candidates are survivors who are not bandits (a bandit cannot take a seat while `bandit_can_extract` is False) and have not quit. They are shuffled (so a full tie is a coin flip), then sorted best first by: most rations; then most rations given away; then fewest times caught by a guard (with `tiebreak` "kindness"; with "coin" only rations). The top `seats` get the seats. If there are fewer candidates than seats, all of them get one.
3. **Goals** are scored (section 7).
4. **Points.** Seat: `pts_extract` (3). Otherwise survived (not a bandit, not a quitter): `pts_survive` (1). Bandit or quitter: 0. Plus `pts_objective` (2) if the goal is done.
5. **Winners.** Highest score. If tied and `winner_tiebreak` is "kindness": most given away, then most rations; whoever is still level shares the win.
6. The reveal is posted to #news.

### The reveal

The text part of the post says "The helicopter takes {names}." and "Winner: {names}.". The per-player table is a picture, one row per player, best score first. If the picture cannot be made, the same table goes out as text lines.

<!-- check:reveal-columns -->
| Column | Key | Top of the column highlighted |
| --- | --- | --- |
| `#` | `rank` | no |
| `Player` | `player` | no |
| `Points` | `score` | yes |
| `Seat` | `seat` | no |
| `Rations` | `rations` | yes |
| `Stole` | `stole` | yes |
| `Robbed` | `times_robbed` | yes |
| `Gave away` | `gave_away` | yes |
| `Goal` | `goal` | no |

Each award card shows who topped that stat (ties share it) and the number, or "nobody" when the top is 0:

<!-- check:awards -->
| Award | Emoji | Stat key |
| --- | --- | --- |
| `Biggest thief` | 🥷 | `stole` |
| `Most robbed` | 🎯 | `times_robbed` |
| `Most generous` | 🎁 | `gave_away` |
| `Biggest stash` | 🥫 | `rations` |

The picture marks the top of each highlighted column in orange, winner rows in green, a seat as "Yes", and a goal as a filled dot when done, an empty circle when missed. Goals are shown with the target's alias filled in.

## 9. What players see

### Everything is private except #news and #radio

Every reply to a player is ephemeral (only they see it) and silent (it makes no sound or notification, because the player just tapped it themselves: owner, 17 October 2026). The night DM and the morning #news post are the only things that notify. Only Torch posts in #news and #radio (threads are shut). Public output uses aliases only. DMs carry the night's private results; if a player's DMs are closed, `/results` shows the same lines. Messages are written to the log first and delivered after, and retried until sent.

### Slash commands

<!-- check:commands -->
| Command | Options | Description (as players see it) | Who |
| --- | --- | --- | --- |
| `/join` | `-` | Join the game and get your secret alias | everyone |
| `/play` | `-` | Make tonight's move: just click | everyone |
| `/scavenge` | `-` | Look for food tonight (0 to 2 rations) | everyone |
| `/guard` | `-` | Protect yourself tonight and tomorrow night | everyone |
| `/steal` | `target` | Steal rations from someone tonight | everyone |
| `/investigate` | `target` | Watch someone tonight and see what they do | everyone |
| `/gift` | `target, amount` | Secretly give someone 1 or 2 rations | everyone |
| `/status` | `-` | Your rations, guards left, secret goal and tonight's move | everyone |
| `/results` | `-` | What happened to you last night | everyone |
| `/radio` | `-` | Send an anonymous rumour by clicks (posted with the morning news) | everyone |
| `/quit` | `-` | Leave the game (your food leaves with you) | everyone |
| `/gm add-sims` | `count, cast` | Add simulated colleagues (before the start) | Game Master |
| `/gm start` | `day_minutes, events, ranges` | Start the game | Game Master |
| `/gm pilot` | `sims, day_minutes, events, ranges, confirm, cast` | One step: new season, you join, add sims, start (defaults = usual pilot) | Game Master |
| `/gm who-moved` | `-` | Who has chosen tonight's move (never rations) | Game Master |
| `/gm history` | `member` | Who played which alias, in FINISHED seasons only (private to you) | Game Master |
| `/gm hall-of-fame` | `since, post` | Totals per person over finished seasons; post:True puts it in #news | Game Master |
| `/gm new-season` | `confirm` | Archive this game and start an empty one | Game Master |

The Game Master is anyone listed in the bot's `TORCH_GM_IDS` setting, or the server owner. `/gm who-moved` lists human players who have and have not chosen (never anyone's rations). `/gm new-season` needs `confirm: True`; it archives the log and starts empty.

### The countdown

For the last `FINAL_STRETCH` (3) nights, Torch adds a line saying how many nights are left. The last night says "LAST NIGHT". The line is added to: the reply that confirms your move, the `/play` header, the board's "night open" line, and the news that opens the night ("Tonight is the LAST NIGHT:" on the final one). With 10 rounds, night 8 says "3 nights left", night 9 "2 nights left" and night 10 "LAST NIGHT". The count includes the night that is open.

### /play and the buttons

`/play` (or the Play button) shows a private message: "{Night label}: {alias}, 🥫 {n} rations. What will you do tonight?" (a bandit shows "🏴‍☠️ bandit"). It has one button per move you may legally make tonight: 🥫 Scavenge, 🛡️ Guard, 🥷 Steal, 🔍 Investigate, 🎁 Gift. Steal, Investigate and Gift then show a list of aliases (never your own, alphabetical, at most `PICKER_MAX_NAMES`); Gift then offers "Give 1" and "Give 2" if both are legal. A Back button returns. A 📻 Radio button appears if you have not used today's message. The move is judged at the time you clicked. The reply confirms: "{Night label}: you'll 🥷 steal from {alias}. You can change your mind until the deadline."

### The status board in #news

One live message pinned in #news, with three buttons that work for everyone and answer privately: 🎮 Play, 📻 Radio, 📋 My status. It is edited in place when its content changes (no new message, no sound, no "pinned" notice; posted silently and pinned only the first time, or again if someone deletes it): whenever someone joins before the start, at the start, after each night's news, and at the end. It waits until the news is above it. Shown: the player count (and "🌴 Events on" / "📊 Ranges on"), which night is open and when moves close (Discord shows the time in each player's own zone, counting down), and the nights done.

### History and Hall of Fame (Game Master only)

Owner decision, 17 October 2026: aliases are tied back to people only once a season has **ended**. An unfinished game is never opened up. Praise only: nothing names who robbed whom, and there is no "most robbed" list. Simulated colleagues are not people and are left out.

- A season counts as finished when its log has a finish record. Torch reads every archived season plus the current one if it has ended.
- Each person's row for a season: the alias they played, points, whether they held a seat, whether they won, rations stolen, successful steals, times caught, thieves they exposed, thieves their guard caught, rations given, whether their goal was met, whether they survived. Quitters have a row too.
- `/gm history` lists these rows, newest season first, at most `HISTORY_ROWS_SHOWN` rows, only to you. `member` limits it to one person. A person who has left the server shows as "<left the server NNNN>".
- `/gm hall-of-fame` adds up each person's finished seasons: `HALL_TOTALS` (in that order). `since` (a date like 2026-10-01) keeps only seasons that started on or after it. It shows one line per award below, naming everyone who shares the top score; an award nobody earned (top score 0) is left out. By default only you see it; `post: True` posts it in #news (cut to `MESSAGE_CUT` characters).

<!-- check:hall-awards -->
| Award | Emoji | Meaning | Stat |
| --- | --- | --- | --- |
| `Sole Survivor` | 🏆 | most wins | `won` |
| `Frequent Flyer` | 🚁 | most helicopter seats | `seat` |
| `Top of the Food Chain` | ⭐ | most points | `points` |
| `Sticky Fingers` | 🥷 | most rations stolen | `stolen` |
| `Herlock Sholmes` | 🕵️ | most thieves exposed | `exposed` |
| `The Bouncer` | 🛡️ | most thieves caught on guard | `guarded` |
| `Santa Paws` | 🎁 | most rations given away | `given` |
| `Mission Accomplished` | 🎯 | most secret goals met | `goal` |

The text comes with a picture (`hall-of-fame.png`, the same look as the reveal): the award cards (title, meaning, names, number), then one row per person, sorted by most wins, then most points, then alias or name. The top of each column except Games is orange; the first row is green when they have at least one win. If the picture cannot be made, the text goes alone.

<!-- check:hall-columns -->
| Column | Key | Top of the column highlighted |
| --- | --- | --- |
| `Player` | `name` | no |
| `Games` | `games` | no |
| `Wins` | `won` | yes |
| `Seats` | `seat` | yes |
| `Points` | `points` | yes |
| `Stolen` | `stolen` | yes |
| `Exposed` | `exposed` | yes |
| `Caught on guard` | `guarded` | yes |
| `Given` | `given` | yes |
| `Goals` | `goal` | yes |

### Lines players see

Lines are listed with placeholders in braces. The test checks that the fixed words in each line still exist in the named file.

<!-- check:lines -->
| Where | Who sees it | Line | File |
| --- | --- | --- | --- |
| Start | #news | `🔥 The game has begun: {n} survivors, {rounds} rounds. Check /status for your secret goal. Choose a move before each deadline.` | `bot/game.py` |
| Start (events on) | #news, added | `🌴 Wilderness events are on: luck, good and bad, can strike anyone.` | `bot/game.py` |
| Start (ranges on) | #news, added | `📊 Every morning #news shows everyone's ration range (🟢 7+ · 🟡 3-6 · 🔴 1-2 · 🏴‍☠️ bandit), never the exact count.` | `bot/game.py` |
| Start | DM to each human | `🔥 The game has begun. Use /status any time to see your rations and your secret goal.` | `bot/game.py` |
| Night news header | #news | `📰 **News: {label}**` | `bot/game.py` |
| Quiet night | #news | `🌙 A quiet night. Nobody lost anything.` | `bot/game.py` |
| Ranges block (ranges on) | #news | `📊 **Rations this morning**` | `bot/game.py` |
| Robbed | #news | `🥷 {who} hit {victim} overnight. {victim} is down {total}.` | `bot/game.py` |
| Robbed, nothing found | #news | `🥷 Someone broke into {victim}'s place and found nothing.` | `bot/game.py` |
| Idol spent | #news | `🗿 Someone tried to rob {player} and left empty-handed: {player} had a hidden idol.` | `bot/game.py` |
| Caught by a guard | #news | `🚨 CAUGHT: {guard} was guarding and caught {thief} red-handed. {thief} paid {paid}.` | `bot/game.py` |
| Exposed | #news | `🕵️ EXPOSED: an investigator saw {thief} rob {victim}. {thief} pays them {paid}{back}.` | `bot/game.py` |
| Exposed, loot returned (the `{back}` part) | #news | `and gives {victim} back the {n} they stole` | `bot/game.py` |
| Out of food | #news | `🏴‍☠️ {player} ran out of food. {player} is back... as a bandit.` | `bot/game.py` |
| Comeback | #news | `🎉 Bandit {player} has scraped together enough to rejoin the survivors.` | `bot/game.py` |
| Quit | #news | `{alias} has left the game. Their food goes with them.` | `bot/game.py` |
| Helicopter | #news | `🚁 The helicopter takes {names}.` | `bot/game.py` |
| Winner | #news | `🏆 Winner: {names}.` | `bot/game.py` |
| Reveal (text fallback) | #news | `- {player}: {score} pts, {rations} rations, goal: {goal} ({result}); stole {stole}, robbed {robbed}x, gave away {gave}` | `bot/game.py` |
| DM header | DM | `🌙 **{label}**` | `bot/game.py` |
| Found an idol | DM | `🗿 You found a hidden idol. The next person to rob you gets nothing. Tell no one.` | `bot/game.py` |
| Idol saved you | DM | `🗿 Your idol saved you: a thief left with nothing. The idol is spent.` | `bot/game.py` |
| Thief met an idol | DM | `🗿 {target} had a hidden idol. You got nothing.` | `bot/game.py` |
| Scavenged | DM | `🥫 You scavenged and found {n}.` | `bot/game.py` |
| Auto-scavenged | DM | `🥫 You didn't choose a move, so you scavenged automatically and found {n}.` | `bot/game.py` |
| Guard up | DM | `🛡️ You're on guard for {span}.` | `bot/game.py` |
| You stole | DM | `🥷 You stole {n} from {target}.` | `bot/game.py` |
| You were beaten to it | DM | `🥷 You broke into {target}'s place, but someone beat you to it.` | `bot/game.py` |
| Nothing there | DM | `🥷 You broke into {target}'s place and found nothing.` | `bot/game.py` |
| You were caught | DM | `🚨 {target} was guarding: you were caught and paid {n}.` | `bot/game.py` |
| You were robbed | DM | `🥷 Someone stole {n} from you.` | `bot/game.py` |
| Your guard caught a thief | DM | `🚨 {whose} caught {thief} red-handed. They paid you {n}.` | `bot/game.py` |
| Guard caught, thief had nothing | DM | `🚨 {whose} caught {thief} red-handed, but they had nothing to pay you.` | `bot/game.py` |
| Guard from last night | DM | `Your guard (still up from night {n})` | `bot/game.py` |
| Investigated | DM | `🔍 You watched {target}: they chose {action}.` | `bot/game.py` |
| You exposed a thief | DM | `🕵️ You exposed {thief}; they paid you {n}.` | `bot/game.py` |
| You exposed your own thief | DM | `🕵️ You also got your {n} back from {thief}, who robbed you.` | `bot/game.py` |
| You were exposed | DM | `🕵️ EXPOSED: an investigator saw you rob {victim}. You paid them {n}{back}.` | `bot/game.py` |
| You were exposed, loot returned (the `{back}` part) | DM | `and gave back the {n} you stole` | `bot/game.py` |
| Your thief was caught | DM to the victim | `🕵️ An investigator caught the thief who robbed you: {thief}. You got your {n} back.` | `bot/game.py` |
| You gave | DM | `🎁 You gave {receiver} {n}.` | `bot/game.py` |
| You received | DM | `🎁 {giver} secretly gave you {n}.` | `bot/game.py` |
| You received (gift bonus) | DM | `🎁 {giver} secretly gave you {n}, and gifts grow: you got {total}.` | `bot/game.py` |
| Watching found food | DM | `🔍 While watching, you found {n} ration{s}.` | `bot/game.py` |
| You became a bandit | DM | `🏴‍☠️ You ran out of food. You're a bandit now: steal or investigate until you get back to 3.` | `bot/game.py` |
| You rejoined | DM | `🎉 You've scraped together enough to rejoin the survivors.` | `bot/game.py` |
| You ate | DM | `🍽️ You ate {n}.` | `bot/game.py` |
| Feast | DM | `🍽️ Feast night: you ate for free.` | `bot/game.py` |
| Total | DM | `🥫 You now have {n} rations.` | `bot/game.py` |
| Nothing yet | /results | `Nothing to report yet.` | `bot/game.py` |
| Joined | reply | `You're in. Your secret alias is **{alias}**. Tell no one.` | `bot/game.py` |
| Already in | reply | `You're already in as **{alias}**.` | `bot/game.py` |
| Closed | reply | `The game has already started; joining is closed.` | `bot/game.py` |
| Full | reply | `The game is full.` | `bot/core.py` |
| Not joined | reply | `You haven't joined. Use /join.` | `bot/core.py` |
| No round | reply | `There's no round open right now.` | `bot/game.py` |
| Too late | reply | `Tonight's deadline has passed; wait for the next round.` | `bot/game.py` |
| Unknown alias | reply | `There's no player called '{alias}'.` | `bot/core.py` |
| Move saved | reply | `{label}: you'll {what}. You can change your mind until the deadline.` | `bot/game.py` |
| Play header | reply | `**{label}**: {alias}, {state}. What will you do tonight?` | `bot/game.py` |
| Status line | reply | `**{alias}**: 🥫 {n} rations` | `bot/game.py` |
| Status: bandit | reply | `🏴‍☠️ BANDIT` | `bot/game.py` |
| Status: guards | reply | `{n} guards left` | `bot/game.py` |
| Status: unlimited | reply | `guards unlimited` | `bot/game.py` |
| Status: guarded | reply | `, guarded tonight` | `bot/game.py` |
| Status: goal | reply | `Secret goal: {goal}.` | `bot/game.py` |
| Status: goal met | reply | `✅ **Goal met:**` | `bot/game.py` |
| Status: goal lost | reply | `❌ **Goal lost:**` | `bot/game.py` |
| Status: progress | reply | `🎯 **Progress:**` | `bot/game.py` |
| Status: end | reply | `⏳ **Progress:**` | `bot/game.py` |
| Status: no move | reply | `not chosen yet (you'll scavenge if you forget)` | `bot/game.py` |
| Status: band | reply | `The camp sees you as {band}.` | `bot/game.py` |
| Status: before start | reply | `You're **{alias}**. The game hasn't started yet.` | `bot/game.py` |
| Status: quit | reply | `You've left the game.` | `bot/game.py` |
| Quit reply | reply | `You've left the game. Thanks for playing.` | `bot/game.py` |
| Quit again | reply | `You've already left.` | `bot/game.py` |
| Goal text | reply | `your target left the game, so this goal no longer counts` | `engine/finish.py` |
| Goal text | reply | `3/3 clean steals before you were ever caught` | `engine/finish.py` |
| Goal text | reply | `you were caught before your 3rd clean steal ({n}/3)` | `engine/finish.py` |
| Goal text | reply | `{n}/3 clean steals, never caught so far` | `engine/finish.py` |
| Goal text | reply | `{n}/{goal} given` | `engine/finish.py` |
| Goal text | reply | `thief exposed` | `engine/finish.py` |
| Goal text | reply | `0/1 thieves exposed` | `engine/finish.py` |
| Goal text | reply | `robbed {n}/{goal} ✓. Now hold a seat on the helicopter` | `engine/finish.py` |
| Goal text | reply | `robbed {n}/{goal} so far, and you'll need a seat at the end` | `engine/finish.py` |
| Goal text | reply | `decided at the end: you have {n}, {target}'s stash is secret.` | `engine/finish.py` |
| Goal text | reply | `They look {band} this morning.` | `engine/finish.py` |
| Goal text | reply | `decided at the end: who gets a seat is only known when the helicopter comes` | `engine/finish.py` |
| Goal text | reply | `robbed {target} {n}/{goal}` | `engine/finish.py` |
| Radio posted (one silent post per night, then `- {text}` per message) | #radio | `📻 **On the radio last night** (anonymous)` | `bot/discord_app.py` |
| Radio sent | reply | `Your anonymous message goes out with the morning news.` | `bot/game.py` |
| Radio used | reply | `One radio message a day. Yours goes out with the morning news.` | `bot/core.py` |
| Radio closed | reply | `Radio opens when the game starts.` | `bot/game.py` |
| Radio: bad line | reply | `Pick one of the radio lines.` | `bot/core.py` |
| Radio: no subject | reply | `Pick who it's about.` | `bot/core.py` |
| Radio picker | reply | `📻 Pick a line. It goes out anonymously with the morning news.` | `bot/discord_app.py` |
| Radio already used | reply | `📻 You've already used today's radio message. It goes out with the morning news.` | `bot/discord_app.py` |
| Board: waiting | #news | `⏳ Waiting for the Game Master to start. /join to play.` | `bot/game.py` |
| Board: head | #news | `🔥 **Survivors** · {n} players` | `bot/game.py` |
| Countdown, 3 or 2 nights left | #news, /play, board, move reply | `⏳ **{n} nights left**, then the helicopter.` | `bot/game.py` |
| Countdown, last night | board, /play, move reply | `🚁 **LAST NIGHT:** the helicopter comes after this. Seats go to the biggest stashes.` | `bot/game.py` |
| Countdown, last night (in the news before it) | #news | `**Tonight is the LAST NIGHT:**` | `bot/game.py` |
| Board: events | #news | `🌴 Events on` | `bot/game.py` |
| Board: ranges | #news | `📊 Ranges on` | `bot/game.py` |
| Board: night open | #news | `🌙 **Night {n} of {rounds}** · moves close <t:{ts}:R> (<t:{ts}:t>) · tap 🎮 Play` | `bot/game.py` |
| Board: last night over | #news | `🚁 The last night is over. The helicopter is coming…` | `bot/game.py` |
| Board: done | #news | `✅ Nights done: {list}` | `bot/game.py` |
| Board: over | #news | `🚁 **Game over.** The reveal is above. Thanks for playing.` | `bot/game.py` |
| Not a GM | reply | `Game Master only.` | `bot/discord_app.py` |
| Error | reply | `Something went wrong on Torch's side. Your move may not have been saved; check /status.` | `bot/discord_app.py` |
| GM: start twice | reply | `Already started.` | `bot/game.py` |
| GM: sims added | reply | `Added {count} sim colleagues.` | `bot/discord_app.py` |
| GM: started | reply | `Started: {n} players, a day every {minutes} minutes, events {mode}, ranges {state}.` | `bot/discord_app.py` |
| GM: pilot started | reply | `🔥 Started: you're **{alias}** (secret), {sims} sims, a round every {minutes} minutes, events {mode}, ranges {state}. Tap 🎮 Play on the board in #news.` | `bot/discord_app.py` |
| GM: pilot, game running | reply | `⚠️ A game is still running. Nothing changed. To end it unfinished and start a new one, run /gm pilot again with confirm: True.` | `bot/discord_app.py` |
| GM: history | reply | `📜 **Finished seasons, newest first**` | `bot/discord_app.py` |
| GM: history row | reply | `**{person}** was {alias} · {n} pts` | `bot/discord_app.py` |
| GM: history, none | reply | `No finished seasons yet` | `bot/discord_app.py` |
| GM: hall of fame, none | reply | `No finished seasons in that period.` | `bot/discord_app.py` |
| GM: hall of fame, bad date | reply | `⚠️ since must look like 2026-10-01.` | `bot/discord_app.py` |
| GM: hall of fame header | reply or #news | `🏛️ **Survivors Hall of Fame**{since} · {n} players · up to {games} games each` | `bot/discord_app.py` |
| GM: hall of fame award | reply or #news | `{emoji} **{title}** ({meaning}): {names} ({n})` | `bot/discord_app.py` |
| GM: hall of fame, private | reply | `*Only you see this. Run again with post: True to share it in #news.*` | `bot/discord_app.py` |
| GM: hall of fame, posted | reply | `Posted in #news.` | `bot/discord_app.py` |
| GM: who moved | reply | `Moved: {names}` | `bot/discord_app.py` |
| GM: who is waiting | reply | `Waiting: {names}` | `bot/discord_app.py` |
| GM: new season, not confirmed | reply | `Nothing changed. Run again with confirm: True.` | `bot/discord_app.py` |
| GM: new season | reply | `New season {id}. The old one is archived.` | `bot/discord_app.py` |
| GM: too few | reply | `Need at least 2 players.` | `bot/game.py` |
| GM: bad events option | reply | `events must be one of: {modes}.` | `bot/game.py` |
| Refusal | reply | `Unknown move '{kind}'.` | `engine/moves.py` |
| Refusal | reply | `'{kind}' doesn't take a target.` | `engine/moves.py` |
| Refusal | reply | `'{kind}' doesn't take an amount.` | `engine/moves.py` |
| Refusal | reply | `You're not in this game.` | `engine/moves.py` |
| Refusal | reply | `Bandits can only steal or investigate.` | `engine/moves.py` |
| Refusal | reply | `Pick a player who is still in the game.` | `engine/moves.py` |
| Refusal | reply | `You can't target yourself.` | `engine/moves.py` |
| Refusal | reply | `You're already protected tonight.` | `engine/moves.py` |
| Refusal | reply | `You've used all {n} guards.` | `engine/moves.py` |
| Refusal | reply | `You can't guard again yet.` | `engine/moves.py` |
| Refusal | reply | `Gifts are {min} or {max} rations.` | `engine/moves.py` |
| Refusal | reply | `You must keep at least 1 ration.` | `engine/moves.py` |

Events add one more line each in #news (the telling from the story deck, section 5). A camp event that took from you (rats) is repeated in your DM; an event that happened to you is repeated in your DM. Lines in #news come in this order: event lines (in the order they happened), then the "hit" lines (in no meaningful order), then caught, idol, exposed, bandit and comeback lines in the order they happened in the night. If there is nothing to say, the quiet-night line is posted.

DMs list the night's lines in this order: your event, camp event that took from you, then in the order things happened in the night (guard going up, catches, thefts, scavenging, gifts, investigations, bandit and rejoin lines), then what you ate, then your new total. Only human players get DMs; sims do not.

### The radio

One message per player per day, picked by clicking (a fixed line, then a player if the line names one). The picker lists the players still in the game except you. All radio lines of a night go out together, anonymously, as ONE silent post in #radio with the next morning's news ("📻 **On the radio last night** (anonymous)", then one line each), so it does not ping per line (owner, 17 October 2026). A message sent between the deadline and the news goes out with that news. Nobody can write their own words, so nobody is recognised by their writing style (owner decision, 17 October 2026).

<!-- check:radio -->
| Key | Line |
| --- | --- |
| `saw` | `I saw {a} sneaking around last night.` |
| `trust` | `Don't trust {a}.` |
| `lying` | `{a} is lying about their rations.` |
| `guarding` | `{a} is guarding. Don't waste your night on them.` |
| `easy` | `{a} looks like an easy target.` |
| `innocent` | `{a} is innocent. Leave them alone.` |
| `watch` | `Someone should watch {a}'s back tonight.` |
| `me` | `I'm innocent. Leave me alone.` |

`{a}` is replaced by the alias you pick. The line `me` names nobody. Lines are not checked for truth: radio can lie.

## 10. The ration ledger

Every ration movement is written to the game log as a "ration" record: player, change, reason, balance after, and who it involved. This is how a night is audited. Food is created only by the reasons marked "creates", and removed only by those marked "destroys"; everything else moves food from one player to another and nets to zero in a night.

<!-- check:ledger -->
| Reason | Effect on the food supply | Phase | Notes |
| --- | --- | --- | --- |
| `scavenge` | creates | 4 | Found food. Detail "auto" for a missed-deadline scavenge. |
| `guard_income` | creates | 4 | 0 to `guard_income_max` for a guard. Never happens with 0 (the live value). |
| `gift_bonus` | creates | 5 | `gift_bonus` for the receiver of a gift. Live: 1 per gift. |
| `investigate_find` | creates | 6 | Food an investigator finds while watching. Live: 0 to 2. |
| `event_found` | creates | 0 | Events that give food. |
| `eat` | destroys | 7 | What survivors eat. A zero line is booked when a survivor starts the night on 0. |
| `fine` | destroys | 2 | The part of a caught thief's payment above `guard_reward`. Never happens with the defaults. |
| `event_lost` | destroys | 0 | Events that take food. |
| `caught_penalty` | transfer | 2 | Out of the caught thief. |
| `guard_reward` | transfer | 2 | Into the guard. |
| `robbed` | transfer | 3 | Out of the victim. |
| `stole` | transfer | 3 | Into the thief. |
| `gift_out` | transfer | 5 | Out of the giver. |
| `gift_in` | transfer | 5 | Into the receiver. |
| `exposed_return` | transfer | 6 | Loot handed back by an exposed thief: out of the thief and into the victim (both lines use this reason). Only booked when the amount is above 0. |
| `exposed_loot` | transfer | 6 | With `exposure_undo` = "split" only: the investigator's half of the loot, out of the thief and into the investigator. |
| `bounty_paid` | transfer | 6 | Out of the exposed thief. With `exposure_undo` "none" a zero line is booked if they held nothing; otherwise only amounts above 0 are booked. |
| `bounty_received` | transfer | 6 | Into the investigator. |

Not booked in the ledger: the starting rations, and a quitter's food leaving the game.

## 11. Known problems and quirks

Verified on 17 October 2026. Remove an item here when it is fixed.

| What | Detail |
| --- | --- |
| Idol event crashes a night in Torch | With `events: gentle`, the idol event (about 8.5% of draws) needs a field that Torch's player record does not have (`idol`). Calling it directly raises `AttributeError: 'PlayerState' object has no attribute 'idol'`. The simulator's players have the field, so the simulator hides it. By reading the code (not run end to end): the dice are fixed by game and night, so the same night would fail on every clock check and the game would stop advancing. |
| Quitters still count | A quitter stays in the roster: they count towards the number of seats, can still have been dealt as a target (their hunters' goals are voided), and their own goal is still scored, so a quitter whose goal was already done can score `pts_objective` and appear in the reveal. Quitting before the start leaves the alias in the deal and its 7 rations show in the reveal. |
| Ranges announcement text is typed by hand | The start announcement and the bandit DM ("get back to 3") use fixed numbers instead of `BAND_EDGES` and `bandit_rejoin`. |
| `/scavenge` description says "0 to 2" | Typed by hand in the command description. |
| Exposure after a catch | A thief caught by a guard who is also investigated pays both the guard and the investigator. Two investigators on one thief both get the bounty (only the first can take the loot back). A steal that found nothing still counts as a steal for exposure. This is how the code works; it was an open design question in `HANDOVER.md`. |
| Returned loot still counts as stolen | When an exposure hands the loot back, the thief's "stole" total, clean steals and grudge hits keep the theft, and the victim keeps their "robbed" count. So a thief can finish the clean-thief goal or the grudge goal with loot that was returned. |
| Weekends | The nights are consecutive: a 24-hour-day game runs through weekends. |

## 12. Change log

| Date | Change |
| --- | --- |
| 17 October 2026 | This file created. It is the first point of reference; changes update it in the same commit. |
| 17 October 2026 | `/gm history` and `/gm hall-of-fame`: who played which alias and totals per person, from finished seasons only. The awards have titles (Sole Survivor, Frequent Flyer, Top of the Food Chain, Sticky Fingers, Herlock Sholmes, The Bouncer, Santa Paws, Mission Accomplished). |
| 17 October 2026 | The Hall of Fame comes with a picture (award cards and a totals table). |
| 17 October 2026 | Investigating finds food: `investigate_find` is 2 in `docs/game.json` (default 0). Gifts grow: `gift_bonus` is 1 live (default 0). New DM lines for both. New ledger reason `investigate_find`. |
| 17 October 2026 | An exposure returns the loot: `exposure_undo` is "full" in `docs/game.json` (default "none"). The exposed thief hands back what they took tonight to the victim, then pays the bounty. New ledger reason `exposed_return`. |
| 17 October 2026 | A game replays under the rules it started with: the start record freezes them, so changing `docs/game.json` only affects new games. |
| 17 October 2026 | `/gm pilot`: one command to archive, join, add sims and start (events gentle and ranges on by default). |
| 17 October 2026 | The last three nights show a countdown; night 10 says LAST NIGHT. |
| 17 October 2026 | Clean thief: the goal needs 3 successful steals before the first catch. Once you reach 3 it is locked in and a later catch does not fail it. /status tracks it ("2/3", goal met, goal lost). |
| 17 October 2026 | Radio is fixed phrases only (8 lines, one a day, anonymous), picked by clicks from /play or /radio. New line: "Someone should watch {a}'s back tonight." |
| 17 October 2026 | Wilderness events in Torch: `/gm start events:gentle` (one event a night, bad events hit the top third, good ones the bottom third). Story variants never repeat until all are used. |
| 17 October 2026 | Morning ration ranges in #news: `/gm start ranges:True` (🟢 7+, 🟡 3-6, 🔴 1-2, 🏴‍☠️ bandit). |
| 17 October 2026 | Live status board in #news with Play, Radio and My status buttons. |
| 17 October 2026 | The reveal is a picture (table plus award cards), with a text fallback. |
| 17 October 2026 | Fair deal of secret goals (like a deck, with a chain of targets) and a sixth goal, Detective. |
| 17 October 2026 | Gifts are 1 or 2 and the giver keeps at least 1. Quitters cannot be targeted and their food leaves the game. |
| 17 October 2026 | Night DMs explain every ration and say which night a guard covers. Only Torch speaks in #news and #radio (threads shut). |
| 17 October 2026 | Sims play with the simulator's own AI (beliefs rebuilt from the log on restart), deal a balanced cast by default (`cast` on `/gm pilot` and `/gm add-sims`), and post radio by personality (about 1.7 lines a night for eight). New DM line for a player who exposes their own thief. |
| 17 October 2026 | A new season avoids the aliases of the newest archived season. |
| 18 October 2026 | No rule change. The game core (log, replay, moves, quits, radio storage, sims, finish) moved from `bot/game.py` into `bot/core.py` (`GameCore`), so the live Godot rooms can share it; Torch's wording, schedule and outbox stay in `bot/game.py`. Refusals that moved: "The game is full.", "You haven't joined.", unknown alias, and the three radio refusals. Proven unchanged by `bot/tests/test_core_fixtures.py` (five full games, every record and reply byte for byte) and the golden master. |
