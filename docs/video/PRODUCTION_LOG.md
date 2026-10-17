# Production log: making the explainer with free tools over MCP

A running ledger of how the Survivors explainer is made, so the next run starts from what is known
instead of rediscovering it. The plan is `AGENT.md`; deviations from the spec are in `output/NOTES.md`.
Newest findings are added to the section they belong to, with the date.

## The toolchain

| Job | Tool | Licence / cost | How it is driven |
| --- | --- | --- | --- |
| Voiceover | Kokoro-82M via `kokoro-onnx` 0.6.1 | Apache 2.0, free, offline on CPU | `tools/tts_kokoro.py` |
| Resample to 48 kHz | ffmpeg (winget) | free | called by `tts_kokoro.py` |
| Drawings | VectorCraft | ArtCraft suite | MCP `vectorcraft`, live window on port 7979 |
| Chat screens | FigCraft 0.6.0 | ArtCraft suite | MCP `figcraft`, live window on 7983 |
| Animation | EffectCraft | ArtCraft suite | `effectcraft-cli --bridge 7981 run …` + MCP `effectcraft` |
| Audio mix | SoundCraft | ArtCraft suite | MCP `soundcraft`, live window on 7982 |
| Edit and export | FilmCraft 0.8.0 | ArtCraft suite | MCP `filmcraft`, live window on 7984 |
| Glue | Python 3.14, Pillow 12.2 | free | scripts in `tools/` |

## Order of work (what actually worked)

1. `python build.py` → read `build/TODO.md`.
2. Voiceover first: `tts_kokoro.py`, then `python build.py done 'vo:*'` and `python build.py`. Scene lengths
   come from the recordings from then on (2:36 with `bm_george` at 0.9).
3. Drawings: `tools/assets_svg.py work/asset_svg` writes every asset as SVG with named groups; VectorCraft
   opens each and exports SVG (text as outlines) + 2x PNG into `output/01_assets/`. Then
   `assets_svg.py work/asset_svg/parts --parts` writes one SVG per pose, icon and moving piece for animation;
   VectorCraft exports those as PNG into `output/01_assets/parts/`.
4. Chat screens: `tools/ui_screens_svg.py work/ui_svg`, FigCraft `file.import` each into one file, check,
   `file.export` PNG 2x + SVG into `output/02_ui/`.
5. Check by eye: `tools/contact_sheet.py <folder> <png>` puts every PNG on one sheet.
6. Scenes: `python tools/effectcraft_scenes.py [scene_XX ...] [--keep] [--no-render]` builds each scene in
   the live EffectCraft window from `build/scenes.json` (lengths and beat times) and renders it to
   `output/04_scenes/scene_XX.mp4`. `--keep` adds to the open project instead of starting a new one.
   Always `--dry` first. Look at scenes: `python tools/scene_strip.py work/probe/x.png scene_03 scene_05`
   (five frames per scene, scenes stacked).
   Known first-pass flaws to fix in the second pass: scene 11 counters "0 / 3" and "1 / 3" overlap
   for a moment; lamp glows in scene 1 wash out the desks; scene 13 "THE REVEAL" in gold is hard to read
   on the cork board (needs a dark band or outline); scene 14 daylight greys the floor plan instead of
   lighting it (use a lit version of the plan, not a translucent overlay).
7. Music: `python tools/score_midi.py` writes `work/music/score.mid` from the scene timings (96 bpm bass
   pulse + drum heartbeat, cut at the scene 13 drumroll, snare roll into a crash on the curtain, back for
   scene 14). Nothing to license: it is played by SoundCraft's built-in synths.
8. Mix in SoundCraft (live window): `new_session {sample_rate: 48000}`, `event.tempo {bpm: 96}`,
   `file.import_midi {path}` (it made an instrument track per MIDI track and put channel 10 on
   `drum_synth` by itself), `track.new {kind: audio, format: mono, name: VO}`, one
   `file.import_audio {path, track: VO, at: {seconds: start_s}, new_tracks: false}` per scene,
   `mix.instrument` for the synth sound, `mix.volume {tracks, db | delta_db}`, then `bounce_mix`
   (it reports integrated LUFS and true peak, so loudness is checked in the same call).
   First bounce: −21.6 LUFS, peak −7.3 → +5.6 dB on all tracks → see the result row below.
9. Final cut in FilmCraft (live window): `file.newSequence {fps: 30, …}`, `media_import` the mix and the 14
   scene clips, `timeline.place {item, track: A1, seconds: 0}` for the mix, `timeline.place {item, track:
   V1, seconds: start_s, audio: false}` per scene, `sequence.applyVideoTransition {clip, effect:
   cross_dissolve, frames: 9, edge: in}` on scenes 2–14 (accepted although the clips have no handles),
   `captions.import {path: build/captions.srt}` (43 segments) + `captions.setStyle` (Inter 44, #F4F1E8 on
   #000000B3, bottom, margin 0.06), then `export.quick {preset: "High Quality 1080p HD", path, wait: false,
   burnCaptions: true, audio: {bitrate_kbps: 192, …}}` and poll `export.queue.list`.
   Check a frame of the cut with `render_frame {seconds}`: it shows picture + caption box together.

How the scene builder works: every image is placed at 50% (2x exports), the avatar part's feet sit
150 px below its centre, chat-screen reveals are rectangles in the screen's own background colour that
fade out on the beat (no masks needed), on-screen text is an Inter Bold text layer held to the end,
and every keyed property is eased with `prop.select {selectKeys}` + `keys.easyEase`.

## Running the apps so the work is visible

- Every Craft MCP decides at start-up whether to drive a live window or run headless. **Start the app
  windows first**, then (re)connect the MCPs in `/mcp`. An MCP started before its window stays headless.
- Launch lines and MCP args:

| App | Launch | MCP args |
| --- | --- | --- |
| VectorCraft | `vectorcraft.exe --control 7979` | `mcp --connect 127.0.0.1:7979` |
| EffectCraft | `effectcraft.exe --control 7981` | `mcp --bridge 7981` |
| SoundCraft | `soundcraft.exe --control 7982` | `mcp --connect 7982` |
| FigCraft | `figcraft.exe --control 7983` | `mcp --attach 7983` |
| FilmCraft | `filmcraft.exe --graphics software --control 7984` | `mcp --bridge 127.0.0.1:7984` |

- Check a port is up: `Get-NetTCPConnection -State Listen -LocalPort 7979,7981,7982,7983,7984`.
- Check an MCP reaches the window, not headless: VectorCraft `screenshot {window:true}` errors when headless;
  FigCraft `inspect_ui` lists `windows`; `tools/mcp_probe.py "exe|--attach|7983"` prints the backend line.
- Bring the app being worked in to the front: `tools/focus.ps1 <processname>` (taps Alt to lift Windows'
  focus lock, maximises, SetForegroundWindow).

## Traps already hit

| Date | Where | What happened | Fix |
| --- | --- | --- | --- |
| 17 Oct 2026 | Kokoro | Package metadata says Python < 3.13 | `pip install --ignore-requires-python kokoro-onnx`; runs fine on 3.14 |
| 17 Oct 2026 | Kokoro | `misaki`/`kokoro` (torch build) pin < 3.13 too | use `kokoro-onnx` (onnxruntime has cp314 wheels, no torch) |
| 17 Oct 2026 | FilmCraft 0.8.0 | Segfault at start-up on Intel Iris Xe, both `default` (Vulkan) and `dx12` | `--graphics software` |
| 17 Oct 2026 | All Craft MCPs | Registered headless because the app wasn't running when Claude Code started | launch windows, then `/mcp` reconnect each |
| 17 Oct 2026 | VectorCraft | A CSS font list falls back to Source Sans 3 after the first family, not to the next one | put an installed font first: `'Arial Rounded MT Bold'` (headline), `'Segoe UI'` (body); Fredoka and Inter aren't installed |
| 17 Oct 2026 | FigCraft | My text-width estimate was too small; timestamps overlapped names | `width()` helper at 0.56 em/char (0.6 bold) |
| 17 Oct 2026 | EffectCraft | It bundles Inter, so EffectCraft text can use the spec's body font | — |
| 17 Oct 2026 | Script | Wording fixes pushed two on-screen texts over the 8-word rule | check: on-screen text ≤ 8 words after every script edit |
| 17 Oct 2026 | Shell | Heredocs are blocked by the guardrail hook | write files with the Write tool, run them |
| 17 Oct 2026 | `claude` in Git Bash | Resolves to a wrapper that rejects `mcp add` | run `claude mcp …` from PowerShell |
| 17 Oct 2026 | Chrome extension | Can't open `file://` pages | serve the folder: `python -m http.server 8765 --bind 127.0.0.1` |
| 17 Oct 2026 | EffectCraft CLI | `renderQueue.render {wait: true}` fails with `timeout` after ~60 s; the render keeps going in the app and finishes | `wait: false`, then poll `renderQueue.list` until the item's `status` is `Done`; remove finished items |
| 17 Oct 2026 | EffectCraft | Rendering is about 4 frames/s here (scene 1: 279 frames in 66 s) with 4K-wide PNG layers | budget ~7 s of render per second of video; smaller source PNGs would be faster |
| 17 Oct 2026 | Title logo | The full `title_logo` has a navy backing rectangle that would cover the scene | `parts`: `title_large` / `title_small` keep only the lettering groups |
| 17 Oct 2026 | EffectCraft | Ration tins at scale 60 were 144 px wide and merged into one gold bar in scene 3 | tins at scale 35 (84 px); always check sizes against the 2x export, not the SVG units |
| 17 Oct 2026 | Scene builder | A crash mid-run left a half-built comp; rerunning would add a second comp with the same name | `Scene()` deletes any comp of the same name first (`project.delete {items: [name]}`) |
| 17 Oct 2026 | EffectCraft import | `file.import` turned `avatar_colours_1..4.png` into one image sequence `avatar_colours_[1-4].png`, so `layer.addItem {item: "avatar_colours_1.png"}` failed with "no item" in scene 9 | `file.import {paths, sequence: false}`; first suspected `project.delete` and checked the project instead of guessing: nothing had been deleted |
| 17 Oct 2026 | Background runs | The task wrapper reported exit 0 for a run whose script printed `exit 1` | read the log's last lines, never the wrapper's status |
| 17 Oct 2026 | SoundCraft mix | First bounce −21.6 LUFS; music ~25 dB under voice (spec 15–20) | +5.6 dB all tracks, +6 dB music: final −15.94 LUFS, true peak −1.52 dB; measure the music in a voice gap with `ffmpeg -ss A -to B -af volumedetect` |
| 17 Oct 2026 | Scene builder | The same Python mistake (a positional scale plus `scale=`) crashed two long runs midway, after minutes of rendering | `effectcraft_scenes.py --dry` builds all 14 scenes against a fake app in a second; run it before every real run |
| 17 Oct 2026 | EffectCraft | Later scenes rendered in about a minute each; scene 1 took 66 s because of three full-frame 4K layers (floor plan, lamps, dim) | render time follows the area of big layers, not the layer count |
| 17 Oct 2026 | FilmCraft | A fresh project already holds a default 23.976 fps sequence ("Main Edit") | create our own with `file.newSequence {fps: 30}` and export that one |
| 17 Oct 2026 | FilmCraft export | `export.quick` ignored the `audio: {bitrate_kbps: 192}` override (file has 320 kbps); the preset's audio wins | save a custom preset with `export.presets.save {name, from, …}` and export with it |
| 17 Oct 2026 | FilmCraft export | `export.quick {wait: false}` doesn't appear in `export.queue.list`; the MP4 has no moov atom until it's finished | wait until `ffprobe` can read the file (loop every 5 s); 156 s took ~410 s in software mode |
| 17 Oct 2026 | Final check | `ffmpeg -af ebur128=peak=true` reads LUFS of the export; one 8-frame `tile` strip across the cut confirms burned-in captions | — |
| 17 Oct 2026 | Animation | Variants on one sheet (8 poses, 5 icons) can't be animated separately | `assets_svg.py --parts`: one image per pose/icon; stacked pieces keep the parent's canvas so they line up |

## Command reference that worked

**VectorCraft (MCP `command_batch`):** `document.open {path}` (SVG groups become named layers),
`document.export {path, format: svg, outlineText: true}`, `document.export {path, format: png, scale: 2,
background: transparent}`, `file.close`, `file.closeAll`, `document.find {name}` to check a layer name.
SVG export keeps layer names as ids by default (`objectIds: layerNames`). `vectorcraft-cli run` is headless
only, so batches go through the MCP to stay visible. A batch of 99 steps ran without trouble.

**FigCraft (MCP):** `file.new {name}`, `file.import {path, x, y}` (an SVG becomes a layered frame; returns
its id), `node.set {ids, name}`, `file.export {ids, format, scale, path}`, `save_file {path}`,
`file.close {force: true}`.

**EffectCraft (`effectcraft-cli --bridge 7981 --json run id json id json …`):** drives the live window.
`file.newProject`, `file.import {paths: [...]}` → `{items}`, items are named after the file
(`avatar_standing.png`), `comp.new {name, width, height, frameRate, duration}` → `{comp}`,
`layer.addItem {item, position}` → `{layer}`, `layer.newText {text, name, position, font, style, size,
fill}`, `layer.rename`, `prop.set {layer, path: transform/scale, value: [50,50]}`,
`prop.addKey {layer, path, time, value}`, `prop.select {layer, path, selectKeys: true}` then
`keys.easyEase`, `comp.settings {background}`,
`renderQueue.add {comp, format: h264, output, audio: off}` then `renderQueue.render {wait: true}`.
A 4 s 1080p30 probe rendered to H.264 in about 7 s wall-clock.
PNGs are exported at 2x, so place them at 50% scale for 1 SVG unit = 1 comp pixel.

**SoundCraft (MCP):** see step 8 above. Built-in instruments: `subtractive_synth`, `drum_synth`
(GM drum notes: 36 kick, 38 snare, 42 hat, 49 crash), `sampler`; effects include `compressor`,
`maximizer`, `room_reverb`, `signal_generator`. `engine.plugins` lists every parameter with its range.
`save_session {path}` writes the session plus its audio files.

**FilmCraft (MCP, live window via `--bridge 127.0.0.1:7984`):** `file.newSequence {name, width, height,
fps, sampleRate, video, audio}`, `media_import {paths}`, `timeline.place {item, track: V1|A1, seconds,
insert: false, video, audio}`, `sequence.applyVideoTransition {clip, effect: cross_dissolve, frames,
edge: in}`, `captions.import {path}` then `captions.setStyle {track: C1, font, size, color, background,
backgroundColor: #rrggbbaa, align, anchor: bottom, margin}`, `export.resolve {preset}` shows every
setting key, `export.quick {preset, path, wait, …overrides}`. Settings keys that matter here:
`burnCaptions`, `crf`, `bitrateMode`, `audio.bitrate_kbps`, `frameRate`. Preset used:
"High Quality 1080p HD" (H.264 1920×1080, 20 Mbps VBR). Time is 254016000000 ticks per second.

## Open questions carried forward

- Launch date for `ui_join` (`[LAUNCH DATE]`).
- Music track: royalty-free, picked by a person.
- Voice: decided 17 Oct 2026, the owner picked `bm_george` (British male) from the four on
  `work/voice_audition/index.html`. Speed 0.9.
