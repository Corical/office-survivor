"""Is Torch's status board in #news, and is it pinned? Read-only. Never prints the token.

    python bot/tools/check_board.py <board message id>
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".secrets", "discord.env")) if "=" in l)
token = env["DISCORD_BOT_TOKEN"]


def get(path):
    req = urllib.request.Request(f"https://discord.com/api/v10{path}", headers={
        "Authorization": f"Bot {token}", "User-Agent": "TorchCheck (office-survivor, 0.1)"})
    return json.load(urllib.request.urlopen(req))


chans = get(f"/guilds/{env['DISCORD_GUILD_ID']}/channels")
news = next(c for c in chans if c["name"] == "news")
board_id = sys.argv[1]
msg = get(f"/channels/{news['id']}/messages/{board_id}")
print("board in #news:", msg["id"] == board_id, "| pinned:", msg.get("pinned"))
print(msg["content"].encode("ascii", "replace").decode())
