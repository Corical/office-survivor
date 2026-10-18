"""Composite transparent PNGs over a background so dark art is visible. usage: python preview.py out.png bg|checker|#hex name [name...]"""
import os
import sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)


def load(name):
    return Image.open(os.path.join(ART, name + ".png")).convert("RGBA")


def main():
    out, bg = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    imgs = [load(n) for n in names]
    h = max(i.height for i in imgs)
    gap = 12
    w = sum(i.width for i in imgs) + gap * (len(imgs) + 1)
    if bg == "far":
        base = load("backdrop_far").resize((w, h + 2 * gap), Image.LANCZOS) if False else None
    sheet = Image.new("RGBA", (w, h + 2 * gap), (0, 0, 0, 255))
    x = gap
    for im in imgs:
        if bg == "far":
            back = load("backdrop_far").resize(im.size, Image.LANCZOS)
        elif bg == "checker":
            back = Image.new("RGBA", im.size, (40, 46, 64, 255))
            px = back.load()
            for yy in range(im.height):
                for xx in range(im.width):
                    if ((xx // 16) + (yy // 16)) % 2:
                        px[xx, yy] = (62, 70, 94, 255)
        else:
            c = bg.lstrip("#")
            back = Image.new("RGBA", im.size, tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
        back.alpha_composite(im)
        sheet.paste(back, (x, gap))
        x += im.width + gap
    sheet.convert("RGB").save(out)
    print(out, sheet.size)


main()
