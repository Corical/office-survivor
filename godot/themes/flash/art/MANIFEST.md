# Flash theme art: manifest

Hand-built layered SVG, exported to PNG at 2x through VectorCraft (`vectorcraft-cli convert --scale 2`). Sizes below are the
nominal size; the PNG is exactly twice that in pixels (checked by `src/contact_sheet.py`). Base layout is 540x960 portrait.
No third-party art or fonts. SVG sources and generators are in `src/` (`src/.gdignore` keeps Godot from importing them).
Rebuild everything with `python src/build.py`, then `python src/contact_sheet.py`.

Light model for every piece: cool moon rim light from the upper left, warm firelight from the camp. Nothing here names a thief,
a bot, or anyone's exact food.

| File | Nominal size | PNG px | What it is |
|---|---|---|---|
| backdrop_far.png | 540x960 | 1080x1920 | Opaque. Night sky, large moon with halo, stars, clouds, ocean with moon road, far islands, faint ember glow at the bottom |
| backdrop_near.png | 540x960 | 1080x1920 | Transparent. Jungle and rock silhouettes framing left, right and bottom, vignette, centre open. Draw over backdrop_far |
| logo.png | 480x220 | 960x440 | Transparent. Fire-over-island medallion plus outlined SURVIVORS wordmark with ember glow. Wordmark is outlines, no font. Subtitle strip (bottom 24 px) left empty |
| move_scavenge.png | 192x192 | 384x384 | Medallion, green accent: crate with leaves, banana, coconut |
| move_guard.png | 192x192 | 384x384 | Medallion, cyan accent: shield with a lit lantern |
| move_steal.png | 192x192 | 384x384 | Medallion, coral accent: a hand in shadow reaching for a ration |
| move_investigate.png | 192x192 | 384x384 | Medallion, violet accent: magnifier with a watching eye |
| move_gift.png | 192x192 | 384x384 | Medallion, ember accent: wrapped parcel with bow |
| hut.png | 192x192 | 384x384 | Transparent. Thatched shack, lit window, ground shadow and warm light pool |
| hut_me.png | 192x192 | 384x384 | Same hut (same position, swap-compatible) plus a bright ember halo ring and back glow so "you" reads at once |
| campfire.png | 256x256 | 512x512 | Transparent. Flames, four logs, ring of stones, rising embers |
| campfire_glow.png | 512x512 | 1024x1024 | Transparent warm radial glow, for additive blending (centre opaque ember-white, fades to nothing) |
| avatar_0.png ... avatar_7.png | 128x128 | 256x256 | Eight survivor busts: beanie and beard, straw hat, bandana and afro, backwards-style cap with glasses, long auburn hair and scarf, parka hood with goggles, eyepatch and red bandana, pith hat and moustache. Cropped at the bottom edge |
| fx_spark.png | 32x32 | 64x64 | White soft spark with a four-point core, tint in engine |
| fx_crumb.png | 32x32 | 64x64 | White soft irregular crumb, tint in engine |
| fx_ring.png | 128x128 | 256x256 | Thin white ring with soft edge and faint glow |
| fx_shield.png | 192x192 | 384x384 | Translucent white-cyan hex-lattice bubble, brighter at the rim, highlights |
| card_frame.png | 128x128 | 256x256 | 9-slice panel frame: dark wood, brass liner, brass corner brackets. Centre transparent. **Margins 40 px nominal (80 px in the PNG)**. Edges are uniform along their length |
| button_wood.png | 256x96 | 512x192 | 9-slice chunky wood button with lip and gloss, brass studs. **Margins: left/right 36, top 30, bottom 30 nominal (double in the PNG)**. Centre is flat, no text |
| button_wood_pressed.png | 256x96 | 512x192 | Same, face sunk onto a thin lip, darker, less gloss. Same margins, same text area (the face sits 5 px lower than in the normal one) |
| contact_sheet.png | 2000x2354 | | Everything together on the dark ocean, plus 9-sliced demos of the frame and button |

Tint notes: avatars, badges, huts and campfire are full colour (do not tint). `fx_*` and `campfire_glow` are meant to be tinted or blended additively.
