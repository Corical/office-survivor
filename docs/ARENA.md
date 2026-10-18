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
| `left_lobby` | pid, kicked (only when the host removed them) | a human gives their seat back (or the host removes them) in the lobby (`leave` before the start); the seat is free again and its pid goes to the next person who joins (pids stay 0..3, which the engine needs) |

On restart every room is loaded from disk: a round whose deadline passed while the server was down closes at once;
a round closed but not yet resolved is resolved (identically, from its moves and seed); a start with no round 1
opens round 1; timers are put back.

## 5. What a seat sees

Built field by field in `arena/views.py`. Hidden from a seat during play: the others' picks, goals, private lines and
exact rations (only the band, when ranges are on), which of them locked (only the count), and which seats are bots.
`arena/tests/test_views.py` scrambles all of that and requires every view to stay byte-identical. Radio in a reveal
is listed in alphabetical order of its wording, never in the order it was sent (bots post at the close). The public
news is ordered the same way (wilderness stories first, then by wording), never in the engine's seat order: humans take
the low seats, so that order would show which seats are people. (Torch's #news still lists lines in engine order; its
players have random aliases and no way to see seat numbers, so it is a much weaker hint there.)

Lines are codes plus values (`arena/lines.py`); `arena/lines_en.json` turns them into Torch's exact English. A seat's goal
(`me.goal`, and each result's `goal` at the end) and its progress (`me.goal_progress`) carry a `line` = `{code, args}`
(codes `goal_*` and `progress_*`, in the same JSON) plus the same words as English `text`, as a fallback. The wording
lives in one table in `engine/finish.py`, shared with Torch's `/status`; `engine/tests/test_goal_codes.py` holds it to a
frozen copy of what those lines said before they became templates, over every goal, state and rule variant.

## 6. Protocol

WebSocket, one JSON object per frame, each with `"t"`. Full field lists: `docs/arena/GODOT_FOUNDATION.md` section 5.

<!-- check:client-messages -->
| Client sends | Meaning |
|---|---|
| `hello` | must be first; carries `proto` |
| `create_room` | make a room and take its first seat; optional `visibility` (`public` default, or `private`) and `name` (see below) |
| `join_room` | take a seat by code |
| `list_rooms` | ask for the open camps (see below); allowed with or without a seat |
| `kick` | host only, in the lobby: remove another seat, named by the opaque `seat` handle from the host's `lobby` message |
| `resume` | come back to a seat with its token |
| `start` | host only, in the lobby |
| `pick` | choose (or change) tonight's move |
| `lock` | make the pick final |
| `radio` | one fixed phrase this round |
| `continue` | done reading the reveal |
| `leave` | leave a started game for good; in the lobby, give the seat back (free for someone else, the token is dead, and a lobby left empty is deleted) |

<!-- check:server-messages -->
| Server sends | Meaning |
|---|---|
| `hello_ok` | protocol accepted; `features` lists optional messages the server knows (`list_rooms`) |
| `rooms` | the open camps: `rooms` = [{`code`, `seats_taken`, `seats_total`, `age_s`, `name`}] |
| `upgrade_required` | the app is too old |
| `seat` | your token, room code, alias and whether you are host |
| `lobby` | seats taken of 4, room code; to the host only also `seats`: one `{id, connected}` per other seat, ordered by `id` (an opaque handle, never join order, never an alias) |
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
| `NAME_MAX` | 24 |
| `LIST_INTERVAL` | 1.0 |
| `FEATURES` | ['list_rooms'] |
| `CLOSE_UPGRADE_REQUIRED` | 4002 |
| `CLOSE_TAKEN_OVER` | 4003 |
| `CLOSE_KICKED` | 4004 |
| `CLOSE_PAUSE` | 0.25 |

<!-- check:error-codes -->
| `error.code` | Meaning |
|---|---|
| `hello_first` | the first message was not `hello` |
| `bad_message` | not a JSON object with a string `t` |
| `refused` | a rule said no (the messages are listed below); nothing changed |
| `seat_gone` | `resume` with a token the server does not know, or whose room is gone: forget the token. The connection stays open, so the client can create or join a room without reconnecting |
| `room_gone` | `join_room` with a code that matches no room |
| `kicked` | the host removed this seat in the lobby; this connection is about to be closed with code 4004 and the token is dead |
| `room_started` | `join_room` for a game that has already started |
| `room_full` | `join_room` for a room with all 4 seats taken |
| `rate_limited` | `list_rooms` again within `LIST_INTERVAL` seconds on the same connection; nothing was sent, ask again later |
| `taken_over` | the same seat was opened on another device; this connection is about to be closed with code 4003 |
| `server_error` | an unexpected failure on the server (logged there) |

**Close codes.** Two ends are ours: `upgrade_required` is followed by close code **4002**, and `taken_over` by **4003**.
Godot's `WebSocketPeer` drops a message that arrives in the same poll as the close frame, so the server sends the
message, waits `CLOSE_PAUSE` seconds, and only then closes. Code 4001 ("seat gone") is deliberately not used: a dead seat
is an ordinary error and the connection stays open. From the moment a seat is taken over, anything the old connection
still sends is ignored.

**Kicking.** In the lobby the host's `lobby` message carries `seats`, one `{id, connected}` per other seat, so a seat whose
player dropped off can be told from one that is there. `kick` with that `id` frees the seat like `leave` does (same
`left_lobby` record, marked `kicked`) and the token dies. A connected target gets `error` `kicked`, then the close with
code **4004** after `CLOSE_PAUSE`, like a takeover; a disconnected one simply finds `seat_gone` on `resume`. The `id` is a
hash of the room's secret salt, the pid, the alias and the occupant's key, so it names the person and not the chair: it
changes when the seat changes hands and a stale handle is refused, never applied to the next person. Only the host sees
`seats`; there is no kick after the start; a kicked player can join again by code (there is no ban).

**Open camps (`list_rooms`).** The client asks, the server answers with one `rooms` message. A room is listed only when
all of these hold: its `visibility` is `public`, it is still in the lobby, a seat is free, and at least one human is
connected (a camp nobody is in is not listed until someone is back). A started game never appears. Entries carry the
code, the seat count, `age_s` since the room was made, and `name`; never an alias, a seat number or a join order. Newest
first, at most the server's room cap (20). The list is a hint, not a reservation: the client then sends `join_room`, and
a camp that filled or started in between answers `room_full` or `room_started` (or `room_gone` if it vanished).
`create_room` may carry `visibility` (exactly `public` or `private`; absent means `public`; anything else is refused, so a
typo cannot publish a private camp) and `name` (the host's own label: control, invisible and unsendable characters are
removed, whitespace collapses to single spaces, cut to `NAME_MAX`; not a string means no label). A private camp is joined
by code as before. One `list_rooms` per `LIST_INTERVAL` per connection; an earlier repeat gets `rate_limited` and no list.
`visibility` and `name` live in the room's `room.json`, so they survive a restart.

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
| `The game has started; use leave to quit it for good.` | `leave_lobby` after the start (the server only calls it in the lobby, so a client never sees this) |
| `Kicking is only possible in the lobby.` | `kick` after the start |
| `Only the host can kick.` | `kick` by a seat that is not the host |
| `That seat is not in the room any more.` | `kick` with a handle nobody holds (the seat left, was kicked, or changed hands) |
| `You can't kick yourself; use leave.` | `kick` naming your own seat |
| `Visibility must be public or private.` | `create_room` with any other `visibility` (a typo must not publish a private camp) |
| `Too many room lists; wait a second.` | a second `list_rooms` within `LIST_INTERVAL` on one connection |

Game refusals from the core and the engine (an illegal move, the radio rules) come through unchanged as `refused`;
they are listed in MECHANICS.md section 9.

## 7. Known limits

| Limit | Why it is acceptable for now |
|---|---|
| When the last human locks before the bots, the remaining bots lock in the same instant | A small timing hint; the count still includes bots |
| `band` in the `progress_beat_band` line is the English band label ("🟡 getting by"), not a band key | It is the same text Torch shows; the board next to it carries the band keys |
| In a 4-seat room only four goal types are ever dealt (beat, robbed twice and extract, clean thief, give): the goal deck is dealt in order, one card per seat, so **grudge and detective need 5 or more seats** | A rules fact (MECHANICS.md section 7), not a bug; it means the Detective goal never appears in a 4-seat room |
| Wilderness event stories travel as English text (code `event`, arg `line`), with `event` (the id), `scope` (`camp` or `player`) and, for a player event, `who` beside it | `engine/events.py` writes the sentence. The story **variant** is not sent: the engine picks it from the seed each time and does not record it, and recording it would add a field to every stored event, which makes every existing log fail to replay |
| Log writes fsync on the event loop | Rooms are capped (20 by default) and records are tiny |
| A player who closes the app in the lobby without pressing leave keeps the seat (they may come back with their token); nothing frees it | Once started, that seat is a human who never answers and after the `grace` the round stops waiting for it. A timeout that frees idle lobby seats: not built |
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
| 18 October 2026 | Leaving the lobby gives the seat back (`left_lobby` record; the creator no longer sees a stuck 2 of 4). A freed pid is handed to the next joiner so pids stay 0..3. Live on the Pi 16:42 (commit feb9e90). |
| 18 October 2026 | Open camps: `list_rooms` / `rooms`, `create_room` `visibility` and `name`, `features` in `hello_ok`, error codes `room_full`, `room_started`, `rate_limited`. Live on the Pi since 18 October 2026 15:41 (commit 4ffe082). |
| 18 October 2026 | The Arena service on the Pi (tailnet-only, loopback behind Tailscale serve, resource ceilings). |
| 18 October 2026 | This file created with the first Arena server: rooms, timed rounds, lock-in, early advance, bots that lock, resume and restart. |
