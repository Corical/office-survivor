"""move_scavenge / guard / steal / investigate / gift: 192x192 illustrated medallions with one shared bezel."""
import math
from artlib import *

CX, CY = 96, 92
R_OUT, R_MID, R_ACC, R_IN = 86, 78, 73.5, 70


def shade(accent):
    return {
        "hi": lighten(accent, 0.62),
        "light": lighten(accent, 0.32),
        "mid": accent,
        "dark": darken(accent, 0.42),
        "deep": darken(accent, 0.72),
    }


def bezel(s, accent):
    c = shade(accent)
    out = []
    # soft ground shadow and drop shadow
    out.append(ellipse(CX, 181, 66, 8, "#000", f'fill-opacity="0.5" filter="{s.blur(5)}"'))
    out.append(circle(CX, CY + 5, R_OUT, "#000", f'fill-opacity="0.5" filter="{s.blur(5)}"'))
    # outer bezel: brushed brass-bronze catching the moon (top-left) and the fire (bottom-right)
    metal = s.lin([(0, "#f4e7c4"), (0.12, "#cdb27a"), (0.3, "#7d6a44"), (0.5, "#2c241a"), (0.7, "#6e5c3a"), (0.86, "#b99c63"), (1, "#3d3120")], 0.1, 0.0, 0.9, 1.0)
    out.append(circle(CX, CY, R_OUT, metal))
    out.append(circle(CX, CY, R_OUT - 0.6, "none", 'stroke="#120d07" stroke-opacity="0.9" stroke-width="1.4"'))
    # groove between bezel and inset
    groove = s.lin([(0, "#0e0a05"), (1, "#8f7a4c")], 0.2, 0.1, 0.8, 0.95)
    out.append(circle(CX, CY, R_MID, groove))
    out.append(circle(CX, CY, R_MID - 1.2, "none", 'stroke="#d8c08a" stroke-opacity="0.35" stroke-width="0.9"'))
    # studs on the bezel
    for i in range(12):
        a = math.radians(i * 30 - 90)
        x, y = CX + math.cos(a) * 82.2, CY + math.sin(a) * 82.2
        out.append(circle(x + 0.5, y + 0.9, 2.5, "#000", 'fill-opacity="0.55"'))
        out.append(circle(x, y, 2.4, s.rad([(0, "#fff3d0"), (0.5, "#b79a5e"), (1, "#4a3b22")], 0.35, 0.3, 0.75)))
    # bezel specular arc (upper left)
    out.append(stroke(f"M{f(CX + 82 * math.cos(math.radians(200)))} {f(CY + 82 * math.sin(math.radians(200)))} A82 82 0 0 1 {f(CX + 82 * math.cos(math.radians(285)))} {f(CY + 82 * math.sin(math.radians(285)))}", "#fff8e6", 2.2, f'stroke-opacity="0.7" filter="{s.blur(0.8)}"'))
    # glowing accent ring (the hue lives here and in the symbol)
    out.append(circle(CX, CY, R_ACC, "none", f'stroke="{c["mid"]}" stroke-width="7" stroke-opacity="0.55" filter="{s.blur(4)}"'))
    out.append(circle(CX, CY, R_ACC, "none", f'stroke="{c["light"]}" stroke-width="3.2"'))
    out.append(circle(CX, CY, R_ACC - 1.6, "none", f'stroke="{c["hi"]}" stroke-width="0.9" stroke-opacity="0.9"'))
    # inner dish
    dish = s.rad([(0, mix(accent, "#0a1020", 0.50)), (0.62, mix(accent, "#060a16", 0.78)), (1, "#04060e")], 0.5, 0.42, 0.62)
    out.append(circle(CX, CY, R_IN, dish))
    out.append(circle(CX, CY, R_IN, "none", 'stroke="#000" stroke-opacity="0.65" stroke-width="2" filter="url(#none)"'.replace(' filter="url(#none)"', "")))
    # glow behind the symbol
    out.append(circle(CX, CY + 2, 54, s.rad([(0, accent, 0.62), (0.55, accent, 0.2), (1, accent, 0)]), ""))
    return "".join(out)


def glass(s):
    clip = s.clip(circle(CX, CY, R_IN))
    hl = s.lin([(0, "#ffffff", 0.34), (1, "#ffffff", 0)], 0, 0, 0, 1)
    out = f'<g clip-path="{clip}">'
    out += ellipse(CX - 8, CY - 40, 58, 30, hl)
    out += circle(CX + 10, CY + 78, 70, s.rad([(0.8, "#000", 0), (1, "#000", 0.28)], 0.5, 0.3, 0.8), "")
    out += "</g>"
    out += circle(CX, CY, R_IN, "none", 'stroke="#ffffff" stroke-opacity="0.14" stroke-width="1"')
    return out


# ------------------------------------------------------------------ symbols (local coords, centre 0,0, about +-48)
def sym_scavenge(s, accent):
    c = shade(accent)
    o = []
    OUTL = "#06120a"
    leaf_g = s.lin([(0, c["hi"]), (0.5, c["mid"]), (1, c["dark"])], 0, 0, 1, 1)
    wood = s.lin([(0, "#e0a35c"), (0.5, "#a8692f"), (1, "#5e3515")], 0, 0, 0, 1)
    wood_dark = "#3a200c"
    # leaves
    leaves = [
        "M-2 -6 C-12 -26 -30 -40 -44 -34 C-38 -18 -20 -8 -2 -6 Z",
        "M2 -6 C12 -26 30 -40 44 -34 C38 -18 20 -8 2 -6 Z",
        "M0 -6 C-12 -22 -10 -40 0 -50 C10 -40 12 -22 0 -6 Z",
    ]
    for d in leaves:
        o.append(path(d, leaf_g, f'stroke="{OUTL}" stroke-width="2.2" stroke-linejoin="round"'))
    o.append(stroke("M0 -6 L0 -40", c["hi"], 1.2, 'opacity="0.8"'))
    o.append(stroke("M-3 -8 Q-20 -22 -38 -32", c["hi"], 1.1, 'opacity="0.7"'))
    o.append(stroke("M3 -8 Q20 -22 38 -32", c["hi"], 1.1, 'opacity="0.7"'))
    # banana and coconut peeking out of the crate
    o.append(path("M10 2 C16 -14 30 -18 40 -14 C32 -12 24 -6 20 6 Z", "#ffd75a", f'stroke="#5a3d00" stroke-width="1.8" stroke-linejoin="round"'))
    o.append(stroke("M14 -2 C20 -10 28 -13 36 -13", "#fff3b0", 1.4, 'opacity="0.85"'))
    o.append(circle(-16, -2, 11, s.rad([(0, "#c28a50"), (0.6, "#7a4a22"), (1, "#3d200c")], 0.35, 0.3, 0.8), f'stroke="#1e0e04" stroke-width="2"'))
    for (dx, dy) in ((-19, -5), (-13, -5), (-16, 1)):
        o.append(circle(-16 + dx + 16 - 0, -2 + dy + 2 - 0, 1.4, "#24120a", 'fill-opacity="0.9"'))
    # crate (front view): rim, three slats, corner posts, shadow slits
    o.append(path(rrect_d(-34, 0, 68, 14, 3), wood, f'stroke="{wood_dark}" stroke-width="2.2"'))
    o.append(path(rrect_d(-32, 12, 64, 30, 3), wood, f'stroke="{wood_dark}" stroke-width="2.2"'))
    for y in (22, 32):
        o.append(stroke(f"M-31 {y} L31 {y}", wood_dark, 1.8, 'opacity="0.9"'))
        o.append(stroke(f"M-31 {y - 1.6} L31 {y - 1.6}", "#ffd08a", 0.9, 'opacity="0.45"'))
    for x in (-27, 27):
        o.append(rect(x - 3.5, 12, 7, 30, "#7a4620", 1.5, f'stroke="{wood_dark}" stroke-width="1.8"'))
        o.append(circle(x, 17, 1.4, "#ffe0a0")); o.append(circle(x, 37, 1.4, "#ffe0a0"))
    o.append(stroke("M-32 2.8 L32 2.8", "#ffd9a0", 1.2, 'opacity="0.55"'))
    # sparkles
    for (x, y, r) in ((-44, -4, 5), (44, 4, 4), (26, -44, 4.5)):
        o.append(path(star4(x, y, r, 0.16), "#eaffd0", 'fill-opacity="0.95"'))
    return "".join(o)


def sym_guard(s, accent):
    c = shade(accent)
    o = []
    steel = s.lin([(0, c["hi"]), (0.45, c["mid"]), (1, c["dark"])], 0.1, 0, 0.9, 1)
    inner = s.lin([(0, c["light"]), (1, c["deep"])], 0, 0, 0, 1)
    d = "M0 -48 L38 -35 V2 C38 26 22 40 0 50 C-22 40 -38 26 -38 2 V-35 Z"
    o.append(path(d, "#001018", 'transform="translate(0 3)" fill-opacity="0.45"'))
    o.append(path(d, steel, 'stroke="#04141c" stroke-width="2.6" stroke-linejoin="round"'))
    d2 = "M0 -39 L30 -29 V1 C30 21 18 32 0 41 C-18 32 -30 21 -30 1 V-29 Z"
    o.append(path(d2, inner, f'stroke="{c["hi"]}" stroke-width="1.6" stroke-opacity="0.8" stroke-linejoin="round"'))
    # centre ridge
    o.append(stroke("M0 -39 L0 41", c["hi"], 1.0, 'opacity="0.25"'))
    # warm halo from the lantern
    o.append(circle(0, 2, 30, s.rad([(0, "#ffd37a", 0.85), (0.5, "#ff9a3c", 0.3), (1, "#ff9a3c", 0)]), ""))
    # lantern: handle, cap, glass body with ember flame, base
    o.append(stroke("M-8 -17 C-8 -29 8 -29 8 -17", "#10202c", 3.2))
    o.append(stroke("M-8 -17 C-8 -29 8 -29 8 -17", "#8fa7b6", 1.0, 'opacity="0.8"'))
    o.append(path("M-12 -14 L12 -14 L9 -20 L-9 -20 Z", "#243746", 'stroke="#04141c" stroke-width="1.8" stroke-linejoin="round"'))
    glass_g = s.lin([(0, "#fff0b0"), (0.5, "#ffb347"), (1, "#e8791f")], 0, 0, 0, 1)
    o.append(path("M-11 -14 L11 -14 L9 14 L-9 14 Z", glass_g, 'stroke="#04141c" stroke-width="2"'))
    o.append(path(flame_d(0, 11, 5.2, 18, 0.1), "#fff6d2", ""))
    o.append(path(flame_d(0, 11, 2.8, 11, 0.06), "#ffffff", ""))
    o.append(stroke("M0 -14 L0 14", "#243746", 1.6)); o.append(stroke("M-10 0 L10 0", "#243746", 1.2, 'opacity="0.9"'))
    o.append(path("M-12 14 L12 14 L10 19 L-10 19 Z", "#243746", 'stroke="#04141c" stroke-width="1.8" stroke-linejoin="round"'))
    o.append(stroke("M-11 15.6 L11 15.6", "#8fa7b6", 0.8, 'opacity="0.7"'))
    # sparkles
    for (x, y, r) in ((-40, -30, 4), (42, -6, 3.5)):
        o.append(path(star4(x, y, r, 0.16), "#e4fbff", 'fill-opacity="0.95"'))
    return "".join(o)


def sym_steal(s, accent):
    c = shade(accent)
    o = []
    SHADOW = "#0d0610"
    # food orb being grabbed: a glowing ration
    o.append(circle(-15, 26, 26, s.rad([(0, "#ffd56b", 0.7), (1, "#ffd56b", 0)]), ""))
    o.append(circle(-15, 28, 13, s.rad([(0, "#fff0b0"), (0.5, "#ffb347"), (1, "#b8581a")], 0.35, 0.3, 0.8), 'stroke="#3a1606" stroke-width="2"'))
    o.append(path("M-15 15 C-18 10 -12 8 -9 11", "#3fb65a", 'stroke="#0c2a14" stroke-width="1.6"'))
    # the arm and hand, drawn pointing down then rotated: dark silhouette with a coral rim on the far-left edge
    def hand(rim=False):
        parts = []
        sleeve = "M-17 -62 L17 -62 L19 -14 L-19 -14 Z"
        parts.append(path(sleeve, SHADOW))
        parts.append(path("M-20 -18 L20 -18 L19 -9 L-19 -9 Z", SHADOW))
        parts.append(path(rrect_d(-13, -12, 26, 28, 9), SHADOW))
        for (x, ln, w) in ((-9.8, 26, 6.2), (-3.4, 31, 6.4), (3.4, 30, 6.4), (9.8, 24, 5.8)):
            parts.append(path(f"M{x - w / 2} 6 L{x - w / 2} {6 + ln - w / 2} Q{x - w / 2} {6 + ln} {x} {6 + ln} Q{x + w / 2} {6 + ln} {x + w / 2} {6 + ln - w / 2} L{x + w / 2} 6 Z", SHADOW))
        parts.append(path("M-12 2 L-26 14 Q-31 20 -26 22 Q-21 24 -17 19 L-9 11 Z", SHADOW))
        return "".join(parts)
    o.append(f'<g transform="translate(15 -10) rotate(32)">'
             f'<g transform="translate(-2.4 0)" opacity="0.95"><g fill="{c["light"]}">{hand().replace(SHADOW, c["light"])}</g></g>'
             f'{hand()}'
             # a hint of cuff trim and knuckle light
             f'<path d="M-20 -17 L20 -17" stroke="{c["mid"]}" stroke-width="1.6" fill="none" opacity="0.8"/>'
             f'</g>')
    # motion streaks behind the hand (it came out of the dark)
    for (x1, y1, x2, y2) in ((34, -42, 46, -52), (40, -30, 50, -38), (28, -50, 36, -58)):
        o.append(stroke(f"M{x1} {y1} L{x2} {y2}", c["light"], 1.6, 'opacity="0.55"'))
    # eyes in the hood-shadow hint: two small glints at the sleeve top
    return "".join(o)


def sym_investigate(s, accent):
    c = shade(accent)
    o = []
    # handle (behind lens), ferrule, then ring and glass
    o.append(f'<g transform="translate(-6 -8) rotate(45)">'
             + rect(26, -6, 36, 12, s.lin([(0, "#7a4a28"), (0.5, "#4a2a14"), (1, "#24120a")], 0, 0, 0, 1), 5, 'stroke="#12090a" stroke-width="2"')
             + rect(24, -7.4, 7, 14.8, s.lin([(0, "#ffe9a8"), (0.5, "#c9a44a"), (1, "#6a5220")], 0, 0, 0, 1), 2, 'stroke="#12090a" stroke-width="1.6"')
             + rect(30, -3.6, 28, 2.4, "#c98c58", 1.2, 'fill-opacity="0.5"')
             + "</g>")
    LX, LY, LR = -8, -8, 31
    o.append(circle(LX + 1, LY + 4, LR + 7, "#000", 'fill-opacity="0.35"'))
    ring = s.lin([(0, "#fff2c0"), (0.35, "#d1a94e"), (0.7, "#6b5222"), (1, "#2b200c")], 0.1, 0, 0.9, 1)
    o.append(circle(LX, LY, LR + 6.5, ring, 'stroke="#12090a" stroke-width="2"'))
    o.append(circle(LX, LY, LR + 1, "#120a04"))
    # glass interior: dark violet room with a big watching eye
    glass_g = s.rad([(0, mix(accent, "#ffffff", 0.2)), (0.6, mix(accent, "#1a1030", 0.45)), (1, "#0c0618")], 0.4, 0.35, 0.75)
    o.append(circle(LX, LY, LR - 1, glass_g))
    clip = s.clip(circle(LX, LY, LR - 1))
    eye = []
    eye.append(circle(LX, LY, 24, s.rad([(0, accent, 0.5), (1, accent, 0)]), ""))
    eye.append(path(f"M{LX - 27} {LY} Q{LX} {LY - 25} {LX + 27} {LY} Q{LX} {LY + 25} {LX - 27} {LY} Z",
                    s.lin([(0, "#ffffff"), (0.55, "#efe4ff"), (1, "#b79ae0")], 0, 0, 0, 1), 'stroke="#1a0c30" stroke-width="2.4" stroke-linejoin="round"'))
    eye.append(circle(LX, LY, 12, s.rad([(0, "#ffd86b"), (0.35, "#c58bff"), (0.8, "#5a2ea8"), (1, "#25104a")], 0.5, 0.5, 0.5), 'stroke="#1a0c30" stroke-width="1.4"'))
    eye.append(circle(LX, LY, 5.4, "#080212"))
    eye.append(circle(LX - 3.8, LY - 4, 2.6, "#ffffff", 'fill-opacity="0.95"'))
    eye.append(circle(LX + 3.4, LY + 3.6, 1.2, "#ffffff", 'fill-opacity="0.7"'))
    # lashes / brow arcs: it is a watching eye, not a cartoon face
    o.append(f'<g clip-path="{clip}">{"".join(eye)}')
    o.append(path(f"M{LX - 34} {LY - 20} A40 40 0 0 1 {LX + 20} {LY - 38} L{LX + 6} {LY - 10} Q{LX - 12} {LY - 18} {LX - 34} {LY - 20} Z", "#ffffff", 'fill-opacity="0.16"'))
    o.append("</g>")
    o.append(circle(LX, LY, LR - 1, "none", 'stroke="#ffffff" stroke-opacity="0.35" stroke-width="1"'))
    o.append(stroke(f"M{LX - 24} {LY - 14} A28 28 0 0 1 {LX - 6} {LY - 27}", "#ffffff", 2.4, 'stroke-opacity="0.7"'))
    # sparkles
    for (x, y, r) in ((34, -36, 4.5), (-42, 30, 3.5), (40, 20, 3)):
        o.append(path(star4(x, y, r, 0.16), "#f1e6ff", 'fill-opacity="0.95"'))
    return "".join(o)


def sym_gift(s, accent):
    c = shade(accent)
    o = []
    box = s.lin([(0, "#ffd27a"), (0.5, "#f09a2e"), (1, "#a8540f")], 0, 0, 1, 1)
    lid = s.lin([(0, "#ffe4a0"), (0.5, "#ffb347"), (1, "#c26a18")], 0, 0, 1, 1)
    rib = s.lin([(0, "#ffffff"), (0.5, "#fff0cc"), (1, "#e0b878")], 0, 0, 1, 1)
    OUTL = "#3a1a04"
    # parcel body and lid (slightly 3/4: a visible lid underside shadow)
    o.append(ellipse(0, 44, 38, 5, "#000", 'fill-opacity="0.3"'))
    o.append(path(rrect_d(-32, -4, 64, 46, 5), box, f'stroke="{OUTL}" stroke-width="2.4"'))
    o.append(rect(-32, -4, 64, 7, "#7a3a08", 0, 'fill-opacity="0.35"'))
    o.append(path(rrect_d(-37, -17, 74, 17, 5), lid, f'stroke="{OUTL}" stroke-width="2.4"'))
    # wrapping-paper pattern: small diamonds
    for (x, y) in ((-22, 14), (-10, 26), (4, 12), (18, 26), (24, 12), (-22, 34), (10, 36), (-6, 6)):
        o.append(path(f"M{x} {y - 3} L{x + 3} {y} L{x} {y + 3} L{x - 3} {y} Z", "#fff0cc", 'fill-opacity="0.35"'))
    # ribbon cross
    o.append(rect(-6, -17, 12, 59, rib, 0, f'stroke="{OUTL}" stroke-width="1.8" stroke-opacity="0.9"'))
    o.append(rect(-32, 12, 64, 9, rib, 0, f'stroke="{OUTL}" stroke-width="1.8" stroke-opacity="0.9"'))
    o.append(rect(-6, -17, 4, 59, "#ffffff", 0, 'fill-opacity="0.45"'))
    # bow
    bow = s.lin([(0, "#ffffff"), (0.6, "#ffe9b8"), (1, "#d9a65c")], 0, 0, 1, 1)
    o.append(path("M0 -17 C-10 -40 -34 -38 -30 -26 C-27 -17 -10 -16 0 -17 Z", bow, f'stroke="{OUTL}" stroke-width="2.2" stroke-linejoin="round"'))
    o.append(path("M0 -17 C10 -40 34 -38 30 -26 C27 -17 10 -16 0 -17 Z", bow, f'stroke="{OUTL}" stroke-width="2.2" stroke-linejoin="round"'))
    o.append(stroke("M-3 -19 C-12 -30 -22 -30 -26 -28", "#d9a65c", 1.2, 'opacity="0.8"'))
    o.append(stroke("M3 -19 C12 -30 22 -30 26 -28", "#d9a65c", 1.2, 'opacity="0.8"'))
    o.append(circle(0, -18, 6, bow, f'stroke="{OUTL}" stroke-width="2"'))
    # a banana leaf and a fruit tucked under the ribbon: it is food
    o.append(path("M26 -4 C40 -10 48 -24 46 -34 C36 -28 28 -18 26 -4 Z", s.lin([(0, "#bff08a"), (1, "#3f9a3a")], 0, 0, 1, 1), 'stroke="#0c2a14" stroke-width="1.8" stroke-linejoin="round"'))
    for (x, y, r) in ((-42, -22, 5), (44, 20, 4), (-40, 28, 3.2)):
        o.append(path(star4(x, y, r, 0.16), "#fff6d6", 'fill-opacity="0.95"'))
    return "".join(o)


def badge(name, accent, symbol, scale=1.12, dy=2):
    s = Svg(192, 192, name)
    s.add(bezel(s, accent))
    sym = symbol(s, accent)
    clip = s.clip(circle(CX, CY, R_IN - 1))
    s.add(f'<g clip-path="{clip}"><g transform="translate({CX} {CY + dy}) scale({scale})">{sym}</g></g>')
    s.add(glass(s))
    return s


JOBS = {
    "move_scavenge": lambda: badge("move_scavenge", "#7ddc5a", sym_scavenge, 1.2, 4),
    "move_guard": lambda: badge("move_guard", "#4fc3f7", sym_guard, 1.08, 3),
    "move_steal": lambda: badge("move_steal", "#ff6b5e", sym_steal, 1.22, 4),
    "move_investigate": lambda: badge("move_investigate", "#c58bff", sym_investigate, 1.14, 4),
    "move_gift": lambda: badge("move_gift", "#ffb347", sym_gift, 1.16, 3),
}
