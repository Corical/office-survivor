"""hut, hut_me (192), campfire (256), campfire_glow (512), fx_spark, fx_crumb, fx_ring, fx_shield."""
import math
import random
from artlib import *

EMBER = "#ffb347"


def _hut_body(s, me=False):
    o = []
    rnd = random.Random(5)
    # --- shadow on the ground and the warm pool of window light spilling forward
    o.append(ellipse(96, 160, 78, 15, "#000", f'fill-opacity="0.6" filter="{s.blur(5)}"'))
    o.append(ellipse(92, 164, 58, 11, s.rad([(0, "#ffb347", 0.55), (1, "#ffb347", 0)]), ""))

    # --- wall
    wall = s.lin([(0, "#6a4a33"), (0.5, "#4a3322"), (1, "#2b1c12")], 0, 0, 0, 1)
    o.append(path(rrect_d(44, 92, 104, 62, 3), wall, 'stroke="#140c07" stroke-width="2"'))
    # vertical planks
    for i in range(1, 9):
        x = 44 + i * 104 / 9
        o.append(stroke(f"M{f(x)} 94 L{f(x)} 153", "#1a100a", 1.2, 'opacity="0.8"'))
        o.append(stroke(f"M{f(x + 1.3)} 94 L{f(x + 1.3)} 153", "#a07850", 0.8, 'opacity="0.3"'))
    for _ in range(18):
        x = rnd.uniform(46, 146)
        y = rnd.uniform(98, 150)
        o.append(stroke(f"M{f(x)} {f(y)} l0 {f(rnd.uniform(3, 8))}", "#1a100a", 0.8, 'opacity="0.5"'))
    # stone footing
    for i in range(9):
        x = 44 + i * 104 / 9
        o.append(path(rrect_d(x + 0.6, 148, 104 / 9 - 1.2, 8, 3), "#3b4256", 'stroke="#10131c" stroke-width="1"'))
        o.append(path(rrect_d(x + 1.6, 148.6, 104 / 9 - 3.4, 2.4, 1), "#8c97b8", 'fill-opacity="0.45"'))

    # --- lit window with warm halo, muntins, sill and a flower-pot of light
    o.append(ellipse(74, 124, 34, 28, s.rad([(0, "#ffc860", 0.7), (0.5, "#ff9a3c", 0.25), (1, "#ff9a3c", 0)]), ""))
    glow = s.lin([(0, "#fff5c4"), (0.5, "#ffc25e"), (1, "#ff8f2a")], 0, 0, 0, 1)
    o.append(path(rrect_d(60, 110, 28, 26, 3), glow, 'stroke="#140c07" stroke-width="2.4"'))
    o.append(stroke("M74 110 L74 136", "#2a1a0e", 2)); o.append(stroke("M60 123 L88 123", "#2a1a0e", 2))
    o.append(path("M62 112 L72 112 L62 122 Z", "#ffffff", 'fill-opacity="0.35"'))
    o.append(path(rrect_d(57, 135, 34, 5, 2), "#5a3b24", 'stroke="#140c07" stroke-width="1.4"'))
    # --- door, slightly ajar with a warm slit
    o.append(path("M108 154 L108 116 Q108 104 121 104 Q134 104 134 116 L134 154 Z", "#22150d", 'stroke="#140c07" stroke-width="2.2"'))
    o.append(path("M112 154 L112 117 Q112 108 121 108 Q121 108 121 108 L121 154 Z", s.lin([(0, "#ffc25e", 0.9), (1, "#ff8f2a", 0.55)], 0, 0, 0, 1), ""))
    o.append(circle(129, 131, 1.8, "#d7b46a"))
    o.append(stroke("M108 154 L108 116 Q108 104 121 104", "#9a7a54", 1.0, 'opacity="0.4"'))

    # --- roof: thatch, hip shape, overhanging the wall
    roof_d = "M24 100 L58 46 Q96 36 134 46 L168 100 Q96 112 24 100 Z"
    thatch = s.lin([(0, "#b49a5c"), (0.45, "#7a6a3a"), (1, "#3b3320")], 0, 0, 0, 1)
    # eave shadow on wall
    o.append(rect(44, 100, 104, 14, s.lin([(0, "#000", 0.6), (1, "#000", 0)], 0, 0, 0, 1), ""))
    # rim light copies (cool on the upper-left edge, warm underside)
    o.append(f'<g transform="translate(-1.4 -1.8)"><path d="{roof_d}" fill="#9cc2ff" fill-opacity="0.85"/></g>')
    o.append(f'<g transform="translate(0.6 2.2)"><path d="{roof_d}" fill="#ff9a3c" fill-opacity="0.5"/></g>')
    o.append(path(roof_d, thatch, 'stroke="#171108" stroke-width="2.2" stroke-linejoin="round"'))
    clip = s.clip(path(roof_d))
    rows = []
    y = 52
    r2 = random.Random(8)
    while y < 112:
        t = (y - 46) / 66
        xl = 58 - 34 * t - 4
        xr = 134 + 34 * t + 4
        x = xl
        while x < xr:
            w = r2.uniform(5, 9)
            shade_c = r2.choice(["#c7ae6e", "#8a7740", "#5a4c2a", "#a28a50", "#6e5d34"])
            rows.append(f'<path d="M{f(x)} {f(y)} q{f(w / 2)} {f(-3)} {f(w)} 0 l-1 {f(9)} l{f(-w + 2)} 0 Z" fill="{shade_c}" fill-opacity="0.8" stroke="#2a2012" stroke-width="0.6" stroke-opacity="0.6"/>')
            x += w - 0.8
        y += 8
    o.append(f'<g clip-path="{clip}">{"".join(rows)}')
    # light falls: moonlit left slope, shaded right slope
    o.append(path("M96 38 L168 100 L24 100 Z", s.lin([(0, "#000", 0), (1, "#000", 0.38)], 0, 0, 1, 0.2), ""))
    o.append(path("M24 100 L58 46 L96 38 L70 100 Z", "#bcd6ff", 'fill-opacity="0.12"'))
    o.append("</g>")
    # ridge cap
    o.append(path(rrect_d(54, 38, 84, 10, 5), s.lin([(0, "#7a5a36"), (1, "#3a2814")], 0, 0, 0, 1), 'stroke="#171108" stroke-width="2"'))
    o.append(stroke("M60 41 L130 41", "#d3b27a", 1.2, 'opacity="0.6"'))
    # pole ends at the ridge
    o.append(stroke("M54 42 L47 34", "#2a1c10", 3)); o.append(stroke("M138 42 L145 34", "#2a1c10", 3))

    # --- small props: a crate and a hanging lantern with its own glow
    o.append(path(rrect_d(150, 138, 22, 18, 2), s.lin([(0, "#a8723a"), (1, "#5a3414")], 0, 0, 0, 1), 'stroke="#1a0e05" stroke-width="1.8"'))
    o.append(stroke("M151 147 L171 147", "#2a1608", 1.2)); o.append(stroke("M160 139 L160 155", "#2a1608", 1.0, 'opacity="0.7"'))
    o.append(circle(143, 118, 16, s.rad([(0, "#ffd37a", 0.8), (1, "#ffd37a", 0)]), ""))
    o.append(stroke("M143 104 L143 111", "#1a1008", 1.4))
    o.append(path("M139.5 112 L146.5 112 L145.5 123 L140.5 123 Z", s.lin([(0, "#fff0b0"), (1, "#ffa83a")], 0, 0, 0, 1), 'stroke="#1a1008" stroke-width="1.4"'))
    return "".join(o)


def hut():
    s = Svg(192, 192, "hut")
    s.add(_hut_body(s))
    return s


def hut_me():
    s = Svg(192, 192, "hut_me")
    # back glow, then the halo ring on the ground (its back half hides behind the hut), then the hut, then the front arc again
    s.add(circle(96, 112, 96, s.rad([(0, "#ffb347", 0.42), (0.6, "#ff9a3c", 0.14), (1, "#ff9a3c", 0)]), ""))
    ring = lambda w, op, extra="": f'<ellipse cx="96" cy="150" rx="86" ry="27" fill="none" stroke="{EMBER}" stroke-width="{w}" stroke-opacity="{op}" {extra}/>'
    s.add(ring(9, 0.55, f'filter="{s.blur(4)}"'))
    s.add(ring(3.4, 0.95))
    s.add(f'<ellipse cx="96" cy="150" rx="86" ry="27" fill="none" stroke="#fff1c4" stroke-width="1.1" stroke-opacity="0.95"/>')
    s.add(_hut_body(s, True))
    front = "M10 150 A86 27 0 0 0 182 150"
    s.add(stroke(front, EMBER, 3.4, 'stroke-opacity="0.95"'))
    s.add(stroke(front, "#fff1c4", 1.1))
    # floating embers: "this one is you"
    for (x, y, r) in ((30, 98, 2.2), (166, 84, 1.8), (150, 60, 1.4), (46, 66, 1.6), (176, 120, 1.5)):
        s.add(circle(x, y, r * 4, s.rad([(0, "#ffd37a", 0.6), (1, "#ffd37a", 0)]), ""))
        s.add(circle(x, y, r, "#fff3cf"))
    return s


# ---------------------------------------------------------------- campfire
def campfire():
    s = Svg(256, 256, "campfire")
    CXF, CYF = 128, 164
    # big warm glow on the ground and in the air
    s.add(ellipse(CXF, CYF, 118, 62, s.rad([(0, "#ff9a3c", 0.62), (0.5, "#e8602a", 0.22), (1, "#e8602a", 0)]), ""))
    s.add(ellipse(CXF, CYF - 38, 62, 78, s.rad([(0, "#ffc36a", 0.55), (0.6, "#ff8a2a", 0.18), (1, "#ff8a2a", 0)]), ""))
    # ground disc inside the stones (ash and coals)
    s.add(ellipse(CXF, CYF + 2, 66, 28, s.rad([(0, "#5a2a14"), (0.6, "#24120a"), (1, "#0c0806")], 0.5, 0.45, 0.55), 'stroke="#05030a" stroke-width="2"'))
    # stones: back half first, logs and fire, then the front half over them
    rnd = random.Random(12)
    stones = []
    N = 14
    for i in range(N):
        a = 2 * math.pi * i / N + 0.2
        x = CXF + math.cos(a) * 80
        y = CYF + 4 + math.sin(a) * 34
        rx = rnd.uniform(13, 17)
        ry = rnd.uniform(9.5, 12.5)
        stones.append((math.sin(a), x, y, rx, ry, i))

    def draw_stone(x, y, rx, ry, i):
        # lit on the fire side (towards the centre), cool rim on top
        ang = math.atan2(y - (CYF + 4), x - CXF)
        lx, ly = -math.cos(ang), -math.sin(ang)  # towards the fire
        g = s.rad([(0, "#a6a2b4"), (0.55, "#5c5a72"), (1, "#222032")], 0.5 + lx * 0.18, 0.4 + ly * 0.2, 0.75)
        d = blob(x, y, 1.0, random.Random(i), 8, 0.1)
        out = f'<g transform="translate({f(x)} {f(y)}) scale({f(rx)} {f(ry)}) translate({f(-x)} {f(-y)})"><path d="{d}" fill="{g}" stroke="#08060f" stroke-width="{f(1.8 / rx)}"/></g>'
        out += f'<g transform="translate({f(x)} {f(y)}) scale({f(rx)} {f(ry)}) translate({f(-x)} {f(-y)})"><path d="{d}" fill="none" stroke="#ffb347" stroke-opacity="0.55" stroke-width="{f(1.4 / rx)}" transform="translate({f(lx * 0.08)} {f(ly * 0.12)})"/></g>'
        out += ellipse(x - rx * 0.25, y - ry * 0.4, rx * 0.45, ry * 0.22, "#d6e4ff", 'fill-opacity="0.35"')
        return out

    for k in sorted(stones, key=lambda t: t[0]):
        if k[0] < 0:  # behind the fire
            s.add(draw_stone(*k[1:]))

    # logs: three crossing logs lying on the ground, burning ends glow
    def log(cx, cy, ang, ln=88, th=17, glow_end=1):
        a = math.degrees(ang)
        bark = s.lin([(0, "#8a5a36"), (0.35, "#5a3a22"), (1, "#24150c")], 0, 0, 0, 1)
        out = f'<g transform="translate({cx} {cy}) rotate({f(a)})">'
        out += rect(-ln / 2, -th / 2 + 3, ln, th, "#000", th / 2, 'fill-opacity="0.45" ')
        out += rect(-ln / 2, -th / 2, ln, th, bark, th / 2.6, 'stroke="#0d0704" stroke-width="2"')
        for i in range(6):
            x = -ln / 2 + 8 + i * (ln - 16) / 5
            out += stroke(f"M{f(x)} {f(-th / 2 + 3)} q3 {f(th / 2)} 0 {f(th - 6)}", "#140a05", 1.2, 'opacity="0.7"')
        out += stroke(f"M{-ln / 2 + 6} {-th / 2 + 2.2} L{ln / 2 - 6} {-th / 2 + 2.2}", "#d29a62", 1.3, 'opacity="0.5"')
        # burning end: glowing coal face
        ex = ln / 2 if glow_end > 0 else -ln / 2
        out += ellipse(ex, 0, 5, th / 2.1, s.rad([(0, "#fff0b0"), (0.5, "#ff9a2a"), (1, "#c2400f")], 0.5, 0.5, 0.6), 'stroke="#2a0e05" stroke-width="1.2"')
        out += circle(ex, 0, th, s.rad([(0, "#ffb347", 0.65), (1, "#ffb347", 0)]), "")
        out += "</g>"
        return out
    # two back logs now, two front logs after the flames; burning ends meet in the middle
    s.add(log(CXF - 34, CYF - 2, math.radians(200), 90, 17, -1))
    s.add(log(CXF + 34, CYF - 2, math.radians(340), 90, 17, -1))

    # flames: layered teardrops, back to front
    def fl(cx, w, h, lean, grad):
        return path(flame_d(cx, CYF + 8, w, h, lean), grad)
    g1 = s.lin([(0, "#ff5a1a"), (0.5, "#e8321a"), (1, "#8a1608")], 0, 1, 0, 0)
    g2 = s.lin([(0, "#ffb02a"), (0.55, "#ff6a1a"), (1, "#e83a14")], 0, 1, 0, 0)
    g3 = s.lin([(0, "#fff0a0"), (0.5, "#ffc43a"), (1, "#ff8a1f")], 0, 1, 0, 0)
    g4 = s.lin([(0, "#ffffff"), (1, "#fff0b8")], 0, 1, 0, 0)
    s.add(f'<g filter="{s.blur(6)}" opacity="0.9">{fl(CXF, 46, 128, 0.15, "#ff6a1a")}</g>')
    s.add(fl(CXF - 30, 24, 70, -0.4, g1)); s.add(fl(CXF + 32, 22, 64, 0.5, g1))
    s.add(fl(CXF, 40, 124, 0.12, g1))
    s.add(fl(CXF - 20, 22, 82, -0.25, g2)); s.add(fl(CXF + 22, 20, 74, 0.3, g2))
    s.add(fl(CXF + 2, 32, 102, -0.1, g2))
    s.add(fl(CXF - 6, 20, 76, -0.06, g3)); s.add(fl(CXF + 12, 14, 56, 0.2, g3))
    s.add(fl(CXF - 1, 11, 46, 0.0, g4))
    s.add(log(CXF - 30, CYF + 17, math.radians(160), 88, 17, -1))
    s.add(log(CXF + 30, CYF + 17, math.radians(20), 88, 17, -1))
    # embers rising
    r3 = random.Random(3)
    for _ in range(18):
        x = CXF + r3.gauss(0, 24)
        y = CYF - r3.uniform(40, 140)
        r = r3.uniform(0.9, 2.2)
        a = r3.uniform(0.5, 1)
        s.add(circle(x, y, r * 3.5, s.rad([(0, "#ffb347", 0.5 * a), (1, "#ffb347", 0)]), ""))
        s.add(circle(x, y, r, "#ffe2a0", f'fill-opacity="{f(a)}"'))
    # front stones
    for k in sorted(stones, key=lambda t: t[0]):
        if k[0] >= 0:
            s.add(draw_stone(*k[1:]))
    return s


def campfire_glow():
    s = Svg(512, 512, "campfire_glow")
    stops = [(0.00, "#fff1d0", 0.95), (0.06, "#ffdca0", 0.88), (0.14, "#ffbf66", 0.66), (0.26, "#ff9a3c", 0.42),
             (0.40, "#ff8a2a", 0.24), (0.56, "#ff6a1f", 0.11), (0.74, "#ff5a1a", 0.04), (1.0, "#ff5a1a", 0.0)]
    s.add(circle(256, 256, 256, s.rad(stops, 0.5, 0.5, 0.5), ""))
    return s


# ---------------------------------------------------------------- fx
def fx_spark():
    s = Svg(32, 32, "fx_spark")
    s.add(circle(16, 16, 15, s.rad([(0, "#ffffff", 1), (0.2, "#ffffff", 0.85), (0.45, "#ffffff", 0.32), (0.75, "#ffffff", 0.07), (1, "#ffffff", 0)]), ""))
    s.add(path(star4(16, 16, 13, 0.09), "#ffffff", 'fill-opacity="0.95"'))
    s.add(circle(16, 16, 2.2, "#ffffff"))
    return s


def fx_crumb():
    s = Svg(32, 32, "fx_crumb")
    rnd = random.Random(2)
    s.add(path(blob(16, 16, 8.6, rnd, 9, 0.16), s.rad([(0, "#ffffff", 1), (0.7, "#ffffff", 0.92), (1, "#ffffff", 0.7)]), f'filter="{s.blur(1.1)}"'))
    s.add(path(blob(16, 16, 7.2, random.Random(2), 9, 0.16), "#ffffff", 'fill-opacity="0.9"'))
    return s


def fx_ring():
    s = Svg(128, 128, "fx_ring")
    s.add(circle(64, 64, 54, "none", 'stroke="#ffffff" stroke-width="9" stroke-opacity="0.32" filter="%s"' % s.blur(3.2)))
    s.add(circle(64, 64, 54, "none", 'stroke="#ffffff" stroke-width="3.2" stroke-opacity="0.9" filter="%s"' % s.blur(0.7)))
    s.add(circle(64, 64, 54, "none", 'stroke="#ffffff" stroke-width="1.3"'))
    return s


def fx_shield():
    s = Svg(192, 192, "fx_shield")
    CXs, CYs, R = 96, 96, 88
    ss = 12.0
    w, h = math.sqrt(3) * ss, 3 * ss

    def hexpts(cx, cy, r=ss):
        return [(cx + r * math.cos(math.radians(30 + 60 * k)), cy + r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    tile = ""
    for (cx, cy) in ((w / 2, ss), (0, 2.5 * ss), (w, 2.5 * ss), (0, -0.5 * ss), (w, -0.5 * ss)):
        tile += f'<polygon points="{pts(hexpts(cx, cy))}" fill="none" stroke="#e9fcff" stroke-width="1.3"/>'
    pat = s.pattern(w, h, tile)
    clip = s.clip(circle(CXs, CYs, R))
    # body: nearly clear in the middle, bright at the limb (a bubble)
    s.add(circle(CXs, CYs, R, s.rad([(0, "#bff4ff", 0.03), (0.6, "#bff4ff", 0.1), (0.85, "#d8f8ff", 0.34), (1, "#ffffff", 0.62)]), ""))
    s.add(circle(CXs, CYs, R, s.rad([(0, "#7fe0ff", 0.0), (0.7, "#7fe0ff", 0.0), (1, "#7fe0ff", 0.4)], 0.5, 0.5, 0.5), ""))
    # hex lattice, strongest near the edge
    m = s.mask(circle(CXs, CYs, R, s.rad([(0, "#000"), (0.45, "#2a2a2a"), (0.8, "#bfbfbf"), (1, "#fff")], 0.5, 0.5, 0.5), ""))
    s.add(f'<g clip-path="{clip}"><g mask="{m}">{rect(0, 0, 192, 192, pat, "")}</g>')
    # a few lit cells, aligned to the lattice
    rnd = random.Random(7)
    cells = []
    for row in range(-2, 12):
        for col in range(-2, 12):
            cx = col * w + (w / 2 if row % 2 else 0)
            cy = ss + row * 1.5 * ss
            d = math.hypot(cx - CXs, cy - CYs)
            if 50 < d < R - 6 and rnd.random() < 0.12:
                cells.append((cx, cy))
    for (cx, cy) in cells:
        s.add(f'<polygon points="{pts(hexpts(cx, cy, ss - 1))}" fill="#e9fcff" fill-opacity="{f(rnd.uniform(0.14, 0.3))}"/>')
    s.add("</g>")
    # rim and highlights
    s.add(circle(CXs, CYs, R - 1, "none", 'stroke="#cdf6ff" stroke-width="5" stroke-opacity="0.45" filter="%s"' % s.blur(2.6)))
    s.add(circle(CXs, CYs, R - 1.2, "none", 'stroke="#f2fdff" stroke-width="2"'))
    s.add(stroke("M34 70 A66 66 0 0 1 80 30", "#ffffff", 4, 'stroke-opacity="0.85" filter="%s"' % s.blur(1.2)))
    s.add(ellipse(58, 46, 17, 8, "#ffffff", f'fill-opacity="0.55" transform="rotate(-38 58 46)" filter="{s.blur(2.2)}"'))
    s.add(stroke("M150 150 A66 66 0 0 1 120 168", "#bfeaff", 3, 'stroke-opacity="0.5"'))
    return s


JOBS = {
    "hut": hut, "hut_me": hut_me, "campfire": campfire, "campfire_glow": campfire_glow,
    "fx_spark": fx_spark, "fx_crumb": fx_crumb, "fx_ring": fx_ring, "fx_shield": fx_shield,
}
