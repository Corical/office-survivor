# Arena: live rooms (Godot client)

The rules of the game itself are in `docs/MECHANICS.md`; a room plays exactly those rules, with the official
`docs/game.json`. This file is everything a live room adds: seats, rounds on a timer, lock-in, early advance, bots,
reconnects and the protocol. `arena/tests/test_arena_doc.py` fails when this file and the code disagree: every change
to room behaviour updates this file in the same commit.

Code: `arena/room.py` (rounds), `arena/views.py` (what each seat sees), `arena/lines.py` (line codes),
`arena/server.py` (WebSocket). The game core is shared with Torch: `bot/core.py`.

## 1. A room

| What | Rule |
|---|---|
| Seats | 4 per room (owner, 18 Oct 2026). Humans take seats in the lobby; at the start, bots fill the empty ones. |
| Code | 4 letters, no I and no O, so it can be read aloud. Not case sensitive. |
| Host | The lowest connected seat. Only the host can start. If the host drops, the next seat becomes host. |
| Aliases | Every seat gets a secret alias from the official pool. No display names, ever (owner decision 7). |
| Radio | The 8 fixed phrases from MECHANICS.md section 9, one a round. |
| Dice | From a secret salt per room, kept in `room.json` on the server. Never the join code, never sent to a client. |
| Rounds | 10, as in MECHANICS.md. |

## 2. Settings

Owner figures are marked; the rest are chosen defaults, not derived from anything. All are stored in the start record,
so a game keeps the settings it started with.

<!-- check:settings -->
| Setting | Default | Source |
|---|---|---|
| `seats` | 4 | owner |
| `timer` | 180.0 | owner (seconds a round stays open) |
| `reveal` | 20.0 | chosen (seconds the results stay up) |
| `grace` | 30.0 | chosen (seconds a dropped player still holds up early advance) |
| `bot_lock_min` | 5.0 | chosen (earliest a bot locks, seconds into the round) |
| `bot_lock_max` | 60.0 | chosen (latest, capped at 90% of the timer) |
| `events` | "gentle" | as Torch's `/gm pilot` |
| `ranges` | True | as Torch's `/gm pilot` |

## 3. A round

1. **Open.** Moves open with a stored deadline (`timer` seconds).
2. **Pick, then lock.** A player may pick and change their mind freely. **Lock** makes the pick final for this round
   (Arena-only rule, owner decision 9; Torch keeps "change your mind until the deadline"). You cannot lock without a
   pick.
3. **Close.** The round closes at the deadline, or as soon as every *connected* human has locked (early advance).
   A dropped player still holds it up for `grace` seconds, then stops blocking. With nobody connected, the round
   waits for its deadline, so an empty room cannot race through the game.
4. **Missed.** At the close, an unlocked pick counts as it stands; no pick at all is the automatic scavenge.
5. **Bots** decide at the close, like Torch's sims. They *lock* at a seeded moment between `bot_lock_min` and
   `bot_lock_max`, logged like a person's lock, so the "N of M locked in" count does not single them out. When the
   last human locks first, the remaining bots lock just before the close.
6. **Reveal.** Everyone sees the night's news, their own private lines and the radio, for `reveal` seconds or until
   every connected human has pressed Continue. Then the next round opens, or after round 10 the final scoring.

## 4. The log

A room's log is its own file (`log.jsonl`), never read by Torch. Besides the core's records (join, start, move,
quit, radio, night, finish), a room writes:

<!-- check:records -->
| Record | Fields | Written when |
|---|---|---|
| `round_open` | round, opened_at, deadline | a round opens |
| `lock` | round, pid | a player or a bot locks |
| `round_closed` | round, reason, reveal_until | a round closes; reason is `all_locked` or `timeout` |
| `continue` | round, pid | a human presses Continue in the reveal |

On restart every room is loaded from disk: a round whose deadline passed while the server was down closes at once;
a round closed but not yet resolved is resolved (identically, from its moves and seed); a start with no round 1
opens round 1; timers are put back.

## 5. What a seat sees

Built field by field in `arena/views.py`. Hidden from a seat during play: the others' picks, goals, private lines and
exact rations (only the band, when ranges are on), which of them locked (only the count), and which seats are bots.
`arena/tests/test_views.py` scrambles all of that and requires every view to stay byte-identical. Radio in a reveal
is listed in alphabetical order of its wording, never in the order it was sent (bots post at the close).

Lines are codes plus values (`arena/lines.py`); `arena/lines_en.json` turns them into Torch's exact English.

## 6. Protocol

WebSocket, one JSON object per frame, each with `"t"`. Full field lists: `docs/arena/GODOT_FOUNDATION.md` section 5.

<!-- check:client-messages -->
| Client sends | Meaning |
|---|---|
| `hello` | must be first; carries `proto` |
| `create_room` | make a room and take its first seat |
| `join_room` | take a seat by code |
| `resume` | come back to a seat with its token |
| `start` | host only, in the lobby |
| `pick` | choose (or change) tonight's move |
| `lock` | make the pick final |
| `radio` | one fixed phrase this round |
| `continue` | done reading the reveal |
| `leave` | leave a started game for good (in the lobby: just disconnects) |

<!-- check:server-messages -->
| Server sends | Meaning |
|---|---|
| `hello_ok` | protocol accepted |
| `upgrade_required` | the app is too old |
| `seat` | your token, room code, alias and whether you are host |
| `lobby` | seats taken of 4, room code |
| `round` | your round screen |
| `reveal` | the night's results |
| `end` | the final scoring |
| `error` | `code` and a `message` safe to show |

<!-- check:limits -->
| Limit | Value |
|---|---|
| `PROTO` | 1 |
| `MIN_PROTO` | 1 |
| `MAX_MESSAGE` | 4096 |
| `TAKEOVERS_PER_MINUTE` | 5 |

Error codes: `hello_first`, `bad_message`, `refused` (with the message below), `taken_over`, `server_error`.

<!-- check:refusals -->
| Refusal (`refused` message) | When |
|---|---|
| `The room is full.` | a 5th human joins |
| `Already started.` | start twice |
| `Need at least one player.` | start an empty room |
| `There's no round open right now.` | pick or lock outside a round |
| `You're not in this game.` | a player who left picks or locks |
| `You've locked in. Your move is final this round.` | pick after lock |
| `You've already locked in.` | lock twice |
| `Pick a move before you lock in.` | lock with no pick |
| `Nothing to continue from.` | continue outside a reveal |
| `You can only leave a game that has started.` | leave_seat in the lobby |
| `Too many reconnects; wait a minute.` | more than 5 takeovers of one seat in a minute |
| `You're already in a room.` | create or join while seated |
| `The server is full; try again later.` | too many rooms |
| `There's no room with that code.` | join an unknown code |
| `That game has already started.` | join a started room |
| `That seat no longer exists.` | resume with an unknown token |
| `Join or create a room first.` | anything else before a seat |
| `Only the host can start.` | start by a non-host |
| `Amount must be a whole number.` | a gift amount that is not an integer |
| `Unknown message type '{t}'.` | any other `t` |

Game refusals from the core and the engine (an illegal move, the radio rules) come through unchanged as `refused`;
they are listed in MECHANICS.md section 9.

## 7. Known limits

| Limit | Why it is acceptable for now |
|---|---|
| When the last human locks before the bots, the remaining bots lock in the same instant | A small timing hint; the count still includes bots |
| Goal wording and goal progress travel as English text (with the goal code) | The engine writes them; a second theme needs codes |
| Wilderness event stories travel as English text (code `event`) | Same: `engine/events.py` writes them |
| Log writes fsync on the event loop | Rooms are capped (20 by default) and records are tiny |
| One server process per data folder | Two processes on one folder would both write the same rounds; the service manager (systemd) runs one |
| `websockets` is not in the project venv or on the Pi yet | Installing it is a download: asked before deploy |

## 8. Running it on the Pi

| What | Value |
|---|---|
| Service | `arena.service` (user `arena`, code `/opt/arena`, data `/var/lib/arena`, its own venv `/opt/arena/.venv`) |
| Listens on | `127.0.0.1:8770` only; nothing on the Pi's network interfaces |
| Way in | Tailscale `serve`, **tailnet only**: `wss://raspberrypi.tail87b476.ts.net:8470` |
| Never | Funnel. The Pi's Funnel ports (443, 8443, 10000) belong to other apps; Arena is not on the public internet |
| Ceilings | 400 MB memory, 50% of one CPU, 64 tasks (the Pi runs about 25 other services) |
| Install / update | build a tarball from committed code (`git archive HEAD arena bot engine deploy docs/game.json docs/sim/survivors_sim.py docs/sim/events.py docs/sim/visibility.py docs/sim/simbrain.py`), copy it to `/tmp/arena-release.tar.gz`, run `sh deploy/arena-install.sh /tmp/arena-release.tar.gz` |
| Torch | untouched by an Arena install or update; port 8765 belongs to another app and is not used |
| Restart | rooms reload from `/var/lib/arena/rooms/*` and re-arm their timers; a game in progress carries on |

Update between games where you can: a restart does not lose a game, but players are disconnected for a few seconds.

## 9. Change log

| Date | Change |
|---|---|
| 18 October 2026 | The Arena service on the Pi (tailnet-only, loopback behind Tailscale serve, resource ceilings). |
| 18 October 2026 | This file created with the first Arena server: rooms, timed rounds, lock-in, early advance, bots that lock, resume and restart. |
