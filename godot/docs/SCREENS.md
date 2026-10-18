# Screens: shared and game

Plan step 3.4 (`game-platform-decoupling.md`, section 4.6). **This table is read by `tests/test_architecture.gd`.** Every script in
`screens/` and `stage/` must have a row, and the owner column (`shared` or a game id) decides which rules apply to it:

- `shared`: knows no game. No game word, no game ruleset, no game id, no game line code. It works from neutral models only.
- a game id (today only `survivors`): may use that game's words but must not reference another game's ruleset, adapter or words.

No file has moved. Moving the `survivors` rows into `games/survivors/` is step 3.7 and needs the owner.

| Script | Owner | Why |
|---|---|---|
| `screens/title_screen.gd` | shared | Create, join, resume and settings are the platform's, whatever game is played |
| `screens/upgrade_screen.gd` | shared | "Update the app" is about the protocol, not a game |
| `screens/overlay.gd` | shared | The connection banner and notices; the connection belongs to the platform |
| `screens/open_camps.gd` | shared | The list of open rooms, one card each; the game label goes on the card in step 3.5 |
| `screens/lobby_screen.gd` | shared | Room code, seats, host and kick are the platform's; no game is chosen yet when it is drawn |
| `screens/ui.gd` | shared | Builders for labels, buttons and lanterns; no rules |
| `screens/fit_label.gd` | shared | A label that shrinks to fit; no rules |
| `screens/ring_timer.gd` | shared | A countdown ring; any timed phase can use it |
| `screens/scroll_hint.gd` | shared | A "more below" cue for a scroll area |
| `screens/pulse_dot.gd` | shared | A small status light |
| `screens/charge_fill.gd` | shared | A fill that runs along a button over a time; its comments name a game, its code does not |
| `stage/backdrop.gd` | shared | The scene behind every screen; takes its art from the theme |
| `screens/round_screen.gd` | survivors | Moves, targets, radio and the goal card are Survivors' round |
| `screens/reveal_screen.gd` | survivors | The night's results and radio are Survivors' reveal |
| `screens/end_screen.gd` | survivors | Survivors' final scoring columns |
| `stage/stage.gd` | survivors | Plays Survivors' beats (food moving, shields, bandits); made generic from two games, not one |
| `stage/timeline.gd` | survivors | The beat timeline of a Survivors reveal |
| `stage/timeline_player.gd` | survivors | Plays that timeline; `Feed` still owns one (known coupling, goes with the round-state move into the ruleset) |
| `stage/fx_pool.gd` | survivors | The effects the Stage's beats use |

## Allowed exceptions (a shared script that still contains a game word)

Each entry is a ceiling in `test_architecture.gd` (`ALLOWED`): the count may fall, never rise, and a new word fails. Each names the step
that removes it.

| Script | Word | Count | Why it is still there | Removed by |
|---|---|---|---|---|
| `screens/title_screen.gd` | camp | see test | The player-facing word for a room is "camp": the create sheet's camp-name field, its translation keys, the theme's glow texture name | 3.5 (the picker and label rename rooms; theme keys follow) |
| `screens/open_camps.gd` | camp | see test | The open-rooms list: node ids, translation keys (`ui.open_camps`, `ui.camp_*`) and the `CampCard` theme variation | 3.5 |
| `stage/backdrop.gd` | camp | see test | The theme's `campfire_glow` texture name | 3.5 (theme art keys are renamed with the theme work) |
