"""Stage 4: build and render every scene in the live EffectCraft window (effectcraft.exe --control 7981).

Scene lengths and beat times come from build/scenes.json, so new voiceover re-times everything.
Images are the VectorCraft/FigCraft exports at 2x, placed at 50% (1 SVG unit = 1 comp pixel).
Each scene renders to output/04_scenes/scene_XX.mp4 (H.264, 1920x1080, 30 fps, no audio).

    python tools/effectcraft_scenes.py [scene_01 scene_02 ...] [--no-render]
"""
import json
import math
import os
import subprocess
import sys
import time

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = r"C:\Program Files\EffectCraft\effectcraft-cli.exe"
PORT = "7981"
BUILD = json.load(open(os.path.join(VIDEO, "build", "scenes.json"), encoding="utf-8"))
STYLE, FACTS = BUILD["style"], BUILD["game_facts"]
PAL = STYLE["palette"]
ACT = {k: v["colour"] for k, v in STYLE["actions"].items()}
SCENES = {s["id"]: s for s in BUILD["scenes"]}
ASSETS = os.path.join(VIDEO, "output", "01_assets").replace("\\", "/")
PARTS = ASSETS + "/parts"
UI = os.path.join(VIDEO, "output", "02_ui").replace("\\", "/")
OUT = os.path.join(VIDEO, "output", "04_scenes").replace("\\", "/")
NIGHT, MAIN_UI, BOX_UI = PAL["night_bg"], "#1A2747", "#223159"
TEXT_Y = 200          # on-screen text: upper third, inside the 96 px safe margin
SWAP = 0.04           # an instant swap's two keys: over one frame (1/30 s) apart, or EffectCraft keeps only one
BADGE = (166, 166)    # action badge pinned top-left


DRY = "--dry" in sys.argv  # build every scene against a fake app: catches script errors before a long run


def run(*steps):
    """Run commands in order against the live app; returns their results."""
    if DRY:
        return [{"comp": 1, "layer": 1, "items": []} if cid != "renderQueue.list" else [{"compName": "x", "status": "Done", "index": 1}]
                for cid, _ in steps]
    args = [CLI, "--bridge", PORT, "--json", "run"]
    for cid, params in steps:
        args += [cid, json.dumps(params)]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise SystemExit(f"effectcraft-cli failed ({p.returncode}): {p.stderr.strip() or p.stdout.strip()}")
    out = json.loads(p.stdout)
    for r in out:
        if isinstance(r, dict) and r.get("error"):
            raise SystemExit(f"{r['command']}: {r['error']}")
    return [r.get("result") for r in out]


class Scene:
    def __init__(self, sid):
        self.s = SCENES[sid]
        self.sid, self.dur = sid, self.s["duration_s"]
        self.beats = [b["at_s"] for b in self.s["beats"]]
        try:  # rebuilding a scene replaces it instead of adding a second comp with the same name
            run(("project.delete", {"items": [sid]}))
        except SystemExit:
            pass
        self.comp = run(("comp.new", {"name": sid, "width": 1920, "height": 1080, "frameRate": 30, "duration": self.dur}),
                        ("comp.settings", {"background": NIGHT}))[0]["comp"]

    def B(self, i):
        return self.beats[i]

    def _anim(self, layer, opacity=None, **paths):
        """paths: position/scale/rotation/opacity -> [(t, v), ...] keyframes, eased; or a single static value."""
        steps = []
        if opacity is not None:
            paths["opacity"] = opacity
        for name, spec in paths.items():
            path = f"transform/{name}"
            if isinstance(spec, list) and spec and isinstance(spec[0], tuple):
                steps += [("prop.addKey", {"layer": layer, "path": path, "time": max(0.0, min(t, self.dur - 1 / 30)), "value": v}) for t, v in spec]
                if len(spec) > 1:
                    steps += [("keys.deselectAll", {}), ("prop.select", {"layer": layer, "path": path, "selectKeys": True}),
                              ("keys.easyEase", {})]
                    if name == "position":  # spatial Bezier bulges between equal keys: a held layer drifts
                        steps.append(("keys.interpolation", {"spatial": "linear"}))
            else:
                steps.append(("prop.set", {"layer": layer, "path": path, "value": spec}))
        if steps:
            run(*steps)

    def img(self, path, x, y, scale=50, name=None, **anim):
        lid = run(("layer.addItem", {"item": os.path.basename(path), "position": [x, y]}))[0]["layer"]
        run(("layer.rename", {"layer": lid, "name": name or os.path.basename(path)[:-4]}))
        if "scale" not in anim:
            anim["scale"] = [scale, scale] if not isinstance(scale, list) else scale
        self._anim(lid, **anim)
        return lid

    def shape(self, kind, size, fill, x, y, name, **anim):
        lid = run(("layer.newShape", {"kind": kind, "size": size, "fill": fill, "position": [x, y], "name": name}))[0]["layer"]
        self._anim(lid, **anim)
        return lid

    def text(self, s, x, y, size=72, fill=None, name=None, bold=True, **anim):
        lid = run(("layer.newText", {"text": s, "name": name or s[:30], "position": [x, y], "font": "Inter",
                                     "style": "Bold" if bold else "Regular", "size": size, "fill": fill or PAL["text_light"]}))[0]["layer"]
        self._anim(lid, **anim)
        return lid

    def expr(self, layer, path, code):
        run(("prop.setExpression", {"layer": layer, "path": f"transform/{path}", "expression": code}))

    # common moves
    def appear(self, t, d=0.3):
        return [(0, 0), (t, 0), (t + d, 100)] if t > 0 else [(0, 0), (d, 100)]

    def vanish(self, t, d=0.3):
        return [(0, 100), (t, 100), (t + d, 0)]

    def pop(self, t, to=50, d=0.3):
        return [(0, [0, 0]), (t, [0, 0]), (t + d, [to * 1.15, to * 1.15]), (t + d + 0.12, [to, to])] if t > 0 else \
               [(0, [0, 0]), (d, [to * 1.15, to * 1.15]), (d + 0.12, [to, to])]

    def caption(self, t=0.4, y=TEXT_Y, x=960, size=72):
        """The scene's on-screen text, held from t to the end (at least 2 s)."""
        return self.text(self.s["on_screen_text"], x, y, size, name="on_screen_text", opacity=self.appear(t))

    def badge(self, action):
        return self.img(f"{PARTS}/icon_{action}.png", *BADGE, name=f"badge_{action}", scale=self.pop(0.0))

    def render(self):
        os.makedirs(OUT, exist_ok=True)
        dst = f"{OUT}/{self.sid}.mp4"
        if os.path.exists(dst):
            os.remove(dst)
        # renderQueue.render {wait: true} hits the CLI's ~60 s timeout on longer scenes: start it, then poll.
        run(("renderQueue.add", {"comp": self.sid, "format": "h264", "output": dst, "audio": "off"}),
            ("renderQueue.render", {"wait": False}))
        while True:
            time.sleep(3)
            items = run(("renderQueue.list", {}))[0]
            items = items if isinstance(items, list) else items.get("items", [])
            mine = [i for i in items if i.get("compName") == self.sid]
            status = mine[-1].get("status") if mine else None
            if status == "Done":
                break
            if status and status not in ("Queued", "Rendering", "Unqueued", "Needs Output"):
                raise SystemExit(f"{self.sid}: render status {status}")
        for i in sorted((i["index"] for i in items if i.get("status") == "Done"), reverse=True):
            run(("renderQueue.remove", {"index": i}))
        return dst


# ---------- layout facts shared by several scenes ----------
CLUSTERS = [(260, 200), (860, 200), (1460, 200), (520, 640), (1200, 640)]
DESK_OFFSETS = [(-140, 0), (20, 0), (-60, 120)]
DESKS = [(cx + dx + 60, cy + dy + 35) for cx, cy in CLUSTERS for dx, dy in DESK_OFFSETS]
FEET = 150  # avatar part: feet are 150 px below the layer's centre (canvas 440x340, feet at y=320)


def avatar(sc, pose, x, feet_y, name=None, **anim):
    return sc.img(f"{PARTS}/avatar_{pose}.png", x, feet_y - FEET, name=name or f"avatar_{pose}", **anim)


def tin(sc, x, y, scale=35, name="tin", **anim):  # 35% of the 2x export: 84 px wide, a third of an avatar's height
    return sc.img(f"{ASSETS}/ration_tin.png", x, y, scale, name=name, **anim)


def s01():
    sc = Scene("scene_01")
    sc.img(f"{PARTS}/floorplan_base.png", 960, 540, opacity=[(0, 0), (1.0, 100)])
    t = sc.B(1)
    flick = [(0, 0), (1.0, 100), (t, 100)] + [(t + 0.4 * i, v) for i, v in enumerate([55, 100, 70, 100, 60, 100], 1)]
    sc.img(f"{PARTS}/floorplan_lamps.png", 960, 540, opacity=flick)
    for i, (x, y) in enumerate(DESKS):
        start = sc.B(2) + (i // 3) * 0.7
        sc.img(f"{PARTS}/tent_top_down.png", x, y, name=f"tent_{i + 1:02d}", scale=sc.pop(start, 33))
    t = sc.B(3)
    sc.shape("rect", [1920, 1080], NIGHT, 960, 540, "dim", opacity=[(0, 0), (t - 0.2, 0), (t + 0.3, 55)])
    sc.img(f"{PARTS}/title_large.png", 960, 540, name="title",
           scale=[(0, [0, 0]), (t, [0, 0]), (t + SWAP, [80, 80]), (t + 0.3, [50, 50])], opacity=sc.appear(t, 0.15))
    return sc


def s02():
    sc = Scene("scene_02")
    y = 470
    slide_out = sc.B(2)
    left = 960 - 610
    sc.img(f"{PARTS}/calendar_tiles.png", 960, y, name="calendar",
           position=[(0, [-700, y]), (sc.B(0) + 1.0, [960, y]), (slide_out, [960, y]), (slide_out + 1.2, [-1000, y])])
    for i in range(10):
        tx = left + 10 + i * 118 + (24 if i >= 5 else 0) + 52
        t = sc.B(1) + i * (6.0 - sc.B(1)) / 10
        sc.img(f"{PARTS}/calendar_tick.png", tx, y, name=f"tick_{i + 1}", scale=sc.pop(t, 45),
               position=[(0, [tx, y]), (slide_out, [tx, y]), (slide_out + 1.2, [tx - 1960, y])])
    hy = 600
    for part in ("helicopter_body", "helicopter_rotor"):
        lid = sc.img(f"{PARTS}/{part}.png", 960, hy, name=part, position=[(0, [2900, hy]), (slide_out, [2900, hy]), (slide_out + 1.2, [960, hy])])
        if part == "helicopter_rotor":
            sc.expr(lid, "scale", "[50 * Math.abs(Math.cos(time * 5)), 50]")
    sc.caption(sc.B(3))
    return sc


def s03():
    sc = Scene("scene_03")
    ax, feet = 520, 800
    avatar(sc, "standing", ax, feet)
    times = [1.9, 2.9, 3.7, 4.4, 5.1, 5.7, 6.4]
    for i, t in enumerate(times):
        x = 780 + i * 100
        tin(sc, x, 740, name=f"tin_{i + 1}", scale=[(0, [35, 35]), (t, [35, 35]), (t + 0.25, [0, 0])])
    night = [(0, 0), (sc.B(1), 0), (sc.B(1) + 0.3, 100)]
    for k, t in enumerate(times):
        night += [(t - 0.15, 100 if k % 2 == 0 else 0), (t, 0 if k % 2 == 0 else 100)]
    sc.img(f"{PARTS}/moon.png", 1560, 470, name="moon", opacity=night)
    sun = [(0, 0)] + [(t, 100 if k % 2 == 0 else 0) for k, t in enumerate(times)]
    sc.img(f"{PARTS}/sun.png", 1560, 470, name="sun", opacity=sun)
    t = sc.B(2)
    head_y = feet - FEET - 20
    sc.img(f"{ASSETS}/bandit_mask.png", ax, head_y, name="bandit_mask", scale=21,
           position=[(0, [ax, -100]), (t, [ax, -100]), (t + 0.3, [ax, head_y])])
    sc.caption()
    return sc


def s04():
    sc = Scene("scene_04")
    shrink = sc.B(2)
    sc.img(f"{UI}/ui_phone_chat.png", 960, 540, name="phone",
           position=[(0, [960, 1700]), (0.8, [960, 540]), (shrink, [960, 540]), (shrink + 0.6, [430, 560])],
           scale=[(0, [50, 50]), (shrink, [50, 50]), (shrink + 0.6, [38, 38])])
    t = sc.B(1)
    sc.shape("rect", [170, 48], BOX_UI, 840, 886, "typing_cover", opacity=sc.vanish(t, 0.8),
             position=[(0, [840, 886]), (t, [840, 886]), (t + 0.8, [920, 886]), (shrink, [920, 886])])
    labels = ["scavenge", "steal", "guard", "investigate", "gift"]
    for i, a in enumerate(labels):
        ang = math.radians(-56 + i * 28)
        x, y = 1000 + 430 * math.cos(ang), 600 + 430 * math.sin(ang)
        ti = shrink + 0.3 + i * 0.18
        sc.img(f"{PARTS}/icon_{a}.png", x, y, name=f"icon_{a}", scale=sc.pop(ti, 50))
        sc.text(a.capitalize(), x + 190, y + 16, 44, name=f"label_{a}", opacity=sc.appear(ti + 0.1))
    sc.caption(sc.B(3), y=150, size=64)
    return sc


def s05():
    sc = Scene("scene_05")
    sc.badge("scavenge")
    feet = 800
    avatar(sc, "digging", 560, feet, opacity=sc.appear(sc.B(1)))
    sc.img(f"{ASSETS}/bin.png", 780, feet - 130, name="bin", opacity=sc.appear(sc.B(1)))
    cx, cy = 1360, 540
    sc.shape("rounded", [200, 150], ACT["steal"], cx, cy, "slot_frame", opacity=sc.appear(sc.B(2) - 0.3))
    sc.shape("rounded", [140, 110], PAL["day_bg"], cx, cy, "slot_window", opacity=sc.appear(sc.B(2) - 0.3))
    t0 = sc.B(2)
    seg = (sc.B(3) - t0 - 0.4) / 3
    for d in range(3):
        a, b = t0 + d * seg, t0 + (d + 1) * seg
        op = [(0, 0), (a, 0), (a + SWAP, 100), (b, 100), (b + SWAP, 0)] if d < 2 else [(0, 0), (a, 0), (a + SWAP, 100)]
        sc.text(str(d), cx, cy + 34, 96, PAL["text_dark"], name=f"digit_{d}", opacity=op)
        for k in range(d):
            tin(sc, cx - 60 + k * 120, 720, name=f"tin_{d}_{k}",
                scale=[(0, [0, 0]), (a, [0, 0]), (a + 0.3, [35, 35]), (b, [35, 35]), (b + SWAP, [0, 0])] if d < 2 else sc.pop(a, 35))
    sc.text("Missed it? Auto-scavenge.", 960, 960, 48, name="missed_note", opacity=sc.appear(sc.B(3)))
    sc.caption()
    return sc


def s06():
    sc = Scene("scene_06")
    sc.badge("steal")
    feet, ax = 820, 620
    wake = sc.B(3)
    avatar(sc, "sleeping", ax, feet + 40, opacity=[(0, 100), (wake, 100), (wake + SWAP, 0)])
    avatar(sc, "startled", ax, feet, opacity=[(0, 0), (wake, 0), (wake + SWAP, 100)])
    t_in, t_take = sc.B(1), sc.B(2)
    thief_x = 1180
    exit_t = t_take + 1.2
    sc.img(f"{ASSETS}/thief_shadow.png", thief_x, feet - 140, name="thief",
           position=[(0, [2150, feet - 140]), (t_in, [2150, feet - 140]), (t_take - 0.3, [thief_x, feet - 140]),
                     (t_take + 0.2, [thief_x, feet - 140]), (exit_t, [2200, feet - 140])])
    for i in range(4):
        x = 860 + i * 70
        if i < 2:
            tin(sc, x, feet - 30, name=f"tin_{i + 1}")
        else:
            tin(sc, x, feet - 30, name=f"tin_{i + 1}", position=[(0, [x, feet - 30]), (t_take, [x, feet - 30]),
                                                                 (t_take + 0.3, [thief_x + (i - 2) * 50, feet - 160]),
                                                                 (exit_t, [2200 + (i - 2) * 50, feet - 160])])
    qy = feet - 300
    sc.img(f"{ASSETS}/question_mark.png", ax, qy, name="question_mark", opacity=sc.appear(wake + 0.1),
           position=[(0, [ax, qy]), (wake + 0.1, [ax, qy]), (wake + 0.4, [ax, qy - 30]), (wake + 0.7, [ax, qy]),
                     (wake + 1.0, [ax, qy - 20]), (wake + 1.3, [ax, qy])])
    sc.caption()
    return sc


def s07():
    sc = Scene("scene_07")
    sc.badge("guard")
    feet, ax = 820, 720
    avatar(sc, "standing", ax, feet)
    sc.img(f"{ASSETS}/shield_glow.png", ax, feet - 140, name="shield_glow", opacity=[(0, 0), (0.5, 90)])
    t = sc.B(1)
    phases = [("moon", t, t + 1.0), ("sun", t + 1.0, t + 2.0), ("moon2", t + 2.0, t + 3.0)]
    for name, a, b in phases:
        part = "sun" if name == "sun" else "moon"
        sc.img(f"{PARTS}/{part}.png", 1500, 470, name=name, opacity=[(0, 0), (a, 0), (a + 0.25, 100), (b - 0.05, 100), (b + 0.2, 0)])
    t_in, t_spot, t_pay, t_count = sc.B(2), sc.B(3), sc.B(4), sc.B(5)
    tx, ty = 1120, feet - 140
    sc.img(f"{ASSETS}/thief_shadow.png", tx, ty, name="thief",
           position=[(0, [2150, ty]), (t_in, [2150, ty]), (t_in + 0.8, [ax + 180, ty]), (t_in + 1.1, [tx, ty])])
    sc.img(f"{ASSETS}/spotlight.png", tx, ty - 120, name="spotlight", opacity=[(0, 0), (t_spot, 0), (t_spot + 0.1, 85)])
    sc.text("CAUGHT", tx, 420, 64, ACT["steal"], name="caught_banner", opacity=sc.appear(t_spot + 0.1, 0.25))
    for i in range(2):
        sx, gx = tx - 30 + i * 60, ax + 90 + i * 60
        tin(sc, sx, feet - 60, name=f"paid_tin_{i + 1}", opacity=sc.appear(t_pay),
            position=[(0, [sx, feet - 60]), (t_pay, [sx, feet - 60]), (t_pay + 0.6 + i * 0.2, [gx, feet - 30])])
    for i in range(3):
        op = sc.appear(t_count + i * 0.15)
        if i == 0:
            op += [(t_count + 1.0, 100), (t_count + 1.4, 30)]
        sc.img(f"{PARTS}/shield.png", 1440 + i * 110, 900, name=f"shield_{i + 1}", opacity=op)
    sc.caption()
    return sc


def s08():
    sc = Scene("scene_08")
    sc.badge("investigate")
    tents = [560, 820, 1080, 1340, 1600]
    ty = 640
    for i, x in enumerate(tents):
        sc.img(f"{PARTS}/tent_front.png", x, ty, 80, name=f"tent_{i + 1}")
    window = (1340 - 5 * 0.8 * 2 / 2, ty - 18 * 0.8 * 2 / 2)
    avatar(sc, "standing", 230, 800)
    t_sweep, t_seen, t_stamp, t_fly = sc.B(1), sc.B(2), sc.B(3), sc.B(4)
    off = 60
    sc.img(f"{ASSETS}/magnifying_glass_large.png", 400, ty + off, 42, name="magnifier", opacity=sc.appear(t_sweep - 0.2),
           position=[(0, [400 + off, ty + off]), (t_sweep, [400 + off, ty + off]), (t_seen - 0.4, [window[0] + off, window[1] + off])])
    sc.img(f"{ASSETS}/thief_shadow.png", window[0], window[1] + 10, 14, name="thief_in_window", opacity=sc.appear(t_seen, 0.4))
    sc.img(f"{ASSETS}/stamp_exposed.png", 1340, 520, name="stamp_exposed", opacity=sc.appear(t_stamp, 0.1),
           scale=[(0, [80, 80]), (t_stamp, [80, 80]), (t_stamp + 0.25, [45, 45])])
    tin(sc, 1340, ty, name="bounty_tin", opacity=sc.appear(t_fly, 0.15),
        position=[(0, [1340, ty]), (t_fly, [1340, ty]), (t_fly + 0.9, [300, 700])])
    sc.caption()
    return sc


def s09():
    sc = Scene("scene_09")
    sc.badge("gift")
    sc.shape("ellipse", [760, 480], ACT["gift"], 960, 640, "glow", opacity=[(0, 0), (0.6, 22)])
    feet = 820
    t_pass, t_hush = sc.B(1), sc.B(2)
    for i, (x, normal, hush) in enumerate([(780, "colours_1", "finger_to_lips"), (1140, "colours_2", "finger_to_lips_2")]):
        avatar(sc, normal, x, feet, opacity=[(0, 100), (t_hush, 100), (t_hush + SWAP, 0)])
        avatar(sc, hush, x, feet, opacity=[(0, 0), (t_hush, 0), (t_hush + SWAP, 100)])
    tin(sc, 840, feet - 90, name="gift_tin", position=[(0, [840, feet - 90]), (t_pass, [840, feet - 90]),
                                                     (t_pass + 1.0, [1080, feet - 90])])
    sc.caption()
    return sc


def s10():
    sc = Scene("scene_10")
    sc.img(f"{UI}/ui_news_post.png", 960, 540, name="news_screen", position=[(0, [2900, 540]), (0.6, [960, 540])])
    x0, w = 572 + 560, 1140
    for i, (y, h) in enumerate([(311, 56), (406, 104), (500, 56)]):
        sc.shape("rect", [w, h], MAIN_UI, x0, y, f"cover_line_{i + 1}", opacity=sc.vanish(sc.B(i + 1), 0.4))
    sc.img(f"{ASSETS}/question_mark.png", 960, 560, 110, name="big_question", opacity=[(0, 0), (sc.B(4), 0), (sc.B(4) + 0.5, 85)])
    sc.text(sc.s["on_screen_text"], 1560, 190, 64, name="on_screen_text", opacity=sc.appear(0.6))
    return sc


def s11():
    sc = Scene("scene_11")
    tents = [260, 640, 1020, 1400, 1780]
    for i, x in enumerate(tents):
        sc.img(f"{PARTS}/tent_front.png", x, 620, 70, name=f"tent_{i + 1}", opacity=70)
    feet, t_free = 860, sc.B(2)
    path = [(0, [240, feet - FEET]), (t_free, [1500, feet - FEET])]
    sc.img(f"{PARTS}/avatar_sneaking.png", 240, feet - FEET, name="bandit", position=path,
           opacity=[(0, 60), (t_free, 60), (t_free + 0.4, 100)])
    mpath = [(t, [p[0] + 34, p[1] - 15]) for t, p in path] + [(t_free + 0.1, [1534, feet - FEET - 15]),
                                                                (t_free + 0.7, [1700, -150])]
    sc.img(f"{ASSETS}/bandit_mask.png", 274, feet - FEET - 15, 21, name="bandit_mask", position=mpath,
           rotation=[(0, 18), (t_free, 18), (t_free + 0.7, 200)])
    t0 = sc.B(1)
    step = (t_free - 0.3 - t0) / 3
    for n in range(4):
        a = t0 + (n - 1) * step if n else 0
        op = [(0, 0 if n else 100)]
        if n:
            op += [(a, 0), (a + SWAP, 100)]
        if n < 3:
            op += [(t0 + n * step, 100), (t0 + n * step + SWAP, 0)]
        sc.text(f"{n} / {FACTS['bandit_rejoin']}", 960, 380, 96, PAL["ration_tin"], name=f"count_{n}", opacity=op)
    sc.caption()
    return sc


def s12():
    sc = Scene("scene_12")
    t_cut = sc.B(1)
    sc.img(f"{ASSETS}/secret_envelope.png", 960, 560, 70, name="envelope",
           position=[(0, [960, -200]), (0.6, [960, 560])],
           rotation=[(0.6, 0), (0.9, -4), (1.2, 4), (1.5, -2), (1.8, 0)],
           opacity=[(0, 100), (t_cut - 0.2, 100), (t_cut, 0)])
    sc.img(f"{UI}/ui_radio_channel.png", 960, 540, name="radio_screen", opacity=[(0, 0), (t_cut - 0.2, 0), (t_cut, 100)])
    for i, t in enumerate([5.5, 7.0, 8.5]):
        sc.shape("rect", [1430, 120], MAIN_UI, 1186, 150 + i * 170 + 50, f"cover_msg_{i + 1}", opacity=[(0, 0), (t_cut - 0.2, 0), (t_cut, 100), (t, 100), (t + 0.3, 0)])
    sc.img(f"{ASSETS}/radio_icon.png", 1720, 320, name="radio_icon", scale=sc.pop(t_cut + 0.2, 60))
    sc.text(sc.s["on_screen_text"], 1180, 820, 60, name="on_screen_text", opacity=sc.appear(sc.B(2)))
    return sc


def s13():
    sc = Scene("scene_13")
    t_board, t_cut, t_curtain = sc.B(2), sc.B(3), sc.B(4)
    hy = 560
    for part in ("helicopter_body", "helicopter_rotor"):
        lid = sc.img(f"{PARTS}/{part}.png", 960, hy, name=part, position=[(0, [960, -260]), (2.0, [960, hy])],
                     opacity=[(0, 100), (t_board, 100), (t_board + 0.4, 0)])
        if part == "helicopter_rotor":
            sc.expr(lid, "scale", "[50 * Math.abs(Math.cos(time * 7)), 50]")
    door = (890, 600)
    starts = [(250, "colours_1"), (420, "colours_2"), (1520, "colours_3"), (1680, "colours_4"), (1840, "standing")]
    for i, (x, pose) in enumerate(starts):
        t = sc.B(1) + i * 1.05
        avatar(sc, pose, x, 860, name=f"climber_{i + 1}",
               position=[(0, [x, 860 - FEET]), (t, [x, 860 - FEET]), (t + 0.8, [door[0], door[1]])],
               opacity=[(0, 100), (t + 0.7, 100), (t + 0.9, 0)])
        sc.shape("rect", [36, 56], "#FFC93C", 960 - 420 + 258 + i * 46, hy + 23, f"seat_light_{i + 1}",
                 opacity=[(0, 0), (t + 0.8, 0), (t + 1.0, 70), (t_board, 70), (t_board + 0.4, 0)])
    sc.img(f"{ASSETS}/scoreboard.png", 960, 600, name="scoreboard",
           scale=[(0, [50, 0]), (t_board, [50, 0]), (t_board + 0.35, [50, 50])],
           opacity=[(0, 100), (t_cut, 100), (t_cut + 0.4, 0)])
    sc.text(sc.s["on_screen_text"], 960, TEXT_Y, 72, name="on_screen_text", opacity=[(0, 0), (t_board, 0), (t_board + 0.3, 100), (t_cut, 100), (t_cut + 0.4, 0)])
    sc.img(f"{ASSETS}/news_clipping_wall.png", 960, 540, name="clipping_wall", opacity=[(0, 0), (t_cut, 0), (t_cut + 0.2, 100)])
    sc.text("THE REVEAL", 960, 560, 150, PAL["ration_tin"], name="reveal_title", opacity=[(0, 0), (t_curtain + 0.6, 0), (t_curtain + 1.0, 100)])
    curtain_scale = [100, 65.85]
    for part, dx in (("curtain_left", -1920), ("curtain_right", 1920)):
        sc.img(f"{PARTS}/{part}.png", 960, 540, name=part, scale=curtain_scale,
               opacity=[(0, 0), (t_cut, 0), (t_cut + 0.3, 100)],
               position=[(0, [960, 540]), (t_curtain, [960, 540]), (t_curtain + 1.4, [960 + dx, 540])])
    sc.img(f"{PARTS}/curtain_valance.png", 960, 540, name="valance", scale=curtain_scale, opacity=[(0, 0), (t_cut, 0), (t_cut + 0.3, 100)])
    return sc


def s14():
    sc = Scene("scene_14")
    t_bg, t_end = sc.B(1), sc.B(2)
    sc.img(f"{PARTS}/floorplan_base.png", 960, 540, name="floorplan")
    sc.shape("rect", [1920, 1080], PAL["day_bg"], 960, 540, "daylight", opacity=[(0, 0), (t_bg + 1.0, 0), (t_bg + 3.5, 70)])
    for i, (x, y) in enumerate(DESKS):
        t = t_bg + 0.6 + (i // 3) * 0.4
        sc.img(f"{PARTS}/tent_top_down.png", x, y, name=f"tent_{i + 1:02d}", scale=[(0, [33, 33]), (t, [33, 33]), (t + 0.3, [0, 0])])
    sc.img(f"{UI}/ui_join.png", 960, 540, name="join_screen", position=[(0, [960, 540]), (t_bg, [960, 540]), (t_bg + 0.6, [960, 1700])])
    sc.shape("rect", [230, 52], BOX_UI, 620, 1004, "typing_cover", opacity=sc.vanish(0.3, 0.6),
             position=[(0, [620, 1004]), (0.3, [620, 1004]), (0.9, [740, 1004]), (t_bg, [740, 1004]), (t_bg + 0.6, [740, 2164])])
    sc.shape("rect", [1300, 230], MAIN_UI, 1150, 668, "reply_cover", opacity=sc.vanish(1.4, 0.5),
             position=[(0, [1150, 668]), (t_bg, [1150, 668]), (t_bg + 0.6, [1150, 1828])])
    sc.text(sc.s["on_screen_text"], 1180, 330, 64, name="on_screen_text", opacity=[(0, 0), (0.4, 0), (0.7, 100), (t_bg, 100), (t_bg + 0.4, 0)])
    sc.shape("rect", [1920, 1080], NIGHT, 960, 540, "end_card_bg", opacity=[(0, 0), (t_end - 0.3, 0), (t_end + 0.3, 100)])
    sc.img(f"{PARTS}/title_small.png", 960, 480, name="title_small", scale=[(0, [0, 0]), (t_end, [0, 0]), (t_end + 0.3, [100, 100])])
    sc.text("trust no one", 960, 600, 60, ACT["steal"], name="trust_no_one", opacity=sc.appear(t_end + 0.5))
    return sc


BUILDERS = {f"scene_{i:02d}": f for i, f in enumerate([s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12, s13, s14], 1)}


def import_footage():
    files = [f"{PARTS}/{f}" for f in sorted(os.listdir(PARTS)) if f.endswith(".png")]
    files += [f"{ASSETS}/{f}" for f in sorted(os.listdir(ASSETS)) if f.endswith(".png")]
    files += [f"{UI}/{f}" for f in sorted(os.listdir(UI)) if f.endswith(".png")]
    # sequence: false, or numbered stills (avatar_colours_1..4.png) import as one image sequence
    res = run(("file.newProject", {}), ("file.import", {"paths": files, "sequence": False}))[1]
    if res.get("errors"):
        raise SystemExit(f"import errors: {res['errors']}")
    return len(res["items"])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    render = "--no-render" not in sys.argv
    wanted = args or list(BUILDERS)
    if DRY:
        for sid in wanted:
            BUILDERS[sid]()
        sys.exit(f"dry run: {len(wanted)} scenes build without errors")
    if "--keep" not in sys.argv:  # --keep: add to the open project (footage already imported)
        print(f"imported {import_footage()} images", flush=True)
    for sid in wanted:
        sc = BUILDERS[sid]()
        print(f"{sid}: built ({sc.dur} s)", flush=True)
        if render:
            print(f"{sid}: rendered -> {sc.render()}", flush=True)
    run(("file.saveAs", {"path": os.path.join(VIDEO, "work", "survivors_scenes.ecproj").replace("\\", "/")}))
    print("saved work/survivors_scenes.ecproj")
