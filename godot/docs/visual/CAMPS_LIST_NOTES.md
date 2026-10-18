# Open camps: what the client does, what it assumes, what the server must do

Client side of the proposal "18 Oct 2026 13:59" in `docs/arena/GODOT_FOUNDATION.md`. The server part is not built yet, so
today the list is invisible and every old path is unchanged (proved by `tools/run_live_tests.py --only rooms`, which prints
`LIVE3 SKIP` against today's server and then checks a plain create still reaches the lobby).

## Where it lives (all protocol knowledge is in ONE file)

| Piece | File |
|---|---|
| The proposal as code: frame shape, limits, sanitiser, 3 s rules, poll rates | `core/rooms_watch.gd` (`RoomsWatch`) |
| Polling, connection use, error attribution, create/join | `autoload/session.gd` (section "the open-camps list") |
| The `rooms` frame passes validation as "an object"; entries are cleaned one by one | `rulesets/survivors/ruleset.gd` (`SCHEMAS.rooms`) |
| Neutral model for screens `{supported, rooms, stale, loading}` | `autoload/model_feed.gd` (`Feed.rooms_model()`) |
| Calls screens may make | `autoload/intents.gd`: `rooms_watch(bool)`, `list_rooms()`, `create_room(visibility, name)`, `join_room(code, from_list)` |
| `list_rooms` gets no ack timer; a tick signal drives the poll | `autoload/net.gd` (`NO_REPLY`, `ticked`) |
| UI | `screens/open_camps.gd` (the list), `screens/title_screen.gd` (the sheet), theme variations `CampCard`, `Veil` |

To change the protocol: edit `rooms_watch.gd` (constants, `sanitize`, the field names) and `Session.create_camp`.

## Behaviour, as built

* The title screen asks for the list while it is showing (`Intents.rooms_watch(true)` in `_ready`, `false` in `_exit_tree`).
  Watchers are counted, so a rebuilt screen cannot switch the list off by leaving late.
* One `list_rooms` as soon as the handshake is done, then about every 3 s. Never while an intent waits for its answer (an
  `error` would be taken for the wrong request), never off the title screen.
* No `rooms` reply 3 s after a request: the list is hidden (`supported:false`), polling drops to every 15 s in case the server
  is upgraded. A later valid reply brings it back. An `error` answering the list request hides it too, silently
  (`rate_limited` is read as "the list you have is current"). The silence is never taken for a dead socket.
* Leaving the title screen (a game starts) stops everything. A dropped line marks the list `stale` (dimmed, still readable) and
  the reconnect asks again at once; the new connection must prove itself with a valid reply before `supported` is true.
* A stored seat is NOT resumed just because the list opened the line; Resume still works on the already open line.
* `create_room` carries `visibility` / `name` ONLY once a valid `rooms` reply has been seen on this connection; otherwise it is
  exactly `{"t":"create_room"}` as before. Name: control and direction characters removed, spaces tidied, at most 24 characters.
* Create opens the sheet (name, Public default / Private, one plain sentence each) only when the server can list camps; on any
  other server it creates at once.
* Tapping a card joins that code through the normal join path. Any refusal of that join (full, started, gone, anything else)
  gives one neutral notice ("That camp filled up or closed first. Here is the fresh list.") and an immediate refresh.
  A typed code keeps the old error path.
* Rows are diffed by code; a refresh changes words in place and adds or removes only what came or went.

## Assumptions where the proposal is silent (all in `rooms_watch.gd` unless noted)

1. Codes are letters and digits, at most 12 characters; anything else is dropped.
2. A camp with no free seat (`seats_taken >= seats_total`) is not joinable and is dropped; so are negative counts, more than 12
   seats, non-whole numbers, and an entry without a usable `age_s` (a negative age, a non-number).
3. `age_s` above a week is shown as a week. `age_s` is seconds; "just now" below a minute, then minutes, hours, days.
4. Replies carry no request id, so they are matched by order: the last valid `rooms` frame wins, a repeated code is kept once
   (the first), and a frame that arrives after the list was closed is ignored.
5. `list_rooms` is allowed before a seat exists and the server needs no new `hello` field. `hello_ok.features` is NOT read yet
   (the proposal offers it as an option); if the server adds `features: ["list_rooms"]` it is a one-line change in
   `Session._on_handshaken` to set `supported` from it.
6. Hostile frames: at most 200 entries are even looked at, 20 kept. A frame over 64 KB is still refused by the existing `Net`
   size guard (too big), which is unrelated to this feature.
7. The "refresh indicator" is a small dot that flashes once per fresh list and is steady while the first answer is awaited.

## What the server session must do for it to light up

1. Answer `list_rooms` with `{"t":"rooms","rooms":[...]}` (newest first, at most 20; entries `code`, `seats_taken`, `seats_total`,
   `age_s`, optional `name`). Only joinable camps (lobby, not full, host connected). No aliases, no seat order.
2. Accept `visibility` (`"public"|"private"`) and `name` (<= 24) on `create_room`, default public when absent.
3. Rate-limit `list_rooms` per connection; either answer or `error` `rate_limited` is handled.
4. Answer a join of a camp that filled, started or vanished with any `error`; the client does not depend on the code.
5. Optional: `hello_ok.features`.

Nothing else changes: with none of this the client behaves exactly as before.
