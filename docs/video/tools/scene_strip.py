"""Look at rendered scenes: five frames of each clip side by side, clips stacked, one PNG.

    python tools/scene_strip.py work/probe/strips.png scene_03 scene_05 [...]
"""
import os
import subprocess
import sys

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(VIDEO, "output", "04_scenes")
AT = (0.1, 0.3, 0.5, 0.7, 0.95)


def strip(sid, out):
    src = os.path.join(SCENES, f"{sid}.mp4")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                               capture_output=True, text=True, check=True).stdout)
    sel = "+".join(f"eq(n\\,{int(dur * 30 * f)})" for f in AT)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"select='{sel}',scale=480:-1,tile=5x1",
                    "-frames:v", "1", out], check=True)


if __name__ == "__main__":
    dst, sids = sys.argv[1], sys.argv[2:]
    parts = []
    for sid in sids:
        p = f"{dst}.{sid}.png"
        strip(sid, p)
        parts.append(p)
    args = sum((["-i", p] for p in parts), [])
    if len(parts) == 1:
        os.replace(parts[0], dst)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", f"vstack={len(parts)}", dst], check=True)
        for p in parts:
            os.remove(p)
    print(dst)
