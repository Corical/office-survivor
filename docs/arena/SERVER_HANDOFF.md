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
| 11:02 | close codes, `seat_gone` / `room_gone`, news order, event args, goal and progress lines (section 7) |

Rooms left on the Pi right now: `ZSKK` and `EBMM` (mine, finished or abandoned smoke tests), `RTEP` and possibly more
from your live tests.

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
| `create_room` | optional `visibility` (`"public"` default, or `"private"`; anything else is refused) and `name` (the camp's label, see 5.4) | You become host. Replies: `seat`, then `lobby` |
| `join_room` | `code` | Not case sensitive. Errors `room_gone`, `room_started`, `room_full` (see 5.3) |
| `list_rooms` | none | Allowed any time after `hello`, seated or not. Reply: `rooms` (see 5.4). One per second per connection |
| `resume` | `token` | Replies: `seat`, then your current screen |
| `start` | none | Host only. Bots fill the empty seats |
| `pick` | `kind`, `target` (alias or null), `amount` (int) | May repeat until you lock |
| `lock` | none | Needs a pick first. Final for the round |
| `radio` | `phrase` (one of 8 keys), `about` (alias or null) | One per round |
| `continue` | none | Reveal screen |
| `leave` | none | Started game: permanent. Lobby: gives the seat back (free for someone else, token dead: `resume` with it answers `seat_gone`; a lobby left empty is deleted). Closing the app without `leave` keeps the seat (see 6) |

**Never send a seat or player id.** The server takes the seat from the connection; extra fields are ignored.

### 5.2 You receive

The server **pushes a full view after every change** (anyone's lock, a pick, a round closing). No deltas. There is
**no ticker**: `seconds_left` is correct at the moment of sending, so run your own countdown and replace it with every
new view.

| `t` | Fields |
|---|---|
| `hello_ok` | `proto`, `features` (`["list_rooms"]`: use it instead of guessing) |
| `rooms` | `rooms`: [{`code`, `seats_taken`, `seats_total`, `age_s`, `name`}] (see 5.4) |
| `upgrade_required` | `min_proto`, `message` (connection then closes) |
| `seat` | `token` (store it; hashed on the server), `room_code`, `alias` (secret, yours), `host` |
| `lobby` | `room_code`, `seats_taken`, `seats_total` (4), `host` (this can change if the host drops) |
| `round` | `round`, `rounds`, `seconds_left`, `me`, `legal`, `gift_amounts`, `my_pick`, `my_locked`, `locked_count`, `seats_total`, `radio_available`, `radio_phrases`, `aliases`, `board` |
| `reveal` | `round`, `news`, `private`, `radio`, `board`, `seconds_left` |
| `end` | `extracted`, `winners`, `results` |
| `error` | `code`, `message` |

`round.me`: `alias`, `rations`, `bandit`, `guards_left` (null = unlimited), `guarded`, `goal` = `{code, target, text, line}`,
`goal_progress` = `{state: open|done|failed|end, text, line}`. **`line` = `{code, args}`**, the same shape as every other
line, with templates in `arena/lines_en.json` (`goal_*` and `progress_*` codes, 20 of them); `text` is the same words in
English, kept as a fallback. `goal.code` is still the goal's identity (`beat`, `give`, ...). `end.results[].goal` has `line` too.
`progress_beat_band` carries `band` as the English label ("🟢 well fed"), not a key.

`round.legal`: `{move kind: [target aliases]}`; kinds with no target (`scavenge`, `guard`) have an empty list. Show exactly
these. `gift_amounts` is the legal amounts for `gift`. `my_pick` = `{kind, target, amount}` or null.
`locked_count` counts bots too, on purpose, so a bot cannot be told from a person by when it locks.

`round.board` (and `reveal.board`): `[{alias, band}]`, bands `well_fed`, `getting_by`, `starving`, `bandit`, or `null`
when ranges are off (they are on by default). Never exact rations for others.

`reveal.news` and `reveal.private`: lists of `{code, args}`. Words: `arena/lines_en.json`, fill `{name}` from `args`;
a list arg joins English-style (`[3,4,5]` -> `3, 4 and 5`). An empty `news` means a quiet night: show `news_quiet`.
Code `event` carries `line` (a finished sentence from the engine: the fallback), `event` (the event id), `scope`
(`camp` or `player`) and, for a player event, `who` (the alias it hit). The story **variant** is not available.
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
| `seat_gone` | `resume` with a token the server does not know, or whose room is gone | forget the token; **the connection stays open**, so `create_room` or `join_room` works on it |
| `room_gone` | `join_room` with a code that matches no room | tell the player; the connection stays open |
| `room_started` | `join_room` for a game that has already started | neutral message, refresh the list; the connection stays open |
| `room_full` | `join_room` for a room with all 4 seats taken | neutral message, refresh the list; the connection stays open |
| `rate_limited` | a second `list_rooms` inside one second on this connection | no list was sent; ask again later |
| `taken_over` | the same token connected elsewhere; **you are about to be disconnected** | stop; the close follows |
| `server_error` | an unexpected failure on the server (logged there) | retry once, then tell the owner |

**Close codes.** After `upgrade_required` the server closes with **4002**, and after `taken_over` with **4003**, each
about **0.25 s after the message** so your poll sees the message first (live-checked: 0.26 s). Anything else that ends a
connection (a dropped network, a frame over 4096 bytes) is an ordinary close with no code of ours. **4001 is not used**:
`seat_gone` is an error on a connection that stays open (say so if you would rather it closed). From the moment a seat
moves to another device, whatever the old connection still sends is ignored.

### 5.4 Open camps (`list_rooms`), built 18 Oct 2026

| Rule | Detail |
|---|---|
| Who is listed | `visibility` is `public`, still in the lobby, a seat free, and at least one human connected. A started game never appears. A camp nobody is in drops off the list until someone resumes |
| Entry fields | `code`, `seats_taken`, `seats_total`, `age_s` (whole seconds since the room was made), `name` (string, `""` when none). No alias, seat number or join order |
| Order and size | Newest first; at most 20 (the server's room cap) |
| Not a reservation | `join_room` with the `code`; a camp that filled, started or vanished answers `room_full`, `room_started` or `room_gone` on a connection that stays open |
| `visibility` | Exactly `"public"` or `"private"`; absent = public. Anything else (wrong case, `null`, a number...) is `refused` and no room is made. Private camps are joined by code as before |
| `name` | Control, invisible (bidi, zero-width) and unsendable characters removed, whitespace runs collapsed to one space, cut to 24 characters, trimmed. Not a string = no label. The server never rejects a name, it cleans it |
| Rate limit | One `list_rooms` per second per connection. A repeat inside the second gets `rate_limited` and no list; the refusal does not restart the clock |
| Restart | `visibility`, `name` and age are in `room.json`; a room from before this feature loads as public, unnamed |
| Seats of people who left | `leave` in the lobby frees the seat at once, so `seats_taken` drops. A player who only closes the app keeps the seat (section 6) |

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
| Two devices, one token | the newest wins; the old one is sent `taken_over`, then closed with 4003 a moment later (and ignored from the instant of the takeover); more than 5 takeovers a minute is refused |
| Host drops | the lowest connected seat becomes host; you will see it in the next `lobby` |
| `leave` in the lobby | the seat is given back (`left_lobby` in the log) and the count drops for everyone still there; your token is dead. **Closing the app without `leave` is different:** the seat stays taken in case you resume, and nothing frees it (`ARENA.md` section 7) |
| After `end` | no more messages; the connection stays open. The room stays on disk |
| Server restart | the same game continues with the same deadline (proven), reconnect and `resume` |

## 7. Your four requests: where each stands

All four are now done, deployed to the Pi at 11:02 and checked live over the tailnet. Two differ from what was asked.

| # | Request | Result |
|---|---|---|
| 1 | Close codes after the terminal message | **Done, with one change.** `upgrade_required` then close **4002**, `taken_over` then close **4003**, each after a 0.25 s pause (commit `0e4826d`). 4001 is not used (see 5.3) |
| 2 | A distinct `seat_gone` (and `room_gone`) error | **Done** (`0e4826d`). A token whose room folder was deleted is `seat_gone` too |
| 3 | `event` lines carrying the event id and variant | **Half done** (`fa9a72c`). The event id (`event`), `scope` and `who` are sent beside `line`. **The variant cannot be sent**: the engine picks it from the seed each time and does not record it; recording it would add a field to every stored event record, and then every existing log (Torch's included) would fail its replay check. If a theme needs per-variant wording, the options are for the client to key on `event` alone, or for the owner to decide on a log-format change |
| 4 | Goal and goal progress as codes plus args | **Done** (`023fa3e`, `2396502`). `goal.line` and `goal_progress.line` = `{code, args}`; English `text` kept. The wording is one table in `engine/finish.py` shared with Torch, and a frozen copy of the old functions is compared in over 30,000 states, so not a word changed for Torch |

Your two new items from the second review:

| Item | Result |
|---|---|
| Public news arrived in seat order | **Real leak, fixed** (`084ed7c`). The engine resolves seats in seat order and humans take the low seats, so the order of the lines told a watcher which seats are people. The reveal's `news` is now sorted by content (event stories first, then by wording). Your client-side sort is now redundant but harmless |
| Guard income has no line | **Not a gap in the live game.** The only income a guard can get is `guard_income`, which exists only when the rule `guard_income_max` is above 0; the live rules leave it at 0, so it never happens. A guard's other income, the reward for catching a thief, has its own line (`caught_thief_paid`). No line added; say if you want one anyway |
| Four codes never seen in 3,120 nights | Measured in 3,000 nights under the live rules with humans who miss the deadline 10% of the time: `scavenged_auto` 700 times and `news_quiet` 168 times, so **both are real, keep them**. `got_gift` 0 and `guard_up_1` 0: they only occur under other rule settings (gifts with no gift bonus; one-night guards), dead under today's rules but harmless to keep |

**A rules fact you will hit:** the goal deck is dealt in order, one card per seat. In a **4-seat room only four goals ever
appear** (beat, robbed twice and extract, clean thief, give). `grudge` needs 5 seats and `detective` needs 6, so the
Detective goal never shows up in a 4-seat room. The owner has been told. Your goal screens still need all six for
bigger rooms and other rule sets.

Also missing, mentioned in the plan but not built: a `history` message (a player's past rounds on reconnect). Today a
client that reconnects gets only the current screen, so keep your own record of past reveals if you want a history view.

## 8. What is proven, and what is not

| Proven (with a test or a live run) | Not proven |
|---|---|
| A whole game over the real tailnet address, including a drop and resume (`arena.tools.smoke`) | A Godot client in a window, on a phone: per the client session's tracker (10:46) Godot has played 2 full games headless, one on a local server and one on the Pi over wss, but nothing has been drawn on screen yet |
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
