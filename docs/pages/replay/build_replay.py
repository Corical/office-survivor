"""Inject replay logs into the viewer template -> survivors-replay.html."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "..", "..", "sim", "results", "replays")   # written by sim/tools/pick_games.py and reel --log
GAMES = [
    ("game_typical_seed10.jsonl", "Typical game · seed 10",
     "The closest of 300 simulated games to the averages."),
    ("game_drama_seed33.jsonl", "Most dramatic · seed 33",
     "The most catches, exposures and comebacks of 300 games."),
    ("seed11_why.jsonl", "Handover sample · seed 11",
     "The game the handover uses as its example. Unusually brutal."),
    ("jev_argmax_seed11.jsonl", "Jev live · seed 11",
     "Same seed, 5 players decided by the real Jev API (its top pick). The rest play by personality."),
]
data = []
for fn, label, blurb in GAMES:
    with open(os.path.join(LOGS, fn), encoding="utf-8") as f:
        events = [json.loads(l) for l in f if l.strip()]
    data.append({"id": fn, "label": label, "blurb": blurb, "events": events})
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
SEASON = os.path.join(HERE, "..", "season")
for template, out in ((os.path.join(HERE, "replay_template.html"), os.path.join(HERE, "survivors-replay.html")),
                      (os.path.join(SEASON, "season_template.html"), os.path.join(SEASON, "survivors-season.html"))):
    with open(template, encoding="utf-8") as f:
        html = f.read()
    with open(out, "w", encoding="utf-8") as f:
        f.write(html.replace("/*__GAMES__*/", blob))
    print(os.path.normpath(out), os.path.getsize(out) // 1024, "KB")
