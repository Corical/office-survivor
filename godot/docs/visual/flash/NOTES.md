# The flash theme ("Long Night"): design notes

Theme id `flash`, title "Long Night". Files: `godot/themes/flash/` (theme.gd, words.po, icons/), registered in
`godot/themes/registry.gd`. Switch with `Themes.use("flash")`.

## The choice, and why

**The Camp, drawn with the Signal's discipline.** The three treatments in `VISUAL_EXPLORATION.md` section 6 differ in
layout (a diorama, a table, a radar), and layout is not a theme's to change. What a theme owns is words, colour,
type, shape and icons. So the Camp is what carries here: the words (nights, camps, a watch, a stake-out, "Camp QYAZ"),
a night-sky palette lit by one ember accent, and hand-drawn icons for the shelter, the fire, the mask and the
helicopter. The Signal supplies the restraint: one accent colour, a strict type scale, nothing decorative that is not
also information. The Table was dropped because its core (cards you slide) is layout. The Stage already puts the homes
on a ring, which is the Camp's own picture, so the theme and the existing Stage agree.

**The design idea.** Everything is night, and the ember is the thing you act on: your name, the clock, Lock in. Raised
slate buttons are for choices; the one ember button on a screen is the next step.

## What was built

| Part | Detail |
|---|---|
| Palette | Night-blue surfaces `#0a0f1c` `#111a2e` `#1b2742` `#26365a`; warm paper text `#f6f1e7`; muted `#d0d9ea`; ember `#ffb347` (hi `#ffcc7a`, lo `#e8892b`, lip `#a8590f`); focus ring `#8fe8f7` |
| Type | Built-in font only (emboldened to three weights through `FontVariation`). Scale 16 (small caps labels, spaced) / 20 (body, buttons, inputs) / 28 (clock, amounts) / 46 (your alias, room code, app name). Default size stays 18 because the Stage derives its label size from it |
| Backdrop | A radial firelight glow rising from the bottom edge, in the ScrollContainer panel slot, fading to the clear colour so there is no visible frame |
| Buttons | Raised slate with soft shadow, lit ember edge on hover, sink on press, 3 px cyan focus ring; `PrimaryButton` is ember with a dark lip and a faint glow; disabled states are dim slate with 5:1 text |
| Other controls | `ProgressBar` (lit top edge, ember glow), `LineEdit` (well, ember focus), scrollbars (rounded, ember on hover/drag), `Card`, `Banner`, tooltip |
| Ready for screens that do not use them yet | `ChosenButton`, `UrgentBar`, `Card`, `Banner` (see REQUESTS.md) |
| Stage colours | `text` paper, `home` slate blue, `home_me` ember, `food` gold, `loss` coral, `shield` cyan, `marked` violet. All 3:1 or better on the sky; `home_me` is far lighter than `home`, so "me" survives greyscale |
| Words | `words.po`: the same 182 keys as the placeholder, the same `{slots}` per key (checked), 80 reworded and 102 deliberately kept (rule numbers, pass-throughs). No emoji. Moves: Forage, Keep watch, Steal, Stake out, Give. Section labels are upper case (`PICK YOUR MOVE FOR TONIGHT`) |
| Icons | 25 SVG files, 28 ids (shared textures for `status`, `shield_on`, `band.bandit`): 5 moves, `food`, `shield`, `bandit`, `helicopter`, `radio`, all 14 beat kinds, 3 band piles. One 96 px grid, paper line + ember accent, each a silhouette |

Rules kept: no number in a rule changed (`back up to 3`, `3 clean steals`, `two nights`); no sentence names a thief,
an investigator, a bot or another player's exact food that the placeholder wording did not; the radio phrases keep
`{a}` and stay unattributed.

## Accessibility (measured by `check.tscn`, WCAG 2.x relative luminance)

| Pair | Ratio | Wanted |
|---|---|---|
| Body text on the sky | 15.4 | 7 |
| Body text on the brightest part of the glow | 9.7 | 7 |
| Muted (small caps) text on the sky / on the glow | 12.2 / 7.7 | 7 / 4.5 |
| Alias and room code (ember) on the sky | 11.7 | 7 |
| Button label on a raised button | 10.6 | 7 |
| Primary label on ember (rest / hover / pressed) | 10.4 / 12.4 / 7.1 | 7 |
| Disabled labels (primary / secondary) | 6.4 / 5.0 | 4.5 / 3 |
| Input text, placeholder | 17.0, 6.7 | 7, 4.5 |
| Button edge, Stage home disc on the sky | 4.0, 3.2 | 3 |
| Stage food / loss / shield / marked on the sky | 12.4 / 6.6 / 10.9 / 9.1 | 3 |

State never rides on colour alone: bands have words (and a pile-shaped icon ready), Lock has three different words and
a different button state, a bandit has a word, the guard has a word, the Stage uses disc / ring / cross / diamond.
Greyscale and a glare simulation of the real game are in `shots/grey_*.png` and `shots/glare_*.png`.

## How to look at it

| Do | Command (from the worktree root, `godot_console` on PATH) |
|---|---|
| Import once | `godot_console --headless --path godot --import` |
| Screens at phone and desktop width | `godot_console --path godot res://themes/flash/tools_snapshot/snapshot.tscn -- --out=<dir> --log=<file>` |
| Every icon, button state, input, bar, colour on one sheet | `godot_console --path godot res://themes/flash/tools_snapshot/sheet.tscn -- --out=<png>` |
| A whole 10-round game against a real server | `python godot/themes/flash/tools_snapshot/drive_flash.py --out <dir>` |
| Keys, slots, icons, colours, variations, contrast | `godot_console --headless --path godot res://themes/flash/tools_snapshot/check.tscn` |
| Greyscale and glare copies | `python godot/themes/flash/tools_snapshot/variants.py <drive dir> <dest>` |
| Regenerate | `python godot/tools/gen_flash_words.py`, `python godot/tools/gen_flash_icons.py` (then import) |

## What I looked at and what I did not

Looked at (screenshots in `shots/`): title, settings open, lobby, round (open, choosing a target, picked, locking, radio
open and disabled, reconnecting banner), reveal (nights 1, 2, 5 and 10 of the driven game; the one beat I saw in flight
was food moving), end, round at 1280 by 720; a full 10-round game driven with real mouse events against a real arena server
(PASS, 58 taps, 0 warnings, run twice); greyscale and glare copies of three screens; every icon and every button
state on one sheet.

Not looked at: a real phone, real sunlight (the glare copy is a simulation); the Upgrade screen; the notice toast and
the "can't reach the server" banner; narrow phones below 450 px logical width; larger OS text scale; the reveal at
desktop width; mid-animation frames of beat kinds other than food moving (`blocked`, `marked`, `status`, `charm`,
`camp` were not seen drawn); a bandit's roster line and the end screen with a bandit; mouse hover and a keyboard focus
ring in the live game (seen on the contact sheet only); the five-second-test with a person who has not seen the game.
The icons are reviewed by me only; none has been seen at 24 px (the size a roster line will use).

Known roughness: the Stage still draws plain discs and its band labels clip long aliases (REQUESTS B1); the end table
wraps names mid-word (A6); the reconnecting banner overlaps content (A5). All are screen or Stage code, not the theme.
