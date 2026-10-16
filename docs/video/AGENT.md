# Survivors explainer video: agent brief

You are producing a 2.5-minute animated explainer for **Survivors**, a two-week office survival game played in Discord. Some viewers are not technical, so every scene teaches one thing, in plain words, with big numbers on screen.

Your tools, reached over MCP: **VectorCraft** (drawing), **FigCraft** (chat-screen mockups), **EffectCraft** (animation), **FilmCraft** (editing and export), and optionally **SoundCraft** (audio mix). Check that each one is available before you start the stage that needs it.

## Golden rules

1. **Start every session with `python3 build.py`.** Work only from `build/` and do only what `build/TODO.md` lists.
2. **Never edit `build/`.** It is regenerated on every run. Words, numbers and visuals come from `../game.json` and `source/`. Never type a game number from memory: they are all in `build/scenes.json` → `game_facts`.
3. **Save each output at the exact path given, then run `python3 build.py done <item>`.** That records what it was made from, so the next run knows it's finished. Wildcards work, e.g. `python3 build.py done 'asset:*'`.
4. **Follow the stage order.** Voiceover comes first because the recordings set every scene's length.
5. **Brand safety:** chat screens look like a generic chat app. Never use the Discord logo, wordmark or mascot. Only the example names in `game_facts` appear on screen.
6. **If a tool can't do what the spec asks,** do the closest thing and write what you did in `output/NOTES.md`. Never skip silently.
7. **Stop and ask the human** at steps marked HUMAN, when a tool is missing, or when a spec is unclear in a way that changes what viewers would learn.

## Folder map

```
survivors/
  game.json                 the game rules: one place for every number (also used by sim/)
  video/
    AGENT.md                this brief
    build.py                regenerates build/ and the to-do list
    source/                 edit these: script.json, assets.json, style.json
    build/                  generated, never edit
      TODO.md               what to (re)make, in order
      scenes.json           every scene: timing, narration, on-screen text, beats, assets, sfx, plus game_facts and style
      assets.json           every asset to draw, resolved, with output paths
      narration.txt         the voiceover, one paragraph per scene
      captions.srt          captions timed to the scenes
      manifest.json         fingerprint of every item's current spec
    output/                 everything the tools make
      01_assets/            VectorCraft exports
      02_ui/                FigCraft exports
      03_audio/vo/          one voiceover WAV per scene; mix.wav and music go in 03_audio/
      04_scenes/            one EffectCraft clip per scene
      05_final/             the finished video
      built.json            what has been made, and from which spec (written by build.py)
      NOTES.md              anything you had to do differently from the spec
```

## Pipeline: what feeds what

| Stage | Tool | Reads | Writes | Mark done |
| --- | --- | --- | --- | --- |
| 1. Voiceover | HUMAN, or a text-to-speech tool | `build/narration.txt`, `style.audio.voice` | `output/03_audio/vo/scene_XX.wav` | `vo:scene_XX` |
| 2. Assets | VectorCraft | `build/assets.json` where `tool` is VectorCraft | `output/01_assets/<id>.svg` + `.png` | `asset:<id>` |
| 3. Chat screens | FigCraft | `build/assets.json` where `tool` is FigCraft | `output/02_ui/<id>.svg` + `.png` | `asset:<id>` |
| 4. Scenes | EffectCraft | `build/scenes.json`, outputs of stages 2 and 3 | `output/04_scenes/scene_XX.mp4` | `scene:scene_XX` |
| 5. Audio mix | SoundCraft, or FilmCraft | voiceover files, music, `sfx` per scene, `start_s` | `output/03_audio/mix.wav` | `audio_mix` |
| 6. Final | FilmCraft | scene clips, `mix.wav`, `build/captions.srt` | `output/05_final/survivors_explainer.mp4` | `final` |

Stages 2 and 3 don't depend on the voiceover, so they can run before or alongside stage 1. Stage 4 must wait for stage 1.

## Stage 1: Voiceover (HUMAN, or text-to-speech)

- One WAV per scene paragraph in `build/narration.txt`: 48 kHz, mono, no more than 0.2 s of silence at either end.
- Voice direction is in `style.audio.voice`.
- Save as `output/03_audio/vo/scene_01.wav` … `scene_14.wav`, run `python3 build.py done 'vo:*'`, then `python3 build.py` again. Scene lengths, beat times and captions now follow the real recordings.
- Until the voice exists, `timing_source` in `build/scenes.json` says `draft`. Don't render scenes from draft timing.

## Stage 2: Assets (VectorCraft)

- Draw the shared look first so everything matches: `avatar`, `ration_tin`, `action_icons`. Then the rest.
- Use `description`, `variants` and `separate_layers` for each asset. Colours come from `style.palette` and `style.actions`; follow `style.art_direction`.
- One file per asset. Put variants (avatar poses, the five icons, tent views) in the same file as clearly named groups or artboards, named exactly as listed.
- Every entry in `separate_layers` must be its own named group so EffectCraft can move it.
- Export SVG (keep group names) and a transparent PNG at 2x, named `<id>.svg` / `<id>.png`.

## Stage 3: Chat screens (FigCraft)

- Build the generic chat app once as a component: dark sidebar with a "survivors" server (simple tent icon), channels `#town-square`, `#news`, `#radio`, a message list and a message box. Then make each screen from it.
- Every message line that appears separately in the video is its own named layer.
- Export SVG and PNG at 1920×1080 (`ui_phone_chat` is a phone screen inside a 1920×1080 frame).

## Stage 4: Scenes (EffectCraft)

For each `scene:` item in `build/TODO.md`:

- Canvas from `style.canvas`. Length exactly `duration_s`.
- Use the assets listed in `assets`, and follow `beats`: each `at_s` is seconds from the start of the scene.
- Show `on_screen_text` following `style.text_rules`. It should appear no later than when the narration says it, and hold for at least 2 seconds.
- Follow `style.motion_rules`. Scenes 5 to 9 share the same icon-badge animation, so build it once and reuse it.
- Use the scene's voiceover WAV as a guide track to check sync, but export without audio. Don't add captions here.
- Export to `output/04_scenes/scene_XX.mp4`.

## Stage 5: Audio mix (SoundCraft, or FilmCraft)

- Place each scene's voiceover at its `start_s`.
- Music: HUMAN picks a royalty-free track matching `style.audio.music` and saves it in `output/03_audio/` as `music.wav` or `music.mp3`. It sits under the voice and cuts out at the drumroll in scene 13.
- Sound effects: the `sfx` list per scene, from any royalty-free library. Keep them subtle.
- Loudness per `style.audio.final_loudness`. Export `output/03_audio/mix.wav`, exactly `total_duration_s` long.

## Stage 6: Final (FilmCraft)

- Timeline from `style.canvas`. Place the scene clips in order at their `start_s`, using a 0.3 s crossfade where `transition_in` says so.
- Add `mix.wav` from 0:00.
- Import `build/captions.srt`, style it per `style.text_rules.captions`, and burn it in.
- Export per `style.export.final` to `output/05_final/survivors_explainer.mp4`.

## Quality check before `done final`

- [ ] Length matches `total_duration_s` within half a second.
- [ ] Every number on screen matches `game_facts` (check scenes 2, 3, 5, 6, 7, 8, 11 and 13).
- [ ] Captions are in sync at three spot checks, and no caption runs past two lines.
- [ ] No Discord logo, wordmark or mascot anywhere. Only the example names appear.
- [ ] Each action always uses its own icon and colour.
- [ ] The voice is clear over the music, and the music drops at the scene 13 drumroll.
- [ ] Watch it once, start to finish, at normal speed.

## When something changes

- **A game number** (say the steal amount): edit `../game.json`, run `python3 build.py`. `build/TODO.md` then lists only what that number touches: the voice line, the screens and scenes that show it, the audio mix and the final cut. Redo those, mark them done.
- **Words or visuals:** edit `source/script.json`, `source/assets.json` or `source/style.json`, then rebuild. A change to `style.json` marks everything for redo, on purpose.
- **A new mechanic** (not just a number): add or change scenes in `source/script.json` and assets in `source/assets.json`, then rebuild.

## Placeholders in source/

Text in `source/` can pull values from `game.json`:

| Write | Becomes |
| --- | --- |
| `{steal_amount}` | 2 |
| `{steal_amount:word}` | two |
| `{steal_amount:Word}` | Two |
| `{guard_reward:rations}` | two rations (or "one ration") |

Derived keys: `seats`, `game_span` ("two weeks"), `scavenge_spoken` ("nothing, one or two rations"), `guard_span` ("tonight and tomorrow night"), `join_spoken` ("slash join"), `name1` to `name4`. A typo in a key stops the build and lists every valid key.
