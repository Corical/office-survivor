#!/usr/bin/env python3
"""
Survivors explainer video - build script.

Reads ../game.json and source/*.json, fills every {placeholder} with the
current game rules, works out timing, writes the ready-to-use specs into
build/, and lists exactly what has to be (re)made in build/TODO.md.

  python3 build.py                 rebuild build/ and show what needs doing
  python3 build.py status          same, but only print the to-do list
  python3 build.py done ITEM...    record that ITEM was made from the current spec
                                   ITEM is vo:scene_03, asset:ration_tin, scene:scene_03,
                                   audio_mix or final. Wildcards work: asset:*, vo:*

Never edit build/ by hand: it is overwritten on every run. Edit game.json or
source/ instead. Standard library only, Python 3.8+.
"""

import fnmatch
import hashlib
import json
import math
import re
import sys
import textwrap
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent / "game.json"
SRC = HERE / "source"
BUILD = HERE / "build"
OUT = HERE / "output"
STATE = OUT / "built.json"

WORDS_PER_SECOND = 2.5        # ~150 words a minute
PAD_AFTER_VOICE = 0.8         # seconds of breathing room after each scene's voiceover
CAPTION_LINE = 42
NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
       "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
       "eighteen", "nineteen", "twenty"]

STAGES = [
    ("vo", "1. Voiceover (a person or text-to-speech)"),
    ("asset:VectorCraft", "2. Draw assets in VectorCraft"),
    ("asset:FigCraft", "3. Build chat screens in FigCraft"),
    ("scene", "4. Animate scenes in EffectCraft"),
    ("audio_mix", "5. Mix voice, music and sound effects (SoundCraft, or FilmCraft)"),
    ("final", "6. Assemble and export in FilmCraft"),
]


# ------------------------------------------------------------------ helpers

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def word(n):
    return NUM[n] if isinstance(n, int) and 0 <= n < len(NUM) else str(n)


def context(game):
    r, p = game["rules"], game["presentation"]
    ctx = {**r, **p}
    ctx["seats"] = max(1, round(r["players"] * r["seat_ratio"]))
    rounds = r["rounds"]
    if rounds % 5 == 0:
        weeks = rounds // 5
        ctx["game_span"] = "week" if weeks == 1 else f"{word(weeks)} weeks"
    else:
        ctx["game_span"] = f"{word(rounds)} workdays"
    vals = list(range(r["scavenge_min"], r["scavenge_max"] + 1))
    items = ["nothing" if v == 0 else word(v) for v in vals]
    phrase = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]
    ctx["scavenge_spoken"] = phrase + (" ration" if vals[-1] == 1 else " rations")
    g = r["guard_nights"]
    ctx["guard_span"] = ("tonight" if g == 1 else "tonight and tomorrow night" if g == 2
                         else f"for {word(g)} nights, starting tonight")
    ctx["join_spoken"] = p["join_command"].replace("/", "slash ")
    for i, n in enumerate(p.get("example_names", []), 1):
        ctx[f"name{i}"] = n
    return ctx


TOKEN = re.compile(r"\{(\w+)(?::(\w+))?\}")


def render(text, ctx, where):
    def sub(m):
        key, fmt = m.group(1), m.group(2)
        if key not in ctx:
            raise SystemExit(f"Unknown placeholder {{{key}}} in {where}.\nAvailable: {', '.join(sorted(ctx))}")
        v = ctx[key]
        if fmt is None:
            return str(v)
        if fmt == "word":
            return word(v)
        if fmt == "Word":
            return word(v).capitalize()
        if fmt in ("rations", "Rations"):
            s = f"{word(v)} ration{'' if v == 1 else 's'}"
            return s.capitalize() if fmt == "Rations" else s
        raise SystemExit(f"Unknown format :{fmt} in {where} (use word, Word, rations or Rations)")
    return TOKEN.sub(sub, text)


def render_obj(obj, ctx, where):
    if isinstance(obj, str):
        return render(obj, ctx, where)
    if isinstance(obj, list):
        return [render_obj(x, ctx, where) for x in obj]
    if isinstance(obj, dict):
        return {k: render_obj(v, ctx, f"{where}.{k}") for k, v in obj.items()}
    return obj


def wav_seconds(path):
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, OSError):
        return None


def fmt_ts(t):
    ms = int(round(t * 1000))
    hh, ms = divmod(ms, 3600000)
    mm, ms = divmod(ms, 60000)
    ss, ms = divmod(ms, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def caption_chunks(text):
    """Split narration into caption cards of at most 2 lines x CAPTION_LINE characters."""
    limit = CAPTION_LINE * 2
    cards = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(sentence) <= limit:
            cards.append(sentence)
            continue
        cur = ""
        for part in re.split(r"(?<=[,:;])\s+", sentence):
            cand = f"{cur} {part}".strip()
            if len(cand) <= limit:
                cur = cand
                continue
            if cur:
                cards.append(cur)
            cur = ""
            for w in part.split():
                cand = f"{cur} {w}".strip()
                if len(cand) <= limit:
                    cur = cand
                else:
                    cards.append(cur)
                    cur = w
        if cur:
            cards.append(cur)
    merged = []                          # fold tiny cards into a neighbour
    for c in cards:
        if merged and (len(c) < 20 or len(merged[-1]) < 20) and len(merged[-1]) + 1 + len(c) <= limit:
            merged[-1] = f"{merged[-1]} {c}"
        else:
            merged.append(c)
    return [two_lines(c) for c in merged]


def two_lines(card):
    if len(card) <= CAPTION_LINE:
        return card
    spaces = [i for i, ch in enumerate(card) if ch == " "]
    best = min(spaces, key=lambda i: max(i, len(card) - i - 1))
    left, right = card[:best], card[best + 1:]
    if max(len(left), len(right)) > CAPTION_LINE + 4:
        return "\n".join(textwrap.wrap(card, CAPTION_LINE))
    return f"{left}\n{right}"


def output_exists(item, scenes_by_id, assets_by_id):
    kind, _, name = item.partition(":")
    if kind == "vo":
        cands = [OUT / "03_audio" / "vo" / f"{name}.wav"]
    elif kind == "asset":
        folder = "01_assets" if assets_by_id[name]["tool"] == "VectorCraft" else "02_ui"
        cands = [OUT / folder / f"{name}.svg", OUT / folder / f"{name}.png"]
    elif kind == "scene":
        cands = [OUT / "04_scenes" / f"{name}.mp4", OUT / "04_scenes" / f"{name}.mov"]
    elif item == "audio_mix":
        cands = [OUT / "03_audio" / "mix.wav"]
    elif item == "final":
        cands = [OUT / "05_final" / "survivors_explainer.mp4"]
    else:
        return None
    return next((c for c in cands if c.exists()), None)


# ------------------------------------------------------------------ build

def build():
    game = load(GAME)
    script, assets_src, style = load(SRC / "script.json"), load(SRC / "assets.json"), load(SRC / "style.json")
    state = load(STATE) if STATE.exists() else {}
    ctx = context(game)
    style_hash = h(style)

    # assets
    assets = []
    for a in assets_src["assets"]:
        ra = render_obj(a, ctx, f"assets.json:{a['id']}")
        folder = "01_assets" if ra["tool"] == "VectorCraft" else "02_ui"
        ra["output"] = f"output/{folder}/{ra['id']}.svg (+ .png at 2x)"
        ra["hash"] = h([ra, style_hash])
        assets.append(ra)
    assets_by_id = {a["id"]: a for a in assets}

    # scenes: text, timing, beats
    scenes, t = [], 0.0
    for s in script["scenes"]:
        where = f"script.json:{s['id']}"
        for a in s["assets"]:
            if a not in assets_by_id:
                raise SystemExit(f"{where} uses asset '{a}', which is not in source/assets.json")
        narration = render(s["narration"], ctx, where)
        vo_hash = h([narration, style["audio"]["voice"]])
        words = len(narration.split())
        speech_est = words / WORDS_PER_SECOND
        base = s["base_duration_s"]
        vo_file = OUT / "03_audio" / "vo" / f"{s['id']}.wav"
        vo_len = wav_seconds(vo_file) if vo_file.exists() else None
        if vo_len and state.get(f"vo:{s['id']}") == vo_hash:
            duration, timing, speech = round(vo_len + PAD_AFTER_VOICE, 1), "voiceover", vo_len
        else:
            est = speech_est + PAD_AFTER_VOICE
            duration = base if est <= base + 1 else math.ceil(est * 2) / 2
            timing, speech = "draft", min(speech_est, duration - 0.3)
        scale = duration / base
        beats = [{"at_s": round(b["at_s"] * scale, 1), "do": render(b["do"], ctx, where)} for b in s["beats"]]
        scene = {
            "id": s["id"], "number": int(s["id"].split("_")[1]), "title": s["title"],
            "start_s": round(t, 1), "duration_s": duration, "timing_source": timing,
            "narration": narration, "word_count": words,
            "on_screen_text": render(s["on_screen_text"], ctx, where),
            "beats": beats, "assets": s["assets"], "sfx": s["sfx"],
            "transition_in": "cut" if not scenes else "0.3 s crossfade",
            "voiceover_file": f"output/03_audio/vo/{s['id']}.wav",
            "output": f"output/04_scenes/{s['id']}.mp4",
            "vo_hash": vo_hash,
        }
        scene["hash"] = h([{k: v for k, v in scene.items() if k not in ("start_s", "vo_hash")},
                           [assets_by_id[a]["hash"] for a in s["assets"]], style_hash])
        scene["_speech_s"] = speech
        scenes.append(scene)
        t += duration
    total = round(t, 1)

    # captions
    srt, n = [], 0
    for sc in scenes:
        chunks = caption_chunks(sc["narration"])
        total_chars = sum(len(c) for c in chunks)
        cur = sc["start_s"] + 0.15
        for c in chunks:
            dur = sc["_speech_s"] * len(c) / total_chars
            n += 1
            srt.append(f"{n}\n{fmt_ts(cur)} --> {fmt_ts(cur + dur - 0.05)}\n{c}\n")
            cur += dur
    captions = "\n".join(srt)

    audio_hash = h([[(s["vo_hash"], s["duration_s"], s["sfx"]) for s in scenes], style["audio"]])
    final_hash = h([[s["hash"] for s in scenes], audio_hash, h(captions), style["export"]])

    current = {}
    for s in scenes:
        current[f"vo:{s['id']}"] = s["vo_hash"]
    for a in assets:
        current[f"asset:{a['id']}"] = a["hash"]
    for s in scenes:
        current[f"scene:{s['id']}"] = s["hash"]
    current["audio_mix"] = audio_hash
    current["final"] = final_hash

    # write build/
    BUILD.mkdir(exist_ok=True)
    for sub in ("01_assets", "02_ui", "03_audio/vo", "04_scenes", "05_final"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    clean = [{k: v for k, v in s.items() if not k.startswith("_")} for s in scenes]
    facts = {**{k: v for k, v in ctx.items()}, "game_version": game.get("version", "")}
    (BUILD / "scenes.json").write_text(json.dumps(
        {"total_duration_s": total, "game_facts": facts, "style": style, "scenes": clean},
        indent=2, ensure_ascii=False), encoding="utf-8")
    (BUILD / "assets.json").write_text(json.dumps({"style": style, "assets": assets}, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    (BUILD / "narration.txt").write_text(
        "".join(f"[{s['id']}] {s['title']} ({s['word_count']} words)\n{s['narration']}\n\n" for s in scenes),
        encoding="utf-8")
    (BUILD / "captions.srt").write_text(captions, encoding="utf-8")
    (BUILD / "manifest.json").write_text(json.dumps(current, indent=2), encoding="utf-8")
    todo = todo_list(current, state, scenes, assets_by_id, total)
    (BUILD / "TODO.md").write_text(todo, encoding="utf-8")
    return current, state, scenes, assets_by_id, todo


def todo_list(current, state, scenes, assets_by_id, total):
    def pending(prefix_filter):
        out = []
        for key, hv in current.items():
            if not prefix_filter(key):
                continue
            if state.get(key) != hv:
                out.append((key, "not made yet" if key not in state else "spec changed since it was made"))
        return out

    lines = [f"# To do\n", f"Video length: {total:.0f} s ({int(total // 60)}:{int(total % 60):02d}). "
             f"Timing: {sum(s['timing_source'] == 'voiceover' for s in scenes)} of {len(scenes)} scenes "
             f"from recorded voiceover, the rest are estimates.\n"]
    any_todo = False
    for stage, title in STAGES:
        if stage == "vo":
            items = pending(lambda k: k.startswith("vo:"))
        elif stage.startswith("asset:"):
            tool = stage.split(":")[1]
            items = pending(lambda k, tool=tool: k.startswith("asset:") and assets_by_id[k[6:]]["tool"] == tool)
        elif stage == "scene":
            items = pending(lambda k: k.startswith("scene:"))
        else:
            items = pending(lambda k, stage=stage: k == stage)
        lines.append(f"\n## {title}\n")
        if not items:
            lines.append("Nothing to do.\n")
            continue
        any_todo = True
        for key, why in items:
            lines.append(f"- [ ] `{key}` ({why})\n")
        lines.append(f"\nWhen each one is saved in output/, run: `python3 build.py done <item>`\n")
    if any_todo and any(s["timing_source"] == "draft" for s in scenes):
        lines.append("\nNote: finish stage 1 and mark it done before animating scenes. Recorded "
                     "voiceover changes scene lengths, which would mark finished scenes for redo.\n")
    if not any_todo:
        lines.append("\nEverything is up to date with game.json and source/.\n")
    return "".join(lines)


def mark_done(patterns):
    current, state, scenes, assets_by_id, _ = build()
    scenes_by_id = {s["id"]: s for s in scenes}
    hits = []
    for pat in patterns:
        matched = [k for k in current if fnmatch.fnmatch(k, pat)]
        if not matched:
            raise SystemExit(f"No item matches '{pat}'. Items look like vo:scene_03, asset:ration_tin, "
                             f"scene:scene_03, audio_mix, final.")
        hits += matched
    missing = [k for k in hits if output_exists(k, scenes_by_id, assets_by_id) is None]
    if missing:
        raise SystemExit("Not marked, output file missing for: " + ", ".join(missing))
    for k in hits:
        state[k] = current[k]
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Marked done: {', '.join(hits)}")
    return build()


def main():
    args = sys.argv[1:]
    if args and args[0] == "done":
        if len(args) < 2:
            raise SystemExit("Usage: python3 build.py done ITEM [ITEM...]")
        *_, todo = mark_done(args[1:])
    else:
        *_, todo = build()
        if not args or args[0] != "status":
            print(f"Built: {', '.join(p.name for p in sorted(BUILD.iterdir()))}\n")
    print(todo)


if __name__ == "__main__":
    main()
