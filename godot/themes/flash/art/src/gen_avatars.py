"""avatar_0 .. avatar_7: 128x128 survivor busts. One parametric bust, eight different people.
Light: cool moon rim up-left, warm fire rim down-right, flat cartoon shading with a dark outline so they read at 40 px.
No face, hat or colour says anything about role, bot or human."""
import math
import random
from artlib import *

OUT = "#0b0f1c"
HEAD = "M39 52 C39 34 50 27 64 27 C78 27 89 34 89 52 C89 70 80 85 64 86 C48 85 39 70 39 52 Z"
BODY = "M14 130 C14 106 36 95 64 95 C92 95 114 106 114 130 Z"


class Bust:
    def __init__(self, name):
        self.s = Svg(128, 128, name)
        self.layers = []
        self.sil = []

    def lit(self, c):
        return self.s.lin([(0, lighten(c, 0.26)), (0.45, c), (1, darken(c, 0.34))], 0.05, 0.0, 0.95, 1.0)

    def part(self, d, color, w=2.2, sil=True, grad=True, extra=""):
        fill = self.lit(color) if grad else color
        self.layers.append(f'<path d="{d}" fill="{fill}" stroke="{OUT}" stroke-width="{w}" stroke-linejoin="round" {extra}/>')
        if sil:
            self.sil.append(d)

    def raw(self, markup):
        self.layers.append(markup)

    def finish(self):
        s = self.s
        sil = " ".join(self.sil)
        # ground shadow so the bust sits on the page
        s.add(ellipse(64, 124, 50, 5, "#000", f'fill-opacity="0.35" filter="{s.blur(3)}"'))
        s.add(f'<g transform="translate(-1.8 -1.8)"><path d="{sil}" fill="#a9c8ff" fill-opacity="0.9"/></g>')
        s.add(f'<g transform="translate(1.8 1.2)"><path d="{sil}" fill="#ff9a3c" fill-opacity="0.75"/></g>')
        for l in self.layers:
            s.add(l)
        # overall light: cool from the top-left, warm bounce from the bottom-right, clipped to the figure
        clip = s.clip(path(sil))
        s.add(f'<g clip-path="{clip}">'
              + rect(0, 0, 128, 128, s.lin([(0, "#bcd8ff", 0.28), (0.4, "#bcd8ff", 0), (0.7, "#ff9a3c", 0), (1, "#ff9a3c", 0.22)], 0, 0, 1, 1), "")
              + "</g>")
        return s


def face(b, skin, eye="#10131f", mouth="smile", brow="#2a1a12", blush=True, brow_tilt=0, eye_dx=0):
    s = b.s
    b.part("M54 78 L74 78 L76 100 L52 100 Z", darken(skin, 0.1), 2.0)  # neck
    b.raw(f'<path d="M54 82 Q64 92 74 82 L74 78 L54 78 Z" fill="#000" fill-opacity="0.22"/>')  # chin shadow on neck
    b.part(HEAD, skin, 2.4)
    # ears
    for sx in (-1, 1):
        cx = 64 + sx * 26.5
        b.raw(f'<ellipse cx="{f(cx)}" cy="58" rx="5.2" ry="7.4" fill="{darken(skin, 0.06)}" stroke="{OUT}" stroke-width="2"/>')
        b.raw(f'<ellipse cx="{f(cx - sx * 0.6)}" cy="58.5" rx="2" ry="3.6" fill="{darken(skin, 0.22)}" fill-opacity="0.6"/>')
    # redraw head over the ear roots so ears tuck behind
    b.raw(f'<path d="{HEAD}" fill="{b.lit(skin)}" stroke="{OUT}" stroke-width="2.4"/>')
    clip = s.clip(path(HEAD))
    if blush:
        b.raw(f'<g clip-path="{clip}"><ellipse cx="49" cy="68" rx="6" ry="3.6" fill="#ff7a6b" fill-opacity="0.30"/><ellipse cx="79" cy="68" rx="6" ry="3.6" fill="#ff7a6b" fill-opacity="0.30"/></g>')
    # eyes
    for sx in (-1, 1):
        cx = 64 + sx * 10.5 + eye_dx
        b.raw(f'<ellipse cx="{f(cx)}" cy="58" rx="3.1" ry="4.1" fill="{eye}"/>')
        b.raw(f'<circle cx="{f(cx - 0.9)}" cy="56.4" r="1.25" fill="#fff"/>')
        b.raw(f'<path d="M{f(cx - 5.6)} {f(50.2 + sx * brow_tilt)} Q{f(cx)} {f(47.2 - sx * brow_tilt * 0.5)} {f(cx + 5.6)} {f(50.2 - sx * brow_tilt)}" fill="none" stroke="{brow}" stroke-width="2.2" stroke-linecap="round"/>')
    # nose
    b.raw(f'<path d="M64 60 Q61.5 68 64.6 69.4" fill="none" stroke="{darken(skin, 0.38)}" stroke-width="1.6" stroke-linecap="round"/>')
    # mouth
    if mouth == "smile":
        b.raw('<path d="M55 74 Q64 82 73 74" fill="none" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>')
    elif mouth == "grin":
        b.raw('<path d="M54 73 Q64 85 74 73 Z" fill="#3a1410" stroke="#3a1a14" stroke-width="1.8" stroke-linejoin="round"/><path d="M56.5 74.2 Q64 77 71.5 74.2 L71 76 Q64 78.6 57 76 Z" fill="#fff"/>')
    elif mouth == "smirk":
        b.raw('<path d="M56 75 Q64 77 74 71" fill="none" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>')
    elif mouth == "flat":
        b.raw('<path d="M57 75 L71 75" fill="none" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>')
    elif mouth == "o":
        b.raw('<ellipse cx="64" cy="75" rx="3.4" ry="3" fill="#3a1410" stroke="#3a1a14" stroke-width="1.4"/>')
    return clip


def body(b, color, collar=None, collar_style="v", pocket=False, strap=None):
    b.part(BODY, color, 2.4)
    clip = b.s.clip(path(BODY))
    if collar_style == "v":
        b.raw(f'<path d="M50 96 L64 114 L78 96 Q64 102 50 96 Z" fill="{collar or darken(color, 0.3)}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    elif collar_style == "crew":
        b.raw(f'<path d="M50 96 Q64 108 78 96 Q64 100 50 96 Z" fill="{collar or darken(color, 0.25)}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    elif collar_style == "hood":
        b.raw(f'<path d="M44 97 Q64 118 84 97 Q76 92 64 92 Q52 92 44 97 Z" fill="{collar or darken(color, 0.28)}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    if strap:
        b.raw(f'<g clip-path="{clip}"><path d="M28 98 L52 130 L66 130 L38 96 Z" fill="{strap}" stroke="{OUT}" stroke-width="1.6" fill-opacity="0.95"/></g>')
    if pocket:
        b.raw(f'<g clip-path="{clip}"><path d="M78 114 L98 114 L98 124 Q88 128 78 124 Z" fill="{darken(color, 0.2)}" stroke="{OUT}" stroke-width="1.4"/></g>')
    # fold lines
    b.raw(f'<g clip-path="{clip}"><path d="M24 118 Q30 112 34 118" fill="none" stroke="#000" stroke-opacity="0.22" stroke-width="1.6"/><path d="M104 118 Q98 112 94 118" fill="none" stroke="#000" stroke-opacity="0.22" stroke-width="1.6"/></g>')


# ----------------------------------------------------------------- hair / hats / accessories
def hair_short(b, c):
    b.part("M38 52 C35 28 49 19 64 19 C81 19 93 28 90 52 C86 42 78 36 66 37 C54 36 44 42 38 52 Z", c, 2.2)


def hair_long_back(b, c):
    b.part("M33 58 C28 30 46 16 64 16 C84 16 100 30 95 58 L100 100 L28 100 Z", c, 2.4)


def hair_afro(b, c):
    for (x, y, r) in ((34, 44, 13), (40, 28, 14), (54, 20, 15), (70, 19, 15), (86, 28, 14), (94, 44, 13), (46, 36, 14), (82, 36, 14), (64, 28, 16)):
        b.part(f"M{x - r} {y} A{r} {r} 0 1 1 {x + r} {y} A{r} {r} 0 1 1 {x - r} {y} Z", c, 2.0, grad=True)


def beard(b, c, full=True):
    d = "M40 56 C40 82 52 94 64 94 C76 94 88 82 88 56 C84 74 76 78 64 78 C52 78 44 74 40 56 Z"
    b.part(d, c, 2.0, sil=False)
    b.raw(f'<path d="M57 75 Q64 79 71 75 Q64 72.5 57 75 Z" fill="{darken(c, 0.5)}" fill-opacity="0.0"/>')


def mustache(b, c, big=False):
    if big:
        b.raw(f'<path d="M64 69 C58 64 48 66 46 74 C52 72 58 74 64 72 C70 74 76 72 82 74 C80 66 70 64 64 69 Z" fill="{lighten(c, 0.1)}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    else:
        b.raw(f'<path d="M64 69 C60 66 54 67 52 71 C57 70 61 71 64 70 C67 71 71 70 76 71 C74 67 68 66 64 69 Z" fill="{c}" stroke="{OUT}" stroke-width="1.5" stroke-linejoin="round"/>')


def hat_beanie(b, c, cuff, pom=None):
    b.part("M36 46 C33 20 50 12 64 12 C78 12 95 20 92 46 Z", c, 2.4)
    b.part("M35 38 L93 38 Q96 52 92 54 L36 54 Q32 52 35 38 Z", cuff, 2.4)
    for x in range(42, 92, 6):
        b.raw(f'<path d="M{x} 40 L{x - 0.6} 53" stroke="#000" stroke-opacity="0.28" stroke-width="1.6"/>')
    if pom:
        b.part("M52 14 A12 12 0 1 1 76 14 A12 12 0 1 1 52 14 Z", pom, 2.0)


def hat_straw(b, c, band):
    b.part("M12 46 C10 36 36 32 64 32 C92 32 118 36 116 46 C114 56 90 58 64 58 C38 58 14 56 12 46 Z", darken(c, 0.04), 2.4)
    b.raw(f'<ellipse cx="64" cy="44" rx="40" ry="6" fill="#000" fill-opacity="0.22"/>')
    b.part("M42 44 C40 18 52 10 64 10 C76 10 88 18 86 44 C78 48 50 48 42 44 Z", c, 2.4)
    b.raw(f'<path d="M41.6 38 C52 42 76 42 86.4 38 L86.2 46 C76 49.6 52 49.6 41.8 46 Z" fill="{band}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    for i in range(7):
        y = 14 + i * 3.6
        b.raw(f'<path d="M{47 + i * 0.6} {y} Q64 {y + 3} {81 - i * 0.6} {y}" stroke="#7a5a1a" stroke-opacity="0.45" stroke-width="1" fill="none"/>')
    for i in range(10):
        x = 20 + i * 9
        b.raw(f'<path d="M{x} 40 Q{x + 1} 46 {x - 1} 54" stroke="#7a5a1a" stroke-opacity="0.35" stroke-width="1" fill="none"/>')


def hat_bandana(b, c, dot="#fff"):
    b.part("M37 44 C40 22 88 22 91 44 L91 52 C80 44 48 44 37 52 Z", c, 2.4)
    # knot and tails at the side
    b.part("M88 44 L108 36 L104 52 L110 62 L92 56 Z", darken(c, 0.08), 2.2)
    b.part("M86 42 A6 6 0 1 1 98 46 A6 6 0 1 1 86 42 Z", c, 2.0)
    for (x, y) in ((46, 36), (58, 31), (72, 31), (84, 37), (52, 46), (66, 44), (80, 46), (104, 46), (100, 56)):
        b.raw(f'<circle cx="{x}" cy="{y}" r="1.8" fill="{dot}" fill-opacity="0.9"/>')


def hat_cap(b, c, bill=None):
    b.part("M37 46 C34 18 52 12 64 12 C78 12 94 18 91 46 Z", c, 2.4)
    for x in (52, 64, 76):
        b.raw(f'<path d="M64 12 Q{x} 28 {x - 2 if x < 64 else x + 2} 45" stroke="#000" stroke-opacity="0.22" stroke-width="1.4" fill="none"/>')
    b.part("M34 44 Q64 40 94 44 Q100 48 94 52 Q64 46 34 52 Q28 48 34 44 Z", bill or darken(c, 0.12), 2.2)
    b.raw(f'<path d="M40 52 Q64 46 88 52 L88 56 Q64 50 40 56 Z" fill="#000" fill-opacity="0.2"/>')
    b.raw(f'<circle cx="64" cy="13.5" r="2.4" fill="{darken(c, 0.2)}" stroke="{OUT}" stroke-width="1.2"/>')


def hat_hood(b, c, fur):
    b.part("M20 100 C10 50 30 12 64 12 C98 12 118 50 108 100 L88 100 L40 100 Z", c, 2.6)
    b.part("M30 64 C28 34 44 20 64 20 C84 20 100 34 98 64 C100 40 86 28 64 28 C42 28 28 40 30 64 Z", fur, 2.2, sil=False)
    # fur fluffs
    for k in range(18):
        a = math.radians(200 + k * (140 / 17))
        x = 64 + math.cos(a) * 36
        y = 62 + math.sin(a) * 40
        b.raw(f'<circle cx="{f(x)}" cy="{f(y)}" r="5.2" fill="{fur}" stroke="{OUT}" stroke-width="1.3"/>')


def hat_pith(b, c):
    b.part("M14 46 C16 36 40 34 64 34 C88 34 112 36 114 46 C112 54 90 56 64 56 C38 56 16 54 14 46 Z", darken(c, 0.04), 2.4)
    b.raw(f'<ellipse cx="64" cy="46" rx="40" ry="5" fill="#000" fill-opacity="0.2"/>')
    b.part("M38 42 C34 14 52 6 64 6 C76 6 94 14 90 42 C80 47 48 47 38 42 Z", c, 2.4)
    b.raw(f'<path d="M37.6 36 C50 41 78 41 90.4 36 L90 43 C80 47.6 48 47.6 38 43 Z" fill="#6a4a28" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    b.raw(f'<path d="M64 8 L64 38" stroke="#000" stroke-opacity="0.18" stroke-width="1.4"/>')
    b.raw(f'<path d="M58 30 L64 25 L70 30 L64 35 Z" fill="#e9c14a" stroke="{OUT}" stroke-width="1.2" stroke-linejoin="round"/>')


def glasses(b, rim="#1a1f33", lens="#cfe8ff", sun=False, mono=False):
    xs = [53.5, 74.5] if not mono else [74.5]
    for x in xs:
        fillc = "#0a0e18" if sun else lens
        op = "0.95" if sun else "0.22"
        b.raw(f'<circle cx="{x}" cy="58" r="8.4" fill="{fillc}" fill-opacity="{op}" stroke="{rim}" stroke-width="2.2"/>')
        b.raw(f'<path d="M{x - 5} 54 Q{x - 2} 51 {x + 2} 52" stroke="#fff" stroke-opacity="0.7" stroke-width="1.4" fill="none" stroke-linecap="round"/>')
    if not mono:
        b.raw(f'<path d="M62 57 Q64 55.4 66 57" stroke="{rim}" stroke-width="2" fill="none"/>')
        b.raw(f'<path d="M45 57 L39.4 55" stroke="{rim}" stroke-width="2" stroke-linecap="round"/><path d="M83 57 L88.6 55" stroke="{rim}" stroke-width="2" stroke-linecap="round"/>')
    else:
        b.raw(f'<path d="M80 64 Q84 78 82 92" stroke="#e9c14a" stroke-width="1.2" fill="none"/>')


def goggles(b, strap="#3a3a2a", lens="#6fdcf0"):
    b.raw(f'<path d="M36 40 Q64 34 92 40 L92 46 Q64 40 36 46 Z" fill="{strap}" stroke="{OUT}" stroke-width="1.8" stroke-linejoin="round"/>')
    for x in (53, 75):
        b.raw(f'<circle cx="{x}" cy="42" r="9" fill="#2a2f3a" stroke="{OUT}" stroke-width="2"/>')
        b.raw(f'<circle cx="{x}" cy="42" r="6.4" fill="{lens}" fill-opacity="0.9" stroke="#0b0f1c" stroke-width="1"/>')
        b.raw(f'<path d="M{x - 4} 40 Q{x - 1} 37 {x + 2.6} 38" stroke="#fff" stroke-opacity="0.85" stroke-width="1.6" fill="none" stroke-linecap="round"/>')


def eyepatch(b):
    b.raw(f'<path d="M36 40 L88 62" stroke="#10131f" stroke-width="2.2" stroke-linecap="round"/>')
    b.raw(f'<path d="M54 56 Q54 48 62 48 Q70 48 70 56 Q70 66 62 66 Q54 66 54 56 Z" transform="translate(11 0)" fill="#161a28" stroke="{OUT}" stroke-width="1.8"/>')
    b.raw('<path d="M70 50 Q74 52 75 54" stroke="#fff" stroke-opacity="0.3" stroke-width="1.2" fill="none"/>')


def scarf(b, c, c2=None, tail=True, big=False):
    y = 92
    b.part(f"M42 {y - 4} C46 {y + 12} 82 {y + 12} 86 {y - 4} L88 {y + 8} C80 {y + 24} 48 {y + 24} 40 {y + 8} Z", c, 2.4)
    for x in range(48, 84, 8):
        b.raw(f'<path d="M{x} {y + 5} Q{x + 1} {y + 12} {x - 1} {y + 18}" stroke="{c2 or darken(c, 0.3)}" stroke-opacity="0.7" stroke-width="2" fill="none"/>')
    if tail:
        b.part(f"M76 {y + 10} L96 {y + 12} L98 {y + 36} L84 {y + 38} Z", c, 2.4)
        b.raw(f'<path d="M80 {y + 18} L95 {y + 20} M81 {y + 26} L96 {y + 28}" stroke="{c2 or darken(c, 0.3)}" stroke-opacity="0.8" stroke-width="2.4" fill="none"/>')


def freckles(b, c="#b8643a"):
    for (x, y) in ((50, 66), (54, 70), (58, 66), (70, 66), (74, 70), (78, 66)):
        b.raw(f'<circle cx="{x}" cy="{y}" r="0.9" fill="{c}" fill-opacity="0.8"/>')


def earring(b):
    b.raw(f'<circle cx="37.5" cy="68" r="2.4" fill="#ffd56b" stroke="{OUT}" stroke-width="1.1"/>')


# ----------------------------------------------------------------- the eight
def a0():
    b = Bust("avatar_0")
    body(b, "#3a4a6a", "#2a3550", "v", pocket=True)
    face(b, "#8d5a3b", mouth="smile")
    beard(b, "#15110f")
    face_mouth_over = '<path d="M56 76 Q64 83 72 76" fill="none" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>'
    b.raw(face_mouth_over)
    scarf(b, "#d9453c", "#8a1f1a")
    hat_beanie(b, "#1fb5a3", "#138a7c", pom="#f0f6f5")
    return b.finish()


def a1():
    b = Bust("avatar_1")
    body(b, "#4d8fd6", "#e8f0ff", "v")
    # sideburns and ginger hair peeking under the hat
    b.part("M38 54 C36 44 38 38 44 36 L44 56 Z", "#c4571f", 1.8, sil=False)
    b.part("M90 54 C92 44 90 38 84 36 L84 56 Z", "#c4571f", 1.8, sil=False)
    face(b, "#f1c7a0", mouth="grin", brow="#8a3c10")
    freckles(b)
    hat_straw(b, "#e8c66a", "#d9453c")
    return b.finish()


def a2():
    b = Bust("avatar_2")
    hair_afro(b, "#17110e")
    body(b, "#4a9a52", "#2f6e3a", "crew", strap="#e8c66a")
    face(b, "#5a3826", mouth="smile", brow="#0a0605")
    earring(b)
    hat_bandana(b, "#8a4fd6")
    return b.finish()


def a3():
    b = Bust("avatar_3")
    body(b, "#7b8497", "#5a6275", "hood")
    # drawstrings
    b.raw('<path d="M56 100 L55 118 M72 100 L73 118" stroke="#e8eef8" stroke-width="2" stroke-linecap="round"/>')
    b.raw('<circle cx="55" cy="119" r="1.8" fill="#e8eef8"/><circle cx="73" cy="119" r="1.8" fill="#e8eef8"/>')
    face(b, "#d9a074", mouth="grin", brow="#3a2410")
    b.part("M40 50 C40 40 46 36 52 36 L52 50 Z", "#2a1a10", 1.6, sil=False)
    glasses(b)
    hat_cap(b, "#f07a1c")
    return b.finish()


def a4():
    b = Bust("avatar_4")
    hair_long_back(b, "#8c2f1f")
    body(b, "#d9cfb8", "#b8ad92", "crew")
    face(b, "#f4d2b8", mouth="smirk", brow="#5a1c10")
    # fringe: swept to one side
    b.part("M37 54 C33 28 50 18 66 18 C84 18 95 30 91 54 C88 40 80 30 70 30 C62 38 48 44 37 54 Z", "#8c2f1f", 2.2)
    b.raw('<path d="M60 22 Q66 30 56 40" stroke="#ff9a6b" stroke-opacity="0.45" stroke-width="2" fill="none" stroke-linecap="round"/>')
    scarf(b, "#3a78d8", "#1e4a96", tail=True)
    return b.finish()


def a5():
    b = Bust("avatar_5")
    hat_hood(b, "#8a8a52", "#e8e2cf")
    body(b, "#8a8a52", "#6c6c3c", "hood", pocket=True)
    face(b, "#c58e62", mouth="flat", brow="#2a1a10")
    # scruff
    b.raw('<path d="M44 70 C46 82 56 88 64 88 C72 88 82 82 84 70 C78 80 70 82 64 82 C58 82 50 80 44 70 Z" fill="#2a1a10" fill-opacity="0.55"/>')
    b.raw('<path d="M56 76 L72 76" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>')
    goggles(b)
    return b.finish()


def a6():
    b = Bust("avatar_6")
    body(b, "#2f3446", "#e8b82a", "crew", strap="#e8b82a")
    face(b, "#e0ac80", mouth="smirk", brow="#3a2a1a")
    b.raw('<path d="M42 62 C44 78 54 86 64 86 C74 86 84 78 86 62 C80 74 72 78 64 78 C56 78 48 74 42 62 Z" fill="#3a2a1a" fill-opacity="0.38"/>')
    b.raw('<path d="M56 76 Q64 78 74 70" fill="none" stroke="#3a1a14" stroke-width="2.2" stroke-linecap="round"/>')
    b.raw('<path d="M42 44 L40 60" stroke="#b86a4a" stroke-width="2" stroke-linecap="round"/><path d="M80 66 L86 74 M82 64 L88 72" stroke="#b05a40" stroke-width="1.6" stroke-linecap="round"/>')
    # bald head gleam
    b.raw('<path d="M48 34 Q56 28 66 29" stroke="#fff" stroke-opacity="0.55" stroke-width="3" fill="none" stroke-linecap="round"/>')
    eyepatch(b)
    scarf(b, "#d03a3a", "#7a1a1a", tail=False)
    return b.finish()


def a7():
    b = Bust("avatar_7")
    body(b, "#6b7a3a", "#f1ece0", "v", pocket=True)
    b.raw('<path d="M50 96 L64 114 L78 96" stroke="#f1ece0" stroke-width="7" fill="none" stroke-linejoin="round"/>')
    # white hair at the sides
    b.part("M37 56 C34 44 36 38 42 38 L44 60 Z", "#f1f1f1", 1.8, sil=False)
    b.part("M91 56 C94 44 92 38 86 38 L84 60 Z", "#f1f1f1", 1.8, sil=False)
    face(b, "#e9bd96", mouth="smile", brow="#cfcfcf")
    mustache(b, "#f1f1f1", big=True)
    glasses(b, rim="#e9c14a", mono=True)
    hat_pith(b, "#cfb98a")
    return b.finish()


JOBS = {f"avatar_{i}": fn for i, fn in enumerate([a0, a1, a2, a3, a4, a5, a6, a7])}
