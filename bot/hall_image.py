"""The Hall of Fame as a picture: award cards with their titles, then one row per person with totals, the top of
each column highlighted. Same look as the reveal (bot/reveal_image.py). Pure: data in, PNG bytes out."""
import io

from PIL import Image, ImageDraw

from .reveal_image import BG, INK, LINE, MUTED, PANEL, TOP, TOP_INK, WIN, _font

COLUMNS = [("Player", "name", False), ("Games", "games", True), ("Wins", "won", True), ("Seats", "seat", True),
           ("Points", "points", True), ("Stolen", "stolen", True), ("Exposed", "exposed", True),
           ("Caught on guard", "guarded", True), ("Given", "given", True), ("Goals", "goal", True)]


def _fit(d, text, size, room, bold=False):
    """The largest font up to `size` that fits `text` in `room` pixels (never below 14)."""
    while size > 14 and d.textlength(text, font=_font(size, bold)) > room:
        size -= 1
    return _font(size, bold)


def render(rows, awards, title="Survivors Hall of Fame", subtitle=""):
    """rows: [{name, games, won, ...}]; awards: [(title, meaning, names, value)]."""
    f, fb, ft, fs, fa = _font(26), _font(26, True), _font(40, True), _font(22), _font(30, True)
    pad, row_h, head_h, card_h, gap = 28, 52, 46, 112, 14
    rows = sorted(rows, key=lambda r: (-r["won"], -r["points"], r["name"]))
    tops = {k: max(r[k] for r in rows) for _, k, num in COLUMNS if num and k != "games"}
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [int(max([probe.textlength(h, font=fs)] + [probe.textlength(str(r[k]), font=fb) for r in rows])) + 40
              for h, k, _ in COLUMNS]
    width = max(pad * 2 + sum(widths), 1500)
    per_row = 4
    card_w = (width - 2 * pad - gap * (per_row - 1)) / per_row
    card_rows = (len(awards) + per_row - 1) // per_row
    awards_h = card_rows * (card_h + gap)
    height = pad + 64 + 34 + awards_h + 16 + head_h + row_h * len(rows) + 52 + pad
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.text((pad, pad), title, font=ft, fill=INK)
    if subtitle:
        d.text((pad, pad + 56), subtitle, font=fs, fill=MUTED)
    y0 = pad + 64 + 34
    for n, (name, meaning, names, value) in enumerate(awards):
        cx = pad + (n % per_row) * (card_w + gap)
        cy = y0 + (n // per_row) * (card_h + gap)
        d.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=12, fill=PANEL)
        room = card_w - 36
        d.text((cx + 18, cy + 26), name.upper(), font=_fit(d, name.upper(), 30, room, True), fill=TOP_INK, anchor="lm")
        d.text((cx + 18, cy + 58), meaning, font=_fit(d, meaning, 22, room), fill=MUTED, anchor="lm")
        line = f"{', '.join(names)}  ({value})"
        if d.textlength(line, font=_font(26, True)) > room:
            line = f"{names[0]} +{len(names) - 1} more  ({value})"
        d.text((cx + 18, cy + 90), line, font=_fit(d, line, 26, room, True), fill=INK, anchor="lm")
    y = y0 + awards_h + 16
    x = pad
    for (head, key, num), cw in zip(COLUMNS, widths):
        d.text((x + cw - 18 if num else x + 14, y + head_h / 2), head, font=fs, fill=MUTED, anchor="rm" if num else "lm")
        x += cw
    y += head_h
    for i, r in enumerate(rows):
        top = y + i * row_h
        if i == 0 and r["won"] > 0:
            d.rectangle([pad, top, width - pad, top + row_h], fill=WIN)
        elif i % 2:
            d.rectangle([pad, top, width - pad, top + row_h], fill=PANEL)
        x, mid = pad, top + row_h / 2
        for (head, key, num), cw in zip(COLUMNS, widths):
            val = r[key]
            best = num and key in tops and tops[key] > 0 and val == tops[key]
            if best:
                d.rounded_rectangle([x + 6, top + 7, x + cw - 6, top + row_h - 7], radius=8, fill=TOP)
            if num:
                d.text((x + cw - 18, mid), str(val), font=fb if best else f, fill=TOP_INK if best else INK, anchor="rm")
            else:
                d.text((x + 14, mid), str(val), font=fb, fill=INK, anchor="lm")
            x += cw
        d.line([pad, top + row_h, width - pad, top + row_h], fill=LINE)
    d.text((pad, height - pad - 22), "Orange = top of the column  ·  green row = most wins  ·  totals over finished "
                                     "seasons only; never who robbed whom", font=fs, fill=MUTED)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
