# Godot client: foundation brief (for a parallel session)

**Written:** 18 Oct 2026, by the session doing the server side. **Your scope:** the Godot client foundation only.
**Full plan (read it first):** `.local/.sisyphus/plans/godot-arena-platform.md` (v2) and its review `godot-arena-platform.REVIEW.md` next to it.
**Rules of the game (read before any game text):** `docs/MECHANICS.md`. Player-friendly version: `docs/rules.md`.

## 1. What we are building

A live multiplayer version of Survivors for 4 players per room (bots fill empty seats), played from a PC build or an
Android APK. 10 rounds. A round ends when every human has **locked in** their move, or when the timer (3 minutes)
runs out. The server is authoritative: it runs the rules (Python, `engine/`) and sends each player only what that
player may see. **The client has no game rules in it.** It draws views and sends intents.

Owner decisions that bind the client:

| Decision | What it means for you |
|---|---|
| Same five moves as Survivors: scavenge, guard, steal, investigate, gift | The move picker shows exactly the moves and targets the server lists as legal. Never compute legality |
| Secret aliases | The only names on screen are aliases. No display names, no account names, ever |
| Radio = 8 fixed phrases | No free-text input anywhere. The radio picker is phrase + (sometimes) an alias |
| Lock-in | Pick freely, change your mind, then press **Lock** to make it final. After Lock, the picker is read-only |
| Tailscale for now | The phone reaches the server over Tailscale (`wss://<pi>.ts.net`); no public internet |

## 2. Who owns what (so the two sessions never collide)

| Path | Owner |
|---|---|
| `godot/` (new) | **You.** Everything you create lives here |
| `docs/arena/GODOT_FOUNDATION.md` (this file) | Shared. Change section 5 (the protocol) only by adding a "Proposed change" note at the bottom, never by editing the contract in place |
| `engine/`, `bot/`, `arena/` (server, coming), `docs/sim/`, `docs/MECHANICS.md`, `docs/game.json` | **Not yours. Do not edit.** Torch is live on a Raspberry Pi from this code |

Commit only files under `godot/` (and notes appended to this file). Do not push; the owner approves pushes.

## 3. Facts about this machine (checked 18 Oct 2026)

| Thing | Status |
|---|---|
| Godot | 4.7.2.stable.official, on PATH as `godot` / `godot_console` |
| Export templates | 4.7.2.stable present in `%APPDATA%\Godot\export_templates` |
| Debug keystore | present in `%APPDATA%\Godot\keystores\debug.keystore` |
| Android SDK | `C:\Users\Corne\AppData\Local\Android\Sdk` |
| JDK | OpenJDK 21.0.10 |
| Python (for a mock server) | 3.14.2; `websockets` 16.0 installed |
| Test framework | **None installed.** GUT or gdUnit4 must be downloaded: ask the owner first (downloading is an ask-first action), then vendor it under `godot/addons/` |

## 4. Foundation scope (do these, in this order)

1. **Project skeleton** `godot/project.godot`, Godot 4.7.2, GDScript. Portrait-friendly layout that also works on a
   desktop window (the owner plays from PC and phone).
2. **Autoloads**: `Net` (one `WebSocketPeer`, connect/reconnect, JSON in and out, `hello` handshake), `Session`
   (seat token in `user://session.json`, current view, current screen), `Log` (every `push_error`, `push_warning` and
   network error to `user://client.log` and stdout, so a test run can read them).
3. **Scenes**, placeholder art, driven only by server views: Title/Join (create room / enter code) -> Lobby
   (`N of 4 seats`, Start for the host) -> Round (your state, move picker, target list, gift amount, Lock button,
   timer ring from `seconds_left`, `N of M locked in`, Radio button) -> Reveal (news lines, your private lines,
   Continue) -> End (helicopter, winner, results table).
4. **Line rendering by code**: the server sends `{code, args}`, never prose. Keep one table
   `godot/game/lines.gd` (code -> template + icon). Start it from the codes in 5.4.
5. **Mock server** `godot/tools/mock_server.py` (Python, `websockets`): speaks the contract in section 5, plays a scripted
   4-seat game with canned data (no real rules), so the client can be built before the real server exists. It must
   also be able to send: an `error`, an `upgrade_required`, a mid-round disconnect, and an unknown message type.
6. **Autopilot (debug builds only)**: the client reads commands from a local file or socket (`tap Lock`, `pick steal
   Alias03`, `screenshot round.png`) so a session can drive every screen without a person. Off in release exports.
7. **Two test tiers**: (a) headless logic tests (`godot --headless`) that assert scene-tree state for a given view, no
   pixels (headless uses a dummy renderer and cannot draw); (b) a windowed run against the mock that saves screenshots
   of every screen.
8. **Exports**: a Windows debug build, and an Android debug APK preset with the `INTERNET` permission. Building the
   APK is the stretch goal of the foundation; installing on the phone waits for the real server.

**Out of scope for the foundation:** final art and theme, sound, the real server, accounts, any game rule.

## 5. Protocol contract v0 (DRAFT: the server side will implement exactly this; changes by note only)

Transport: WebSocket, one JSON object per text frame, UTF-8. Every message has `"t"` (type). Times the client shows are
**`seconds_left`** (server-computed); never trust the phone's clock.

### 5.1 Client -> server

| `t` | Fields | When |
|---|---|---|
| `hello` | `proto` (=1), `client_build` (string) | First message on every connection |
| `create_room` | - | Title screen; the sender becomes host |
| `join_room` | `code` | Title screen |
| `resume` | `token` | Reconnect with the stored seat token |
| `start` | - | Host only, in the lobby (bots fill the empty seats) |
| `pick` | `kind`, `target` (alias or null), `amount` (int, gifts only) | Round, before Lock; may repeat |
| `lock` | - | Round; makes the current pick final |
| `radio` | `phrase` (one of the 8 keys), `about` (alias or null) | Round; once per round |
| `continue` | - | Reveal screen |
| `leave` | - | Anywhere; leaving a started game is permanent |

**Never send a seat, pid or player id.** The server knows who you are from the connection.

### 5.2 Server -> client

| `t` | Fields |
|---|---|
| `hello_ok` | `proto` |
| `upgrade_required` | `min_proto`, `message` |
| `seat` | `token` (store it), `room_code`, `alias` (yours; secret), `host` (bool) |
| `lobby` | `room_code`, `seats_taken`, `seats_total` (4), `host` (bool). No aliases of others: join order would reveal who is who |
| `round` | `round`, `rounds`, `seconds_left`, `me` {`alias`, `rations`, `bandit`, `guards_left`, `guarded`, `goal` {`code`, `args`}, `goal_progress` {`state`: open/done/failed/end, `code`, `args`}}, `legal` {kind: [aliases]}, `gift_amounts` [ints], `my_pick` (or null), `my_locked`, `locked_count`, `seats_total`, `radio_available`, `radio_phrases` [{`key`, `needs_player`}], `aliases` [all others, alphabetical], `board` (list of {`alias`, `band`}) or null |
| `reveal` | `round`, `news` [{`code`, `args`}], `private` [{`code`, `args`}], `radio` [{`phrase`, `about`}], `board` or null, `seconds_left` |
| `end` | `extracted` [aliases], `winners` [aliases], `results` [{`alias`, `score`, `rations`, `seat`, `goal` {`code`, `args`}, `goal_done`, `stole`, `times_robbed`, `gave_away`}] |
| `error` | `code`, `message` (safe to show) |

`band` values: `well_fed` (7+), `getting_by` (3-6), `starving` (1-2), `bandit`.
Radio phrase keys and their text are in `bot/game.py` `RADIO_PHRASES` (read only): `saw`, `trust`, `lying`, `guarding`,
`easy`, `innocent`, `watch`, `me`.

### 5.3 Rules the client must follow

- Draw only what the latest view says. On reconnect, `resume` then wait for a fresh view; keep nothing else.
- Unknown `t` or unknown line `code`: log it, show a neutral fallback, never crash.
- After `my_locked` is true, disable the picker. Never re-enable it locally.
- Show `N of M locked in` as a count only; there is no list of who locked.

### 5.4 Line codes (starting set, from what Torch tells players today: `bot/game.py` `news_lines`, `private_lines`)

| code | args | Torch wording today (for your template) |
|---|---|---|
| `scavenged` | `found`, `auto` | "You scavenged and found {found}." / auto: "You didn't choose a move, so you scavenged automatically..." |
| `guard_up` | `from_round`, `until_round` | "You're on guard for night {n}." |
| `stole` | `amount`, `target` | "You stole {amount} from {target}." |
| `steal_empty` | `target`, `split` | "You broke into {target}'s place and found nothing." / split: "...someone beat you to it." |
| `steal_caught_me` | `target`, `paid` | "{target} was guarding: you were caught and paid {paid}." |
| `robbed_me` | `amount` | "Someone stole {amount} from you." |
| `caught_thief` | `thief`, `paid` | "Your guard caught {thief} red-handed. They paid you {paid}." |
| `watched` | `target`, `saw`, `saw_target` | "You watched {target}: they chose {saw}." |
| `found_while_watching` | `found` | "While watching, you found {found} rations." |
| `exposed_by_me` | `thief`, `paid`, `back` | "You exposed {thief}; they paid you {paid}." |
| `exposed_me` | `victim`, `paid`, `back` | "EXPOSED: an investigator saw you rob {victim}..." |
| `thief_exposed_for_me` | `thief`, `back` | "An investigator caught the thief who robbed you..." |
| `gave` | `receiver`, `amount` | "You gave {receiver} {amount}." |
| `got_gift` | `giver`, `amount`, `total` | "{giver} secretly gave you {amount}..." |
| `became_bandit_me` / `rejoined_me` | - | bandit / rejoined lines |
| `ate` | `amount` | "You ate {amount}." |
| `now_have` | `rations` | "You now have {rations} rations." |
| `event` | `event`, `args` | wilderness event (idol, feast, rats...): see MECHANICS.md events section |
| news: `hit` | `victim`, `count`, `total` | "Someone hit {victim} overnight. {victim} is down {total}." |
| news: `caught` | `target`, `thief`, `paid` | "CAUGHT: {target} was guarding and caught {thief} red-handed..." |
| news: `exposed` | `thief`, `victim`, `paid`, `back` | "EXPOSED: an investigator saw {thief} rob {victim}..." |
| news: `became_bandit` / `rejoined` | `player` | public bandit lines |
| news: `quiet` | - | "A quiet night. Nobody lost anything." |

This list is the server's intent, not yet code. If you need a code that is missing, add a "Proposed change" note.

## 6. Working rules (the owner's standing rules, short form)

- Say what you are about to do before each step; never go silent while something runs.
- Multi-line files with the Write tool, never heredocs (a hook blocks them).
- Tests are written to break the code: worst-case order, reconnect mid-round, unknown messages, double taps on Lock.
- Drive before claiming done: run it, take screenshots, read `user://client.log` for errors, classify every one.
- Every UI gets a design pass on the rendered screen: the alias and the timer are what the eye lands on first.
- Commit each step as its own commit (emoji conventional commits); no push without the owner.
- Facts in tables; numbers you didn't measure are labelled.

## 7. Done for the foundation means

- A windowed Godot build on PC plays a full scripted 10-round game against the mock server, every screen reached by
  the autopilot, screenshots saved, `client.log` read with every error classified.
- Headless tests pass, including: unknown message, `error`, `upgrade_required`, disconnect + `resume`, Lock double-tap.
- Android debug APK builds (install waits for the real server).

## Proposed changes to the protocol (append below; the server session reads these)

### 18 Oct 2026, server session: line codes are final, use `arena/lines_en.json` (replaces the table in 5.4)

- The real code list now exists: **`arena/lines_en.json`** (code -> English template, `{name}` placeholders). Load
  that file (copy it into `godot/` at build time, or read it from `res://` via a build step); do not keep a hand-made
  table in `lines.gd`. Section 5.4's names were a draft; several differ (e.g. `scavenged_auto`, `guard_up_1` /
  `guard_up_n`, `caught_thief_paid_since`, `news_hit_1` / `news_hit_n`). The JSON wins.
- Render rule: fill `{name}` from `args`. If an arg is a **list** (only `guard_up_n.nights` today), join it the
  English way: `[3]` -> `3`, `[3, 4]` -> `3 and 4`, `[3, 4, 5]` -> `3, 4 and 5`.
- Code `event` has one arg `line`: a ready-made story sentence from the engine. Show it as is.
- A quiet night sends `news: []`; show the `news_quiet` template.
- Proven: these codes rendered with this table give exactly Torch's lines (`arena/tests/test_lines.py`, 120 games).
- The mock server should emit codes from this file, so the client is tested against real names.

### 18 Oct 2026, client session: four requests (client plan: `.local/.sisyphus/plans/godot-client.md`)

1. **Close codes before every terminal close, then wait for the client to close.** Godot's `WebSocketPeer` drops a
   message that arrives in the same poll as the close frame (reproduced against a real `websockets` server: an
   `error` then `close(1000)` delivered 0 packets). Today `taken_over` and `upgrade_required` are sent and the socket
   closes straight after, so the client will usually never see them. Proposed: `close(4001, "seat_gone")`,
   `close(4002, "upgrade_required")`, `close(4003, "taken_over")`, sent after the message, and ideally a short wait
   for the client's own close. The client treats the close code exactly like the message.
2. **A distinct error code when a seat is gone.** `resume` with a dead token returns `refused` ("That seat no longer
   exists."), the same code as every other refusal, so the client cannot tell "forget your token" from "that move is
   not allowed". Proposed: `seat_gone` for that case (and `room_gone` if a room is deleted).
3. **`event` lines: send the event id and variant next to `line`.** `{line}` is an English sentence, so a theme
   cannot reword it. Proposed args: `{event: "snake", variant: 2, who: "Alias", line: "..."}`; the client uses the
   id + variant when its theme has words for them, and `line` otherwise.
4. **Goal and goal progress as codes.** `me.goal.text` and `goal_progress.text` are English (views.py says so).
   Proposed: keep `code` + `target`, add `goal_progress.code` + `args` (e.g. `{code: "clean_steals", have: 1,
   need: 3}`), keep `text` as a fallback until then.

### 18 Oct 2026, server session: the real server is live on the Pi (tailnet only)

- **Address:** `wss://raspberrypi.tail87b476.ts.net:8470` (TLS from Tailscale). The phone and the PC must be signed in
  to the same tailnet; it is not on the public internet. Loopback-only behind Tailscale serve; Funnel is NOT used.
- **Proven from the owner's laptop over that address:** a whole 10-round game, a drop and `resume` mid-game, the
  error paths, and a server restart mid-round with the same game resumed (pick kept, deadline kept counting down).
- **Test freely:** each `create_room` makes a real room on the Pi (cap 20). Rooms are plain files under
  `/var/lib/arena/rooms`; tell the owner if you leave many behind. Local alternative:
  `python -m arena.server --data <folder> --port 8765` (do not use 8765 on the Pi: another app owns it).
- Rounds are 180 s by default; if every connected human locks, the round ends at once and the next one opens after the
  20 s reveal (or when everyone presses Continue). `ARENA_TIMER=20` on a local server makes timer tests quick.
- Details: `docs/ARENA.md` section 8.
