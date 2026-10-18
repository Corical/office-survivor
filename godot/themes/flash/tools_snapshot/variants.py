"""Make greyscale and "sunlight glare" copies of screenshots, to judge the two conditions the brief names.

    python variants.py <src dir with drive shots> <dest dir>

Greyscale: ITU-R 601 luma, no colour left. Glare: the picture lifted 38 percent toward white and contrast cut to 70
percent, which is what a screen looks like with the sun on it (a rough stand-in, not a measurement of any phone).
"""
import os
import shutil
import sys

from PIL import Image, ImageEnhance

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for name in sorted(os.listdir(src)):
    if not name.endswith(".png"):
        continue
    shutil.copyfile(os.path.join(src, name), os.path.join(dst, "drive_" + name))
for name in ["round_10_picked.png", "reveal_05.png", "20_end.png"]:
    img = Image.open(os.path.join(src, name)).convert("RGB")
    stem = name[:-4]
    img.convert("L").save(os.path.join(dst, "grey_%s.png" % stem))
    lifted = Image.blend(ImageEnhance.Contrast(img).enhance(0.7), Image.new("RGB", img.size, (255, 255, 255)), 0.38)
    lifted.save(os.path.join(dst, "glare_%s.png" % stem))
print("done", dst)
