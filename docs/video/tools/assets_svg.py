"""Stage 2 starting point: every VectorCraft asset as SVG with named groups (variants, moving parts).

Each SVG is opened in VectorCraft, checked there, and exported from VectorCraft to
output/01_assets/<id>.svg + .png at 2x. Colours come from build/scenes.json style.

Group names: one group per variant or separate layer; inside an avatar pose the parts are
<pose>__head, <pose>__body, ... because SVG ids must be unique.

    python tools/assets_svg.py <out_dir> [asset_id ...]
"""
import json
import math
import os
import sys
from xml.sax.saxutils import escape

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scenes = json.load(open(os.path.join(VIDEO, "build", "scenes.json"), encoding="utf-8"))
style, facts = scenes["style"], scenes["game_facts"]
P = style["palette"]
A = {k: v["colour"] for k, v in style["actions"].items()}
# VectorCraft uses only the first family it is given, so put the one that is installed first.
# Fredoka (style.json) isn't installed here; Arial Rounded MT Bold is the nearest bold rounded sans.
HEAD_FONT = "'Arial Rounded MT Bold'"
BODY_FONT = "'Segoe UI'"
INK, PANTS, WHITE = P["shadow"], "#2B2F3A", "#FFFFFF"


def g(name, *parts, transform=None):
    tr = f' transform="{transform}"' if transform else ""
    return f'<g id="{name}"{tr}>' + "".join(parts) + "</g>"


def svg(w, h, *body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            + "".join(body) + "</svg>")


def text(x, y, s, size, fill, weight=700, font=HEAD_FONT, anchor="middle", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{extra}>{escape(s)}</text>')


# ---------- avatar ----------
# Standing figure is about 210 tall: feet at y=0, head centre at y=-168. Pivots: shoulders (±30,-118), hips (±13,-46).
def limb(x, y, length, angle, colour, width=18):
    """A rounded limb from (x, y) pointing down, rotated by angle degrees about its top."""
    return (f'<rect x="{x - width / 2}" y="{y}" width="{width}" height="{length}" rx="{width / 2}" fill="{colour}" '
            f'transform="rotate({angle} {x} {y})"/>')


POSES = {  # arm angles (left, right), leg angles (left, right), body tilt, extra
    "standing": dict(arms=(8, -8), legs=(3, -3), tilt=0),
    "sleeping": dict(arms=(10, -10), legs=(0, 0), tilt=-90),
    "digging": dict(arms=(-55, -35), legs=(12, -8), tilt=12),
    "sneaking": dict(arms=(-70, -95), legs=(28, -24), tilt=18),
    "startled": dict(arms=(150, -150), legs=(10, -10), tilt=0),
    "climbing": dict(arms=(170, -20), legs=(-30, 5), tilt=0),
    "finger_to_lips": dict(arms=(8, -150), legs=(3, -3), tilt=0),
    "holding_tin": dict(arms=(-80, 80), legs=(3, -3), tilt=0),
}


def tin_shape(cx, cy, s=1.0):
    w, h = 44 * s, 54 * s
    x, y = cx - w / 2, cy - h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{6 * s}" fill="{P["ration_tin"]}"/>'
            f'<ellipse cx="{cx}" cy="{y + 2 * s}" rx="{w / 2}" ry="{7 * s}" fill="#E8C35A"/>'
            f'<rect x="{x}" y="{cy - 9 * s}" width="{w}" height="{20 * s}" fill="{P["ration_tin_label"]}"/>'
            f'<rect x="{x + 6 * s}" y="{y + 10 * s}" width="{5 * s}" height="{h - 18 * s}" rx="{2.5 * s}" fill="#F3DC8B" opacity="0.8"/>')


def shovel(x, y, angle):
    return (f'<g transform="rotate({angle} {x} {y})"><rect x="{x - 4}" y="{y}" width="8" height="110" rx="4" fill="#8A5A2B"/>'
            f'<path d="M{x - 22} {y + 106} h44 v18 q0 26 -22 34 q-22 -8 -22 -34 z" fill="#B8C2CC"/></g>')


def avatar(pose="standing", skin=None, shirt=None, prefix=None, ox=0, oy=0, mono=None, big_eyes=False):
    skin = mono or skin or P["avatar_skin_tones"][0]
    shirt = mono or shirt or P["avatar_shirts"][0]
    pants = mono or PANTS
    eye = P["night_bg"] if not mono else mono
    p = POSES[pose]
    pre = prefix or pose
    la, ra = p["arms"]
    ll, rl = p["legs"]
    held = ""
    if pose == "sleeping":
        held = f'<g transform="rotate(90 40 -150)">{text(40, -150, "z z z", 34, P["text_light"], 700)}</g>'
    elif pose == "digging":
        held = shovel(36, -122, -40)
    elif pose == "holding_tin":
        held = tin_shape(0, -100)
    elif pose == "finger_to_lips":
        held = f'<rect x="-3" y="-160" width="6" height="26" rx="3" fill="{skin}"/>'
    er = 6.5 if big_eyes or pose == "startled" else 5
    eyes_y = -172 if pose != "sleeping" else -168
    eyes = ("" if mono else
            f'<circle cx="-12" cy="{eyes_y}" r="{er}" fill="{eye}"/><circle cx="12" cy="{eyes_y}" r="{er}" fill="{eye}"/>')
    if pose == "sleeping" and not mono:
        eyes = (f'<rect x="-19" y="-171" width="14" height="4" rx="2" fill="{eye}"/>'
                f'<rect x="5" y="-171" width="14" height="4" rx="2" fill="{eye}"/>')
    parts = [
        g(f"{pre}__legs", limb(-13, -48, 50, ll, pants, 20), limb(13, -48, 50, rl, pants, 20)),
        g(f"{pre}__left_arm", limb(-31, -120, 64, la, skin)),
        g(f"{pre}__right_arm", limb(31, -120, 64, ra, skin)),
        g(f"{pre}__body", f'<rect x="-32" y="-134" width="64" height="92" rx="24" fill="{shirt}"/>'),
        g(f"{pre}__head", f'<circle cx="0" cy="-170" r="36" fill="{skin}"/>', eyes),
        g(f"{pre}__held_item", held),
    ]
    if pose == "holding_tin":  # arms reach round the tin, so they draw in front of the body
        parts = [parts[0], parts[3], parts[4], parts[5], parts[1], parts[2]]
    tilt = p["tilt"]
    rot = f" rotate({tilt} 0 -60)" if tilt else ""
    return g(pre, *parts, transform=f"translate({ox} {oy}){rot}")


def a_avatar():
    poses = list(POSES)
    w = 260 * len(poses)
    row1 = [avatar(pz, ox=130 + i * 260, oy=300) for i, pz in enumerate(poses)]
    combos = [(P["avatar_skin_tones"][i], P["avatar_shirts"][i]) for i in range(4)]
    row2 = [avatar("standing", s, c, prefix=f"colours_{i + 1}", ox=130 + i * 260, oy=600) for i, (s, c) in enumerate(combos)]
    return svg(w, 640, g("poses", *row1), g("colour_combos", *row2))


def a_bandit_mask():
    return svg(220, 110, g("bandit_mask",
               '<path d="M18 46 Q110 18 202 46 Q210 72 196 82 Q110 64 24 82 Q10 72 18 46 Z" fill="#111111"/>',
               '<path d="M18 50 Q-4 62 6 92 Q14 70 24 62 Z M202 50 Q224 62 214 92 Q206 70 196 62 Z" fill="#111111"/>',
               f'<ellipse cx="78" cy="58" rx="19" ry="10" fill="{P["night_mid"]}"/><ellipse cx="142" cy="58" rx="19" ry="10" fill="{P["night_mid"]}"/>'))


def a_thief_shadow():
    return svg(300, 320, avatar("sneaking", prefix="thief_shadow", ox=140, oy=300, mono=P["shadow"]))


def a_ration_tin():
    return svg(120, 140, g("ration_tin", tin_shape(60, 72, 2.0)))


ICON_STROKE = 'stroke="#FFFFFF" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none"'


def badge(name, colour, inner, cx):
    return g(name, f'<circle cx="{cx}" cy="70" r="62" fill="{colour}"/>',
             f'<circle cx="{cx}" cy="70" r="62" fill="none" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="4"/>',
             f'<g transform="translate({cx - 70} 0)">{inner}</g>')


def a_action_icons():
    shovel_i = f'<path d="M70 28 L70 82" {ICON_STROKE}/><path d="M60 28 H80" {ICON_STROKE}/><path d="M56 82 H84 V96 Q70 114 56 96 Z" {ICON_STROKE}/>'
    hand_i = (f'<path d="M48 100 Q40 80 46 66 L46 50 M58 64 L58 38 M70 62 L70 34 M82 64 L82 40 M94 74 L94 56" {ICON_STROKE}/>'
              f'<path d="M46 66 Q50 104 72 108 Q96 108 94 74" {ICON_STROKE}/>')
    shield_i = f'<path d="M70 28 L102 40 V68 Q102 96 70 112 Q38 96 38 68 V40 Z" {ICON_STROKE}/><path d="M56 70 L66 80 L86 58" {ICON_STROKE}/>'
    glass_i = f'<circle cx="64" cy="62" r="24" {ICON_STROKE}/><path d="M82 80 L102 100" {ICON_STROKE}/>'
    gift_i = (f'<rect x="42" y="58" width="56" height="46" rx="6" {ICON_STROKE}/><path d="M38 58 H102 M70 58 V104" {ICON_STROKE}/>'
              f'<path d="M70 56 Q56 30 46 44 Q42 54 70 56 Q84 30 94 44 Q98 54 70 56" {ICON_STROKE}/>')
    icons = [("icon_scavenge", A["scavenge"], shovel_i), ("icon_steal", A["steal"], hand_i), ("icon_guard", A["guard"], shield_i),
             ("icon_investigate", A["investigate"], glass_i), ("icon_gift", A["gift"], gift_i)]
    return svg(700, 140, *[badge(n, c, i, 70 + k * 140) for k, (n, c, i) in enumerate(icons)])


def stencil_cuts(x0, y0, w, h, colour):
    return "".join(f'<rect x="{x0}" y="{y0 + h * f}" width="{w}" height="5" fill="{colour}"/>' for f in (0.36, 0.62))


def a_title_logo():
    big = g("title_large", text(800, 210, "SURVIVORS", 220, P["text_light"], 800, extra=' letter-spacing="12"'),
            stencil_cuts(40, 55, 1520, 170, P["night_bg"]))
    small = g("title_small", text(800, 380, "SURVIVORS", 72, P["text_light"], 800, extra=' letter-spacing="5"'),
              stencil_cuts(560, 325, 480, 60, P["night_bg"]))
    return svg(1600, 420, f'<rect width="1600" height="420" fill="{P["night_bg"]}"/>', big, small)


def desk(i, x, y, rot):
    return g(f"desk_{i:02d}", f'<g transform="rotate({rot} {x + 60} {y + 35})">'
             f'<rect x="{x}" y="{y}" width="120" height="70" rx="8" fill="#2A3A63" stroke="#3B4F82" stroke-width="3"/>'
             f'<rect x="{x + 40}" y="{y + 12}" width="40" height="24" rx="3" fill="#162447"/>'
             f'<circle cx="{x + 60}" cy="{y + 92}" r="16" fill="#22325A"/></g>')


def a_office_floorplan_night():
    W, H = 1920, 1080
    grid = "".join(f'<rect x="{x}" y="0" width="2" height="{H}" fill="{P["night_mid"]}" opacity="0.35"/>' for x in range(0, W, 120))
    grid += "".join(f'<rect x="0" y="{y}" width="{W}" height="2" fill="{P["night_mid"]}" opacity="0.35"/>' for y in range(0, H, 120))
    floor = g("floor", f'<rect width="{W}" height="{H}" fill="{P["night_bg"]}"/>', grid,
              f'<rect x="40" y="40" width="{W - 80}" height="{H - 80}" rx="12" fill="none" stroke="#3B4F82" stroke-width="6"/>')
    clusters = [(260, 200), (860, 200), (1460, 200), (520, 640), (1200, 640)]
    desks, lamps, n = [], [], 1
    defs = ('<defs><radialGradient id="glow"><stop offset="0" stop-color="#FFE7A3" stop-opacity="0.75"/>'
            '<stop offset="1" stop-color="#FFE7A3" stop-opacity="0"/></radialGradient></defs>')
    for c, (cx, cy) in enumerate(clusters):
        for k, (dx, dy, r) in enumerate([(-140, 0, 0), (20, 0, 0), (-60, 120, 0)]):
            desks.append(desk(n, cx + dx, cy + dy, r))
            n += 1
        lamps.append(g(f"lamp_glow_{c + 1}", f'<circle cx="{cx + 10}" cy="{cy + 80}" r="190" fill="url(#glow)"/>'))
    return svg(W, H, defs, floor, g("desks", *desks), g("lamp_glows", *lamps))


def a_tent():
    top = g("top_down", f'<rect x="20" y="20" width="160" height="110" rx="10" fill="{A["guard"]}" opacity="0.9"/>',
            '<path d="M20 75 H180" stroke="#FFFFFF" stroke-width="5" stroke-opacity="0.6"/>',
            '<path d="M20 20 L100 75 L20 130 M180 20 L100 75 L180 130" stroke="#0B1222" stroke-width="3" stroke-opacity="0.35" fill="none"/>')
    front = g("front_with_window", '<path d="M240 140 L330 20 L420 140 Z" fill="#2EC4B6"/>',
              '<path d="M310 140 L330 70 L350 140 Z" fill="#0B1222" opacity="0.55"/>',
              '<circle cx="330" cy="62" r="16" fill="#FFE7A3"/><circle cx="330" cy="62" r="16" fill="none" stroke="#0B1222" stroke-width="3"/>',
              '<rect x="226" y="138" width="208" height="6" rx="3" fill="#0B1222" opacity="0.5"/>')
    return svg(450, 160, top, front)


def a_calendar_strip():
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"] * 2
    tiles = []
    for i, d in enumerate(days):
        x = 10 + i * 118 + (24 if i >= 5 else 0)
        tiles.append(g(f"tile_{i + 1:02d}", f'<rect x="{x}" y="10" width="104" height="120" rx="12" fill="{P["day_bg"]}"/>',
                       f'<rect x="{x}" y="10" width="104" height="34" rx="12" fill="{A["steal"]}"/><rect x="{x}" y="30" width="104" height="14" fill="{A["steal"]}"/>',
                       text(x + 52, 36, d, 22, WHITE, 700, BODY_FONT), text(x + 52, 104, str(i + 1), 48, P["text_dark"], 800)))
    tick = g("tick_mark", f'<path d="M30 80 L52 104 L94 52" stroke="{A["scavenge"]}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" fill="none"/>')
    return svg(1220, 140, *tiles, tick)


def a_helicopter():
    body = g("body", '<path d="M120 120 Q120 60 220 60 H420 Q500 60 520 130 Q520 200 440 200 H200 Q120 200 120 120 Z" fill="#FF9F1C"/>',
             '<path d="M500 110 H760 L780 80 H800 L790 140 H520 Z" fill="#FF9F1C"/>',
             '<circle cx="790" cy="110" r="26" fill="none" stroke="#5C6B73" stroke-width="8"/>',
             '<path d="M140 110 Q150 76 210 74 V130 H140 Z" fill="#BDE0FE"/>',
             '<path d="M180 230 H480 M220 200 V230 M440 200 V230" stroke="#5C6B73" stroke-width="10" stroke-linecap="round" fill="none"/>',
             f'<rect x="300" y="40" width="40" height="22" rx="6" fill="#5C6B73"/>', text(640, 132, "RESCUE", 24, WHITE, 800))
    door = g("door", '<rect x="225" y="78" width="250" height="110" rx="12" fill="#14213D"/>')
    seats = [g(f"seat_{i + 1}", f'<rect x="{240 + i * 46}" y="120" width="36" height="56" rx="8" fill="#5C6B73"/>',
               f'<rect x="{240 + i * 46}" y="110" width="36" height="20" rx="6" fill="#8A97A0"/>') for i in range(5)]
    rotor = g("rotor", '<rect x="40" y="26" width="560" height="12" rx="6" fill="#2B2F3A"/><circle cx="320" cy="32" r="12" fill="#2B2F3A"/>')
    return svg(840, 250, body, door, *seats, rotor)


def a_bin():
    return svg(220, 260, g("bin", '<path d="M40 70 L180 70 L164 248 H56 Z" fill="#6C7A80"/>',
               '<path d="M76 90 L84 230 M110 90 V230 M144 90 L136 230" stroke="#56636A" stroke-width="8" stroke-linecap="round"/>',
               '<path d="M120 150 q16 8 10 26" stroke="#4A565C" stroke-width="6" fill="none"/>',
               '<path d="M28 56 Q110 34 192 58 L190 72 H30 Z" fill="#7F8D93" transform="rotate(-6 110 60)"/>',
               '<rect x="96" y="30" width="30" height="14" rx="7" fill="#56636A" transform="rotate(-6 110 60)"/>'))


def a_slot_counter():
    digits = g("reel_digits", *[text(110, 112 + i * 120, str(d), 96, P["text_dark"], 800) for i, d in enumerate([0, 1, 2])])
    return svg(220, 400, '<defs><clipPath id="win"><rect x="40" y="30" width="140" height="110" rx="14"/></clipPath></defs>',
               g("frame", '<rect x="10" y="10" width="200" height="150" rx="24" fill="#E5484D"/>',
                 f'<rect x="40" y="30" width="140" height="110" rx="14" fill="{P["day_bg"]}"/>'),
               f'<g clip-path="url(#win)">{digits}</g>')


def a_moon_sun():
    rays = "".join(f'<rect x="248" y="6" width="10" height="26" rx="5" fill="#FFC93C" transform="rotate({a} 253 80)"/>' for a in range(0, 360, 45))
    return svg(340, 160, g("moon", '<path d="M90 20 A60 60 0 1 0 140 120 A48 48 0 1 1 90 20 Z" fill="#F4F1E8"/>'),
               g("sun", rays, '<circle cx="253" cy="80" r="40" fill="#FFC93C"/>'))


def a_shield_glow():
    return svg(320, 300, g("shield_glow", f'<path d="M20 280 A140 260 0 0 1 300 280 Z" fill="{A["guard"]}" fill-opacity="0.28" stroke="{A["guard"]}" stroke-width="6"/>',
                           '<path d="M70 150 Q120 70 190 60" stroke="#FFFFFF" stroke-opacity="0.5" stroke-width="10" stroke-linecap="round" fill="none"/>'))


def a_spotlight():
    return svg(500, 700, '<defs><linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFF6D6" stop-opacity="0.9"/>'
               '<stop offset="1" stop-color="#FFF6D6" stop-opacity="0.25"/></linearGradient></defs>',
               g("spotlight", '<path d="M210 0 H290 L480 640 H20 Z" fill="url(#beam)"/>',
                 '<ellipse cx="250" cy="640" rx="230" ry="50" fill="#FFF6D6" fill-opacity="0.45"/>'))


def shield_path(cx, colour, name):
    return g(name, f'<path d="M{cx} 14 L{cx + 40} 28 V62 Q{cx + 40} 98 {cx} 116 Q{cx - 40} 98 {cx - 40} 62 V28 Z" fill="{colour}"/>',
             f'<path d="M{cx} 30 L{cx + 26} 40 V62 Q{cx + 26} 86 {cx} 98" stroke="#FFFFFF" stroke-opacity="0.45" stroke-width="6" fill="none"/>')


def a_shield_counter():
    return svg(300, 130, *[shield_path(55 + i * 95, A["guard"], f"shield_{i + 1}") for i in range(3)])


def a_magnifying_glass_large():
    return svg(520, 520, g("magnifying_glass_large",
                           '<circle cx="200" cy="200" r="160" fill="none" stroke="#2B2F3A" stroke-width="34"/>',
                           f'<circle cx="200" cy="200" r="160" fill="none" stroke="{A["investigate"]}" stroke-width="14"/>',
                           '<path d="M110 120 Q150 70 210 66" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="12" stroke-linecap="round" fill="none"/>',
                           '<path d="M318 318 L470 470" stroke="#2B2F3A" stroke-width="52" stroke-linecap="round"/>',
                           f'<path d="M340 340 L460 460" stroke="{A["investigate"]}" stroke-width="20" stroke-linecap="round"/>'))


def a_stamp_exposed():
    red = A["steal"]
    specks = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#FFFFFF"/>'
                     for x, y, r in [(90, 70, 5), (240, 150, 4), (420, 80, 6), (520, 170, 3), (160, 180, 3), (330, 60, 4), (600, 120, 5)])
    return svg(720, 260, '<defs><mask id="grunge"><rect width="720" height="260" fill="#FFFFFF"/>' + specks.replace('#FFFFFF', '#000000') + '</mask></defs>',
               g("stamp_exposed", f'<g transform="rotate(-8 360 130)" mask="url(#grunge)">'
                 f'<rect x="40" y="40" width="640" height="180" rx="18" fill="none" stroke="{red}" stroke-width="16"/>'
                 f'<rect x="62" y="62" width="596" height="136" rx="10" fill="none" stroke="{red}" stroke-width="5"/>'
                 + text(360, 166, "EXPOSED", 120, red, 800, extra=' letter-spacing="10"') + "</g>"))


def a_question_mark():
    return svg(140, 200, g("question_mark", text(70, 170, "?", 190, P["ration_tin"], 800, extra=f' stroke="{P["night_bg"]}" stroke-width="8" paint-order="stroke"')))


def a_secret_envelope():
    return svg(420, 300, g("secret_envelope",
                           f'<rect x="20" y="40" width="380" height="240" rx="14" fill="{P["day_bg"]}"/>',
                           '<path d="M20 54 L210 180 L400 54" stroke="#C9C2AE" stroke-width="6" fill="none"/>',
                           '<path d="M20 280 L160 150 M400 280 L260 150" stroke="#DDD6C2" stroke-width="5" fill="none"/>',
                           f'<circle cx="210" cy="180" r="40" fill="{P["ration_tin_label"]}"/>',
                           f'<circle cx="210" cy="180" r="28" fill="none" stroke="#B5523A" stroke-width="5"/>',
                           text(210, 192, "S", 34, "#E9B9A8", 800),
                           text(210, 30, "SECRET GOAL", 34, P["text_light"], 800)))


def a_radio_icon():
    grille = "".join(f'<rect x="58" y="{y}" width="64" height="7" rx="3.5" fill="#0B1222"/>' for y in (98, 114, 130, 146))
    return svg(180, 260, g("radio_icon", '<rect x="132" y="10" width="12" height="70" rx="6" fill="#2B2F3A"/>',
                           f'<rect x="40" y="60" width="100" height="180" rx="22" fill="{A["guard"]}"/>',
                           f'<rect x="54" y="80" width="72" height="88" rx="10" fill="#2B5BC4"/>', grille,
                           '<circle cx="90" cy="200" r="16" fill="#E5484D"/>'))


def a_scoreboard():
    rows = [("Seat", facts["pts_extract"]), ("Alive, no seat", facts["pts_survive"]), ("Secret goal", facts["pts_objective"])]
    body = [f'<rect x="10" y="10" width="700" height="{60 + 110 * len(rows)}" rx="24" fill="#0B1222" stroke="{P["ration_tin"]}" stroke-width="8"/>']
    for i, (label, pts) in enumerate(rows):
        y = 50 + i * 110
        body.append(g(f"row_{i + 1}", f'<rect x="40" y="{y}" width="640" height="90" rx="14" fill="#1F3B6E"/>',
                      text(70, y + 60, label, 44, P["text_light"], 700, anchor="start"),
                      text(650, y + 62, f"+{pts}", 54, P["ration_tin"], 800, anchor="end")))
    return svg(720, 80 + 110 * len(rows), g("scoreboard", *body))


def curtain_half(name, x0, flip):
    folds = "".join(f'<rect x="{x0 + i * 60}" y="60" width="30" height="740" fill="#7A1420" opacity="0.55"/>' for i in range(8))
    return g(name, f'<rect x="{x0}" y="60" width="480" height="740" fill="#B3202E"/>', folds,
             f'<path d="M{x0 if not flip else x0 + 480} 800 Q{x0 + 240} 740 {x0 + 480 if not flip else x0} 800 Z" fill="#7A1420"/>')


def a_curtain():
    return svg(960, 820, g("reveal_title", f'<rect y="60" width="960" height="740" fill="{P["night_bg"]}"/>',
                           text(480, 470, "THE REVEAL", 120, P["ration_tin"], 800, extra=' letter-spacing="6"')),
               curtain_half("left", 0, False), curtain_half("right", 480, True),
               g("valance", '<rect width="960" height="80" fill="#8E1824"/>',
                 "".join(f'<circle cx="{40 + i * 80}" cy="80" r="40" fill="#8E1824"/>' for i in range(12))))


def a_news_clipping_wall():
    n = [facts[f"name{i}"] for i in range(1, 5)]
    clips = [(f"{n[0]} ROBBED", "Down 2 overnight", 120, 120, -4), (f"{n[1]} STRIKES", "Caught a thief red-handed", 640, 90, 3),
             (f"WHERE WAS {n[2].upper()}?", "Out late again", 1200, 140, -2), (f"{n[3]} STARVES", "Ran out of food", 260, 560, 2),
             ("WHO DID IT?", "Every theft revealed", 820, 520, -3), (f"{n[0]} LIED", "About their rations", 1340, 560, 4)]
    defs = '<defs><pattern id="cork" width="24" height="24" patternUnits="userSpaceOnUse"><rect width="24" height="24" fill="#B98A57"/><circle cx="6" cy="8" r="2" fill="#A47645"/><circle cx="17" cy="16" r="2.5" fill="#C99A66"/></pattern></defs>'
    items, pins = [], []
    for i, (head, sub, x, y, rot) in enumerate(clips):
        items.append(g(f"clipping_{i + 1}", f'<g transform="rotate({rot} {x + 190} {y + 130})">'
                       f'<rect x="{x}" y="{y}" width="380" height="260" fill="#F2EDE0"/>'
                       + text(x + 190, y + 70, head, 34, "#1A1A1A", 800, "Georgia, 'Times New Roman', serif")
                       + f'<rect x="{x + 30}" y="{y + 92}" width="320" height="4" fill="#1A1A1A"/>'
                       + text(x + 190, y + 140, sub, 24, "#333333", 400, "Georgia, 'Times New Roman', serif")
                       + "".join(f'<rect x="{x + 30}" y="{y + 168 + k * 22}" width="{320 - k * 50}" height="8" fill="#C9C2AE"/>' for k in range(3))
                       + "</g>"))
        pins.append((x + 190, y + 18))
    string = g("red_string", '<path d="M' + " L".join(f"{px} {py}" for px, py in [pins[0], pins[1], pins[4], pins[3], pins[0], pins[2], pins[5], pins[4]])
               + '" stroke="#C0182B" stroke-width="5" fill="none"/>')
    pin_g = g("pins", *[f'<circle cx="{px}" cy="{py}" r="12" fill="#D62839"/><circle cx="{px - 3}" cy="{py - 3}" r="4" fill="#FF8A95"/>' for px, py in pins])
    return svg(1920, 1080, defs, g("cork_board", '<rect width="1920" height="1080" fill="url(#cork)"/>'), g("clippings", *items), string, pin_g)


ASSETS = {name[2:]: fn for name, fn in globals().items() if name.startswith("a_")}

if __name__ == "__main__":
    out, only = sys.argv[1], sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    for name, fn in ASSETS.items():
        if only and name not in only:
            continue
        path = os.path.join(out, f"{name}.svg")
        open(path, "w", encoding="utf-8").write(fn())
        print(path)
