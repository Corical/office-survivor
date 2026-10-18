"""card_frame (128x128, 9-slice margin 40), button_wood / button_wood_pressed (256x96, 9-slice margins 36 / 30).
Edges are uniform along their length so they stretch cleanly; all ornament lives inside the corner squares."""
import random
from artlib import *


def card_frame():
    s = Svg(128, 128, "card_frame")
    W = 128
    FW = 22  # frame band width
    outer = rrect_d(1, 1, W - 2, W - 2, 14)
    inner = rrect_d(FW, FW, W - 2 * FW, W - 2 * FW, 6)
    hole = f"{outer} {inner}"
    ev = 'fill-rule="evenodd"'
    # drop shadow outside
    s.add(f'<path d="{outer}" fill="#000" fill-opacity="0.5" transform="translate(0 2)" filter="{s.blur(2)}"/>')
    # dark wood band with grain running along each edge (a diagonal-free gradient so it stretches)
    wood = s.lin([(0, "#6a4630"), (0.5, "#40291a"), (1, "#24160d")], 0, 0, 1, 1)
    s.add(f'<path d="{hole}" fill="{wood}" {ev} stroke="#08050a" stroke-width="2"/>')
    clip = s.clip(f'<path d="{hole}" clip-rule="evenodd"/>')
    grain = []
    rnd = random.Random(4)
    for i in range(26):
        t = 3 + i * (FW - 5) / 25
        a = rnd.uniform(0.08, 0.3)
        c = rnd.choice(["#000", "#000", "#b88a5a"])
        for (x1, y1, x2, y2) in ((t, 6, t, W - 6), (W - t, 6, W - t, W - 6), (6, t, W - 6, t), (6, W - t, W - 6, W - t)):
            grain.append(f'<path d="M{f(x1)} {f(y1)} L{f(x2)} {f(y2)}" stroke="{c}" stroke-opacity="{f(a * 0.7)}" stroke-width="0.8"/>')
    s.add(f'<g clip-path="{clip}">{"".join(grain)}')
    # bevel: light on the top-left band, shade on the bottom-right
    s.add(rect(0, 0, W, 6, s.lin([(0, "#ffd9a8", 0.35), (1, "#ffd9a8", 0)], 0, 0, 0, 1), ""))
    s.add(rect(0, 0, 6, W, s.lin([(0, "#ffd9a8", 0.28), (1, "#ffd9a8", 0)], 0, 0, 1, 0), ""))
    s.add(rect(0, W - 6, W, 6, s.lin([(0, "#000", 0), (1, "#000", 0.45)], 0, 0, 0, 1), ""))
    s.add(rect(W - 6, 0, 6, W, s.lin([(0, "#000", 0), (1, "#000", 0.4)], 0, 0, 1, 0), ""))
    s.add("</g>")
    # brass inner liner
    liner = rrect_d(FW - 4, FW - 4, W - 2 * FW + 8, W - 2 * FW + 8, 8)
    s.add(f'<path d="{liner}" fill="none" stroke="#0d0905" stroke-width="3.6"/>')
    s.add(f'<path d="{liner}" fill="none" stroke="{s.lin([(0, "#fff0c0"), (0.5, "#c9a252"), (1, "#6a4f20")], 0, 0, 1, 1)}" stroke-width="2"/>')
    # outer metal edge line
    s.add(f'<path d="{rrect_d(3.5, 3.5, W - 7, W - 7, 12)}" fill="none" stroke="#9fb4d8" stroke-opacity="0.35" stroke-width="1"/>')
    # inner shadow cast onto the (transparent) panel, so text sits on a calm surface
    s.add(f'<path d="{rrect_d(FW - 2, FW - 2, W - 2 * FW + 4, W - 2 * FW + 4, 6)} {rrect_d(FW + 9, FW + 9, W - 2 * FW - 18, W - 2 * FW - 18, 3)}" fill="#000" fill-opacity="0.32" fill-rule="evenodd" filter="{s.blur(3)}"/>')
    # corner brackets (brass) with rivets: inside the 40 px corner squares
    def corner(sx, sy):
        # sx, sy in {0,1}: which corner
        ang = {(0, 0): 0, (1, 0): 90, (1, 1): 180, (0, 1): 270}[(sx, sy)]
        brass = s.lin([(0, "#fff0c0"), (0.4, "#d6ae5c"), (1, "#6a4f20")], 0, 0, 1, 1)
        d = "M4 4 L36 4 Q38 4 38 6 L38 10 Q38 12 36 12 L14 12 L12 14 L12 36 Q12 38 10 38 L6 38 Q4 38 4 36 Z"
        g = f'<g transform="rotate({ang} 64 64)">'
        g += f'<path d="{d}" fill="#000" fill-opacity="0.5" transform="translate(0.8 1.6)"/>'
        g += f'<path d="{d}" fill="{brass}" stroke="#2a1d0a" stroke-width="1.6" stroke-linejoin="round"/>'
        g += stroke("M8 7.5 L34 7.5", "#fff8dc", 1, 'stroke-opacity="0.7"')
        g += circle(9, 9, 2.8, "#1a1208") + circle(9, 9, 2.2, s.rad([(0, "#fff3d0"), (0.5, "#c9a252"), (1, "#5a4218")], 0.35, 0.3, 0.8))
        g += circle(30, 8, 1.7, "#1a1208") + circle(30, 8, 1.3, "#e6c27a")
        g += circle(8, 30, 1.7, "#1a1208") + circle(8, 30, 1.3, "#e6c27a")
        g += "</g>"
        return g
    for c in ((0, 0), (1, 0), (1, 1), (0, 1)):
        s.add(corner(*c))
    return s


def button(pressed):
    name = "button_wood_pressed" if pressed else "button_wood"
    # 72 px tall (it was 96). The studs sit inside the TOP margin (36 px) so they are never stretched; the stretched middle band
    # is plain wood only. A button must be at least top+bottom margin = 62 px tall (the UI uses 64 and 72).
    s = Svg(256, 72, name)
    W, H = 256, 72
    lip = 3 if pressed else 10
    top = 9 if pressed else 4  # the face sinks when pressed
    fx, fy, fw = 6, top, W - 12
    fh = H - lip - top - 6
    R = 24
    face_d = rrect_d(fx, fy, fw, fh, R)
    # drop shadow
    s.add(rrect_d_path := f'<path d="{rrect_d(fx, fy + lip + 3, fw, fh, R)}" fill="#000" fill-opacity="0.5" filter="{s.blur(4)}"/>')
    # lip: the visible side of the slab
    lip_g = s.lin([(0, "#7a4a22"), (1, "#3a1f0c")], 0, 0, 0, 1)
    s.add(f'<path d="{rrect_d(fx, fy + lip, fw, fh, R)}" fill="{lip_g}" stroke="#1a0c04" stroke-width="3"/>')
    base1, base2 = ("#d8883c", "#a85a22") if not pressed else ("#b8702f", "#8a4818")
    face_g = s.lin([(0, base1), (1, base2)], 0, 0, 0, 1)
    s.add(f'<path d="{face_d}" fill="{face_g}" stroke="#1a0c04" stroke-width="3"/>')
    clip = s.clip(f'<path d="{face_d}"/>')
    s.add(f'<g clip-path="{clip}">')
    # grain only along the ends and rim, never in the flat middle (x 40..216)
    rnd = random.Random(9)
    for i in range(46):
        x = rnd.choice([rnd.uniform(8, 38), rnd.uniform(218, 248)])
        y = rnd.uniform(fy + 4, fy + fh - 4)
        ln = rnd.uniform(6, 16)
        s.add(f'<path d="M{f(x)} {f(y)} q{f(ln / 2)} {f(rnd.uniform(-1.2, 1.2))} {f(ln)} 0" stroke="#5a2e10" stroke-opacity="{f(rnd.uniform(0.15, 0.38))}" stroke-width="1" fill="none"/>')
    # glossy top highlight and warm bounce at the bottom
    gl = 0.18 if pressed else 0.42
    s.add(rect(fx, fy, fw, fh * 0.46, s.lin([(0, "#fff3d6", gl), (1, "#fff3d6", 0)], 0, 0, 0, 1), ""))
    s.add(rect(fx, fy + fh * 0.7, fw, fh * 0.3, s.lin([(0, "#ffb347", 0), (1, "#ffb347", 0.28)], 0, 0, 0, 1), ""))
    if pressed:
        s.add(rect(fx, fy, fw, 9, s.lin([(0, "#000", 0.4), (1, "#000", 0)], 0, 0, 0, 1), ""))
    s.add("</g>")
    # bevel line just inside the face
    s.add(f'<path d="{rrect_d(fx + 2.5, fy + 2.5, fw - 5, fh - 5, R - 2.5)}" fill="none" stroke="#fff0cc" stroke-opacity="{0.25 if pressed else 0.55}" stroke-width="1.4"/>')
    # brass studs on each end (inside the 36 px 9-slice margin), not in the text area
    # The stud must lie ENTIRELY inside the 36 px top margin or it is cut by the stretch seam (the pressed face is 5 px lower,
    # so its middle, 36, would put the 5.4 px stud across the seam: found by the stud-roundness probe at 64 px). 30 is fixed
    # for both states, 1 px above the face middle on the normal button and 6 px above it on the pressed one.
    cy = 30
    for x in (20, W - 20):
        s.add(circle(x + 0.6, cy + 1.2, 5.4, "#000", 'fill-opacity="0.45"'))
        s.add(circle(x, cy, 5.2, s.rad([(0, "#fff3d0"), (0.5, "#c9a252"), (1, "#4a3512")], 0.35, 0.3, 0.8), 'stroke="#1a0c04" stroke-width="1.4"'))
        s.add(path(f"M{x - 2.4} {cy} h4.8", "none", 'stroke="#3a2808" stroke-width="1" stroke-opacity="0.7"'))
    return s


JOBS = {
    "card_frame": card_frame,
    "button_wood": lambda: button(False),
    "button_wood_pressed": lambda: button(True),
}
