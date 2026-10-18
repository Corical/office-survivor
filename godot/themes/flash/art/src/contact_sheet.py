"""Build contact_sheet.png (everything on the dark backdrop, flow layout) and check each PNG is exactly 2x its nominal size."""
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)

NOMINAL = {
    "backdrop_far": (540, 960), "backdrop_near": (540, 960), "logo": (480, 220),
    "move_scavenge": (192, 192), "move_guard": (192, 192), "move_steal": (192, 192), "move_investigate": (192, 192), "move_gift": (192, 192),
    "hut": (192, 192), "hut_me": (192, 192), "campfire": (256, 256), "campfire_glow": (512, 512),
    **{f"avatar_{i}": (128, 128) for i in range(8)},
    "fx_spark": (32, 32), "fx_crumb": (32, 32), "fx_ring": (128, 128), "fx_shield": (192, 192),
    "card_frame": (128, 128), "button_wood": (256, 96), "button_wood_pressed": (256, 96),
}
INK = (226, 234, 250, 255)


def load(n):
    return Image.open(os.path.join(ART, n + ".png")).convert("RGBA")


def nine(img, margin, size):
    w, h = img.size
    m = margin * 2
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    tw, th = size
    xs_s = [0, m, w - m, w]; ys_s = [0, m, h - m, h]
    xs_d = [0, m, tw - m, tw]; ys_d = [0, m, th - m, th]
    for i in range(3):
        for j in range(3):
            p = img.crop((xs_s[i], ys_s[j], xs_s[i + 1], ys_s[j + 1]))
            p = p.resize((max(1, xs_d[i + 1] - xs_d[i]), max(1, ys_d[j + 1] - ys_d[j])), Image.LANCZOS)
            out.alpha_composite(p, (xs_d[i], ys_d[j]))
    return out


def main():
    bad = [(n, Image.open(os.path.join(ART, n + ".png")).size, (w * 2, h * 2)) for n, (w, h) in NOMINAL.items()
           if Image.open(os.path.join(ART, n + ".png")).size != (w * 2, h * 2)]
    print("size mismatches:", bad or "none")

    W = 2000
    items = []  # (image, label, gap_after)

    def add(img, label):
        items.append((img, label))

    def scaled(n, k):
        im = load(n)
        return im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)

    far, near = load("backdrop_far"), load("backdrop_near")
    comp = far.copy(); comp.alpha_composite(near)
    k = 0.42
    sz = (int(far.width * k), int(far.height * k))
    add(far.resize(sz, Image.LANCZOS), "backdrop_far 540x960")
    add(comp.resize(sz, Image.LANCZOS), "backdrop_near over far 540x960")
    add(scaled("logo", 0.62), "logo 480x220")
    for n in ("move_scavenge", "move_guard", "move_steal", "move_investigate", "move_gift"):
        add(scaled(n, 0.7), f"{n} 192x192")
    add(scaled("hut", 0.85), "hut 192x192")
    add(scaled("hut_me", 0.85), "hut_me 192x192")
    add(scaled("campfire", 0.8), "campfire 256x256")
    add(scaled("campfire_glow", 0.45), "campfire_glow 512x512 (soft glow)")
    for i in range(8):
        add(scaled(f"avatar_{i}", 0.8), f"avatar_{i} 128x128")
    add(scaled("fx_shield", 0.7), "fx_shield 192x192")
    add(scaled("fx_ring", 0.9), "fx_ring 128x128")
    pad = Image.new("RGBA", (170, 70), (0, 0, 0, 255))
    pad.alpha_composite(load("fx_spark"), (14, 3)); pad.alpha_composite(load("fx_crumb"), (92, 3))
    add(pad, "fx_spark / fx_crumb 32x32 (on black)")
    add(scaled("card_frame", 0.9), "card_frame 128x128")
    add(nine(load("card_frame"), 40, (340, 190)), "card_frame 9-sliced, margin 40 (at 2x px)")
    add(scaled("button_wood", 0.9), "button_wood 256x96")
    add(scaled("button_wood_pressed", 0.9), "button_wood_pressed 256x96")
    add(nine(load("button_wood"), 36, (520, 150)), "button_wood 9-sliced, margin 36")

    # layout
    gap, label_h = 26, 30
    rows, row, x, rh = [], [], 24, 0
    for img, label in items:
        w = max(img.width, 190)
        if x + w > W - 24 and row:
            rows.append((row, rh)); row, x, rh = [], 24, 0
        row.append((x, img, label)); x += w + gap; rh = max(rh, img.height)
    rows.append((row, rh))
    H = 24 + sum(r[1] + label_h + gap for r in rows)

    bg = far.crop((0, 600, 540, 960)).resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    sheet = bg.convert("RGBA")
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    y = 24
    for row, rh in rows:
        for x, img, label in row:
            sheet.alpha_composite(img, (x, y + (rh - img.height)))
            d.text((x, y + rh + 4), label, fill=INK, font=font)
        y += rh + label_h + gap
    sheet.convert("RGB").save(os.path.join(ART, "contact_sheet.png"))
    print("saved", sheet.size)


main()
