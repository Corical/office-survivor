"""Print the public view of the running season as JSON: schedule, size, and the news posted so far. Nothing secret
(no moves, rations, goals, identities or unposted text). Used to feed the live game page.

    TORCH_DATA=/var/lib/torch python -m bot.tools.public_feed
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from bot.game import news_lines  # noqa: E402

data = os.environ.get("TORCH_DATA", "bot/data")
recs = [json.loads(l) for l in open(os.path.join(data, "season.jsonl"), encoding="utf-8") if l.strip()]
start = next((r for r in recs if r["type"] == "start"), None)
sent = {r["id"] for r in recs if r["type"] == "sent"}
nights, posted_news = {}, set()
for r in recs:
    if r["type"] == "night":
        nights[r["night"]] = news_lines(r["events"]) or ["A quiet night. Nobody lost anything."]
    if r["type"] == "news" and all(i["id"] in sent for i in r.get("outbox", []) if i["to"] == "news"):
        posted_news.add(r["night"])
finished = next((r for r in recs if r["type"] == "finish"), None)
out = {
    "season": open(os.path.join(data, "season_id.txt")).read().strip(),
    "started": bool(start),
    "start_ts": start and start["start_ts"], "day_seconds": start and start["day_seconds"],
    "news_delay": start and start["news_delay"], "rounds": start and start["rules"]["rounds"],
    "players": start and len(start["roster"]),
    "news": {n: lines for n, lines in nights.items() if n in posted_news},
    "quits": sum(1 for r in recs if r["type"] == "quit"),
    "finished": bool(finished),
    "extracted": finished and next(e for e in finished["events"] if e["type"] == "extraction")["extracted"],
    "winners": finished and next(e for e in finished["events"] if e["type"] == "game_end")["winners"],
}
print(json.dumps(out))
