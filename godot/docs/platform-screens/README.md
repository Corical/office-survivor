# Platform screens: renders and the lone-Survivors check (plan step 3.5, slice C4)

Made by `tests/snapshot/platform_shots.tscn` (windowed, `--mode=lone|two`), at 360x640, 412x915 and 1280x720, flash theme, reduced motion.
The designer's pictures are in `wt/ui-designer/docs/platform/design`.

| Folder | What | Files |
|---|---|---|
| `two_games/` | A server offering three games (`hello_ok.games`), rooms with `game`, a room of an unlisted game | `title_*` (before hello), `picker_*` (picker on the title), `camps_*` (open rooms with the game label, scrolled into view), `lobby_*` (game name and seat range), `neutral_*` (a phase nothing draws), `update_game_*` (a room of a game this app lacks), `update_*` (protocol upgrade); each at all three sizes |
| `before_lone/` | A lone-Survivors server, code before this slice | the same names for `title`, `picker`, `camps`, `lobby`, `update` at 360 and 412 (PNG) and all three sizes (`.tree.txt`) |
| `after_lone/` | The same, after this slice | same files |

**How "identical for a lone server" is checked.** The backdrop and the logo move between two runs of the same code, so two pictures never
match to the pixel (checked: even two runs of unchanged code differ). Each shot therefore also writes `<name>.tree.txt`: every control with its
class, id, text, visibility and rectangle. Two runs of unchanged code give identical trees (apart from the logo's settling by under 0.2 px).
`before_lone` against `after_lone`: title, picker, camps and lobby are identical except one invisible, zero-size label per open-room card
(`game_tag`, hidden) and the logo's sub-pixel settling. `update_*` differs on purpose: that screen was redesigned (centred, a body line).
