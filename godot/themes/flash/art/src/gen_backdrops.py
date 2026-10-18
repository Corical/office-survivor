"""backdrop_far (540x960) and backdrop_near (540x960, transparent)."""
import math
import random
from artlib import *

W, H = 540, 960
HORIZON = 610
MOON = (352, 262, 104)  # cx, cy, r


def far():
    s = Svg(W, H, "backdrop_far")
    rnd = random.Random(11)
    mx, my, mr = MOON

    # --- sky
    sky = s.lin([(0, "#03050e"), (0.22, "#0b1233"), (0.48, "#16275a"), (0.74, "#2a4a86"), (1, "#5b86b8")], 0, 0, 0, HORIZON + 2, True)
    s.add(rect(0, 0, W, HORIZON + 2, sky))
    # colour washes so the sky is not one blue: violet upper left, teal low right
    s.add(ellipse(60, 170, 330, 260, s.rad([(0, "#5a3c9a", 0.34), (0.6, "#3a2a7a", 0.12), (1, "#2a2a6a", 0)]), ""))
    s.add(ellipse(500, 520, 300, 120, s.rad([(0, "#3fa6b8", 0.22), (1, "#3fa6b8", 0)]), ""))
    # warm-cool horizon haze, brightest under the moon
    s.add(ellipse(mx, HORIZON, 360, 150, s.rad([(0, "#bcd8ff", 0.55), (0.5, "#6d95cf", 0.22), (1, "#3b5f9a", 0)]), ""))
    # cool vignette at the very top corners
    s.add(rect(0, 0, W, 220, s.lin([(0, "#02040a", 0.55), (1, "#02040a", 0)], 0, 0, 0, 1)))

    # --- stars (fewer near the moon glow)
    star_layer = []
    for _ in range(190):
        x, y = rnd.uniform(0, W), rnd.uniform(0, HORIZON - 40) ** 1.0
        y = rnd.uniform(0, 1) ** 1.35 * (HORIZON - 60)
        d = math.hypot(x - mx, y - my)
        if d < mr + 55:
            continue
        fade = min(1, (d - mr - 55) / 160)
        r = rnd.choice([0.5, 0.6, 0.7, 0.9, 1.1, 1.4])
        a = rnd.uniform(0.35, 1.0) * (0.35 + 0.65 * fade) * (1 - y / (HORIZON * 1.05))
        col = rnd.choice(["#ffffff", "#dbe8ff", "#fff2d8", "#bcd2ff"])
        star_layer.append(circle(x, y, r, col, f'fill-opacity="{f(max(0.08, a))}"'))
    s.add("".join(star_layer))
    # bright twinkles with glow and a four-point cross
    for (x, y, r) in [(70, 96, 7), (205, 170, 6), (470, 70, 8), (96, 330, 5.5), (440, 420, 5), (250, 40, 5), (515, 250, 4.5), (160, 470, 4)]:
        s.add(circle(x, y, r * 2.4, s.rad([(0, "#e8f0ff", 0.65), (1, "#e8f0ff", 0)], 0.5, 0.5, 0.5), ""))
        s.add(path(star4(x, y, r * 1.5, 0.12), "#ffffff", 'fill-opacity="0.95"'))
        s.add(circle(x, y, r * 0.28, "#ffffff"))
    # a faint shooting star
    s.add(stroke("M436 120 L372 164", s.lin([(0, "#ffffff", 0), (1, "#ffffff", 0.85)], 436, 120, 372, 164, True), 1.6))
    s.add(circle(372, 164, 1.7, "#ffffff"))

    # --- moon: wide halo, mid halo, disc with lit-from-upper-left shading, maria, craters
    s.add(circle(mx, my, 330, s.rad([(0, "#cfe3ff", 0.32), (0.35, "#8fb4ee", 0.14), (1, "#4a74c4", 0)]), ""))
    s.add(circle(mx, my, 190, s.rad([(0, "#eaf2ff", 0.55), (0.55, "#a9c8f6", 0.22), (1, "#7aa2e6", 0)]), ""))
    s.add(circle(mx, my, mr + 20, "#dbe9ff", f'fill-opacity="0.35" filter="{s.blur(14)}"'))
    clip = s.clip(circle(mx, my, mr))
    disc = s.rad([(0, "#fffdf3"), (0.55, "#e6eefc"), (0.86, "#b9c9e8"), (1, "#8da4cf")], 0.38, 0.34, 0.78, user=False)
    s.add(circle(mx, my, mr, disc))
    mg = []
    for (dx, dy, rx, ry, a) in [(-30, -22, 36, 26, 0.22), (22, 8, 40, 30, 0.2), (-8, 42, 30, 18, 0.18), (46, -34, 22, 16, 0.16), (-52, 18, 20, 24, 0.14)]:
        mg.append(ellipse(mx + dx, my + dy, rx, ry, "#6b7fae", f'fill-opacity="{a}" filter="{s.blur(6)}"'))
    for (dx, dy, r) in [(-38, -40, 9), (14, -52, 6), (40, 22, 11), (-20, 26, 7), (6, 4, 5), (52, -8, 6), (-56, 4, 7), (24, 56, 8)]:
        mg.append(circle(mx + dx, my + dy, r, "#7e92bd", 'fill-opacity="0.22"'))
        mg.append(circle(mx + dx - r * 0.18, my + dy - r * 0.2, r * 0.8, "#ffffff", 'fill-opacity="0.18"'))
    s.add(f'<g clip-path="{clip}">{"".join(mg)}')
    # terminator shade on the lower right so it reads as a sphere
    s.add(circle(mx, my, mr, s.rad([(0, "#1a2650", 0), (0.62, "#1a2650", 0), (1, "#1a2650", 0.55)], 0.36, 0.32, 0.9), ""))
    s.add("</g>")
    s.add(circle(mx, my, mr, "none", f'stroke="#f4f9ff" stroke-opacity="0.55" stroke-width="1.2"'))

    # --- clouds crossing the moon (dark with a moonlit upper edge)
    def cloud(cx, cy, w, h, a=0.7, seed=0):
        r = random.Random(seed)
        out = []
        for i in range(7):
            ox = (i - 3) * w / 7 + r.uniform(-8, 8)
            oy = r.uniform(-h * 0.25, h * 0.25)
            rx = w / 7 * r.uniform(1.1, 1.7)
            ry = h * r.uniform(0.45, 0.7)
            out.append(ellipse(cx + ox, cy + oy - 1.5, rx, ry, "#cfe0ff", f'fill-opacity="{a * 0.55}" filter="{s.blur(2.2)}"'))
        for i in range(7):
            pass
        body = []
        r = random.Random(seed)
        for i in range(7):
            ox = (i - 3) * w / 7 + r.uniform(-8, 8)
            oy = r.uniform(-h * 0.25, h * 0.25)
            rx = w / 7 * r.uniform(1.1, 1.7)
            ry = h * r.uniform(0.45, 0.7)
            body.append(ellipse(cx + ox, cy + oy, rx, ry, "#16224b", f'fill-opacity="{a}" filter="{s.blur(3)}"'))
        return "".join(out) + "".join(body)
    s.add(cloud(mx - 20, my + 70, 250, 26, 0.78, 4))
    s.add(cloud(mx + 80, my - 20, 160, 14, 0.5, 8))
    s.add(cloud(120, 205, 210, 20, 0.42, 5))
    s.add(cloud(430, 470, 260, 18, 0.34, 6))
    s.add(cloud(250, 330, 150, 12, 0.3, 9))

    # --- far islands (3 layers, atmospheric perspective), then mist
    def island(points, fill, hz=HORIZON):
        d = smooth([(points[0][0], hz + 6)] + points + [(points[-1][0], hz + 6)], closed=True, tension=0.5)
        return d

    layers = [
        # farthest, pale blue
        ([(-20, 596), (40, 584), (96, 570), (150, 584), (200, 600)], "#4d6f9f", 0.85),
        ([(330, 598), (396, 583), (450, 572), (520, 580), (580, 592)], "#4a6a9b", 0.85),
        # mid
        ([(-30, 606), (30, 586), (84, 560), (126, 566), (170, 590), (230, 606)], "#2d4a7d", 1.0),
        ([(300, 608), (372, 596), (420, 582), (472, 588), (560, 606)], "#2a4577", 1.0),
    ]
    for p, col, a in layers:
        d = island(p, col)
        s.add(path(d, col, f'fill-opacity="{a}"'))
        # reflection in water, squashed, blurred
        s.add(f'<g transform="translate(0 {2 * HORIZON}) scale(1 -1)" opacity="0.18"><path d="{d}" fill="{col}" filter="{s.blur(3)}"/></g>')
    # the big near island on the left with palms, and a spiky rock stack on the right
    near_l = [(-30, 614), (-12, 580), (20, 548), (62, 536), (104, 552), (140, 578), (188, 598), (240, 612)]
    dL = island(near_l, "#14274d")
    s.add(path(dL, "#14274d"))
    s.add(f'<g transform="translate(-1.4 -1.6)" opacity="0.9"><path d="{dL}" fill="#4d78b8" fill-opacity="0.55"/></g>')
    s.add(path(dL, s.lin([(0, "#1a315f"), (0.7, "#0f1f42"), (1, "#0b1733")], 0, 0, 0, 1)))
    for (px, py, ph, lean, sd) in [(34, 566, 62, 10, 1), (78, 548, 84, -8, 2), (122, 572, 52, 12, 3), (10, 578, 44, -10, 4), (160, 590, 34, 8, 5)]:
        s.add(palm(s, px, py + 6, ph, lean, "#0b1631", rim="#6a95d6", fronds=8, seed=sd))
    near_r = [(330, 614), (352, 600), (378, 584), (402, 568), (420, 548), (434, 538), (448, 554), (464, 562), (488, 574), (520, 584), (560, 596), (580, 612)]
    dR = island(near_r, "#14274d")
    s.add(path(dR, "#10224a"))
    s.add(f'<g transform="translate(-1.2 -1.6)"><path d="{dR}" fill="#5a88c8" fill-opacity="0.35"/></g>')
    s.add(path(dR, s.lin([(0, "#1a315f"), (0.8, "#0e1d3f"), (1, "#0a1530")], 0, 0, 0, 1)))
    s.add(palm(s, 468, 586, 58, -8, "#0b1631", rim="#6a95d6", fronds=8, seed=7))
    s.add(palm(s, 500, 596, 40, 6, "#0b1631", rim="#6a95d6", fronds=7, seed=8))
    # a lit beach strip at the island bases (moon catching wet sand)
    s.add(rect(0, HORIZON - 4, 250, 5, s.lin([(0, "#9fc4f5", 0), (0.4, "#9fc4f5", 0.35), (1, "#9fc4f5", 0)], 0, 0, 1, 0), f'filter="{s.blur(1.5)}"'))
    # mist in front of island bases
    for (x, w, a) in [(100, 330, 0.5), (430, 300, 0.45), (260, 420, 0.3)]:
        s.add(ellipse(x, HORIZON - 6, w / 2, 16, s.rad([(0, "#a9c6f0", a), (1, "#a9c6f0", 0)], 0.5, 0.5, 0.5), ""))

    # --- ocean
    ocean = s.lin([(0, "#2b4d82"), (0.05, "#1d3868"), (0.22, "#122648"), (0.6, "#0a1631"), (1, "#050a1a")], 0, HORIZON, 0, H, True)
    s.add(rect(0, HORIZON, W, H - HORIZON, ocean))
    # horizon line glint
    s.add(rect(0, HORIZON - 1, W, 2.5, s.lin([(0, "#cfe4ff", 0), (0.62, "#e8f2ff", 0.95), (1, "#cfe4ff", 0)], 0, 0, 1, 0), ""))
    s.add(rect(0, HORIZON - 3, W, 7, s.lin([(0, "#9cc2f5", 0), (0.65, "#cfe4ff", 0.5), (1, "#9cc2f5", 0)], 0, 0, 1, 0), f'filter="{s.blur(3)}"'))

    # moon road on the water: blurred underlay then broken horizontal glints, wider toward the viewer
    s.add(f'<path d="M{mx - 26} {HORIZON} L{mx + 26} {HORIZON} L{mx + 120} {H - 80} L{mx - 120} {H - 80} Z" fill="{s.lin([(0, "#d8e8ff", 0.5), (0.35, "#8fb4ee", 0.2), (1, "#5d86d0", 0)], 0, HORIZON, 0, H - 80, True)}" filter="{s.blur(14)}"/>')
    road = []
    r2 = random.Random(21)
    y = HORIZON + 4
    k = 0
    while y < H - 120:
        t = (y - HORIZON) / (H - 120 - HORIZON)
        spread = 22 + t * 120
        n = 2 + int(t * 4)
        for _ in range(n):
            x = mx + r2.uniform(-spread, spread) * r2.uniform(0.2, 1)
            w = r2.uniform(14, 34) * (0.7 + t * 1.6)
            h = 1.4 + t * 2.6
            a = max(0.05, 0.9 - t * 0.85) * r2.uniform(0.5, 1)
            road.append(rect(x - w / 2, y, w, h, "#e6f1ff", h / 2, f'fill-opacity="{f(a)}"'))
        y += 3 + t * 13 + r2.uniform(0, 3)
        k += 1
    s.add("".join(road))

    # waves: thin lighter ripples, tighter near the horizon
    wv = []
    r3 = random.Random(5)
    y = HORIZON + 8
    while y < H:
        t = (y - HORIZON) / (H - HORIZON)
        n = 5 + int(t * 7)
        for _ in range(n):
            x = r3.uniform(-20, W)
            w = r3.uniform(18, 60) * (0.5 + t * 1.5)
            dist = abs(x - mx) / 260
            a = (0.10 + 0.20 * (1 - min(1, dist))) * (1 - t * 0.55)
            wv.append(stroke(f"M{f(x)} {f(y)} q{f(w / 4)} {f(-1.2 - t * 2)} {f(w / 2)} 0 t{f(w / 2)} 0", "#8fb8f2", 0.7 + t * 1.0, f'stroke-opacity="{f(a)}"'))
        y += 5 + t * 18
    s.add("".join(wv))
    # distant boat-free swell shading
    s.add(rect(0, HORIZON, W, H - HORIZON, s.speckle(64, 64, 80, ("#9fc2f5", "#ffffff", "#04080f"), 0.10, 0.4, 0.9, seed=2), ""))

    # --- warm glow rising from the bottom (the camp fire, off screen)
    s.add(ellipse(W / 2, H + 40, 440, 330, s.rad([(0, "#ff9a3c", 0.34), (0.45, "#e0602a", 0.14), (1, "#8a2a1a", 0)]), ""))
    # --- overall depth: darken the bottom a touch so UI reads
    s.add(rect(0, H - 260, W, 260, s.lin([(0, "#02040a", 0), (1, "#02040a", 0.45)], 0, 0, 0, 1)))
    # global grain
    s.add(rect(0, 0, W, H, s.speckle(96, 96, 90, ("#ffffff", "#0a1030"), 0.06, 0.4, 0.8, seed=9), ""))
    return s



if __name__ == "__main__":
    import sys, os
    out = os.path.dirname(os.path.abspath(__file__))
    for fn, name in ((far, "backdrop_far"),):
        n = fn().save(os.path.join(out, name + ".svg"))
        print(name, n, "bytes")
