# Torch build log

Running ledger for the bot, newest findings added as they happen. The plan is `PLAN.md`.

## Setup facts

| Item | Value |
| --- | --- |
| Discord app | Torch (bot id 1560879015139475487), Server Members + Message Content intents on |
| Test server | F x D: 13 members, 12 of them bots (Torch + 11 FileX agents) |
| Game channels | Category **Survivors**: `#town-square`, `#news` (people read-only), `#radio` (people read-only, posts go through Torch) |
| Secrets | `.secrets/discord.env` (`DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`), git-ignored |
| Pi | `ssh pi` (Tailscale 100.114.85.20, user corical); Python 3.13.5; Africa/Johannesburg, NTP synced; 87 GB free; apps live in `/opt/<app>` as systemd services |
| Grysstof | `grysstof-discord` runs on the Pi but is **not** a member of F x D (checked with `list_bots.py`) |

## Tools (`bot/tools/`, all read-only unless stated)

| Tool | Does |
| --- | --- |
| `check_discord.py` | Token logs in as whom, intents, server name, missing game channels |
| `list_bots.py` | Every bot member of the server and its role count |
| `setup_channels.py` | Creates/repairs the category and channels; changes nothing without `--apply`; idempotent |
| `verify_channels.py` | Reads the overwrites back from Discord and checks them; exit 1 if anything is wrong |

## Traps already hit

| Date | What happened | Fix |
| --- | --- | --- |
| 17 Oct 2026 | Locking other bots out by their *role* missed 6 of 11: a bot invited without permissions has no role | deny every bot *member* by user id as well; `verify_channels.py` reads it back from Discord |
| 17 Oct 2026 | `python -I` doesn't import from the current folder, so a one-liner couldn't import `check_discord` | put checks in `bot/tools/*.py`, which add their own folder to `sys.path` |

## Step 1: engine extracted (17 Oct 2026)

`engine/` (rules, player facts, `resolve_night`) holds the night's rules; `docs/sim/survivors_sim.py` calls it and
keeps its AI bookkeeping in `SimObserver` hooks placed where it used to update inline (so the no-bounty radio
roll draws from the rng in the same order). Simulator: 261 lines out, 73 in.

| Check | Result |
| --- | --- |
| Golden master (20 rules games, 10 adaptive games as full event logs, 300-game batch) | 31/31 identical |
| Old vs new simulator, 100-game batch on 7 rule variants (no_bounty, v1_original, gift_bonus, guard_income, catch_1, guard_cooldown_1, missed_half) | all identical |

The engine has no clock: nights are numbers. Real dates, the midnight deadline, the 07:30 post or a
5-minute compressed day are all scheduler config (owner, 17 Oct 2026: "every five minutes is a day").

## Golden master for the engine extraction

`docs/sim/tools/golden_master.py record|check bot/tests/golden`: 20 rules-player games and 10 adaptive games
as full event logs, plus the 300-game batch report. Recorded before any engine code moved (17 Oct 2026,
31 files); a second run matched byte for byte, so the simulator is deterministic and any difference after the
extraction is a real change.
