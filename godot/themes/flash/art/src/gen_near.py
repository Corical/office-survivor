"""backdrop_near.png: foreground jungle and rock silhouettes framing left, right and bottom; centre stays open."""
import math
import random
from artlib import *

W, H = 540, 960
DARK = "#04070e"
RIM_COOL = "#6a98e0"
RIM_WARM = "#ff9a3c"


def smoothstep_stops(c, a_edge, n=7, start=0.0, end=1.0, lo=0.0):
    out = []
    for i in range(n + 1):
        t = i / n
        a = lo + (a_edge - lo) * (t * t * (3 - 2 * t))
        out.append((start + (end - start) * t, c, round(a, 3)))
    return out


def near():
    s = Svg(W, H, "backdrop_near")

    def leafy_rim(d, ribs):
        """Leaf mass: rim copy, dark leaflets, then a solid dark spine over each rib so the dense centre has no weave."""
        return (rim(d, DARK, True, None, leafy=True)
                + f'<path d="{ribs}" fill="none" stroke="{DARK}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>')

    def rim(d, fill, cool=True, warm=None, wa=0.5, leafy=False):
        out = ""
        if cool:
            out += f'<g transform="translate(-1.1 -1.4)"><path d="{d}" fill="{RIM_COOL}" fill-opacity="{0.5 if leafy else 0.85}"/></g>'
        if warm:
            sx = 2.2 if warm == "r" else -2.2
            out += f'<g transform="translate({sx} 1.2)"><path d="{d}" fill="{RIM_WARM}" fill-opacity="{wa}"/></g>'
        return out + f'<path d="{d}" fill="{fill}"/>'

    # soft side shadows that frame the centre
    s.add(rect(0, 0, 150, H, s.lin(smoothstep_stops("#02040a", 0.0, lo=0.62, end=1.0)[::-1] and [(0, "#02040a", 0.62), (0.4, "#02040a", 0.3), (1, "#02040a", 0)], 0, 0, 1, 0), ""))
    s.add(rect(W - 150, 0, 150, H, s.lin([(0, "#02040a", 0), (0.6, "#02040a", 0.3), (1, "#02040a", 0.62)], 0, 0, 1, 0), ""))
    s.add(rect(0, H - 230, W, 230, s.lin([(0, "#02040a", 0), (1, "#02040a", 0.6)], 0, 0, 0, 1), ""))

    # ---------------- ground along the bottom (curving up both sides)
    def ground_top(x):
        base = 934 - 18 * math.sin(x / 71.0) - 8 * math.sin(x / 23.0 + 1)
        edge = max(0, 1 - x / 130) ** 2 * 190 + max(0, (x - (W - 130)) / 130) ** 2 * 170
        return base - edge

    top = [(x, ground_top(x)) for x in range(-20, W + 40, 16)]
    gd = smooth(top, closed=False) + f" L{W + 30} {H + 20} L-20 {H + 20} Z"
    s.add(f'<g filter="{s.blur(9)}" opacity="0.75"><path d="{gd}" fill="#000" transform="translate(0 -10)"/></g>')
    s.add(rim(gd, s.lin([(0, "#080e1e"), (1, "#03050b")], 0, 880, 0, H, True), cool=True))
    # firelight skimming the ground edge, strongest in the middle
    s.add(stroke(smooth(top, closed=False), s.lin([(0, "#ff9a3c", 0), (0.3, "#ff9a3c", 0.25), (0.5, "#ffc36a", 0.7), (0.7, "#ff9a3c", 0.25), (1, "#ff9a3c", 0)], 0, 0, 1, 0, False), 2.4, 'transform="translate(0 -1.5)"'))

    # grass blades
    rnd = random.Random(33)
    blades = []
    for _ in range(170):
        x = rnd.uniform(-10, W + 10)
        base = ground_top(x) + 4
        edge_boost = 1.0 if (x < 150 or x > W - 150) else 0.5
        h = rnd.uniform(16, 50) * edge_boost
        lean = rnd.uniform(-14, 14)
        w = rnd.uniform(2.0, 3.4)
        blades.append(f"M{f(x - w)} {f(base)} Q{f(x + lean * 0.3)} {f(base - h * 0.6)} {f(x + lean)} {f(base - h)} Q{f(x + lean * 0.5 + w)} {f(base - h * 0.5)} {f(x + w)} {f(base)} Z")
    s.add(rim(" ".join(blades), DARK))

    # ---------------- rocks
    def rock(cx, cy, w, h, seed, n=10):
        r = random.Random(seed)
        ps = [(cx - w * 1.05, cy + 8)]
        for i in range(n):
            a = math.pi + math.pi * i / (n - 1)
            rr = 1 + r.uniform(-0.12, 0.12)
            ps.append((cx + math.cos(a) * w * rr, cy + math.sin(a) * h * rr))
        ps.append((cx + w * 1.05, cy + 8))
        return smooth(ps, closed=True, tension=0.4)

    rock_fill = s.lin([(0, "#0d1629"), (1, "#05080f")], 0, 0, 1, 1)
    r1 = rock(40, 860, 120, 170, 2)
    r2 = rock(-10, 720, 90, 150, 4)
    r3 = rock(520, 880, 110, 130, 6)
    r4 = rock(590, 760, 90, 160, 8)
    for d, warm in ((r2, "r"), (r1, "r"), (r4, "l"), (r3, "l")):
        s.add(rim(d, rock_fill, True, warm, 0.4))
    # moss/lichen speckle and a few cracks catching moonlight
    clipL = s.clip(path(r1 + " " + r2 + " " + r3 + " " + r4))
    s.add(rect(0, 560, W, 400, s.speckle(48, 48, 26, ("#4a6fb0", "#ffb86a"), 0.16, 0.5, 1.3, seed=4), f'clip-path="{clipL}"'))
    for d in ("M20 800 q18 -34 40 -52", "M92 880 q-8 -40 12 -78", "M470 850 q16 -30 12 -64", "M510 790 q-14 -26 -4 -52"):
        s.add(stroke(d, "#7aa4ea", 1.2, 'opacity="0.35"'))

    # ---------------- palms: solid leaf masses, trunks hugging the edges
    def leafmass(x, y, angles, L, droop_k, seed, fat=1.15, lj=6, Lj=0.18):
        r = random.Random(seed)
        d = ""
        ribs = ""
        for a in angles:
            LL = L * r.uniform(1 - Lj, 1 + Lj)
            dd, rb = frond(x, y, a + r.uniform(-lj, lj), LL, droop=LL * droop_k * r.uniform(0.8, 1.2), n=max(8, int(LL / 7)), fat=fat, leaflet=LL * 0.30)
            d += dd
            ribs += rb + " "
        leafmass.last_ribs = ribs
        return d

    def palm_big(bx, by, h, lean, angles, L, seed):
        tw = h * 0.03
        topx, topy = bx + lean, by - h
        midx, midy = bx + lean * 0.12, by - h * 0.55
        trunk = (f"M{f(bx - tw * 1.35)} {f(by)} Q{f(midx - tw)} {f(midy)} {f(topx - tw * 0.6)} {f(topy)} "
                 f"L{f(topx + tw * 0.6)} {f(topy)} Q{f(midx + tw)} {f(midy)} {f(bx + tw * 1.35)} {f(by)} Z")
        leaves = leafmass(topx, topy, angles, L, 0.55, seed)
        out = rim(trunk, DARK, True, "r" if lean > 0 else "l", 0.45)
        # ring texture on the trunk
        rings = ""
        for i in range(1, 24):
            t = i / 24
            yy = by - h * t
            xx = bx + lean * (t * t * 0.88 + t * 0.12)
            rings += f"M{f(xx - tw * 1.15)} {f(yy)} L{f(xx + tw * 1.15)} {f(yy - 3)} "
        out += stroke(rings, "#243a66", 1.1, 'opacity="0.85"')
        out += leafy_rim(leaves, leafmass.last_ribs)
        out += ellipse(topx, topy + 4, 26, 16, DARK)
        # coconuts
        for (dx, dy) in ((-6, 10), (8, 14), (0, 20)):
            out += circle(topx + dx, topy + dy, tw * 0.9, "#05080f")
        return out

    s.add(palm_big(34, 972, 520, 78, [-204, -180, -156, -132, -108, -82, -30], 170, 3))
    s.add(palm_big(512, 976, 420, -72, [24, 0, -24, -48, -74, -100, -150], 150, 9))
    s.add(palm_big(470, 972, 230, -22, [14, -22, -62, -104, -142, -172], 100, 12))

    # ---------------- ferns and broad leaves in the bottom corners
    def clump(cx, cy, n, L, seed, spread, cool=True):
        d = leafmass(cx, cy, [-90 + (i / (n - 1) - 0.5) * spread for i in range(n)], L, 0.4, seed, fat=1.2, lj=7, Lj=0.25)
        return leafy_rim(d, leafmass.last_ribs) + ellipse(cx, cy - 4, 30, 18, DARK)
    s.add(clump(58, 952, 9, 150, 1, 170))
    s.add(clump(12, 905, 7, 120, 2, 150))
    s.add(clump(486, 954, 9, 150, 3, 170))
    s.add(clump(534, 890, 6, 115, 4, 140))
    s.add(clump(272, 972, 7, 80, 5, 160))

    # ---------------- hanging foliage from the top corners
    def banana_leaf(x, y, ang, L, droop, wmax, seed):
        """A broad torn leaf: sampled bezier spine, width swelling then tapering, sawtooth splits along both edges."""
        r = random.Random(seed)
        a = math.radians(ang)
        p0 = (x, y)
        p1 = (x + math.cos(a) * L * 0.55, y + math.sin(a) * L * 0.55)
        p2 = (x + math.cos(a) * L, y + math.sin(a) * L + droop)
        left, right, spine = [], [], []
        N = 14
        for i in range(N + 1):
            t = i / N
            u = 1 - t
            bx = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            by = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            dx = 2 * u * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
            dy = 2 * u * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
            m = math.hypot(dx, dy) or 1
            nx, ny = -dy / m, dx / m
            w = wmax * math.sin(math.pi * min(1, t * 0.92 + 0.06)) ** 0.8
            cutL = 0.58 if (i % 2 == 1 and 2 < i < N - 1) else 1.0
            cutR = 0.58 if (i % 2 == 0 and 2 < i < N - 1) else 1.0
            left.append((bx + nx * w * cutL * r.uniform(0.95, 1.05), by + ny * w * cutL))
            right.append((bx - nx * w * cutR * r.uniform(0.95, 1.05), by - ny * w * cutR))
            spine.append((bx, by))
        outline = left + right[::-1]
        d = "M" + " L".join(f"{f(px)} {f(py)}" for px, py in outline) + " Z"
        vein = "M" + " L".join(f"{f(px)} {f(py)}" for px, py in spine)
        return d, vein

    def leaf_cluster(specs, seed0):
        out = ""
        for i, (x, y, ang, L, droop, w) in enumerate(specs):
            d, vein = banana_leaf(x, y, ang, L, droop, w, seed0 + i)
            out += rim(d, DARK, True, None, leafy=False)
            out += stroke(vein, RIM_COOL, 1.0, 'opacity="0.45" transform="translate(-0.8 -1)"')
            out += stroke(vein, "#0a1224", 1.2, 'opacity="0.9"')
        return out
    s.add(leaf_cluster([(-24, -14, 52, 250, 70, 34), (-24, -14, 76, 230, 40, 30), (-24, -14, 28, 200, 80, 28), (-24, 70, 20, 140, 70, 22)], 30))
    s.add(leaf_cluster([(W + 24, -14, 128, 230, 70, 34), (W + 24, -14, 104, 220, 40, 30), (W + 24, 70, 160, 130, 70, 22)], 40))
    # a couple of vines
    for (x0, x1, y1) in ((60, 74, 220), (470, 458, 250)):
        s.add(stroke(f"M{x0} -4 Q{x0 + 8} {y1 * 0.5} {x1} {y1}", "#04070e", 3.2))
        s.add(stroke(f"M{x0 - 1.4} -4 Q{x0 + 6.6} {y1 * 0.5} {x1 - 1.4} {y1}", RIM_COOL, 1.0, 'opacity="0.55"'))

    # ---------------- fireflies / floating embers
    for (x, y, r, a) in [(110, 690, 2.4, 0.95), (152, 636, 1.7, 0.7), (436, 742, 2.2, 0.9), (396, 688, 1.5, 0.7), (66, 818, 1.9, 0.85), (484, 648, 1.6, 0.7), (190, 770, 1.3, 0.6), (350, 800, 1.3, 0.6)]:
        s.add(circle(x, y, r * 6, s.rad([(0, "#ffd37a", 0.5 * a), (1, "#ffd37a", 0)]), ""))
        s.add(circle(x, y, r, "#fff3cf", f'fill-opacity="{a}"'))

    # ---------------- vignette: centre clear, edges dark (many stops to stay smooth)
    st = smoothstep_stops("#02040a", 0.58, n=10, start=0.55, end=1.05)
    st = [(0, "#02040a", 0)] + st
    s.add(rect(0, 0, W, H, s.rad(st, 0.5, 0.47, 0.75), ""))
    return s


JOBS = {"backdrop_near": near}
