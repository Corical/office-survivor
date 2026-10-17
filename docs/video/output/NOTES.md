# Notes: where production differs from the spec

## Stage 1: Voiceover (17 Oct 2026)
- Text-to-speech, not a person: Kokoro-82M (Apache 2.0) run locally, voice `bm_george`, speed 0.9.
  Made by `tools/tts_kokoro.py`. A different voice is one command; scene timings then follow the new recordings.
- Kokoro's package says Python < 3.13; it runs on 3.14 with `pip install --ignore-requires-python kokoro-onnx`.

## Stage 3: Chat screens (17 Oct 2026)
- Spec asks for the chat app built once as a FigCraft component. First pass instead: `tools/ui_screens_svg.py`
  writes the four screens as SVG with every animated line as its own named group, imported into FigCraft
  (`file.import` keeps each group as a layer), checked there, exported from FigCraft. Source file:
  `02_ui/survivors_screens.figcraft`. Turning the shared shell into a component is a later polish step.
- Palette is the game's navy, not Discord's greys. No logo, wordmark or mascot.
- `ui_join` still says `[LAUNCH DATE]`: open question in docs/video_script.md.

## Stage 2: Assets, extra parts (17 Oct 2026)
- Besides the 24 specced files, `01_assets/parts/` holds 36 single images (one per pose, icon and moving
  piece, plus the title lettering without its navy backing) because EffectCraft animates layers, not
  groups inside a PNG. Made by `tools/assets_svg.py --parts`, exported from VectorCraft.
- Fonts: Fredoka and Inter aren't installed, so VectorCraft art uses Arial Rounded MT Bold (headline) and
  Segoe UI; EffectCraft and FigCraft text use their bundled Inter.

## Stage 4: Scenes (17 Oct 2026)
- Built by `tools/effectcraft_scenes.py` in the live EffectCraft window; project `work/survivors_scenes.ecproj`.
- Chat-screen "typing" and line-by-line reveals are covers in the screen's background colour that fade
  out on the beat, not masks.
- Scene 1 shows no separate SURVIVORS caption: the title itself is the on-screen text.
- Scenes 10, 12 and 14 put the on-screen text where the chat screen has room, not the upper third.
- Dust puff (scene 1, 13), clock icon (scene 5) and the seal glint (scene 12) are left out of this pass.
- First-pass flaws are listed in PRODUCTION_LOG.md.

## Stage 5: Audio mix (17 Oct 2026)
- Music: no person picked a track. A score generated from the scene timings (`tools/score_midi.py`) is
  played by SoundCraft's built-in synths, so nothing needs licensing. It cuts at the scene 13 drumroll
  (a generated snare roll and crash) and returns for scene 14.
- No other sound effects in this pass (the per-scene `sfx` lists).
- Result: −15.94 LUFS integrated, −1.52 dBTP; music about 19 dB under the voice.

## Stage 6: Final (17 Oct 2026)
- Preset "High Quality 1080p HD" (20 Mbps VBR) instead of CRF 18; audio overridden to AAC 192 kbps 48 kHz.

## Apps
- FilmCraft 0.8.0 crashes at start-up on this laptop's Intel Iris Xe in both `default` (Vulkan) and `dx12`
  graphics modes. It runs with `--graphics software` (CPU compositing, slower).
