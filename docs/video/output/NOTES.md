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

## Apps
- FilmCraft 0.8.0 crashes at start-up on this laptop's Intel Iris Xe in both `default` (Vulkan) and `dx12`
  graphics modes. It runs with `--graphics software` (CPU compositing, slower).
