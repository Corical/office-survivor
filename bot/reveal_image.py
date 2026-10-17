"""The end-of-game reveal as a picture: one row per player, one column per stat, the top of each column highlighted.

Discord has no tables and a text table wraps on a phone, so Torch posts this PNG with the reveal. Pure: rows in,
PNG bytes out. If Pillow or a font is missing, the caller falls back to the text reveal.
"""
import io

from PIL import Image, ImageDraw, ImageFont

FONTS = {  # first one found wins: the Pi (DejaVu), then Windows for local previews
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf",
           "C:/Windows/Fonts/arialbd.ttf"],
}
BG, PANEL, INK, MUTED, LINE = "#1e1f22", "#2b2d31", "#f2f3f5", "#a5a9b3", "#3a3c42"
TOP, TOP_INK, WIN, DONE, MISS = "#5c3216", "#ffb37a", "#2d4a33", "#6cc28f", "#8a8e96"

# (header, key, numeric, highlight the max)
COLUMNS = [("#", "rank", True, False), ("Player", "player", False, False), ("Points", "score", True, True),
           ("Seat", "seat", False, False), ("Rations", "rations", True, True), ("Stole", "stole", True, True),
           ("Robbed", "times_robbed", True, True), ("Gave away", "gave_away", True, True),
           ("Goal", "goal", False, False)]


def _font(size, bold=False):
    for path in FONTS[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise OSError("no usable font")


def cell(row, key):
    """The text drawn in one cell (also what the column width is measured from)."""
    if key == "seat":
        return "Yes" if row["seat"] else ""
    if key == "goal":
        return "     " + row["goal"]            # room for the done/missed dot drawn in front
    return str(row[key])


AWARDS = [("🥷", "Biggest thief", "stole"), ("🎯", "Most robbed", "times_robbed"), ("🎁", "Most generous", "gave_away"),
          ("🥫", "Biggest stash", "rations")]


def awards(rows):
    """One headline per stat: who topped it (ties share it), or 'nobody' when the top is 0."""
    out = []
    for emoji, title, key in AWARDS:
        top = max(r[key] for r in rows)
        who = ", ".join(r["player"] for r in rows if r[key] == top) if top > 0 else "nobody"
        out.append((title, who, top))
    return out


def rows_from_results(results, extracted):
    """Result events (from engine.finish) -> table rows, best score first."""
    rows = []
    for n, e in enumerate(sorted(results, key=lambda e: -e["score"]), 1):
        rows.append({"rank": n, "player": e["player"], "score": e["score"],
                     "seat": e["player"] in extracted, "rations": e["rations"], "stole": e["stole"],
                     "times_robbed": e["times_robbed"], "gave_away": e["gave_away"],
                     "goal": e["objective"], "goal_done": e["objective_done"]})
    return rows


def render(rows, winners, title="The reveal"):
    f, fb, ft, fs = _font(26), _font(26, True), _font(38, True), _font(22)
    pad, row_h, head_h = 28, 54, 48
    tops = {k: max(r[k] for r in rows) for _, k, num, hi in COLUMNS if hi}
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = lambda text, font: probe.textlength(str(text), font=font)
    widths = []
    for head, key, num, _ in COLUMNS:
        cells = [cell(r, key) for r in rows]
        widths.append(int(max([w(head, fs)] + [w(c, fb) for c in cells])) + 36)
    width = pad * 2 + sum(widths)
    aw = awards(rows)
    card_h = 92
    height = pad + 60 + card_h + 24 + head_h + row_h * len(rows) + 56 + pad
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.text((pad, pad), f"{title}   ·   Winner: {', '.join(winners)}", font=ft, fill=INK)
    # award cards: who topped each stat
    gap = 14
    cw_card = (width - 2 * pad - gap * (len(aw) - 1)) / len(aw)
    for n, (name, who, top) in enumerate(aw):
        cx = pad + n * (cw_card + gap)
        d.rounded_rectangle([cx, pad + 60, cx + cw_card, pad + 60 + card_h], radius=10, fill=PANEL)
        d.text((cx + 16, pad + 60 + 26), name.upper(), font=fs, fill=MUTED, anchor="lm")
        line = who if who == "nobody" else f"{who}  ({top})"
        names = who.split(", ")
        if who != "nobody" and d.textlength(line, font=fb) > cw_card - 32:     # a tie too long for the card
            line = f"{names[0]} +{len(names) - 1} more  ({top})"
        d.text((cx + 16, pad + 60 + 62), line, font=fb, fill=MUTED if who == "nobody" else TOP_INK, anchor="lm")
    y = pad + 60 + card_h + 24
    x = pad
    for (head, key, num, _), cw in zip(COLUMNS, widths):
        d.text((x + cw - 18 if num else x + 14, y + head_h / 2), head, font=fs, fill=MUTED,
               anchor="rm" if num else "lm")
        x += cw
    y += head_h
    for i, r in enumerate(rows):
        top = y + i * row_h
        if r["player"] in winners:
            d.rectangle([pad, top, width - pad, top + row_h], fill=WIN)
        elif i % 2:
            d.rectangle([pad, top, width - pad, top + row_h], fill=PANEL)
        x, mid = pad, top + row_h / 2
        for (head, key, num, hi), cw in zip(COLUMNS, widths):
            val = r[key]
            best = hi and tops[key] > 0 and val == tops[key]
            if best:
                d.rounded_rectangle([x + 6, top + 7, x + cw - 6, top + row_h - 7], radius=8, fill=TOP)
            if key == "seat":
                d.text((x + 14, mid), cell(r, key), font=fb, fill=DONE, anchor="lm")
            elif key == "goal":
                colour = DONE if r["goal_done"] else MISS
                if r["goal_done"]:
                    d.ellipse([x + 16, mid - 8, x + 32, mid + 8], fill=DONE)
                else:
                    d.ellipse([x + 16, mid - 8, x + 32, mid + 8], outline=MISS, width=2)
                d.text((x + 14, mid), cell(r, key), font=f, fill=colour, anchor="lm")
            elif num:
                d.text((x + cw - 18, mid), str(val), font=fb if best or key == "score" else f,
                       fill=TOP_INK if best else INK, anchor="rm")
            else:
                d.text((x + 14, mid), str(val), font=fb, fill=INK, anchor="lm")
            x += cw
        d.line([pad, top + row_h, width - pad, top + row_h], fill=LINE)
    d.text((pad, height - pad - 24), "Orange = top of the column  ·  green row = winner  ·  Seat = on the helicopter  ·  filled dot = goal done",
           font=fs, fill=MUTED)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
