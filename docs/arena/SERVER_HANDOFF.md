# Arena server: handoff to the Godot client session

**Written:** 18 Oct 2026, 09:55, by the session that built the server side. **For:** the session building `godot/`.
**Read this first, then** `docs/arena/GODOT_FOUNDATION.md` (the brief and the protocol notes both sessions append to)
and `docs/ARENA.md` (the room rules, kept true by a test). This file says what exists *now*, how it really behaves,
what is proven, what is not, and what is still open.

## 1. In one minute

| | |
|---|---|
| The server is real and live | `wss://raspberrypi.tail87b476.ts.net:8470`, on the owner's Raspberry Pi, **tailnet only** (not on the public internet) |
| Your phone and PC must be | signed in to the owner's Tailscale network |
| You can test against it today | `python -m arena.tools.smoke wss://raspberrypi.tail87b476.ts.net:8470` plays a full game without Godot |
| A game | 4 seats (you + bots fill the rest), 10 rounds, 180 s rounds, a 20 s reveal; everyone locked in = the round ends at once |
| The client has no rules | the server sends exactly what each seat may see; you draw it |
| Not done yet | your four requests (section 7), a `history` message, and a real Godot client has never connected to it |

## 2. What was built and where (commit order, newest last)

| Commit | What | Files |
|---|---|---|
| `99150cc` | A test that locks Torch's behaviour byte for byte (5 full games) before any refactor | `bot/tests/test_core_fixtures.py` |
| `03300b5` | The game core split out of Torch so rooms and Discord share one implementation. Torch's behaviour proven unchanged | `bot/core.py` (shared), `bot/game.py` (Torch only) |
| `3f13637` | **Line codes**: what a player is told, as `{code, args}`. English table as JSON for you | `arena/lines.py`, **`arena/lines_en.json`** |
| `d8c178f` | **Room**: rounds, timer, lock, early advance, bots, restart from disk | `arena/room.py` |
| `b88b453` | **Views**: what each seat is sent, proven leak-free | `arena/views.py` |
| `a87dd37` | **Server**: WebSocket, seats, resume, takeover | `arena/server.py` |
| `d720590` | `docs/ARENA.md` plus a test that fails if it drifts from the code | `arena/tests/test_arena_doc.py` |
| `2d1e186` | A sim bot crash found by the fuzz test (also fixed Torch) | `docs/sim/simbrain.py` |
| `4cd0a09` | Fuzz test: 300 rooms of random actions, restarts included | `arena/tests/test_fuzz.py` |
| `7cf5fcc` | The Pi service: systemd unit, install script, tailnet-only access | `deploy/arena.service`, `deploy/arena-install.sh` |
| `0aecbc6` | Fix: leaving the lobby no longer holds up round 1; smoke tool added | `arena/server.py`, `arena/tools/smoke.py` |

Your own work (`4a602bf`, the Net/Session/Log foundation and 44 tests) I have only seen as a commit title. I have not
reviewed it.

## 3. The live server

| What | Value |
|---|---|
| Address | `wss://raspberrypi.tail87b476.ts.net:8470` (TLS comes from Tailscale; the server itself speaks plain `ws` on loopback) |
| Where it runs | `arena.service` on the Pi: code `/opt/arena`, data `/var/lib/arena`, user `arena`, its own Python environment |
| Limits | 400 MB memory, 50% of one CPU, 20 rooms, frames over 4096 bytes drop that connection |
| Keepalive | the server pings every 20 s and drops a client that does not answer within 20 s (library defaults for `websockets` 17.2; **not yet tested against Godot's `WebSocketPeer`**: if your client is dropped while idle, tell me) |
| Not Funnel | do not ask for it to be put on the public internet; that is the owner's decision |
| Not the same port | the Pi's port 8765 belongs to a different app. Locally, `--port 8765` is fine on a laptop |

**It restarts.** I redeploy the server from committed code, and each deploy restarts it (a few seconds). Rooms and
games survive a restart and your `resume` brings you back; treat a dropped connection as normal and reconnect with the
seat token. Restarts so far, for correlating odd disconnects:

| Time (SAST) | Why |
|---|---|
| 09:38 | first install |
| 09:39 | test-room cleanup |
| about 09:41 | the restart test |
| 09:48 | the lobby-leave fix |

**Test rooms.** Every `create_room` makes a real room folder on the Pi (up to 20). One finished smoke-test room, `ZSKK`,
is there now. If you create many, tell the owner or me; removing rooms needs the service stopped, so do not delete by
hand.

## 4. How to run it yourself

| Goal | Command (from the repo root) |
|---|---|
| Play a whole game on the Pi, no Godot | `python -m arena.tools.smoke wss://raspberrypi.tail87b476.ts.net:8470` |
| Local server | `python -m arena.server --data %TEMP%\arena-dev --port 8765 --timer 20` (a 20 s timer makes timeout tests quick) |
| All server tests | `python -I -m unittest discover -s arena/tests -t .` (59 tests; needs `websockets`, already in the project venv and the system Python) |
| The wording table | `arena/lines_en.json` |

## 5. The protocol as it really is today

Draft v0 is in `GODOT_FOUNDATION.md` section 5; **this section wins where they differ.** Every message is one JSON
object with `"t"`.

### 5.1 You send

| `t` | Fields | Notes |
|---|---|---|
| `hello` | `proto` (1), `client_build` | Must be first. Any other first message gets `error hello_first` and the connection is dropped |
| `create_room` | none | You become host. Replies: `seat`, then `lobby` |
| `join_room` | `code` | Not case sensitive. Refused once the game has started |
| `resume` | `token` | Replies: `seat`, then your current screen |
| `start` | none | Host only. Bots fill the empty seats |
| `pick` | `kind`, `target` (alias or null), `amount` (int) | May repeat until you lock |
| `lock` | none | Needs a pick first. Final for the round |
| `radio` | `phrase` (one of 8 keys), `about` (alias or null) | One per round |
| `continue` | none | Reveal screen |
| `leave` | none | Started game: permanent. Lobby: just disconnects (see 6) |

**Never send a seat or player id.** The server takes the seat from the connection; extra fields are ignored.

### 5.2 You receive

The server **pushes a full view after every change** (anyone's lock, a pick, a round closing). No deltas. There is
**no ticker**: `seconds_left` is correct at the moment of sending, so run your own countdown and replace it with every
new view.

| `t` | Fields |
|---|---|
| `hello_ok` | `proto` |
| `upgrade_required` | `min_proto`, `message` (connection then closes) |
| `seat` | `token` (store it; hashed on the server), `room_code`, `alias` (secret, yours), `host` |
| `lobby` | `room_code`, `seats_taken`, `seats_total` (4), `host` (this can change if the host drops) |
| `round` | `round`, `rounds`, `seconds_left`, `me`, `legal`, `gift_amounts`, `my_pick`, `my_locked`, `locked_count`, `seats_total`, `radio_available`, `radio_phrases`, `aliases`, `board` |
| `reveal` | `round`, `news`, `private`, `radio`, `board`, `seconds_left` |
| `end` | `extracted`, `winners`, `results` |
| `error` | `code`, `message` |

`round.me`: `alias`, `rations`, `bandit`, `guards_left` (null = unlimited), `guarded`, `goal` = `{code, target, text}`,
`goal_progress` = `{state: open|done|failed|end, text}`. (`goal` and `goal_progress` text are English for now: request 4.)

`round.legal`: `{move kind: [target aliases]}`; kinds with no target (`scavenge`, `guard`) have an empty list. Show exactly
these. `gift_amounts` is the legal amounts for `gift`. `my_pick` = `{kind, target, amount}` or null.
`locked_count` counts bots too, on purpose, so a bot cannot be told from a person by when it locks.

`round.board` (and `reveal.board`): `[{alias, band}]`, bands `well_fed`, `getting_by`, `starving`, `bandit`, or `null`
when ranges are off (they are on by default). Never exact rations for others.

`reveal.news` and `reveal.private`: lists of `{code, args}`. Words: `arena/lines_en.json`, fill `{name}` from `args`;
a list arg joins English-style (`[3,4,5]` -> `3, 4 and 5`). An empty `news` means a quiet night: show `news_quiet`.
Code `event` carries one arg, `line`, a finished sentence from the engine.
`reveal.radio`: `[{phrase, about}]`, ordered by wording, **not** by send time (that is deliberate: bots post at the
close). Phrase texts are in `bot/core.py` `RADIO_PHRASES`.

`end.results[]`: `alias`, `score`, `rations`, `seat` (got a helicopter seat), `goal` = `{code, target, text}`,
`goal_done`, `stole`, `times_robbed`, `gave_away`.

### 5.3 Error codes you can get

| `code` | Meaning | What the client does |
|---|---|---|
| `hello_first` | first message was not `hello` | bug on the client |
| `bad_message` | not a JSON object with a string `t` | bug on the client |
| `refused` | a rule said no; `message` is safe to show | show it; the state did not change |
| `taken_over` | the same token connected elsewhere; **you are about to be disconnected** | see request 1: this may not arrive |
| `server_error` | an unexpected failure on the server (logged there) | retry once, then tell the owner |

Today **every** refusal is `refused`, including "That seat no longer exists." (request 2).

## 6. Behaviour that is easy to get wrong

| Situation | What happens |
|---|---|
| Last connected human locks | the round closes at once; bots that have not locked lock in that instant |
| A human drops | the round still waits for them for 30 s, then stops waiting; their pick still counts at the timer |
| Nobody connected | the round waits for its full timer; the room does not race ahead |
| You pick, do not lock, timer ends | your pick counts as it stands |
| You never pick | the server scavenges for you |
| Pick or lock after locking | `refused`: "You've locked in. Your move is final this round." Disable the picker, never re-enable it locally |
| Reveal ends | after 20 s, or when every connected human sent `continue`; then round n+1 opens (or `end` after round 10) |
| Two devices, one token | the newest wins; the old one is sent `taken_over` and closed; more than 5 takeovers a minute is refused |
| Host drops | the lowest connected seat becomes host; you will see it in the next `lobby` |
| `leave` in the lobby | your connection is dropped but **the seat stays counted as taken** (the join is in the log). After the 30 s grace the round stops waiting for it. A known limit, in `ARENA.md` section 7 |
| After `end` | no more messages; the connection stays open. The room stays on disk |
| Server restart | the same game continues with the same deadline (proven), reconnect and `resume` |

## 7. Your four requests: where each stands

None is built yet. I am writing down what I found, not promising a design.

| # | Request | Status |
|---|---|---|
| 1 | Close codes (`4001` seat gone, `4002` upgrade required, `4003` taken over) sent after the message, then wait for the client's close | **Agreed in principle; not built.** Today `taken_over` and `upgrade_required` are sent and the socket closes right after, so your reproduced race is real. Small server change |
| 2 | A distinct `seat_gone` error (and `room_gone`) instead of `refused` for a dead token | **Agreed in principle; not built.** Small server change |
| 3 | `event` lines carrying an event id and variant next to `line` | **Not checked yet.** The engine's event records have an event name; whether the story variant is recorded I have not looked at |
| 4 | Goal and goal progress as codes plus args | **Not built.** It means changing `engine/finish.py` (`goal_progress` returns text today), updating `docs/MECHANICS.md`, and re-recording tests: a bigger change than 1 and 2 |

Also missing, mentioned in the plan but not built: a `history` message (a player's past rounds on reconnect). Today a
client that reconnects gets only the current screen, so keep your own record of past reveals if you want a history view.

## 8. What is proven, and what is not

| Proven (with a test or a live run) | Not proven |
|---|---|
| A whole game over the real tailnet address, including a drop and resume (`arena.tools.smoke`) | A real Godot client has never connected |
| A server restart mid-round: same game, pick kept, deadline kept counting down (live, on the Pi) | Keepalive pings against Godot's `WebSocketPeer` |
| No view leaks another seat's picks, goals, exact rations, locks or bot status (scramble test, 1,000+ checks, 3 planted leaks caught) | Phone behaviour: backgrounding, Android battery limits, cellular |
| 300 random-action rooms always finish; a bad room is skipped and the rest load | More than one human playing at once on the live server (tested locally with 2 in unit tests, not on the Pi) |
| Rendering the codes with `lines_en.json` gives exactly Torch's lines (120 games) | Load: how many rooms the Pi sustains next to its 25 other services |

## 9. Ground rules between our two sessions

| Rule | Why |
|---|---|
| You own `godot/`. I own `arena/`, `bot/`, `engine/`, `deploy/`, `docs/ARENA.md`, `docs/MECHANICS.md` | no collisions |
| Ask for server changes by appending a dated note under "Proposed changes" in `GODOT_FOUNDATION.md` | I read it |
| Stage files by name; never `git add -A` | two sessions share one branch |
| Do not push | the owner approves pushes |
| Do not change the live server or the Pi | I redeploy it; tell me what you need |
| Bugs you find in the server are welcome: send the message sequence that shows it | I turn each into a test first |
