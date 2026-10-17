# Torch: architecture plan (v2)

Goal (owner, 17 Oct 2026): "carry on with one to four": (1) pull the engine out of the simulator behind
ports, (2) the Discord adapter, (3) run it against the F x D test server, (4) install it on the Pi.

v1 went through a hostile rules review (34 findings, 11 blockers). v2 answers every blocker; the "Review" column
below cites the finding number.

## Owner decisions (17 Oct 2026)

| Question | Decision |
| --- | --- |
| A player quits mid-game | Their food leaves the game (`quit_forfeit`, a destroy reason like `fine`); they become untargetable; objectives aimed at them are void |
| Gift size | 1 or 2, giver keeps at least 1; checked at submit, and a gift cut at resolve is reported to the giver (`gift_reduced`) |
| #radio timing | Batched: radio lines post with the 07:30 news, never live |
| Weekends | Paused: Friday night resolves at midnight, its news posts Monday 07:30; no eating Sat/Sun; 10 weekday rounds |

| Goal dealing | Fair deal, not independent dice: goal types dealt evenly from a deck; Grudge/Beat targets dealt as a chain so each player is the target of at most one goal, and never a mutual pair. Measured before: 66% of games had someone targeted 2+ times, 11% 3+ (`tools/target_pileup.py`, 1000 games) |
| New goal | **Detective**: expose a thief red-handed with `/investigate` at least once (2 points, like the others) |

Both goal changes land *after* the extraction is proven identical, then the batches and `tools/objective_stats.py`
are rerun so the owner sees the new rates before anyone plays.

Still open (engine keeps current behaviour, value recorded in `game_start`): two investigators on one thief both
paid; bounty on an empty or caught steal.

## Paradigm

Commands are the truth, outcomes are derived. The log stores, per night, the **moves** that were locked at the
deadline plus the **seed**, then the **outcome events** `resolve_night` produced from them. On start the bot
re-runs `resolve_night` on the stored moves and checks it reproduces the stored outcomes byte for byte (one
rules implementation, no second hand-written `apply`; Review 27). Outcome events keep LOG_FORMAT so the replay and
season pages work unchanged. `game_start` records `engine_version` and the full rules (including open-decision
values and `players = len(roster)`; Review 10, 11).

## Storage: three files, three jobs

| File | Holds | Never holds | Mode |
| --- | --- | --- | --- |
| `season.jsonl` | game events under **internal ids** (p01…p15) and aliases | Discord ids, real names, radio/DM text | 0600 |
| `identity.json` | internal id ↔ Discord id ↔ alias (decision 17: a separate locked table) | game events | 0600, never posted, deleted after the season |
| `texts.jsonl` | radio and DM bodies, by reference id; the log keeps only a hash | — | 0600; a `redaction` event + overwrite honours deletion (Review 4, 5) |

Atomic nights (Review 2): a night is written as ONE line `{"type": "night", "night": n, "moves": …, "seed": …,
"events": [...]}`, one write, one fsync. On start, a torn last line is cut off and logged. Moves before the
deadline are single lines too; the last valid move per player counts.

Outbox (Review 3, 23): every Discord side effect is `post_intent{id, channel, chunk}` → send (message carries the
id in a hidden marker) → `post_done{id, message_id}`. On restart an intent without a `done` checks channel history
for the marker before resending. DMs the same, plus `dm_failed`; `/results` replays last night's private lines
ephemerally because DMs can be closed (Review 17).

## Engine extraction (Review 1, 8, 12)

- `engine.resolve_night(state, moves, rules, rng)` draws from the caller's `rng` in the simulator's exact order:
  guards, caught thieves, thefts (`rng.shuffle(wants)`), scavenge `randint` per player in pid order, gifts in pid
  order, investigations. Moves are keyed by internal id and processed in sorted id order, never arrival order.
- Engine state holds game facts only: rations, bandit, guard_until, guards_used, next_guard_night, times_robbed,
  steals_ok/caught, rations_stolen, gifted_out, grudge_hits, quit.
- Everything that steers the AI stays in the simulator (suspicion, notes, caution, public_delta, rumours, the
  investigator radio roll, `ev` counters, stats): the sim reads the engine's events and keeps its own bookkeeping,
  drawing from the same `rng` right after the engine call. The golden master proves the sim is unchanged.
- The bot seeds each night from `sha256(f"{season_id}:{night}")`, so nights replay independently.

## Ports

| Port | Kind | Default | Test |
| --- | --- | --- | --- |
| GameService | driving: what Discord, the console and tests call (join, submit, status, results, gm_*) | `bot/app.py` | — |
| EventStore | driven | JSONL (above) | in-memory |
| IdentityStore | driven | `identity.json` | in-memory |
| Messenger | driven: post, DM, history lookup | discord.py | recording fake / console |
| Clock + Scheduler | driven | system time + asyncio timers from the round calendar | fake clock, compressed rounds |
| Alert | driven: "Torch is down / a post failed" | `notify-relay` on the Pi | list |
| Content | aliases + objective cards from `game.json` | file | fixture |

Discord types stay inside the Discord adapter (Review 28).

## Time (Review 7, 14, 15, 30)

- The deadline is judged by Discord's own timestamp (`interaction.created_at`), not the Pi clock: valid if
  `created_at < deadline_instant`. Resolve starts only after a `deadline_locked` line.
- The round calendar is explicit config (dates, deadline `00:00`, news `07:30`, weekends skipped) or a compressed
  pilot mode (a round every N minutes) so a whole game can run in an hour on the test server.
- systemd: `After=time-sync.target` with `systemd-time-wait-sync`; the bot refuses to schedule until the clock is
  synchronised.

## Discord rules (Review 6, 13, 18, 19, 20, 21)

- Every player command answers through one `reply_private()` (ephemeral, deferred ephemerally first); the global
  error handler is ephemeral; a test fails if any player path can answer publicly.
- Validation is server-side every time: target exists, isn't self, isn't quit, actor role (bandit: steal 1 or
  investigate only), gift 1 or 2, guard limit and cooldown.
- Targets: plain string option, aliases sorted alphabetically, no state in autocomplete, autocomplete never logged.
- `/radio`: length cap, `allowed_mentions=none`, markdown escaped, batched to 07:30.
- GM commands: guild only, checked against the GM role id server-side, confirm step for irreversible ones, every
  one logged as an `admin` event; `/gm status` shows who has moved, never rations.
- Config names the guild, channel ids and GM role; the bot ignores other guilds; startup fails if an id is missing.
- `/gm start` freezes the roster; later `/join` is refused.

## Commands

Players: `/join`, `/scavenge`, `/steal target`, `/guard`, `/investigate target`, `/gift target amount`, `/status`
(rations, guards left, objective, today's move), `/results` (last night's private lines), `/radio text`, `/quit`.
GM: `/gm start`, `/gm status`, `/gm resolve-now`, `/gm post-news`, `/gm pause`, `/gm radio-log`.

## Operations on the Pi (Review 22, 29)

`/opt/torch` (code + venv), `/var/lib/torch` (the three files, 0600, user `torch`), `/etc/torch/torch.env` (token,
0600). systemd `Restart=on-failure` with a start limit; journald gets internal ids and command names, never move
arguments or text. Nightly encrypted backup of `/var/lib/torch` off the Pi. Install script asserts Grysstof is not
in the game server (`list_bots.py`). Alert through `notify-relay` when Torch goes offline.

## Tests that break it (Testing HARD RULE, Review 26)

Engine: conservation every night across every rule variant; permuted submission order gives identical events;
self-targeting, quit targets, bandit moves, gift 0/3, guard limit exactly 3 and on the last night; two
investigators on one thief; guard + investigator on one thief; caught thief with 0 rations; odd split between
thieves; wash-gifting pair (logged as a finding for the owner, Review 25). Store: torn last line; crash between
every append; disk full. Outbox: crash between intent and send, between send and done (no duplicate post).
Time: move at deadline ±1 ms; clock jumping back. Discord: 429 and 403 on post; DMs closed.
Golden master: `docs/sim/tools/golden_master.py check bot/tests/golden` stays 31/31 identical.

## Rules compliance (`~/.claude/CLAUDE.md`, `~/.claude/rules/`)

| Rule | How |
| --- | --- |
| plan-passes-rules-review | v1 reviewed (34 findings); v2 answers the blockers |
| paradigm-fit-first | commands-as-truth with derived, verified outcome events |
| architectural-production-lens | driving + driven ports; impls chosen at wiring |
| delegated-work-is-a-state-change | outbox intents/done for every Discord side effect |
| logging-everywhere | structured logs at every port call, without move arguments or text (privacy) |
| testing hard rule | the adversarial list above, written before the code it tests |
| never commit secrets | token only in `.secrets/` (git-ignored) and `/etc/torch` |
| CPU cap | golden-master and test runs are single-process |

## Build order

1. `engine/` extracted, sim switched to it, golden master 31/31, engine tests green.
2. `bot/app.py` + stores + console messenger + fake clock: a full compressed game from the console.
3. Discord adapter against F x D; owner plays; one forced restart mid-game.
4. Pi install; Torch online; restart survives; alert fires when stopped.
