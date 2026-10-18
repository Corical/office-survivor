"""Shared helpers for the flash theme art generators. Pure Python, no third-party art, no fonts.

Every asset is a hand-built layered SVG. Light model used everywhere:
  - key light: the moon, upper left, cool blue-white  (rim light on edges that face up-left)
  - fill light: the camp fire, warm amber, from the middle of the camp (warm light on edges that face the fire)
"""
import math
import random

SIZE_LIMIT = 16 * 1024 * 1024


def f(x):
    s = f"{x:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def pts(points):
    return " ".join(f"{f(x)},{f(y)}" for x, y in points)


class Svg:
    def __init__(self, w, h, name=""):
        self.w, self.h, self.name = w, h, name
        self.defs, self.body = [], []
        self._n = 0
        self._blurs = {}

    # ---- ids / defs
    def uid(self, p="g"):
        self._n += 1
        return f"{p}{self._n}"

    def _stops(self, stops):
        out = []
        for s in stops:
            off, col = s[0], s[1]
            op = s[2] if len(s) > 2 else 1
            out.append(f'<stop offset="{f(off)}" stop-color="{col}" stop-opacity="{f(op)}"/>')
        return "".join(out)

    def lin(self, stops, x1=0, y1=0, x2=0, y2=1, user=False):
        i = self.uid("lg")
        u = "userSpaceOnUse" if user else "objectBoundingBox"
        self.defs.append(
            f'<linearGradient id="{i}" gradientUnits="{u}" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}">{self._stops(stops)}</linearGradient>')
        return f"url(#{i})"

    def rad(self, stops, cx=0.5, cy=0.5, r=0.5, user=False, fx=None, fy=None):
        i = self.uid("rg")
        u = "userSpaceOnUse" if user else "objectBoundingBox"
        extra = ""
        if fx is not None:
            extra = f' fx="{f(fx)}" fy="{f(fy if fy is not None else cy)}"'
        self.defs.append(
            f'<radialGradient id="{i}" gradientUnits="{u}" cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"{extra}>{self._stops(stops)}</radialGradient>')
        return f"url(#{i})"

    def blur(self, sd):
        key = round(sd, 2)
        if key not in self._blurs:
            i = self.uid("bl")
            self._blurs[key] = i
            self.defs.append(
                f'<filter id="{i}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="{f(sd)}"/></filter>')
        return f"url(#{self._blurs[key]})"

    def clip(self, inner):
        i = self.uid("cp")
        self.defs.append(f'<clipPath id="{i}">{inner}</clipPath>')
        return f"url(#{i})"

    def mask(self, inner):
        i = self.uid("mk")
        self.defs.append(f'<mask id="{i}">{inner}</mask>')
        return f"url(#{i})"

    def pattern(self, w, h, inner):
        i = self.uid("pt")
        self.defs.append(f'<pattern id="{i}" patternUnits="userSpaceOnUse" width="{f(w)}" height="{f(h)}">{inner}</pattern>')
        return f"url(#{i})"

    def speckle(self, w=64, h=64, n=60, colors=("#ffffff",), amax=0.25, rmin=0.4, rmax=1.1, seed=1):
        """A tile of tiny random dots: stands in for noise grain (feTurbulence is not supported)."""
        rnd = random.Random(seed)
        parts = []
        for _ in range(n):
            x, y = rnd.uniform(0, w), rnd.uniform(0, h)
            r = rnd.uniform(rmin, rmax)
            c = rnd.choice(colors)
            a = rnd.uniform(amax * 0.3, amax)
            parts.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="{c}" fill-opacity="{f(a)}"/>')
        return self.pattern(w, h, "".join(parts))

    # ---- body
    def add(self, s):
        self.body.append(s)

    def open_g(self, attrs=""):
        self.body.append(f"<g {attrs}>")

    def close_g(self):
        self.body.append("</g>")

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                f'<title>{self.name}</title><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>')

    def save(self, path):
        data = self.render()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)
        return len(data)


# ---------------------------------------------------------------- shapes (return markup)
def circle(cx, cy, r, fill="#fff", extra=""):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}" {extra}/>'


def ellipse(cx, cy, rx, ry, fill="#fff", extra=""):
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="{fill}" {extra}/>'


def rect(x, y, w, h, fill="#fff", rx=0, extra=""):
    if isinstance(rx, str):
        rx, extra = 0, rx
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{f(rx)}" fill="{fill}" {extra}/>'


def path(d, fill="#fff", extra=""):
    return f'<path d="{d}" fill="{fill}" {extra}/>'


def stroke(d, color, w, extra="", cap="round"):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{f(w)}" stroke-linecap="{cap}" stroke-linejoin="round" {extra}/>'


def poly(points, fill="#fff", extra=""):
    return f'<polygon points="{pts(points)}" fill="{fill}" {extra}/>'


def group(inner, attrs=""):
    return f"<g {attrs}>{inner}</g>"


def shifted(markup_fn, dx, dy):
    """Wrap a drawing function's output in a translate (used for rim light: a lighter copy under a dark copy)."""
    return f'<g transform="translate({f(dx)} {f(dy)})">{markup_fn}</g>'


# ---------------------------------------------------------------- curves
def smooth(points, closed=True, tension=0.5):
    """Catmull-Rom through points -> cubic bezier path data."""
    n = len(points)
    if n < 3:
        return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in points)
    d = f"M{f(points[0][0])} {f(points[0][1])}"
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = points[(i - 1) % n] if (closed or i > 0) else points[i]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n] if (closed or i + 2 < n) else points[(i + 1) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3 * 2 / 2 * 1.0, p1[1] + (p2[1] - p0[1]) * tension / 3 * 2 / 2 * 1.0)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3 * 2 / 2 * 1.0, p2[1] - (p3[1] - p1[1]) * tension / 3 * 2 / 2 * 1.0)
        d += f" C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p2[0])} {f(p2[1])}"
    return d + (" Z" if closed else "")


def blob(cx, cy, r, rnd, n=9, jitter=0.18, squash=1.0):
    ps = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1 + rnd.uniform(-jitter, jitter))
        ps.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * squash))
    return smooth(ps)


def rrect_d(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    return (f"M{f(x + r)} {f(y)} H{f(x + w - r)} Q{f(x + w)} {f(y)} {f(x + w)} {f(y + r)} V{f(y + h - r)} "
            f"Q{f(x + w)} {f(y + h)} {f(x + w - r)} {f(y + h)} H{f(x + r)} Q{f(x)} {f(y + h)} {f(x)} {f(y + h - r)} "
            f"V{f(y + r)} Q{f(x)} {f(y)} {f(x + r)} {f(y)} Z")


def star4(cx, cy, r, ratio=0.18):
    k = r * ratio
    return (f"M{f(cx)} {f(cy - r)} Q{f(cx + k)} {f(cy - k)} {f(cx + r)} {f(cy)} Q{f(cx + k)} {f(cy + k)} {f(cx)} {f(cy + r)} "
            f"Q{f(cx - k)} {f(cy + k)} {f(cx - r)} {f(cy)} Q{f(cx - k)} {f(cy - k)} {f(cx)} {f(cy - r)} Z")


def flame_d(cx, by, w, h, lean=0.0):
    """A flame teardrop, base centre (cx, by), width w, height h, tip leaning by lean*w."""
    tx = cx + lean * w
    ty = by - h
    return (f"M{f(cx)} {f(by)} C{f(cx - w)} {f(by - h * 0.12)} {f(cx - w * 0.85)} {f(by - h * 0.55)} {f(tx)} {f(ty)} "
            f"C{f(cx + w * 0.55)} {f(by - h * 0.55)} {f(cx + w)} {f(by - h * 0.15)} {f(cx)} {f(by)} Z")


def frond(x, y, ang, length, droop, leaflet=None, n=15, fat=0.95, lift=0.12, wbase=None):
    """A palm frond. Returns (leaflets_path_d, rib_path_d). ang in degrees (0 = right, -90 = up).
    Leaflet bases overlap along the rib (fat * spacing), so they merge into one solid serrated blade."""
    a = math.radians(ang)
    lm = leaflet if leaflet is not None else length * 0.34
    p0 = (x, y)
    p1 = (x + math.cos(a) * length * 0.6, y + math.sin(a) * length * 0.6 - length * lift)
    p2 = (x + math.cos(a) * length, y + math.sin(a) * length + droop)

    def B(t):
        u = 1 - t
        return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])

    def T(t):
        u = 1 - t
        dx = 2 * u * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
        dy = 2 * u * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
        m = math.hypot(dx, dy) or 1
        return dx / m, dy / m

    d = ""
    for i in range(1, n + 1):
        t = i / (n + 0.6)
        px, py = B(t)
        tx, ty = T(t)
        l = lm * (0.30 + 0.70 * math.sin(math.pi * min(1, t * 1.05 + 0.04))) * (1 - 0.40 * t)
        for side in (-1, 1):
            spread = math.radians(62 - 22 * t) * side
            ca, sa = math.cos(spread), math.sin(spread)
            dx, dy = tx * ca - ty * sa, tx * sa + ty * ca
            dy += 0.42  # gravity
            m = math.hypot(dx, dy)
            dx, dy = dx / m, dy / m
            qx, qy = px + dx * l, py + dy * l
            hw = (length / n) * fat * 0.5 * (1.0 if wbase is None else wbase / 1.3)
            ax_, ay_ = px + tx * hw * 1.1, py + ty * hw * 1.1
            bx_, by_ = px - tx * hw * 0.9, py - ty * hw * 0.9
            c1 = ((ax_ + qx) / 2, (ay_ + qy) / 2 + l * 0.10)
            c2 = ((bx_ + qx) / 2, (by_ + qy) / 2 + l * 0.10)
            d += (f"M{f(ax_)} {f(ay_)} Q{f(c1[0])} {f(c1[1])} {f(qx)} {f(qy)} Q{f(c2[0])} {f(c2[1])} {f(bx_)} {f(by_)} Z ")
    rib = f"M{f(p0[0])} {f(p0[1])} Q{f(p1[0])} {f(p1[1])} {f(p2[0])} {f(p2[1])}"
    return d, rib


def palm(svg, x, y, h, lean, fill, rim=None, fronds=7, scale=1.0, rim_shift=(-1.2, -1.4), seed=3, trunk_w=None):
    """A palm tree from base (x, y) of trunk height h leaning by `lean` px at the top. Returns markup string."""
    rnd = random.Random(seed)
    tw = trunk_w if trunk_w is not None else max(2.0, h * 0.045)
    topx, topy = x + lean, y - h
    midx, midy = x + lean * 0.25, y - h * 0.5
    trunk = (f"M{f(x - tw)} {f(y)} Q{f(midx - tw * 0.8)} {f(midy)} {f(topx - tw * 0.5)} {f(topy)} "
             f"L{f(topx + tw * 0.5)} {f(topy)} Q{f(midx + tw * 0.8)} {f(midy)} {f(x + tw)} {f(y)} Z")
    leaf_d = ""
    ribs = ""
    angs = [-165, -135, -105, -75, -45, -15, -90, -120, -60][:fronds]
    for a in angs:
        L = h * rnd.uniform(0.55, 0.78) * scale
        d, rib = frond(topx, topy, a + rnd.uniform(-8, 8), L, droop=L * rnd.uniform(0.3, 0.55), n=max(7, int(L / 4.5)), fat=1.1)
        leaf_d += d
        ribs += rib + " "
    parts = []
    all_d = trunk + " " + leaf_d
    if rim:
        parts.append(f'<g transform="translate({f(rim_shift[0])} {f(rim_shift[1])})"><path d="{all_d}" fill="{rim}"/></g>')
    parts.append(f'<path d="{all_d}" fill="{fill}"/>')
    parts.append(circle(topx, topy + h * 0.01, tw * 1.6, fill))
    return "".join(parts)


def lerp(a, b, t):
    return a + (b - a) * t


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def mix(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex([lerp(a[i], b[i], t) for i in range(3)])


def lighten(c, t):
    return mix(c, "#ffffff", t)


def darken(c, t):
    return mix(c, "#000000", t)
