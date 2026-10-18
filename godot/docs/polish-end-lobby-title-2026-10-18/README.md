# End, lobby and title polish: evidence, 18 October 2026

Pictures are 128-colour copies (to keep the repo small). `before/` is the code at the start of the work (old wood art), `after/` is the merged result. The 1904x1001 pictures are not kept here.

| Folder | What it shows |
|---|---|
| `before/`, `after/` | `title_idle`, `title_settings`, `title_settings_advanced`, `title_sheet`, `lobby_host_1of4`, `lobby_host_4of4`, `lobby_guest_2of4`, `end_three_tied_second`, `end_four_tied`, `end_distinct` at 450x800 and 540x960 (the before set has no `title_sheet`, `lobby_host_4of4` or `end_distinct`) |
| `measure/before_slitscan.png`, `after_slitscan.png` | The title logo over 400 frames, one pixel column per frame: a staircase before, a smooth wave after (`tests/perf/logo_bob.gd`) |
| `measure/zoom_title_buttons_450_before_after.png` | Create, Join and Settings at 2x, old art above, new art below |
| `measure/stud_tiles.png` | Each wood variation at 2x, left end: columns Create 72 px, Button 64 px, Button 72 px; top row normal, bottom row pressed. The Button 64 px pressed stud is cut in half |
| `measure/zoom_corners2_540.png` | Left and right ends of Settings and Join at 6x |
| `measure/end_fixture_540x960.png` | The end screen on the harvested fixture |

Tools: `tests/snapshot/polish_shots.gd` (these pictures, with the clearance check), `tests/perf/button_centre.gd` (label centring and stud roundness), `tests/perf/logo_bob.gd` (logo smoothness), `tests/snapshot/title_transitions.gd` (30 fps frame differences), `tests/test_nine_fit.gd` (no nine-patch smaller than its edges).
