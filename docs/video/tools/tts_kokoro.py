"""Stage 1 voiceover with Kokoro-82M (Apache 2.0), run locally.

Reads build/narration.txt and writes output/03_audio/vo/scene_XX.wav: 48 kHz mono, at most 0.2 s of
silence at either end (AGENT.md, stage 1). Then run `python build.py done 'vo:*'` and `python build.py`.

Needs: pip install kokoro-onnx soundfile (add --ignore-requires-python on Python 3.14; it works),
ffmpeg on PATH, and the model files in ~/.cache/kokoro (kokoro-v1.0.onnx, voices-v1.0.bin) from
https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

    python tools/tts_kokoro.py --voice bm_george --speed 0.9 [--scenes scene_01,scene_07]
"""
import argparse
import os
import re
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
NARRATION = os.path.join(VIDEO, "build", "narration.txt")
OUT = os.path.join(VIDEO, "output", "03_audio", "vo")
CACHE = os.path.expanduser("~/.cache/kokoro")
EDGE_SILENCE_S = 0.2


def paragraphs():
    text = open(NARRATION, encoding="utf-8").read()
    return dict(re.findall(r"\[(scene_\d+)\][^\n]*\n(.+?)(?=\n\n|\n*\Z)", text, re.S))


def trim(samples, sr, threshold_db=-45.0):
    """Keep at most EDGE_SILENCE_S of quiet at each end."""
    level = 10 ** (threshold_db / 20)
    loud = np.flatnonzero(np.abs(samples) > level)
    if not len(loud):
        raise SystemExit("rendered audio is silent")
    pad = int(EDGE_SILENCE_S * sr)
    return samples[max(0, loud[0] - pad): loud[-1] + pad]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="bm_george")
    ap.add_argument("--speed", type=float, default=0.9)
    ap.add_argument("--scenes", help="comma-separated scene ids; default all")
    a = ap.parse_args()

    paras = paragraphs()
    wanted = a.scenes.split(",") if a.scenes else sorted(paras)
    missing = [s for s in wanted if s not in paras]
    if missing:
        raise SystemExit(f"not in narration.txt: {missing}")
    k = Kokoro(os.path.join(CACHE, "kokoro-v1.0.onnx"), os.path.join(CACHE, "voices-v1.0.bin"))
    os.makedirs(OUT, exist_ok=True)
    lang = "en-gb" if a.voice.startswith("b") else "en-us"
    for scene in wanted:
        samples, sr = k.create(paras[scene].strip(), voice=a.voice, speed=a.speed, lang=lang)
        samples = trim(samples, sr)
        dst = os.path.join(OUT, f"{scene}.wav")
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw.wav")
            sf.write(raw, samples, sr)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ac", "1", "-ar", "48000",
                            "-c:a", "pcm_s16le", dst], check=True)
        print(f"{scene}  {len(samples) / sr:5.1f} s  {a.voice} x{a.speed}  -> {os.path.relpath(dst, VIDEO)}")


if __name__ == "__main__":
    main()
