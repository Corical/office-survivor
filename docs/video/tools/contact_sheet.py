"""Contact sheet of every exported PNG in a folder, each scaled into a labelled tile, for a quick visual check.

    python tools/contact_sheet.py output/01_assets work/contact_assets.png
"""
import os
import sys

from PIL import Image, ImageDraw

src, dst = sys.argv[1], sys.argv[2]
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
cols, tile, label_h = 6, 300, 26
rows = -(-len(files) // cols)
sheet = Image.new("RGB", (cols * tile, rows * (tile + label_h)), "#1F3B6E")
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(src, f)).convert("RGBA")
    im.thumbnail((tile - 16, tile - 16))
    x, y = (i % cols) * tile, (i // cols) * (tile + label_h)
    draw.rectangle([x + 4, y + 4, x + tile - 4, y + tile - 4], fill="#14213D")
    sheet.paste(im, (x + (tile - im.width) // 2, y + (tile - im.height) // 2), im)
    draw.text((x + 8, y + tile + 4), f[:-4], fill="#F4F1E8")
os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
sheet.save(dst)
print(dst, sheet.size)
