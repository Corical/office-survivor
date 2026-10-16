# Survivors: handover

Written 16 Oct 2026 at the end of the first design session (updated the same evening with luck and events, replay logging and aliases), for whoever (person or agent) picks this up next. Read this first, then `README.md`.

## Status in one minute

- **Game design:** done for phase 1 (rules v2). Camps (alliances) are deferred to phase 2. A few edge cases still need a decision (see "Known inconsistencies").
- **Balance:** tested in a simulator across 43 rule sets, 3 office personality mixes and "all-in" strategies. v2 fixes everything the first draft got wrong. One open worry: when simulated players *learn*, they abandon guarding and thieves gain ground.
- **Simulator:** working, reproducible, reads the shared `game.json`. Three player brains: fixed personalities, adaptive learning, and Jev (built and tested offline, never run against the real API).
- **Explainer video:** script (about 2:34), storyboard and a regenerable production kit exist. Nothing has been drawn, recorded or rendered yet.
- **New ideas, not yet tested:** random events (the "apparition" and friends), an underdog bonus for the least-chosen action, luck that carries over between seasons, beginner's luck, and cosmetic titles. They're written up in the rules doc under "Luck and random events (proposed, behind the scenes)". Players won't be told how they work. The simulator doesn't model them yet.
- **Replay logging:** every simulated game can now write a complete log of everything that happened, and `sim/replay.py` rebuilds the game from the log alone. The bot must write the same format (`sim/LOG_FORMAT.md`), so a season-recap animation can be built and tested on simulated games before the real season ends.
- **Aliases:** everyone plays under a secret, bot-assigned alias (decision 17). The rules doc, the video script, `game.json` example names and the simulator all use aliases now.
- **Discord bot:** not started. A plan is below.
- **Where things ran:** everything ran in Claude's cloud workspace. Nothing has been installed or deployed on the Raspberry Pi.

## What Survivors is (the brief)

An opt-in, two-week survival game for the whole company (about 15 people), played in Discord in about two minutes a day. Inspired by DayZ: what makes it fun is real colleagues choosing to help or betray each other. The owner's goals, in his words: something everyone talks about at the water cooler, mysterious, with real options for blindsiding, alliances possible, betrayal always on the cards. It must not be intrusive, and needs no special software beyond Discord. The bot runs on the owner's always-on Raspberry Pi.

## Where everything is

| Thing | Where |
| --- | --- |
| Rules doc (human-readable rules, written by hand) | Claude doc "Survivors: Office Game Rules", https://claude.ai/code/artifact/25ac394f-6632-4708-b011-4324fc9b2e65 |
| Video script doc (storyboard, narration, look and sound) | Claude doc "Survivors: Explainer Video Script", https://claude.ai/code/artifact/3a65813b-1184-4d96-b576-82667e61863c |
| Every game number | `game.json` (read by the simulator and the video build) |
| Simulator | `sim/survivors_sim.py`, `sim/brains.py`, `sim/experiments.py`, `sim/check_invariants.py` |
| Replay log format and tools | `sim/LOG_FORMAT.md`, `sim/replay.py` |
| All test results | `sim/results/` (see "Test history") |
| Video production kit | `video/` (start with `video/AGENT.md`) |

Snapshots of both docs, taken at handover, are in `docs/rules.md` and `docs/video_script.md`, so this folder works on its own. The two live docs are private to the owner until shared from their Share menu. Neither updates automatically: if `game.json` changes, update the rules doc and rerun `video/build.py`.

## Current rules (v2)

These are the values in `game.json` (version "v2 (16 Oct 2026)").

- **Aliases:** everyone plays under a secret alias assigned at `/join` (e.g. RustyKettle). All game output uses aliases; the reveal and stats never show real names. #town-square is normal chat where people talk as themselves about aliases.
- **Length:** 10 weekday rounds over two weeks, about 15 players.
- **Each day:** one secret action via slash command, locked at 23:59. Results resolve and post in #news at 07:30. You can change your action until the deadline; the last one counts. Miss the deadline and you auto-scavenge.
- **Food:** start with 7 rations, eat 1 a night.
- **Scavenge:** find 0–2 rations at random.
- **Steal @player:** take 2, anonymously. Several thieves on one target split what's there.
- **Guard:** protects you for 2 nights (tonight and tomorrow). Any thief who tries is named publicly and pays the guard 2. **Max 3 guards per player per game.** You find no food the night you set one.
- **Investigate @player:** the bot DMs you what they did that night. If they stole, they're exposed in #news and pay you 1.
- **Gift @player:** give rations secretly. Only giver and receiver know.
- **Bandits:** at 0 rations you become a bandit. Bandits don't eat, can only steal or investigate, take 1 per steal, and rejoin as survivors at 3 rations.
- **Radio:** one anonymous message a day in #radio, logged under the sender's alias. Only abuse justifies looking up who's behind it.
- **Secret objectives:** one private goal card each, worth 2 points. The card types used: finish with more rations than @player; get robbed at least once and still extract; steal 3 times without being caught; give away 3 rations; successfully rob @player at least once.
- **Extraction:** after the last night, seats for about a third of players (5 of 15) go to the survivors with the most rations. Ties go to whoever gave away the most, then a coin flip. Bandits can't extract.
- **Scoring:** seat 3 points, secret goal 2, survived without a seat 1. Highest total wins; a tie goes to whoever gave away the most.
- **Final reveal:** the last #news post unmasks every objective, theft and betrayal, night by night.
- **Phase 2 (not in v2):** camps, a shared stash any member can secretly loot. Designed in the rules doc, not simulated.
- **Guardrails:** opt-in, quit any time, rations are the only currency (no work tasks, money or real favours), radio logged under aliases, Game Master sits out or never peeks at the database, one #news post a day and no pings.

Night resolution order (as the simulator implements it): guards go up → steals against guarded targets are caught (thief pays guard) → other steals resolve and split → scavenging → gifts → investigations (DMs, exposures and bounties) → everyone eats → anyone at 0 becomes a bandit, bandits at 3+ rejoin → #news at 07:30.

## Decision log

In order, with the reason for each.

1. **Discord bot on the Pi, slash commands, ephemeral replies.** Everyone is already on Discord, and the Pi is always on. Keep it a separate Discord app and systemd service from the owner's existing bot on the Pi, so one can't take the other down.
2. **Hidden information as the core.** You always know *what* happened, rarely *who*. The gap is what people talk about.
3. **#news at 07:30, not 17:00.** The morning reveal lands right before coffee.
4. **Camps moved to phase 2.** The owner wanted people to learn the basic game first.
5. **First simulation (100 games, first draft rules) showed:** about 11 of 15 players hit zero at some point, half ended as bandits, bandits came back 5–6 times a game, guards caught only 13% of steals, 39–43% of finales were coin flips, and "give away 5" was never completed.
6. **First recommendation (R1):** start 7, bandits steal 1, 2-night guard, caught thief pays the guard 2, kindness tiebreaks, easier objectives. This fixed deaths, comebacks, catch rate and coin flips.
7. **Winner tiebreak by generosity, not rations.** Breaking win ties by rations made hoarders and guard-spammers dominant and generous players almost never won.
8. **Extremes test exposed a loophole in R1.** With a 2-night guard you can guard, scavenge while protected, and repeat. One such "turtle" took a seat 86% of the time (normal players: 33%).
9. **Fix: max 3 guards per game, plus the investigation bounty.** The guard cap killed the turtle (seat rate down to 36%). The bounty was the only change that also stopped a lone dedicated thief from beating everyone (1.85× down to 1.04× a fair share of wins).
10. **Steal size stays 2 (open dial).** At 1, crime stops paying (a lone thief wins about 0.1× their share), but robberies make weaker headlines. The owner hasn't decided; 2 is the current pick.
11. **One rules file drives everything.** The owner asked that any change be easy to regenerate, so `game.json` feeds the simulator and the video templates, and `video/build.py` lists only what a change affects.
12. **Smarter players at small scale.** The owner approved adding Jev for player decisions on small runs. It's implemented but not yet run live.
13. **A flat random bonus for guarding was tested and not adopted.** The owner suggested giving under-used strategies a chance of an advantage. A 50% chance of +1 food while guarding barely brought guarding back among learning players (catch rate 14% to 15%) and made a lone thief stronger in a normal office (1.04× to 1.30×). See "Guard bonus" under Test history.
14. **Luck and random events proposed, to be tested before adoption.** All from the owner:
    - **Random events:** a daily random roll on the Pi, mostly private. The "apparition" leaves a ration; others are lucky finds, rats, one-use mystery items, a public supply drop, or a storm.
    - **Underdog bonus:** the least-chosen action each night has a chance of a lucky find. This replaces the flat guard bonus, because it balances itself.
    - **Luck across seasons:** capped at +3, earned by interesting play rather than just winning, partly fading between seasons.
    - **Beginner's luck:** a hidden boost for first-season players that fades, to stop veterans running away with it.
    - **Titles:** cosmetic Discord roles.

    The owner's framing: none of this has to be in the game; it's worth exploring. The game isn't meant to run for years, so progression only needs to work over a handful of seasons.
15. **Hidden mechanics.** Players are never told how luck, the underdog bonus, beginner's luck or event odds work; they just experience the events. Those rules exist for balancing only, so they stay out of the explainer video and any player-facing rules. The rules doc marks the section "behind the scenes".
16. **Log literally everything.** The owner wants the whole season replayable, so it can end with an animation of exactly how things happened. The simulator writes the same log the bot will, so simulated games are test data for the replay and animation tools. The format is append-only JSON Lines: every action, change of mind, random roll, ration change (as a ledger), message and DM. `replay.py --check` proves a log is complete by rebuilding every ration count from it.

17. **Secret aliases.** The owner's idea: everyone enrols under an alias so betrayals can't be pinned on a person. In detail:
    - The bot assigns fun names, rather than letting people pick, because a familiar handle would give its owner away.
    - Every game message uses aliases. The alias-to-account link is in a separate locked table that even the Game Master can't see during the season.
    - The reveal shows aliases only, and anyone may unmask themselves.
    - Open question: keep an alias across seasons (builds a legend) or get a new one each season (fresher mystery, with luck tied to the real account behind the scenes).
18. **Keep it light.** The owner rejected extra systems such as bot-relayed chat, private whispers between aliases, and daily discussion prompts: the game must not eat into work time. #town-square stays ordinary, optional chat. People talk as themselves and role-play about aliases ("RustyKettle got me"), and giving yourself away is your own choice.
19. **One log, handled carefully.** The replay log is the single source of truth; no second copy goes into the owner's personal memory system (fed by his Discord logger, grysstof) during the season.
    - **Pseudonymous:** the log uses aliases and internal ids.
    - **Locked until the reveal.**
    - **Retention:** moves are kept to balance future seasons; radio posts are deleted after the recap; anyone can have their data deleted.
    - **Open chat:** goes in the replay only if players are told up front.
    - **After a season:** its moves can be loaded into a separate space for conversational analysis, kept apart from work data.
    - **Private messages between players:** never collected.

## The simulator

### How it models the game

- **Players:** 15 per game, each given a personality drawn from an office mix. Default mix: casual 25%, farmer 20%, opportunist 15%, paranoid 10%, saint 8%, detective 8%, shark 7%, chaos 7%. Two alternative mixes exist, "honest" and "cutthroat", to check findings hold for different crowds.
- **Personalities** (`ARCH` in `survivors_sim.py`): base odds for each action, plus a chance of missing the deadline (casual 35%, others 5–10%).
- **Each night's decision** starts from the personality odds, then adjusts: robbed last night → more guarding; knows who robbed them → revenge steal; 2 or fewer rations → more stealing, no gifts; 8+ rations → more guarding; final night → more stealing and guarding; caught stealing → stealing odds halve, permanently; secret objective → nudges toward it.
- **Targets:** thieves pick whoever *looks* richest (starting rations minus publicly known losses, plus noise) and avoid people who recently caught a thief. Investigators pick their top suspect. Gifts go to whoever looks worst off. Rations are private, as in the real game.
- **Radio:** investigators broadcast true accusations (when there's no bounty); chaos and shark players spread rumours.
- **"Ultra" test players:** always guard, turtle (guard whenever not protected, otherwise scavenge), always steal, always scavenge, always gift, always investigate.
- **Brains** (`--brain`): `rules` (default, the personality logic above), `adaptive` (each player shifts toward moves that gained them rations), and `jev` (see below).

### Commands

```
python3 sim/survivors_sim.py batch --runs 100          stats + automatic warnings, current rules
python3 sim/survivors_sim.py extremes                  everyone / 1 / 3 / 5 players going all-in on one action
python3 sim/survivors_sim.py compare baseline v1_original steal_1
python3 sim/survivors_sim.py reel --seed 11            one game as #news posts with what really happened
python3 sim/survivors_sim.py rules                     current values, named variants, personalities
python3 sim/survivors_sim.py batch --brain adaptive    players that learn
python3 sim/experiments.py                             rerun the whole test history (about 2 minutes)
python3 sim/check_invariants.py                        engine sanity checks; run after any engine change
python3 sim/survivors_sim.py reel --log game.jsonl     write the complete replay log of one game
python3 sim/replay.py game.jsonl [--check | --player NAME | --frames out.json]
```

Useful options: `--variant NAME` (named rule sets, combine with `+`), `--set key=value`, `--mix honest|cutthroat`, `--rules path/to/game.json` (default `../game.json`; `none` for built-in values).

### Limitations

- **The personalities are guesses.** Treat the numbers as a stress test of the rules, not a prediction of how colleagues will play.
- **Rule-brain players don't learn or talk.** No deals, no lying in DMs, no coordinated grudges. Real players will do all of that.
- **The adaptive brain only counts what a move gained.** A guard that prevented a theft scores zero, so learning players undervalue guarding. A better reward would credit avoided losses.
- **Gift size is fixed** (1, or 2 when holding 7+). The real game lets players choose.
- **Office size is assumed to be 15.** Seats are a third of players, so a different turnout changes the seat count and the video's "five seats".
- **The chat numbers from the session differ slightly from `sim/results/`.** The session used different seeds and run counts as it went. `sim/results/` is the reference; every number there reproduces exactly with the commands above.

## Test history

Full tables: `sim/results/experiments.md` (readable) and `sim/results/experiments.csv` (every metric). 300 games per config and per mix, seed 7.

### Headline comparison (default office, 300 games each)

| Measure | First draft (v1) | First pick (R1) | Current (v2) |
| --- | --- | --- | --- |
| Alive at the end (of 15) | 7.1 | 10.6 | 10.9 |
| Hit zero at some point | 11.2 | 5.6 | 5.3 |
| Bandit comebacks | 5.6 | 1.6 | 1.5 |
| Steals caught by a guard | 13% | 28% | 24% |
| Robberies per night | 2.6 | 1.9 | 2.0 |
| Last seat decided by coin flip | 39% | 17% | 18% |
| Seats won by heavy thieves (3+ steals) | 49% | 25% | 26% |
| Lone always-stealer: wins vs fair, seat rate | 1.92×, 54% | 1.55×, 50% | 1.04×, 41% |
| Lone turtle: wins vs fair, seat rate | 0.88×, 37% | 1.07×, 86% | 0.33×, 36% |

### The phases

1. **First draft.** Too deadly, revolving-door bandits, weak guards, coin-flip finales, a dominant thief strategy, and objectives that were either impossible ("give away 5": 0%) or automatic ("make sure @player doesn't extract": 69%).
2. **Single fixes, one knob at a time** (14 configs). Starting rations, scavenge range, guard reward and income, harsher catches, steal size, bandit rejoin and steal size, 2-night guard, kindness tiebreak, objective thresholds, missed-deadline penalty, investigation bounty. Lessons: more starting food fixes deaths but makes thieves stronger, because there's more to steal (a lone thief goes from 1.92× to 2.46×). A cheaper bandit steal slows comebacks (5.6 to 3.2). A 2-night guard is the only knob that meaningfully raises the catch rate (13% to 21%). The kindness tiebreak cuts coin flips (39% to 23%).
3. **Combined packages** (7 configs). Three economy options (start 7, scavenge 1–2, scavenge 0–3) with the other fixes. Scavenge 1–2 rewards doing nothing: a lone always-scavenger wins 2.3× their share and takes a seat about 80% of the time. So start 7 was preferred. A missed-deadline penalty made the game harsher (10.3 to 9.1 alive) and helped thieves, so it was dropped.
4. **R1 and variants** (7 configs). R1 fixed the economy. Breaking win ties by rations made guard-hoarders dominant, so ties go to the most generous.
5. **Fixing the turtle loophole** (12 configs). Guard limits, cooldowns, 1-night guards, guard income, harsher catches, steal size and the bounty. Going back to a 1-night guard made the lone thief dominant again (2.5–3×). Limit 3 plus bounty was the only combination that kept 2-ration steals while the turtle (0.33×) and the lone thief (1.04×) both stayed at or below a fair share, with the catch rate near 24%. Limit 3 with 1-ration steals also balances, but crime stops paying.
6. **Current rules.** v2, and v2 with 1-ration steals for the open dial.

### All-in strategies (`sim/results/*_extremes_300.txt`)

Whole office playing one way, current rules:

| Everyone… | Alive at end | Robberies/night | Quiet nights (of 10) |
| --- | --- | --- | --- |
| plays normally | 10.9 | 2.0 | 0.4 |
| always steals | 0.5 | 5.5 | 0.0 |
| always guards | 3.5 | 1.1 | 6.0 |
| turtles (guard, scavenge, repeat) | 14.0 | 0.1 | 8.3 |
| always scavenges | 14.9 | 0.0 | 9.9 |

If everyone plays safe, the game goes dead quiet. That's not stable: a lone thief in a cautious office cleans up, so drama returns as soon as anyone gets bold.

One player going all-in, current rules (fair = 1.0): always steal 1.04×, always gift 0.80×, turtle 0.33×, always scavenge 0.30×, always guard 0.10×, always investigate 0.00×. No all-in strategy beats mixing it up. In the first draft a lone thief won 1.92× their share.

### Learning players (`sim/results/*_adaptive.txt`)

With the adaptive brain on v2: more people survive (12.4 of 15), but players drop guarding (catch rate 24% → 13%) and gifting ("give away 3" completed 35% → 3%), and thief personalities win far more (sharks about 2.9× their share). The likely cause is the reward blind spot under Limitations: guards look worthless to a player who only counts gains. **This is the most important thing to check next.** Either improve the adaptive reward and rerun, or run Jev players. If real players also stop guarding, consider giving guards a little income (`guard_income_max: 1`).

### Guard bonus (`sim/results/guard_bonus_test.txt`)

Question: does a random reward for guarding (50% chance of +1 food the night you guard, `guard_income_max: 1`) bring guarding back?

| Measure | No bonus | With bonus |
| --- | --- | --- |
| Learning players: steals caught by a guard | 14% | 15% |
| Learning players: paranoid players' wins (10% of office) | 7% | 13% |
| Learning players: sharks' wins (7% of office) | 20% | 18% |
| Normal players: lone always-stealer, wins vs fair | 1.04× | 1.30× |

Answer: barely. Cautious players do a bit better, but guarding isn't used much more and thieves gain. This led to the underdog-bonus idea in decision 14.

### Secret objective completion (default office)

| Objective | First draft | Current |
| --- | --- | --- |
| More rations than @player | 40% | 48% |
| Robbed and still extract | 17% (needed 2 robberies) | 29% (needs 1) |
| Steal 3 times, never caught | 35% | 17% |
| Give away rations | 0% (5 needed) | 35% (3 needed) |
| Grudge against @player | 69% ("doesn't extract") | 40% ("rob them once") |

### Jev (smart players)

- **What it is:** TypeSafe's Jev, a "System One" model that returns typed choices with probabilities instead of text. Each smart player's situation is written as plain text and Jev picks one move from the legal options. `sim/results/jev_example_request.json` shows exactly what one call sends.
- **Status:** implemented in `sim/brains.py` and tested end to end with the offline mock (`--jev-mock`). **Never called against the real API:** there was no API key, and Jev is early access with a waitlist.
- **Wire format:** taken from LiteLLM's pass-through docs (`POST https://api.typesafe.ai/v1/systemone`, Bearer auth with `TYPESAFE_API_KEY`). Verify the endpoint and auth header against TypeSafe's own API reference before the first real run.
- **Cost:** the mock estimates about 1,200 input tokens per decision and 150 decisions per game, so about $0.01 per game at TypeSafe's launch price of $0.042 per million input tokens. 50 games is under $1. (The session's first guess of "a few cents for 50 games" was too low.) `--max-calls` caps spending at 3,000 calls by default.
- **First real run:** `TYPESAFE_API_KEY=... python3 sim/survivors_sim.py reel --brain jev --smart 5`, then `batch --runs 20 --brain jev`.
- **Sources:** [TypeSafe launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [Pydantic AI TypeSafe docs](https://pydantic.dev/docs/ai/models/typesafe.md), [LiteLLM TypeSafe pass-through docs](https://docs.litellm.ai/docs/pass_through/typesafe.md).

## Explainer video

- **Script:** 14 scenes, about 2:30, written for non-technical colleagues. Storyboard, narration and look-and-sound guide are in the video script doc.
- **Tools:** the owner has VectorCraft and EffectCraft installed and will install FigCraft and FilmCraft (all from getartcraft.com, all early alpha or in development, all controllable over MCP). SoundCraft is optional. None were connected to this session.
- **Kit:** `video/AGENT.md` is the brief for the agent that drives those tools. It covers 6 stages (voiceover → assets → chat screens → scenes → audio mix → final), what each reads and writes, and how to mark work done. `video/build.py` turns `game.json` plus `video/source/` into ready specs and captions, and lists only what needs (re)doing.
- **Needs a person:** someone to read the voiceover (or a text-to-speech tool) and a royalty-free music track.
- **Open:** launch date (a `[LAUNCH DATE]` placeholder in `game.json`), final game name, narrator, and whether to also cut a 30-second teaser.
- **Brand rule:** chat screens look like a generic chat app. Never use the Discord logo. Only invented names on screen.
- **Aliases:** scene 14 now tells players they'll get a secret alias, and every on-screen name (`game.json` → `example_names`) is an alias such as RustyKettle. The script runs about 2:34.
- **Luck and events:** stay out of the video, because the mechanics are hidden from players (decision 15). At most, a one-line tease like "and expect the unexpected" could be added to the script in `video/source/script.json`.

## Discord bot: plan (not started)

- **Stack:** Python, discord.py, SQLite, a systemd service on the Pi. Separate Discord application and token from the existing bot there.
- **Channels:** #town-square (open chat), #news and #radio (bot posts only).
- **Commands:** `/join`, `/status`, `/scavenge`, `/steal`, `/guard`, `/investigate`, `/gift`, `/radio`, `/quit`. All replies ephemeral. Commands that name someone (steal, investigate, gift) take an alias, with autocomplete. Phase 2 adds `/camp`.
- **Aliases (decision 17):** `/join` assigns a random fun name from a list and tells the player privately. Store the alias-to-Discord-id link in its own table, unreadable through any Game Master command until the reveal. #news, #radio and the log only ever use aliases.
- **Schedule:** actions lock at 23:59; resolve and post #news at 07:30, weekdays, Africa/Johannesburg time.
- **Data:** players, rounds, actions per round, guards used, objectives, radio messages with their real senders (Game Master only).
- **Logging (decision 16):** write every event in the format in `sim/LOG_FORMAT.md`, including the bot-only events listed there: commands, changes of mind, DMs, random rolls, Game Master actions. Run `python3 sim/replay.py season.jsonl --check` on the real log every night as a health check. If it fails, something wasn't logged.
- **Fairness:** one seeded random roll per round, saved, so any result can be audited afterwards.
- **Strong recommendation:** move the night-resolution code out of the simulator into a shared module and have both the bot and the simulator import it. Then the balance tests always test the real rules and the two can't drift apart.
- **Game Master tooling:** admin-only commands to pause a round, fix a mistake, and read the radio log. No command that shows anyone's rations mid-game.
- **If luck and events are adopted:**
  - An event scheduler that rolls once a day at a random time, seeded and logged, and delivers private events by DM.
  - A players table that outlives a single game: luck, seasons played, titles.
  - Discord roles for titles.
  - Event odds and sizes read from `game.json`, like every other number.

## Known inconsistencies and decisions still needed

1. **Order of investigations vs eating.** The simulator settles investigation bounties *before* everyone eats (moved there to fix a bug where paying a bounty could leave a survivor at 0 rations). The rules doc lists investigations after eating. Pick the simulator's order and update the doc.
2. **Double penalty.** If a thief targets someone who's guarding *and* an investigator is watching the thief, the simulator charges both (pays the guard 2, then the investigator 1). Decide whether an attempted, caught theft counts as "stealing" for the bounty.
3. **Guarding while already protected.** The simulator treats it as a wasted night that doesn't use up a guard. The bot should probably refuse it with a message.
4. **Gift amounts.** The simulator gives 1 (2 when the giver holds 7+). The bot lets players choose; decide whether there's a maximum.
5. **Turnout.** Seats are a third of players. Confirm the real head count once people opt in, then update `players` in `game.json` and rerun the video build.
6. **Open dials from the rules doc:** steal size (2 or 1), secret roles (none for game one is the current pick), extraction method (ration ranking or group vote), length (10 rounds or a 5-round pilot).

## Suggested next steps, in order

1. Settle the inconsistencies and open dials above, and update the rules doc and `game.json`.
2. Check the learning-player worry: improve the adaptive reward to credit avoided theft, rerun, and do a small real Jev run once there's an API key.
3. Simulate the luck and events ideas (decision 14) before adopting any of them. The owner sees this as needed for balancing.
   - **Config:** add an `events` block to `game.json` (each event's daily chance, effect and size, private or public), plus `underdog_bonus_chance` and luck settings: cap, how luck is earned, fade between seasons, beginner's boost and how fast it fades.
   - **Engine:** in `survivors_sim.py`, roll events once per night (private ones add notes for the smart brains), apply the underdog bonus after counting tonight's actions, and let luck tilt event odds.
   - **Seasons:** add a mode that plays several games back to back with the same named players, carrying luck over and adding a few newcomers each season.
   - **Measure:** veteran vs newcomer win share by season, whether all five actions stay in use, quiet nights, and the existing balance and all-in checks.
4. Build the bot around a shared resolution module, then playtest with 4–6 volunteers over a few compressed days before the company launch.
5. Produce the video once FigCraft and FilmCraft are installed and the Craft MCP servers are connected.
   Later, the season-recap animation: build it from `replay.py --frames` output on simulated logs now (`sim/results/sample_game_v2_frames.json`), reusing the explainer's avatars, tins and icons, then run it on the real log after the season.
6. Design and simulate camps for phase 2. The simulator has no camp mechanics yet.

## Results files

| File | What it is |
| --- | --- |
| `sim/results/experiments.md`, `.csv` | Every config tested, all metrics, by phase |
| `sim/results/v1_first_draft_batch_100.txt`, `r1_first_pick_batch_100.txt`, `v2_current_batch_100.txt` | Full 100-game reports (the size the owner asked for) |
| `sim/results/*_extremes_300.txt` | All-in strategy tests for v1, R1 and v2 |
| `sim/results/v1_r1_v2_compare_300.txt` | Side by side, including v2 with 1-ration steals |
| `sim/results/*_batch_100_adaptive.txt` | v1 and v2 with learning players |
| `sim/results/sample_game_*.txt` | One full game each for v1, v2, and v2 with mock-Jev players, told as #news with what really happened |
| `sim/results/jev_example_request.json` | Exactly what one Jev call sends |
| `sim/results/guard_bonus_test.txt` | The flat guard-bonus test (decision 13) |
| `sim/results/sample_game_v2_log.jsonl` | A complete replay log of one simulated game (seed 11) |
| `sim/results/sample_game_v2_replay.txt` | That game rebuilt from the log alone and told night by night |
| `sim/results/sample_game_v2_frames.json` | Per-night frames from the same game, the input for a recap animation |

## Second session, 16 Oct 2026 evening

### What was added

| Thing | Where | Notes |
| --- | --- | --- |
| Architecture page | `pages/survivors-architecture.html`, live at https://claude.ai/artifact/CQd8CUW8CvGVx8AHWDuveK | Where everything runs, one game day, logging, every part, code split, open items |
| Game replay page | `pages/replay/` (template + `build_replay.py`), live at https://claude.ai/artifact/CdXPvaG1qs5M8oZDGrkk4b | Night by night: what #news showed, what really happened, every move and why, what players can see, others' guess vs real rations |
| Replay logs behind it | `sim/results/replays/` | Typical game (seed 30), most dramatic of 300 (seed 33), handover sample (seed 11), seed 11 with 5 live Jev players |
| "Why" in the log | `survivors_sim.py` (`choose` / `_choose`, target pickers) | Every rules-brain `action` event now has `why` (reasons) and `odds`. Proven not to change results: batch, adaptive batch and seed 11 log identical apart from the new fields |
| Tools | `sim/tools/pick_games.py`, `sim/tools/leader_hold.py` | Pick typical/dramatic games; how often the mid-game leader wins |
| Jev wired for real | `sim/brains.py` | Key read from `../.secrets/typesafe.env` (git-ignored) or `TYPESAFE_API_KEY`. `metadata` now only sent to the mock (undocumented in TypeSafe's API). Live calls work: model `jev-1.13.0`, ~2,900 input tokens and ~420 ms per decision, ~$0.006 per 5-player game |
| CPU cap | `sim/experiments.py` | Defaults to half the logical processors and below-normal priority (it pinned every core before) |
| Secrets slots | `../.secrets/typesafe.env`, `../.secrets/discord.env` | Outside `docs/`, git-ignored |

### Verified

- `check_invariants.py` passes; `replay.py --check` passes on every log.
- All 43 configs in `experiments.csv` reproduce exactly on the current engine (rerun on a copy).
- The night order (thefts from start-of-night rations → scavenge → gifts → investigations → eat → bandit check) is what every run used. Nobody can go below 0; death is only checked at the end of the night.

### Found

1. **Rations created from nothing.** When a caught thief can't pay, the thief pays only what they have (down to 0), but the guard still receives the full `guard_reward`. Same when someone is robbed and caught the same night. 19 cases in 3 games. Present in every balance result so far, so guarding is slightly flattered. Needs a rule decision, then rerun the tables.
2. **Double bounty.** Two investigators watching the same thief both get paid (seed 30, night 4).
3. **Leader after night 5** takes a seat 77% of the time but wins only 21% (random 7%), because secret goals carry points. Use this as the gate for random events: an event that pushes it up is rejected.
4. **Public guess vs truth.** From #news alone, the guess of someone's rations is exact only 15–34% of nights; off by 3+ on 12–21%.
5. **Jev play quality.** One flat 45-option question with prose state: no Jev player guarded in 100 decisions, players fixated on one target, one fed the rival it had to beat. Same seed + top pick still gives a different game each run. Parked by the owner; fix would be split questions + structured state.
6. **Action colours** (green/red/blue/amber/purple, from the video style) fail colour-blind checks (red–green ΔE 2.0). Keep the action word on every use.
7. **Grysstof** (`grysstof-discord.service` on the Pi) captures every channel of every server it's in, with backfill. Keep it out of the game's server or deny it View Channel.
8. **"Two minutes a day" is unmeasured.** The pilot's command log (timestamps, `/status` checks, work-hours activity) should measure it.

### Decisions still open (owner)

| Decision | Options |
| --- | --- |
| Guard payout when the thief can't pay | Guard gets only what's paid · game pays the difference |
| #radio timing | Batched with 07:30 news · batched at 17:00 · live (only daytime interruption today) |
| Double bounty | Both paid · first only · split |
| Bounty on an empty or caught steal | Counts · doesn't |
| Pilot | 5 rounds on the test server first |

### Bot preparation

- Separate Discord app and bot, test server first. Token and server id go in `../.secrets/discord.env`. No privileged intents needed.
- Pi: Raspberry Pi 4, Debian 13, Python 3.13.5, ~1.8 GB RAM free, 87 GB disk, already on Africa/Johannesburg, 18 systemd services, `notify-relay.service` available for alerts.
- Stack: discord.py 2.x, SQLite, `season.jsonl`, systemd, no Docker. Engine stays chat-agnostic behind a Messenger/Clock/Random/EventLog/Store contract; Discord is one adapter.
