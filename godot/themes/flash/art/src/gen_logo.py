"""logo.png 480x220: flame-over-island medallion and the SURVIVORS wordmark.
The wordmark text is converted to outlines by VectorCraft (`vectorcraft-cli convert --outline-text`), so the shipped
art needs no font. The only font involved is Windows' own Impact, used at build time only."""
import os
import re
import subprocess
from artlib import *

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = r"C:\Program Files\VectorCraft\vectorcraft-cli.exe"


def outlined_paths():
    src = os.path.join(HERE, "wordmark_text.svg")
    out = os.path.join(HERE, "wordmark_outlined.svg")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write('<svg xmlns="http://www.w3.org/2000/svg" width="440" height="100" viewBox="0 0 440 100">'
                 '<text x="220" y="80" text-anchor="middle" font-family="Impact" font-size="86" letter-spacing="3" fill="#ffffff">SURVIVORS</text></svg>')
    r = subprocess.run([CLI, "convert", src, out, "--outline-text"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    txt = open(out, encoding="utf-8").read()
    ds = re.findall(r'<path d="([^"]+)"', txt)
    nums = [float(n) for d in ds for n in re.findall(r"-?\d+\.?\d*", d)]
    xs, ys = nums[0::2], nums[1::2]
    return " ".join(ds), (min(xs), min(ys), max(xs), max(ys))


def logo():
    s = Svg(480, 220, "logo")
    d, (x0, y0, x1, y1) = outlined_paths()
    sc = 436 / (x1 - x0)
    tx = 240 - (x0 + x1) / 2 * sc
    ty = 124 - y0 * sc
    th = (y1 - y0) * sc
    tf = f"translate({f(tx)} {f(ty)}) scale({f(sc)})"
    sw = 7 / sc

    # --- emblem: a glowing ember medallion with the camp fire over an island
    cx, cy, R = 240, 64, 52
    s.add(circle(cx, cy, 96, s.rad([(0, "#ff9a3c", 0.5), (0.5, "#ff7a2a", 0.16), (1, "#ff7a2a", 0)]), ""))
    s.add(ellipse(cx, cy + R + 2, 56, 7, "#000", f'fill-opacity="0.5" filter="{s.blur(4)}"'))
    metal = s.lin([(0, "#fff0c0"), (0.15, "#d6ae5c"), (0.4, "#7a5f2c"), (0.6, "#2e2412"), (0.85, "#b8964e"), (1, "#4a3a1c")], 0.1, 0, 0.9, 1)
    s.add(circle(cx, cy, R, metal, 'stroke="#120d06" stroke-width="2"'))
    s.add(circle(cx, cy, R - 7, "#0d0905"))
    s.add(circle(cx, cy, R - 9, "none", f'stroke="{s.lin([(0, "#ffe9a8"), (1, "#c2661a")], 0, 0, 0, 1)}" stroke-width="2.4"'))
    dish = s.rad([(0, "#7a3a1c"), (0.55, "#2a1a30"), (1, "#0a0f1e")], 0.5, 0.78, 0.75)
    s.add(circle(cx, cy, R - 11, dish))
    clip = s.clip(circle(cx, cy, R - 11.5))
    s.add(f'<g clip-path="{clip}">')
    # moonlit sky hint, sea, island with palms
    s.add(circle(cx - 20, cy - 24, 5.5, "#eaf2ff", 'fill-opacity="0.9"')); s.add(circle(cx - 20, cy - 24, 12, s.rad([(0, "#cfe0ff", 0.5), (1, "#cfe0ff", 0)]), ""))
    s.add(rect(cx - 50, cy + 22, 100, 30, s.lin([(0, "#1d3868"), (1, "#0a1330")], 0, 0, 0, 1), ""))
    for (a, b, w) in ((-22, 27, 18), (6, 32, 22), (-4, 38, 14)):
        s.add(stroke(f"M{cx + a - w / 2} {cy + b} q{w / 4} -1.4 {w / 2} 0 t{w / 2} 0", "#8fb8f2", 1.1, 'stroke-opacity="0.6"'))
    s.add(path(f"M{cx - 38} {cy + 30} Q{cx - 18} {cy + 14} {cx} {cy + 18} Q{cx + 20} {cy + 14} {cx + 38} {cy + 30} Z", "#0a0f1e"))
    s.add(path(f"M{cx - 38} {cy + 30} Q{cx - 18} {cy + 14} {cx} {cy + 18}", "none", 'stroke="#ff9a3c" stroke-opacity="0.6" stroke-width="1.2"'))
    s.add(palm(s, cx - 26, cy + 26, 20, -4, "#05080f", rim=None, fronds=6, seed=3))
    s.add(palm(s, cx + 26, cy + 26, 17, 4, "#05080f", rim=None, fronds=6, seed=5))
    # the flame
    s.add(path(flame_d(cx, cy + 22, 22, 56, 0.1), "#ff5a1a", f'filter="{s.blur(3.5)}" fill-opacity="0.9"'))
    s.add(path(flame_d(cx, cy + 22, 20, 52, 0.1), s.lin([(0, "#ff5a1a"), (0.5, "#e8321a"), (1, "#8a1608")], 0, 1, 0, 0)))
    s.add(path(flame_d(cx - 11, cy + 22, 10, 30, -0.4), s.lin([(0, "#ffb02a"), (1, "#e83a14")], 0, 1, 0, 0)))
    s.add(path(flame_d(cx + 11, cy + 22, 9, 26, 0.5), s.lin([(0, "#ffb02a"), (1, "#e83a14")], 0, 1, 0, 0)))
    s.add(path(flame_d(cx, cy + 22, 14, 42, -0.05), s.lin([(0, "#ffb02a"), (0.6, "#ff6a1a"), (1, "#e83a14")], 0, 1, 0, 0)))
    s.add(path(flame_d(cx - 1, cy + 22, 9, 30, 0.04), s.lin([(0, "#fff0a0"), (1, "#ffc43a")], 0, 1, 0, 0)))
    s.add(path(flame_d(cx, cy + 22, 4.6, 16, 0), "#ffffff"))
    # crossed logs under it
    s.add(f'<g transform="translate({cx} {cy + 24})"><rect x="-17" y="-3" width="34" height="6.5" rx="3" fill="#5a3a22" stroke="#0d0704" stroke-width="1.4" transform="rotate(12)"/><rect x="-17" y="-3" width="34" height="6.5" rx="3" fill="#6a4426" stroke="#0d0704" stroke-width="1.4" transform="rotate(-12)"/></g>')
    s.add("</g>")
    s.add(path(f"M{cx - 38} {cy - 26} A44 44 0 0 1 {cx + 6} {cy - 44}", "none", 'stroke="#fff" stroke-opacity="0.45" stroke-width="2.4" stroke-linecap="round"'))
    s.add(circle(cx, cy, R - 11, "none", 'stroke="#000" stroke-opacity="0.5" stroke-width="1.2"'))
    # bezel studs
    for i in range(8):
        a = math.radians(i * 45 - 90 + 22.5)
        s.add(circle(cx + math.cos(a) * (R - 3.6), cy + math.sin(a) * (R - 3.6), 1.7, "#fff0c0", 'fill-opacity="0.9"'))

    # --- wordmark: glow, dark outline slab, ember fill, gloss
    gold = s.lin([(0, "#fff3c0"), (0.28, "#ffd36a"), (0.55, "#ffa030"), (1, "#d9561a")], 0, 0, 0, 1)
    s.add(f'<g transform="{tf}"><path d="{d}" fill="#ff8a2a" fill-opacity="0.9" stroke="#ff8a2a" stroke-width="{f(sw * 2.2)}" stroke-linejoin="round" filter="{s.blur(9)}"/></g>')
    s.add(f'<g transform="translate(0 6) {tf}"><path d="{d}" fill="#2a0e04" stroke="#2a0e04" stroke-width="{f(sw * 1.5)}" stroke-linejoin="round"/></g>')
    s.add(f'<g transform="{tf}"><path d="{d}" fill="#12080a" stroke="#12080a" stroke-width="{f(sw * 1.5)}" stroke-linejoin="round"/></g>')
    s.add(f'<g transform="{tf}"><path d="{d}" fill="{gold}"/></g>')
    clip2 = s.clip(f'<g transform="{tf}"><path d="{d}"/></g>')
    s.add(f'<g clip-path="{clip2}">'
          + rect(0, ty, 480, th * 0.48, s.lin([(0, "#ffffff", 0.55), (1, "#ffffff", 0.05)], 0, 0, 0, 1), "")
          + rect(0, ty + th * 0.8, 480, th * 0.25, s.lin([(0, "#ff4a10", 0), (1, "#ff4a10", 0.4)], 0, 0, 0, 1), "")
          + "</g>")
    s.add(f'<g transform="{tf}"><path d="{d}" fill="none" stroke="#fff6d8" stroke-opacity="0.7" stroke-width="{f(sw * 0.18)}"/></g>')
    # a few sparks above the wordmark
    for (x, y, r) in ((92, 112, 2), (396, 116, 2.4), (150, 120, 1.4), (340, 112, 1.6)):
        s.add(circle(x, y, r * 4, s.rad([(0, "#ffd37a", 0.6), (1, "#ffd37a", 0)]), ""))
        s.add(circle(x, y, r, "#fff3cf"))
    return s


JOBS = {"logo": logo}
