"""Generate the STAND-IN art for the flash theme into godot/themes/flash/art_standin/.

    python godot/tools/gen_flash_standins.py [--sheet PATH]

The real art (another designer) is delivered to godot/themes/flash/art/<id>.png under the SAME ids; the theme loads
art/<id>.png first and falls back to art_standin/<id>.png, so dropping the real files in changes the look with no code
change. These stand-ins exist so the screens can be built and judged now. They are deliberately simple flat shapes with
a consistent night-and-ember palette. Everything is drawn 4x and scaled down for clean edges.

Ids required by the brief: backdrop_far backdrop_near logo move_scavenge move_guard move_steal move_investigate move_gift
hut hut_me campfire campfire_glow avatar_0..7 fx_spark fx_crumb fx_ring fx_shield card_frame (9-slice, margin 28)
button_wood button_wood_pressed (9-slice, margins 40/30). Extras only this stand-in set carries (the theme falls back
to nothing when they are missing): cloud, vignette, crown, lantern_on, lantern_off.
"""
import argparse
import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SS = 4
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "themes", "flash", "art_standin"))
FONT = "C:/Windows/Fonts/impact.ttf"

INK = (10, 15, 28)
OUTLINE = (24, 14, 20)
CREAM = (255, 244, 220)
EMBER = (255, 179, 71)


def hexc(h, a=255):
    h = h.lstrip("#")
    if len(h) == 8:
        a = int(h[6:8], 16)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


class Cv:
    """A supersampled RGBA canvas. Coordinates are in final pixels."""

    def __init__(self, w, h, bg=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.im)

    # ---- plain shapes
    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def _go(self, colors, fn):
        """Draw with `fn(draw)`. A colour with alpha < 255 is composited instead of written over what is there."""
        if any(c is not None and len(c) == 4 and c[3] < 255 for c in colors):
            layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
            fn(ImageDraw.Draw(layer))
            self.im.alpha_composite(layer)
            self.d = ImageDraw.Draw(self.im)
        else:
            fn(self.d)

    def poly(self, pts, fill=None, outline=None, width=0):
        def f(d):
            d.polygon(self._p(pts), fill=fill)
            if outline and width:
                d.line(self._p(list(pts) + [pts[0]]), fill=outline, width=int(width * SS), joint="curve")
        self._go([fill, outline], f)

    def ell(self, box, fill=None, outline=None, width=0):
        x0, y0, x1, y1 = box
        self._go([fill, outline], lambda d: d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=fill, outline=outline,
                                                      width=int(width * SS)))

    def rr(self, box, r, fill=None, outline=None, width=0):
        x0, y0, x1, y1 = box
        self._go([fill, outline], lambda d: d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius=r * SS,
                                                               fill=fill, outline=outline, width=int(width * SS)))

    def line(self, pts, fill, width):
        self._go([fill], lambda d: d.line(self._p(pts), fill=fill, width=int(width * SS), joint="curve"))

    def arc(self, box, a0, a1, fill, width):
        x0, y0, x1, y1 = box
        self._go([fill], lambda d: d.arc([x0 * SS, y0 * SS, x1 * SS, y1 * SS], a0, a1, fill=fill, width=int(width * SS)))

    # ---- gradient-filled shape: `draw(maskdraw, S)` paints white where the shape is
    def shape_grad(self, draw, c0, c1, y0, y1, horizontal=False):
        mask = Image.new("L", self.im.size, 0)
        md = ImageDraw.Draw(mask)
        draw(md, SS)
        n = self.im.size[0] if horizontal else self.im.size[1]
        a, b = (y0 * SS, y1 * SS)
        t = np.clip((np.arange(n) - a) / max(1.0, (b - a)), 0, 1)
        col = np.stack([c0[i] + (c1[i] - c0[i]) * t for i in range(4)], axis=-1)
        if horizontal:
            arr = np.broadcast_to(col[None, :, :], (self.im.size[1], n, 4))
        else:
            arr = np.broadcast_to(col[:, None, :], (n, self.im.size[0], 4))
        layer = Image.fromarray(arr.astype(np.uint8), "RGBA")
        alpha = ImageChops.multiply(layer.getchannel("A"), mask)
        layer.putalpha(alpha)
        self.im.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.im)

    def glow(self, cx, cy, r, color, strength=1.0, power=2.0):
        """A soft radial glow composited normally (alpha falls off with distance)."""
        W, H = self.im.size
        yy, xx = np.mgrid[0:H, 0:W]
        dist = np.sqrt((xx - cx * SS) ** 2 + (yy - cy * SS) ** 2) / (r * SS)
        a = np.clip(1.0 - dist, 0, 1) ** power * strength
        arr = np.zeros((H, W, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2] = color[0], color[1], color[2]
        arr[..., 3] = (a * 255 * (color[3] / 255 if len(color) > 3 else 1)).astype(np.uint8)
        self.im.alpha_composite(Image.fromarray(arr, "RGBA"))
        self.d = ImageDraw.Draw(self.im)

    def blur_layer(self, fn, radius):
        main = self.im
        self.im = Image.new("RGBA", main.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        fn()
        layer = self.im.filter(ImageFilter.GaussianBlur(radius * SS))
        self.im = main
        self.im.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.im)

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        img = self.im.resize((self.w, self.h), Image.LANCZOS)
        img.save(os.path.join(OUT, name + ".png"))
        return img


# ---------------------------------------------------------------- backgrounds

def backdrop_far():
    w, h = 720, 1280
    c = Cv(w, h)
    stops = [(0.0, hexc("070b1e")), (0.38, hexc("141f4a")), (0.66, hexc("2c2f63")), (0.86, hexc("5a3a5c")),
             (1.0, hexc("7a4655"))]
    arr = np.zeros((h * SS, w * SS, 4), np.uint8)
    ys = np.linspace(0, 1, h * SS)
    for i in range(3):
        ch = np.interp(ys, [s[0] for s in stops], [s[1][i] for s in stops])
        arr[..., i] = ch[:, None]
    arr[..., 3] = 255
    c.im = Image.fromarray(arr, "RGBA")
    c.d = ImageDraw.Draw(c.im)
    # moon with halo
    c.glow(520, 250, 330, (170, 190, 255, 255), 0.34, 2.2)
    c.glow(520, 250, 140, (230, 238, 255, 255), 0.5, 1.6)
    c.ell((470, 200, 570, 300), fill=hexc("f1f0e6"))
    c.ell((492, 222, 520, 250), fill=hexc("dcd9cc"))
    c.ell((528, 256, 552, 280), fill=hexc("dcd9cc"))
    c.ell((505, 268, 520, 283), fill=hexc("e3e1d4"))
    # mountain ridges, far to near
    rnd = random.Random(7)
    for k, (base, amp, col) in enumerate([(820, 150, "232b5b"), (930, 120, "1a2150"), (1030, 90, "131a40")]):
        pts = [(0, h)]
        x = 0
        while x <= w + 40:
            y = base - amp * (0.35 + 0.65 * abs(math.sin(x / (120 + 40 * k) + k * 1.7))) + rnd.randint(-12, 12)
            pts.append((x, y))
            x += 36
        pts.append((w + 40, h))
        c.poly(pts, fill=hexc(col))
    # a warm horizon haze behind the ridges
    c.glow(360, 1180, 520, (255, 140, 80, 255), 0.22, 2.0)
    return c.save("backdrop_far")


def pine(c, cx, base, height, width, col):
    tiers = 6
    for i in range(tiers):
        t = i / tiers
        y1 = base - height * t
        y0 = y1 - height / tiers * 1.7
        half = width * (1 - t * 0.85) / 2
        c.poly([(cx - half, y1), (cx + half, y1), (cx, y0)], fill=col)
    c.poly([(cx - width * 0.05, base + 30), (cx + width * 0.05, base + 30), (cx + width * 0.05, base - 20),
            (cx - width * 0.05, base - 20)], fill=col)


def backdrop_near():
    w, h = 720, 1280
    c = Cv(w, h)
    dark = hexc("060913")
    mid = hexc("0c1224")
    rnd = random.Random(11)
    # side trees, big at the edges, fading toward the middle
    for side in (-1, 1):
        for i in range(7):
            x = (-10 + i * 36) if side < 0 else (w + 10 - i * 36)
            hgt = rnd.randint(520, 940) - i * 55
            wd = rnd.randint(150, 230) - i * 8
            pine(c, x, h - 80 - rnd.randint(0, 60), hgt, wd, dark if i < 4 else mid)
    # ground
    pts = [(0, h)]
    for x in range(0, w + 20, 20):
        pts.append((x, h - 110 + 22 * math.sin(x / 70.0) + rnd.randint(-5, 5)))
    pts.append((w, h))
    c.poly(pts, fill=dark)
    # grass tufts
    for _ in range(90):
        x = rnd.randint(0, w)
        y = h - 110 + 22 * math.sin(x / 70.0) + 8
        for dx in (-6, 0, 6):
            c.poly([(x + dx - 2, y + 6), (x + dx + 2, y + 6), (x + dx + rnd.randint(-5, 5), y - rnd.randint(20, 46))],
                   fill=dark)
    # a warm rim light on the ground edge from the camp
    c.blur_layer(lambda: c.line([(0, h - 108), (w, h - 108)], (255, 150, 80, 90), 10), 14)
    return c.save("backdrop_near")


def cloud():
    w, h = 1024, 384
    rnd = np.random.default_rng(5)
    base = np.zeros((h, w), np.float32)
    for oct_, amp in ((4, 1.0), (8, 0.5), (16, 0.25), (32, 0.12)):
        n = rnd.random((oct_, oct_ * 3)).astype(np.float32)
        im = Image.fromarray((n * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
        base += np.asarray(im, np.float32) / 255 * amp
    base = (base - base.min()) / (base.max() - base.min())
    yy, xx = np.mgrid[0:h, 0:w]
    fall = np.clip(1 - np.abs((yy - h / 2) / (h / 2)) ** 1.5, 0, 1) * np.clip(1 - np.abs((xx - w / 2) / (w / 2)) ** 3, 0, 1)
    a = np.clip((base - 0.45) * 2.4, 0, 1) * fall
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 150, 165, 215
    arr[..., 3] = (a * 130).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, "cloud.png"))
    return img


def vignette():
    w = h = 256
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = np.clip((d - 0.55) / 0.75, 0, 1) ** 1.6 * 0.82
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 4, 6, 14
    arr[..., 3] = (a * 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    img.save(os.path.join(OUT, "vignette.png"))
    return img


# ---------------------------------------------------------------- logo

def logo():
    w, h = 900, 440
    c = Cv(w, h)
    c.glow(450, 190, 330, (255, 150, 60, 255), 0.5, 2.0)
    # crescent moon + flame emblem
    c.ell((345, 18, 465, 138), fill=hexc("f1ead2"), outline=OUTLINE, width=5)
    c.ell((383, 4, 503, 124), fill=hexc("0e1636"))
    # the flame
    def flame(md, s):
        pts = [(450, 52), (500, 118), (492, 168), (450, 188), (408, 168), (400, 118)]
        md.polygon([(x * s, y * s) for x, y in pts], fill=255)
    c.poly([(450, 40), (506, 116), (498, 172), (450, 194), (402, 172), (394, 116)], fill=OUTLINE)
    c.shape_grad(flame, hexc("ffd75a"), hexc("ef6a22"), 52, 188)
    c.poly([(450, 96), (474, 138), (468, 168), (450, 178), (432, 168), (426, 138)], fill=hexc("fff4c4"))
    # title text on a plank, gold gradient with a dark outline
    font = ImageFont.truetype(FONT, 150 * SS)
    text = "LONG NIGHT"
    mask = Image.new("L", c.im.size, 0)
    md = ImageDraw.Draw(mask)
    tw = md.textlength(text, font=font)
    pos = ((w * SS - tw) / 2, 205 * SS)
    # outline: stroke
    ol = Image.new("L", c.im.size, 0)
    ImageDraw.Draw(ol).text(pos, text, font=font, fill=255, stroke_width=14 * SS // 2, stroke_fill=255)
    shadow = ol.filter(ImageFilter.GaussianBlur(6 * SS))
    sh = Image.new("RGBA", c.im.size, (0, 0, 0, 0))
    sh.putalpha(shadow.point(lambda v: int(v * 0.6)))
    sh2 = Image.new("RGBA", c.im.size, (0, 0, 0, 0))
    sh2.paste((0, 0, 0, 255), (0, 10 * SS), sh.getchannel("A"))
    c.im.alpha_composite(sh2)
    outl = Image.new("RGBA", c.im.size, OUTLINE + (255,))
    outl.putalpha(ol)
    c.im.alpha_composite(outl)
    md.text(pos, text, font=font, fill=255)
    arr_h = c.im.size[1]
    y0, y1 = 205 * SS, 205 * SS + 150 * SS
    t = np.clip((np.arange(arr_h) - y0) / (y1 - y0), 0, 1)
    top, bot = np.array(hexc("fff0b0")), np.array(hexc("f08a2a"))
    col = (top[None, :] + (bot - top)[None, :] * t[:, None]).astype(np.uint8)
    layer = Image.fromarray(np.broadcast_to(col[:, None, :], (arr_h, c.im.size[0], 4)).copy(), "RGBA")
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    c.im.alpha_composite(layer)
    c.d = ImageDraw.Draw(c.im)
    # a lit top edge
    return c.save("logo")


# ---------------------------------------------------------------- moves

MEDAL = {"scavenge": ("7ad06a", "2f7a3c"), "guard": ("63bfee", "2a63a8"), "steal": ("ee6d7a", "8a2a40"),
         "investigate": ("b08aee", "5a3ea6"), "gift": ("ffcf5e", "c0711a")}


def medallion(kind, glyph):
    c = Cv(256, 256)
    hi, lo = MEDAL[kind]
    c.glow(128, 140, 124, (0, 0, 0, 255), 0.5, 1.4)
    c.ell((14, 14, 242, 242), fill=OUTLINE)
    def disc(md, s, r=(22, 22, 234, 234)):
        md.ellipse([r[0] * s, r[1] * s, r[2] * s, r[3] * s], fill=255)
    c.shape_grad(disc, hexc("f6d98a"), hexc("a8691f"), 22, 234)           # gold rim
    def inner(md, s):
        md.ellipse([36 * s, 36 * s, 220 * s, 220 * s], fill=255)
    c.shape_grad(inner, hexc(hi), hexc(lo), 36, 220)
    c.ell((36, 36, 220, 220), outline=hexc("00000055"), width=3)
    c.ell((52, 44, 204, 116), fill=(255, 255, 255, 42))                # gloss
    glyph(c)
    return c.save("move_" + kind)


def g_scavenge(c):
    # basket with an apple and a leaf
    c.poly([(74, 128), (182, 128), (166, 192), (90, 192)], fill=hexc("c98a43"), outline=OUTLINE, width=5)
    for x in (95, 118, 141, 164):
        c.line([(x - 6, 130), (x - 12 + (x - 128) * -0.08, 190)], hexc("8a5a26"), 4)
    for y in (146, 164, 182):
        c.line([(80, y), (176, y)], hexc("8a5a26"), 4)
    c.arc((78, 70, 178, 190), 195, 345, OUTLINE, 9)
    c.arc((82, 74, 174, 186), 195, 345, hexc("e0aa5e"), 5)
    c.ell((92, 100, 132, 140), fill=hexc("e0463f"), outline=OUTLINE, width=5)
    c.ell((100, 106, 112, 118), fill=(255, 255, 255, 120))
    c.ell((124, 108, 160, 142), fill=hexc("f0c24a"), outline=OUTLINE, width=5)
    c.poly([(116, 100), (132, 84), (140, 100)], fill=hexc("4aa24a"), outline=OUTLINE, width=4)


def g_guard(c):
    pts = [(128, 66), (184, 86), (184, 138), (128, 192), (72, 138), (72, 86)]
    c.poly(pts, fill=hexc("e9eef7"), outline=OUTLINE, width=6)
    c.poly([(128, 78), (172, 94), (172, 136), (128, 178), (84, 136), (84, 94)], fill=hexc("3b6fb8"))
    c.poly([(128, 78), (172, 94), (172, 136), (128, 178)], fill=hexc("2f5da0"))
    c.rr((120, 96, 136, 160), 4, fill=hexc("fff4dc"))
    c.rr((100, 112, 156, 128), 4, fill=hexc("fff4dc"))


def g_steal(c):
    # bandit mask
    mask = [(64, 112), (92, 94), (128, 102), (164, 94), (192, 112), (184, 146), (160, 156), (140, 138), (116, 138),
            (96, 156), (72, 146)]
    c.poly(mask, fill=hexc("23152b"), outline=OUTLINE, width=6)
    c.poly([(80, 116), (96, 106), (112, 120), (104, 134), (88, 136)], fill=hexc("fff4dc"))
    c.poly([(176, 116), (160, 106), (144, 120), (152, 134), (168, 136)], fill=hexc("fff4dc"))
    c.ell((92, 118, 104, 130), fill=OUTLINE)
    c.ell((152, 118, 164, 130), fill=OUTLINE)
    c.line([(64, 112), (48, 108)], hexc("23152b"), 8)
    c.line([(192, 112), (208, 108)], hexc("23152b"), 8)
    # coin
    c.ell((108, 160, 148, 200), fill=hexc("ffd45a"), outline=OUTLINE, width=5)
    c.ell((118, 170, 138, 190), outline=hexc("c8921a"), width=4)


def g_investigate(c):
    c.line([(150, 150), (196, 196)], OUTLINE, 24)
    c.line([(150, 150), (196, 196)], hexc("c98a43"), 14)
    c.ell((66, 62, 168, 164), fill=hexc("bfe6ff55"), outline=OUTLINE, width=8)
    c.ell((74, 70, 160, 156), fill=hexc("a8d8f866"), outline=hexc("fff4dc"), width=6)
    c.arc((84, 80, 140, 136), 200, 280, hexc("ffffffcc"), 6)
    c.ell((100, 96, 124, 120), fill=hexc("e0463f55"))


def g_gift(c):
    c.rr((74, 120, 182, 196), 8, fill=hexc("e0463f"), outline=OUTLINE, width=6)
    c.rr((66, 98, 190, 128), 8, fill=hexc("f2605a"), outline=OUTLINE, width=6)
    c.rr((118, 98, 138, 196), 2, fill=hexc("ffe27a"))
    c.poly([(128, 98), (96, 66), (84, 84), (110, 100)], fill=hexc("ffe27a"), outline=OUTLINE, width=5)
    c.poly([(128, 98), (160, 66), (172, 84), (146, 100)], fill=hexc("ffe27a"), outline=OUTLINE, width=5)
    c.ell((118, 92, 138, 112), fill=hexc("ffcf3a"), outline=OUTLINE, width=4)


# ---------------------------------------------------------------- camp

def fx_glow_light(c, cx, cy, r, a):
    c.glow(cx, cy, r, (255, 190, 90, 255), a, 2.0)


def hut(mine):
    c = Cv(256, 256)
    wall0, wall1 = (hexc("b27a46"), hexc("7a4a28")) if mine else (hexc("8c6a50"), hexc("5a4034"))
    roof0, roof1 = (hexc("e1b25c"), hexc("a8742c")) if mine else (hexc("a08a62"), hexc("6e5b3c"))
    c.ell((28, 196, 228, 238), fill=(0, 0, 0, 90))
    # walls
    def wall(md, s):
        md.rectangle([58 * s, 112 * s, 198 * s, 214 * s], fill=255)
    c.shape_grad(wall, wall0, wall1, 112, 214)
    c.rr((58, 112, 198, 214), 2, outline=OUTLINE, width=5)
    for x in (82, 106, 130, 154, 178):
        c.line([(x, 114), (x, 212)], hexc("00000050"), 3)
    # door with warm light
    c.poly([(104, 214), (104, 160), (116, 146), (140, 146), (152, 160), (152, 214)], fill=OUTLINE)
    if mine:
        c.glow(128, 186, 62, (255, 190, 90, 255), 0.95, 1.4)
    c.poly([(110, 214), (110, 162), (119, 152), (137, 152), (146, 162), (146, 214)],
           fill=hexc("ffbe5a") if mine else hexc("3a3050"))
    # window
    c.rr((164, 130, 190, 156), 4, fill=hexc("ffd783") if mine else hexc("2e2a48"), outline=OUTLINE, width=4)
    c.line([(177, 130), (177, 156)], OUTLINE, 3)
    # thatched roof
    def roof(md, s):
        md.polygon([(x * s, y * s) for x, y in [(128, 36), (222, 124), (216, 140), (40, 140), (34, 124)]], fill=255)
    c.poly([(128, 30), (230, 126), (222, 146), (34, 146), (26, 126)], fill=OUTLINE)
    c.shape_grad(roof, roof0, roof1, 36, 140)
    for i, y in enumerate((58, 78, 98, 118)):
        half = (y - 36) * 0.95
        c.line([(128 - half + 8, y), (128 + half - 8, y)], hexc("00000040"), 3)
    for x in range(44, 218, 14):
        c.poly([(x, 138), (x + 12, 138), (x + 6, 150)], fill=roof1)
    if mine:
        c.line([(128, 36), (128, 4)], OUTLINE, 5)
        c.poly([(128, 4), (160, 14), (128, 24)], fill=hexc("ff6a4a"), outline=OUTLINE, width=3)
        # a hanging lantern
        c.line([(196, 146), (196, 160)], OUTLINE, 3)
        c.glow(196, 168, 26, (255, 200, 100, 255), 0.9, 1.5)
        c.rr((190, 160, 202, 178), 3, fill=hexc("ffd45a"), outline=OUTLINE, width=3)
    return c.save("hut_me" if mine else "hut")


def campfire():
    c = Cv(256, 256)
    c.ell((38, 188, 218, 236), fill=(0, 0, 0, 100))
    for ang in range(0, 360, 32):
        x = 128 + math.cos(math.radians(ang)) * 74
        y = 208 + math.sin(math.radians(ang)) * 22
        c.ell((x - 14, y - 10, x + 14, y + 10), fill=hexc("7c8296"), outline=OUTLINE, width=4)
    for sx, rot in ((-1, 24), (1, -24)):
        x0, y0, x1, y1 = 128 - sx * 62, 208, 128 + sx * 62, 178
        c.line([(x0, y0), (x1, y1)], OUTLINE, 24)
        c.line([(x0, y0), (x1, y1)], hexc("8a5a30"), 15)
        c.line([(x0 + 6, y0 - 4), (x1 - 6, y1 + 4)], hexc("a8743d"), 4)
    def f(md, s, pts):
        md.polygon([(x * s, y * s) for x, y in pts], fill=255)
    outer = [(128, 40), (160, 100), (176, 150), (162, 190), (128, 204), (94, 190), (80, 150), (96, 100)]
    c.poly(outer, fill=OUTLINE)
    c.shape_grad(lambda md, s: f(md, s, outer), hexc("ffc03a"), hexc("e8421e"), 40, 204)
    mid = [(132, 86), (156, 130), (160, 166), (138, 192), (110, 190), (100, 160), (114, 126)]
    c.shape_grad(lambda md, s: f(md, s, mid), hexc("fff0a0"), hexc("ffa62e"), 86, 192)
    core = [(130, 130), (146, 160), (138, 186), (118, 186), (112, 164)]
    c.poly(core, fill=hexc("fffbe0"))
    return c.save("campfire")


def campfire_glow():
    c = Cv(512, 512)
    c.glow(256, 256, 250, (255, 170, 70, 255), 0.95, 2.2)
    c.glow(256, 256, 110, (255, 220, 140, 255), 0.55, 1.6)
    return c.save("campfire_glow")


# ---------------------------------------------------------------- avatars

SKINS = ["f1c9a0", "d89a6a", "8d5a3a", "f6d8b8", "b9794c", "e8b88a", "6b4028", "f0bf94"]
BGS = [("3f7fd0", "20407a"), ("d0743f", "7a3a20"), ("5fae5a", "2c6a30"), ("a56ad0", "5a2f80"), ("d05f7a", "7a2840"),
       ("d0b43f", "7a6420"), ("3fb0b0", "20686a"), ("8890a8", "40485e")]


def avatar(i):
    c = Cv(128, 128)
    b0, b1 = BGS[i]
    c.ell((2, 2, 126, 126), fill=OUTLINE)
    def disc(md, s):
        md.ellipse([8 * s, 8 * s, 120 * s, 120 * s], fill=255)
    c.shape_grad(disc, hexc(b0), hexc(b1), 8, 120)
    skin = hexc(SKINS[i])
    cloth = [hexc(x) for x in ("2f3f6a", "6a2f3a", "3a5a3a", "5a4a2a", "2f5a6a", "6a3a5a", "4a4a5a", "7a5a2a")][i]
    # shoulders (clipped to the disc below)
    layer = Cv(128, 128)
    layer.ell((14, 84, 114, 170), fill=cloth, outline=OUTLINE, width=4)
    layer.rr((52, 78, 76, 102), 6, fill=skin, outline=OUTLINE, width=3)
    # head
    layer.ell((34, 28, 94, 96), fill=skin, outline=OUTLINE, width=4)
    hair = [hexc(x) for x in ("2a1a10", "d0a040", "7a2a1a", "1a1a24", "e0e0e0", "5a3a20", "2a1a10", "9a4a1a")][i]
    style = i % 8
    if style == 0:      # short crop
        layer.poly([(32, 58), (36, 34), (50, 24), (78, 24), (92, 34), (96, 58), (88, 44), (64, 38), (42, 46)], fill=hair, outline=OUTLINE, width=3)
    elif style == 1:    # long hair
        layer.rr((26, 26, 102, 100), 22, fill=hair, outline=OUTLINE, width=3)
        layer.ell((34, 34, 94, 96), fill=skin, outline=OUTLINE, width=3)
        layer.poly([(34, 52), (50, 38), (78, 38), (94, 52), (80, 46), (48, 46)], fill=hair)
    elif style == 2:    # beanie
        layer.ell((30, 22, 98, 64), fill=hexc("d0463f"), outline=OUTLINE, width=3)
        layer.rr((30, 50, 98, 64), 5, fill=hexc("f0e4c8"), outline=OUTLINE, width=3)
        layer.ell((56, 14, 72, 28), fill=hexc("f0e4c8"), outline=OUTLINE, width=3)
    elif style == 3:    # mohawk
        layer.poly([(56, 30), (60, 8), (68, 8), (72, 30)], fill=hair, outline=OUTLINE, width=3)
        layer.poly([(34, 52), (44, 42), (84, 42), (94, 52), (80, 38), (48, 38)], fill=hair)
    elif style == 4:    # white hair + beard
        layer.poly([(32, 56), (36, 32), (50, 22), (78, 22), (92, 32), (96, 56), (88, 40), (64, 34), (42, 42)], fill=hair, outline=OUTLINE, width=3)
        layer.poly([(36, 66), (92, 66), (86, 98), (64, 106), (42, 98)], fill=hair, outline=OUTLINE, width=3)
    elif style == 5:    # bun
        layer.ell((54, 10, 78, 34), fill=hair, outline=OUTLINE, width=3)
        layer.poly([(32, 58), (36, 34), (50, 26), (78, 26), (92, 34), (96, 58), (88, 44), (64, 38), (42, 46)], fill=hair, outline=OUTLINE, width=3)
    elif style == 6:    # cap
        layer.poly([(32, 52), (36, 30), (50, 20), (78, 20), (92, 30), (96, 52)], fill=hexc("2f7fc0"), outline=OUTLINE, width=3)
        layer.poly([(34, 50), (96, 50), (110, 58), (34, 58)], fill=hexc("1f5a90"), outline=OUTLINE, width=3)
    else:               # headband
        layer.poly([(32, 56), (36, 32), (50, 22), (78, 22), (92, 32), (96, 56), (88, 42), (64, 36), (42, 44)], fill=hair, outline=OUTLINE, width=3)
        layer.rr((32, 44, 96, 54), 4, fill=hexc("e0463f"), outline=OUTLINE, width=3)
    # face
    layer.ell((48, 62, 56, 72), fill=OUTLINE)
    layer.ell((72, 62, 80, 72), fill=OUTLINE)
    layer.ell((50, 63, 53, 66), fill=(255, 255, 255, 220))
    layer.ell((74, 63, 77, 66), fill=(255, 255, 255, 220))
    layer.arc((54, 70, 74, 88), 20, 160, OUTLINE, 3)
    layer.ell((40, 74, 52, 82), fill=(255, 110, 110, 60))
    layer.ell((76, 74, 88, 82), fill=(255, 110, 110, 60))
    # clip the figure to the disc
    mask = Image.new("L", layer.im.size, 0)
    ImageDraw.Draw(mask).ellipse([8 * SS, 8 * SS, 120 * SS, 120 * SS], fill=255)
    fig = layer.im.copy()
    fig.putalpha(ImageChops.multiply(fig.getchannel("A"), mask))
    c.im.alpha_composite(fig)
    c.d = ImageDraw.Draw(c.im)
    c.ell((8, 8, 120, 120), outline=hexc("ffe9b0"), width=4)
    c.ell((2, 2, 126, 126), outline=OUTLINE, width=3)
    return c.save("avatar_%d" % i)


# ---------------------------------------------------------------- fx

def fx_spark():
    c = Cv(64, 64)
    c.glow(32, 32, 30, (255, 220, 140, 255), 0.55, 2.0)
    c.poly([(32, 2), (37, 27), (62, 32), (37, 37), (32, 62), (27, 37), (2, 32), (27, 27)], fill=hexc("fff6d0"))
    c.ell((26, 26, 38, 38), fill=(255, 255, 255, 255))
    return c.save("fx_spark")


def fx_crumb():
    c = Cv(32, 32)
    c.glow(16, 16, 15, (255, 200, 90, 255), 0.4, 1.6)
    c.poly([(8, 12), (16, 6), (24, 11), (25, 20), (17, 25), (9, 21)], fill=hexc("f2c14e"), outline=OUTLINE, width=1.4)
    c.ell((12, 11, 17, 16), fill=hexc("ffe9a0"))
    return c.save("fx_crumb")


def fx_ring():
    c = Cv(256, 256)
    c.blur_layer(lambda: c.ell((22, 22, 234, 234), outline=(255, 255, 255, 255), width=14), 8)
    c.ell((26, 26, 230, 230), outline=(255, 255, 255, 255), width=8)
    return c.save("fx_ring")


def fx_shield():
    c = Cv(256, 256)
    c.glow(128, 128, 126, (120, 220, 255, 255), 0.55, 1.2)
    c.ell((16, 16, 240, 240), fill=(120, 215, 255, 70), outline=(190, 240, 255, 230), width=8)
    c.ell((40, 36, 140, 100), fill=(255, 255, 255, 80))
    c.arc((30, 30, 226, 226), 200, 250, (255, 255, 255, 220), 8)
    return c.save("fx_shield")


# ---------------------------------------------------------------- ui chrome

def card_frame():
    w = h = 96
    c = Cv(w, h)
    def body(md, s):
        md.rounded_rectangle([3 * s, 3 * s, 93 * s, 93 * s], radius=20 * s, fill=255)
    c.shape_grad(body, hexc("23325e", 242), hexc("111b38", 246), 3, 93)
    c.rr((3, 3, 93, 93), 20, outline=hexc("0a0f1c"), width=4)
    c.rr((6, 6, 90, 90), 17, outline=hexc("e0a24a"), width=3)
    c.rr((10, 10, 86, 86), 13, outline=hexc("e0a24a", 70), width=1.5)
    for (x, y) in ((16, 16), (80, 16), (16, 80), (80, 80)):
        c.ell((x - 3.4, y - 3.4, x + 3.4, y + 3.4), fill=hexc("ffd783"), outline=OUTLINE, width=1.2)
    return c.save("card_frame")


def button_wood(pressed):
    w, h = 144, 112
    c = Cv(w, h)
    lip = 4 if pressed else 12
    top = 8 if pressed else 2
    base0, base1 = (hexc("a8693a"), hexc("7d4a26")) if pressed else (hexc("d49458"), hexc("a8673a"))
    # lip (the dark underside)
    c.rr((3, top + 10, w - 3, h - 3), 26, fill=hexc("5d3519"), outline=OUTLINE, width=4)
    bot = h - 3 - lip
    def plank(md, s):
        md.rounded_rectangle([3 * s, (top + 3) * s, (w - 3) * s, bot * s], radius=26 * s, fill=255)
    c.shape_grad(plank, base0, base1, top + 3, bot)
    c.rr((3, top + 3, w - 3, bot), 26, outline=OUTLINE, width=4)
    # grain
    rnd = random.Random(3)
    for k in range(5):
        y = top + 16 + k * (bot - top - 30) / 4
        pts = [(18 + t * 6, y + 2.2 * math.sin(t / 2.4 + k) + rnd.uniform(-0.4, 0.4)) for t in range(int((w - 36) / 6) + 1)]
        c.line(pts, (60, 30, 12, 70), 2.2)
    # highlight and nails
    c.line([(26, top + 9), (w - 26, top + 9)], hexc("f6c98a", 150 if not pressed else 80), 3)
    for x in (18, w - 18):
        c.ell((x - 4, (top + bot) / 2 - 4, x + 4, (top + bot) / 2 + 4), fill=hexc("3a2010"))
        c.ell((x - 2.4, (top + bot) / 2 - 3, x + 1.6, (top + bot) / 2 + 1), fill=hexc("b0a090"))
    return c.save("button_wood_pressed" if pressed else "button_wood")


def lantern(on):
    c = Cv(64, 80)
    if on:
        c.glow(32, 46, 34, (255, 190, 80, 255), 0.85, 1.4)
    c.line([(32, 4), (32, 14)], OUTLINE, 4)
    c.arc((20, 6, 44, 24), 180, 360, OUTLINE, 4)
    c.rr((18, 14, 46, 22), 3, fill=hexc("5a4a3a"), outline=OUTLINE, width=3)
    c.poly([(18, 24), (46, 24), (50, 58), (14, 58)], fill=hexc("ffd45a") if on else hexc("39425e"), outline=OUTLINE, width=3.5)
    if on:
        c.poly([(32, 28), (40, 44), (32, 54), (24, 44)], fill=hexc("fff6c0"))
    else:
        c.line([(32, 28), (32, 54)], hexc("56627f"), 2.5)
    c.rr((12, 56, 52, 66), 4, fill=hexc("5a4a3a"), outline=OUTLINE, width=3)
    return c.save("lantern_on" if on else "lantern_off")


def crown():
    c = Cv(96, 72)
    c.poly([(8, 60), (8, 22), (28, 40), (48, 10), (68, 40), (88, 22), (88, 60)], fill=hexc("ffcf3a"), outline=OUTLINE, width=4)
    c.rr((8, 52, 88, 64), 3, fill=hexc("e0a21a"), outline=OUTLINE, width=3)
    for x, col in ((28, "e0463f"), (48, "4aa8e8"), (68, "e0463f")):
        c.ell((x - 5, 44, x + 5, 54), fill=hexc(col), outline=OUTLINE, width=2)
    for x, y in ((8, 22), (48, 10), (88, 22)):
        c.ell((x - 5, y - 5, x + 5, y + 5), fill=hexc("fff4c0"), outline=OUTLINE, width=2.5)
    return c.save("crown")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="")
    args = ap.parse_args()
    imgs = {}
    imgs["backdrop_far"] = backdrop_far()
    imgs["backdrop_near"] = backdrop_near()
    imgs["cloud"] = cloud()
    imgs["vignette"] = vignette()
    imgs["logo"] = logo()
    for kind, g in (("scavenge", g_scavenge), ("guard", g_guard), ("steal", g_steal), ("investigate", g_investigate),
                    ("gift", g_gift)):
        imgs["move_" + kind] = medallion(kind, g)
    imgs["hut"] = hut(False)
    imgs["hut_me"] = hut(True)
    imgs["campfire"] = campfire()
    imgs["campfire_glow"] = campfire_glow()
    for i in range(8):
        imgs["avatar_%d" % i] = avatar(i)
    imgs["fx_spark"] = fx_spark()
    imgs["fx_crumb"] = fx_crumb()
    imgs["fx_ring"] = fx_ring()
    imgs["fx_shield"] = fx_shield()
    imgs["card_frame"] = card_frame()
    imgs["button_wood"] = button_wood(False)
    imgs["button_wood_pressed"] = button_wood(True)
    imgs["lantern_on"] = lantern(True)
    imgs["lantern_off"] = lantern(False)
    imgs["crown"] = crown()
    print("%d stand-ins written to %s" % (len(imgs), OUT))
    if args.sheet:
        small = [(k, v) for k, v in imgs.items() if k not in ("backdrop_far", "backdrop_near", "cloud", "vignette", "campfire_glow")]
        cols = 6
        cell = 200
        rows = (len(small) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * cell, rows * cell), (40, 50, 80, 255))
        for n, (k, v) in enumerate(small):
            v2 = v.copy()
            v2.thumbnail((cell - 12, cell - 28))
            x, y = (n % cols) * cell + 6, (n // cols) * cell + 6
            sheet.alpha_composite(v2, (x + (cell - 12 - v2.width) // 2, y))
            ImageDraw.Draw(sheet).text((x, y + cell - 24), k, fill=(255, 255, 255, 255))
        sheet.save(args.sheet)


if __name__ == "__main__":
    main()
