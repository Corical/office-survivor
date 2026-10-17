"""Stage 3 starting point: the four chat screens as SVG, one named group per layer the video animates.

Imported into FigCraft (file.import keeps each <g id> as a layer), checked there, then exported from
FigCraft to output/02_ui/<id>.svg + .png at 2x. A generic chat app in the game's palette: no Discord
logo, wordmark, mascot or colours (AGENT.md brand rules). Text comes from build/assets.json.

    python tools/ui_screens_svg.py <out_dir>
"""
import json
import os
import sys
from xml.sax.saxutils import escape

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
build = json.load(open(os.path.join(VIDEO, "build", "scenes.json"), encoding="utf-8"))
facts = build["game_facts"]
pal = build["style"]["palette"]

W, H = 1920, 1080
RAIL, LIST = 96, 340
FONT = "Inter, 'Segoe UI', Arial, sans-serif"
C = dict(rail="#0B1222", list="#14213D", main="#1A2747", line="#2A3A63", muted="#8E9BBF", text=pal["text_light"],
         active="#1F3B6E", box="#223159", bot=pal["ration_tin"], anon="#5C6B73", accent="#2EC4B6")


def t(x, y, s, size=26, fill=C["text"], weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')


def width(s, size, bold=False):
    """Rough rendered width of Inter/Segoe text: about 0.56 em a character, 0.6 em bold."""
    return len(s) * size * (0.6 if bold else 0.56)


def g(name, *parts):
    return f'<g id="{name}">' + "".join(parts) + "</g>"


def tent_icon(cx, cy, r):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{C["accent"]}"/>'
            f'<path d="M{cx - r * .55} {cy + r * .4} L{cx} {cy - r * .5} L{cx + r * .55} {cy + r * .4} Z" fill="{C["rail"]}"/>'
            f'<path d="M{cx - r * .12} {cy + r * .4} L{cx} {cy + r * .05} L{cx + r * .12} {cy + r * .4} Z" fill="{C["accent"]}"/>')


def app_shell(active, topic):
    chans = ["town-square", "news", "radio"]
    rows = []
    for i, ch in enumerate(chans):
        y = 150 + i * 56
        on = ch == active
        rows.append(g(f"channel_{ch.replace('-', '_')}",
                      f'<rect x="{RAIL + 14}" y="{y - 36}" width="{LIST - 28}" height="48" rx="8" fill="{C["active"] if on else "none"}"/>',
                      t(RAIL + 34, y, f"#  {ch}", 26, C["text"] if on else C["muted"], 600 if on else 400)))
    return (g("server_rail", f'<rect width="{RAIL}" height="{H}" fill="{C["rail"]}"/>', tent_icon(RAIL / 2, 62, 32))
            + g("channel_list", f'<rect x="{RAIL}" width="{LIST}" height="{H}" fill="{C["list"]}"/>',
                t(RAIL + 28, 66, "survivors", 30, C["text"], 700),
                f'<rect x="{RAIL}" y="92" width="{LIST}" height="2" fill="{C["line"]}"/>', *rows)
            + g("main_bg", f'<rect x="{RAIL + LIST}" width="{W - RAIL - LIST}" height="{H}" fill="{C["main"]}"/>')
            + g("channel_header", t(RAIL + LIST + 40, 62, f"#  {active}", 32, C["text"], 700),
                t(RAIL + LIST + 40 + width(f"#  {active}", 32, True) + 36, 62, topic, 24, C["muted"]),
                f'<rect x="{RAIL + LIST}" y="92" width="{W - RAIL - LIST}" height="2" fill="{C["line"]}"/>'))


def message_box(placeholder, typed=None):
    x0 = RAIL + LIST + 40
    inner = (t(x0 + 32, 1014, typed, 30, C["text"], 600) if typed else t(x0 + 32, 1014, placeholder, 28, C["muted"]))
    return g("message_box", f'<rect x="{x0}" y="966" width="{W - x0 - 40}" height="76" rx="14" fill="{C["box"]}"/>', inner)


def author(x, y, name, time, colour, glyph, tag=None):
    parts = [f'<circle cx="{x + 34}" cy="{y + 30}" r="34" fill="{colour}"/>',
             t(x + 34, y + 42, glyph, 32, C["rail"], 700, "middle"), t(x + 96, y + 26, name, 28, C["text"], 700)]
    nx = x + 96 + width(name, 28, True) + 18
    if tag:
        parts += [f'<rect x="{nx}" y="{y + 2}" width="62" height="30" rx="6" fill="{C["accent"]}"/>',
                  t(nx + 31, y + 25, tag, 18, C["rail"], 700, "middle")]
        nx += 78
    parts.append(t(nx, y + 26, time, 22, C["muted"]))
    return "".join(parts)


def svg(body, bg=True):
    back = f'<rect width="{W}" height="{H}" fill="{C["main"]}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f"{back}{body}</svg>")


X = RAIL + LIST + 40


def news_post():
    names = [facts[k] for k in ("name1", "name2", "name3", "name4")]
    lines = [[f"Someone hit {names[0]} overnight. Down {facts['steal_amount']}."],
             [f"CAUGHT: {names[1]} caught {names[2]} red-handed.", f"{names[2]} pays {names[1]} {facts['caught_penalty']}."],
             [f"{names[3]} ran out of food."]]
    body = app_shell("news", "Every morning at " + facts["news_time"])
    body += g("bot_author", author(X, 150, "Survivors Bot", f"Today at {facts['news_time']}", C["bot"], "S", "BOT"))
    body += g("headline", t(X + 96, 252, f"{facts['news_time']} MORNING NEWS", 34, C["bot"], 800))
    y = 322
    for i, rows in enumerate(lines):
        body += g(f"line_{i + 1}", *[t(X + 96, y + j * 46, s, 32, C["text"], 500) for j, s in enumerate(rows)])
        y += 46 * (len(rows) - 1) + 72
    return svg(body + message_box("Only the bot posts in #news"))


def radio_channel():
    msgs = [f"{facts['name3']} was out late last night...", "Don't trust the quiet ones.",
            f"{facts['name1']} is lying about their rations."]
    body = app_shell("radio", "One anonymous message a day")
    for i, (m, tm) in enumerate(zip(msgs, ["13:02", "15:47", "21:10"])):
        y = 150 + i * 170
        body += g(f"message_{i + 1}", author(X, y, "Anonymous", f"Today at {tm}", C["anon"], "?"),
                  t(X + 96, y + 78, m, 32, C["text"], 500))
    return svg(body + message_box("Message #radio"))


def join():
    alias = facts["name1"]
    reply = [f"You're in. Your secret alias is {alias}.", "Tell no one.", "Day 1 starts [LAUNCH DATE] at " + facts["news_time"] + "."]
    body = app_shell("town-square", "Say hello. Trust no one.")
    body += g("bot_reply", author(X, 560, "Survivors Bot", "Only you can see this", C["bot"], "S", "BOT"),
              *[t(X + 96, 650 + i * 52, s, 32, C["text"], 500 if i else 700) for i, s in enumerate(reply)])
    return svg(body + message_box("Message #town-square", facts["join_command"]))


def phone_chat():
    pw, ph = 500, 980
    px, py = (W - pw) / 2, (H - ph) / 2
    sx, sy, sw = px + 22, py + 70, pw - 44
    chans = ["town-square", "news", "radio"]
    cmds = [("/scavenge", "look for food"), ("/steal", "take rations from someone"), ("/guard", "protect yourself"),
            ("/investigate", "watch someone"), ("/gift", "give food away")]
    body = g("phone_body", f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="64" fill="#05080F"/>',
             f'<rect x="{sx}" y="{py + 22}" width="{sw}" height="{ph - 44}" rx="46" fill="{C["list"]}"/>',
             f'<rect x="{px + pw / 2 - 60}" y="{py + 34}" width="120" height="26" rx="13" fill="#05080F"/>')
    body += g("screen_header", tent_icon(sx + 52, sy + 52, 28), t(sx + 98, sy + 64, "survivors", 32, C["text"], 700),
              f'<rect x="{sx}" y="{sy + 104}" width="{sw}" height="2" fill="{C["line"]}"/>')
    for i, ch in enumerate(chans):
        y = sy + 170 + i * 66
        body += g(f"channel_{ch.replace('-', '_')}", t(sx + 36, y, f"#  {ch}", 30, C["muted"], 500))
    by = sy + ph - 250
    popup_h = len(cmds) * 62 + 44
    popup_y = by - popup_h - 18
    rows = []
    for i, (c, d) in enumerate(cmds):
        y = popup_y + 30 + i * 62
        on = c == "/steal"
        rows.append(f'<rect x="{sx + 22}" y="{y - 6}" width="{sw - 44}" height="56" rx="10" fill="{C["active"] if on else "none"}"/>'
                    + t(sx + 40, y + 32, c, 28, C["text"] if on else C["muted"], 700)
                    + t(sx + 40 + width(c, 28, True) + 14, y + 32, d, 20, C["muted"]))
    body += g("command_popup", f'<rect x="{sx + 14}" y="{popup_y}" width="{sw - 28}" height="{popup_h}" rx="16" fill="{C["box"]}"/>', *rows)
    body += g("message_box", f'<rect x="{sx + 14}" y="{by}" width="{sw - 28}" height="72" rx="36" fill="{C["box"]}"/>',
              t(sx + 46, by + 47, "/steal", 30, C["text"], 700),
              f'<rect x="{sx + 152}" y="{by + 20}" width="3" height="34" fill="{C["accent"]}"/>')
    return svg(body, bg=False)


SCREENS = {"ui_news_post": news_post, "ui_radio_channel": radio_channel, "ui_join": join, "ui_phone_chat": phone_chat}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, fn in SCREENS.items():
        open(os.path.join(out, f"{name}.svg"), "w", encoding="utf-8").write(fn())
        print(os.path.join(out, f"{name}.svg"))
