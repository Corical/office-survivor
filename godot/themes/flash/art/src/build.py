"""Generate every SVG (gen_*.py) and export it to PNG at 2x through the VectorCraft CLI.

usage: python build.py [name ...]      (no names = everything)
The PNG lands next to the art folder root (godot/themes/flash/art/<name>.png); the SVG source stays in src/.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
CLI = r"C:\Program Files\VectorCraft\vectorcraft-cli.exe"
sys.path.insert(0, HERE)


def export(name, scale=2, outline=False):
    svg = os.path.join(HERE, name + ".svg")
    png = os.path.join(OUT, name + ".png")
    cmd = [CLI, "convert", svg, png, "--scale", str(scale)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    msg = (r.stdout.strip() or r.stderr.strip())
    try:
        j = json.loads(msg.splitlines()[-1])
        warn = j.get("warnings", []) + j.get("importWarnings", [])
    except Exception:
        warn = [msg]
    print(f"  {name}.png  exit={r.returncode}  warnings={warn}")
    return r.returncode == 0


def main():
    wanted = sys.argv[1:]
    import gen_backdrops
    jobs = {}
    jobs["backdrop_far"] = gen_backdrops.far
    for mod_name, table in (("gen_near", "JOBS"), ("gen_badges", "JOBS"), ("gen_props", "JOBS"), ("gen_ui", "JOBS"), ("gen_logo", "JOBS")):
        try:
            mod = __import__(mod_name)
            jobs.update(getattr(mod, table))
        except ImportError:
            pass
    for name, fn in jobs.items():
        if wanted and name not in wanted:
            continue
        svg = fn()
        n = svg.save(os.path.join(HERE, name + ".svg"))
        print(f"{name}: svg {n} bytes")
        export(name)


if __name__ == "__main__":
    main()
