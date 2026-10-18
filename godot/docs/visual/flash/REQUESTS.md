# Requests from the flash theme to the engineer who owns screens, stage and autoload

The flash theme is finished as far as a theme alone can go. Each item below is something a theme cannot do. Every one
names the file, the change, why, and what the theme already has ready (so the change is small and the look appears at
once). None of these was made by the design pass; `godot/screens/**`, `godot/stage/**`, `godot/autoload/**`,
`godot/core/**` are untouched.

Ids in this file match `godot/rulesets/survivors/adapter.gd` (`BEAT_KINDS`, move ids) and `themes/flash/theme.gd`.

## A. Needed for the theme to look as designed

| # | File | Change | Why | Theme side, already done |
|---|---|---|---|---|
| A1 | `screens/ui.gd` (`Ui.button`) and `screens/round_screen.gd` (`_act`) | Give `Ui.button` an optional icon id and set `b.icon = Themes.icon(id)` (and `b.expand_icon = true`, `b.icon_alignment`). In `_act` pass the move id (`p.server_id`: `scavenge`, `guard`, `steal`, `investigate`, `gift`). | A move is a picture and a word. The five moves are currently five identical grey-blue pills with text only. A thumb finds a shape faster than a word. | `Themes.icon("scavenge" ... "gift")` return 96 px SVG textures. Button `h_separation` is set. |
| A2 | `screens/round_screen.gd` (`_act`, lines marking `chosen`) | Replace the `" *"` suffix by `b.theme_type_variation = "ChosenButton"` on the picked move, picked target and picked amount (keep the text, drop the asterisk). | The asterisk is the only sign of what you picked, and it is text jammed on a label. A selected pick should look selected. | `ChosenButton` exists: a thick ember frame on a warm fill, bright in greyscale. |
| A3 | `screens/round_screen.gd` (`_tick`) | When `left <= 10` set `_timer_bar.theme_type_variation = "UrgentBar"` (and back above 10). | The clock is the most important thing on the screen and has one look from 180 s to 0 s. The number keeps counting, so this is never colour alone. | `UrgentBar` exists: the bar fill in coral with a glow. |
| A4 | `screens/round_screen.gd` (`_roster`, `_head`) and `screens/ui.gd` | Wrap groups in a `PanelContainer` with `theme_type_variation = "Card"`: the head (alias, clock, food), the picker, the roster, the goal, the radio. Put a band icon (`Themes.icon(e.band)`, ids `band.well_fed`, `band.getting_by`, `band.starving`, `band.bandit`) before each roster line. | Today the round screen is one undivided column of text. Cards give groups, depth and a place for the icons. The band icon is shape-coded (full pile, middle pile, thin pile, mask) so the band is not carried by words alone. | `Card` (rounded, shadow, 18 px padding) exists. Band icons exist. The question in `VISUAL_EXPLORATION.md` 5.4 item 3 (is my home bigger) is a layout choice for the engineer. |
| A5 | `screens/overlay.gd` | Put the net banner and the notice toast each in a `PanelContainer` with `theme_type_variation = "Banner"`, and give the overlay a 16 px top/side margin. | The banner is a bare label glued to the window edge and drawn over the screen content: in `docs/visual/flash/shots/07_round_reconnecting.png` it overlaps the first button and its first letter touches the window edge. | `Banner` exists: coral frame, dark red fill, shadow. |
| A6 | `screens/end_screen.gd` | Render the results as one card per player (alias, a line of marks, then the five numbers as label/value pairs) instead of one grid of six columns. Or put the grid in a horizontal `ScrollContainer`. | On a 540 px wide phone every alias breaks mid-word (`IronSp / atula`, `Wobbl / yTable`) and the marks wrap one syllable per line (`winner / , seat, / goal / met`): see `shots/drive_20_end.png`. A grid of six columns does not fit a portrait phone with 16 px aliases. The `ui.seat_mark` word cannot fix it. | `Card` exists. Icons `helicopter`, `bandit` exist for the winner row and the seat mark. |
| A7 | `autoload/themes.gd` (`use`) and `core/theme_def.gd` | Add `ThemeDef.clear_color: Color` and make `Themes.use` call `RenderingServer.set_default_clear_color(current.clear_color)`. Then delete the `RenderingServer.set_default_clear_color` line in `themes/flash/theme.gd` `build()`. | The flash theme currently sets a global from inside `build()`. It is the only way for a theme to colour the 16 px page margin, because `ScrollContainer` clips its own panel. Switching back to `placeholder` leaves the dark clear colour behind, which is a bug waiting to happen. | One line to delete on my side. |

## B. Stage (`stage/stage.gd`): what it needs from the theme to be a picture rather than a diagram

| # | Change | Why |
|---|---|---|
| B1 | Label width: `draw_string(... Vector2(-70, ...), label, ..., 140, fs - 4 ...)` clips real aliases: `SaltyPretzel  Starvin`, `SoggyBiscuit  Gettin`, `WobblyTable  Well f` (`shots/drive_reveal_05.png`; seen with the flash theme only: I did not render the placeholder reveal to compare). Draw the alias on one line and the band on a second line, or draw the band as its icon (`Themes.icon(e.band)`) next to the alias and drop the word. | The band word is the information the board exists to give, and it is cut off in a normal game. |
| B2 | Draw `Themes.icon(beat.kind)` at the beat's endpoint (and `Themes.icon("food")` for the travelling food instead of the plain gold disc; `Themes.icon("bandit")` in place of the red ring on a `status` beat; `Themes.icon("shield")` on `shield_on`). All 14 beat kinds have an icon. | Right now every beat is a coloured circle or arc. The icons give each of the 13 beat kinds its own shape, which is also what makes them readable without colour. |
| B3 | Draw a centre: `Themes.icon("camp")` at `get_meta("centre")`, a camp fire the homes sit around. | The ring of homes has nothing in the middle; the Camp metaphor needs the fire. |
| B4 | Add named Stage colours the theme can fill: `backdrop` (a rect behind the ring), `ring` (a faint circle the homes sit on), `glow` (the fire's light). The theme will supply values. | Today the Stage is transparent and draws nothing but the homes. |
| B5 | Instance `ThemeDef.beat_scenes[kind]` (already declared in `core/theme_def.gd`, unused by the Stage) at the beat's endpoint when present. | `beat_scenes` exists for exactly this and is the only way to get particles (ember sparks on a theft, a flare on `blocked`, a stamp on `marked`). The flash theme ships none yet because the Stage never asks for them. |
| B6 | Pass the event id to the Stage on an `event` beat (the adapter has it: `bananas`, `coconut`, `cache`, `idol`, `snake`, `rain`, `shelter`, `storm`, `feast`, `rats_top`, `rats`, `raid`) so a theme can supply `Themes.icon("event." + id)`. | There are 12 events and one generic `event` icon. Weather over the whole camp (`storm`, `feast`) and a visitor at one shelter (`snake`) are different pictures. The flash theme can draw all 12 as soon as the id arrives. |
| B7 | `stage/stage.gd` sets `custom_minimum_size = Vector2(0, 340)`, and the ring radius is `min(width, height) * 0.34`, so on a wide window the ring stays about 340 px tall with the log below it. Worth giving the reveal a side-by-side layout (Stage left, log right) at `WIDE_PX` like the round screen has. From the code only: I did not capture the reveal at desktop width. | The reveal is the show. |

## C. Things the theme cannot supply and I did not add

| # | Item | Needs |
|---|---|---|
| C1 | A display typeface for `BigLabel` and `HeaderLabel` (the built-in font is the only one used; weights come from emboldening it). One candidate: a condensed OFL-licensed face such as Oswald, bundled as a `.ttf` in `themes/flash/fonts/`. | The owner's permission to add a third-party font file. Not downloaded. |
| C2 | Sound (ambient fire, a lock click, a theft sting, the helicopter). `ThemeDef` has no audio slot. | A `ThemeDef.sounds: Dictionary` and a player in the Stage/screens. |
| C3 | A second variant of the same theme for a high-contrast setting (`flash_hc`). One line in `registry.gd` plus a colour table; the architecture already supports it. | A settings control, and a decision that it is wanted. The default flash palette already meets 7:1 for text. |
| C4 | Per-event and per-goal icons (12 + 6). | Only useful once B6 and a goal-card icon slot exist. |
| C5 | A pulsing fire for the timer (animation of the bar), a "locked" check mark on the Lock button. | Needs a screen-side AnimationPlayer or tween; `PrimaryButton` disabled state is the static stand-in: a dim slate button reading `Locked in`. |

## Where each icon should appear (for the screen work)

| Icon id | Where |
|---|---|
| `scavenge`, `guard`, `steal`, `investigate`, `gift` | On the five move buttons (A1); in `Your pick: ...` line; in the Stage when a move resolves |
| `food` | Next to `Rations: N` in the head; the travelling item on a `move_resource` beat |
| `shield` | Next to a status line `On guard`; on `shield_on` |
| `bandit` | Next to `Bandit` status and the roster line of a bandit; on `status`; in the end table for a bandit |
| `band.well_fed`, `band.getting_by`, `band.starving`, `band.bandit` | Each roster line and each home on the Stage |
| `helicopter` | The end screen header, and the seat mark in the results |
| `radio` | The `Radio` button and each line of the radio at dawn |
| `move_resource`, `shield_on`, `shield_off`, `blocked`, `empty`, `learn`, `marked`, `status`, `camp`, `charm`, `total`, `quiet`, `event`, `unknown` | The Stage endpoint for the beat of that kind (B2); the centre fire is `camp` (B3) |
