"""Read back the Survivors channels' permission overwrites from Discord and check them. Read-only.

    python bot/tools/verify_channels.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_discord import env, get  # noqa: E402

VIEW, SEND = 1 << 10, 1 << 11
READ_ONLY = {"news", "radio"}

token, guild = env()
me = get("/users/@me", token)[1]["id"]
_, members = get(f"/guilds/{guild}/members?limit=1000", token)
bots = {m["user"]["id"] for m in members if m["user"].get("bot") and m["user"]["id"] != me}
_, chans = get(f"/guilds/{guild}/channels", token)
cat = next(c for c in chans if c["type"] == 4 and c["name"].lower() == "survivors")
ok = True
for c in [cat] + [c for c in chans if c.get("parent_id") == cat["id"]]:
    o = {x["id"]: x for x in c["permission_overwrites"]}
    blocked = sum(1 for b in bots if b in o and int(o[b]["deny"]) & VIEW)
    ev = o.get(guild)
    people_post = not (ev and int(ev["deny"]) & SEND)
    torch = me in o and int(o[me]["allow"]) & (VIEW | SEND) == (VIEW | SEND)
    want_post = c["type"] == 4 or c["name"] not in READ_ONLY
    good = blocked == len(bots) and torch and people_post == want_post
    ok &= good
    print(f"{'OK ' if good else 'BAD'} {c['name']:12} other bots blocked {blocked}/{len(bots)} | "
          f"people can post: {people_post} | Torch view+send: {torch}")
sys.exit(0 if ok else 1)
