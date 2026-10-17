"""Render one scene of build/narration.txt in several Kokoro voices, for auditioning."""
import os, re, sys, time
import soundfile as sf
from kokoro_onnx import Kokoro

CACHE = os.path.expanduser("~/.cache/kokoro")
VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NARR = os.path.join(VIDEO, "build", "narration.txt")
OUT = os.path.join(VIDEO, "work", "voice_audition")
scene = sys.argv[1] if len(sys.argv) > 1 else "scene_07"
voices = sys.argv[2].split(",") if len(sys.argv) > 2 else ["am_michael", "bm_george", "bm_lewis", "am_fenrir"]
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 0.9

text = open(NARR, encoding="utf-8").read()
m = re.search(rf"\[{scene}\][^\n]*\n(.+?)(?:\n\n|\Z)", text, re.S)
para = m.group(1).strip()
k = Kokoro(os.path.join(CACHE, "kokoro-v1.0.onnx"), os.path.join(CACHE, "voices-v1.0.bin"))
if "--list" in sys.argv:
    print(sorted(k.get_voices())); sys.exit()
os.makedirs(OUT, exist_ok=True)
print(f"{scene}: {para}")
for v in voices:
    t = time.time()
    samples, sr = k.create(para, voice=v, speed=speed, lang="en-us" if v[0] == "a" else "en-gb")
    path = os.path.join(OUT, f"{scene}_{v}.wav")
    sf.write(path, samples, sr)
    print(f"{v:12} {len(samples)/sr:5.1f}s audio  {time.time()-t:4.1f}s to render  {sr} Hz  -> {path}")
