"""Read-only check of the bot's Discord setup: who the token logs in as, whether it can see the test server,
which channels exist and which intents are enabled. Never prints the token.

    python bot/tools/check_discord.py
"""
import json
import os
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = "https://discord.com/api/v10"


def env():
    vals = {}
    with open(os.path.join(ROOT, ".secrets", "discord.env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals["DISCORD_BOT_TOKEN"], vals["DISCORD_GUILD_ID"]


def get(path, token):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bot {token}",
                                                      "User-Agent": "TorchSetupCheck (office-survivor, 0.1)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


if __name__ == "__main__":
    token, guild = env()
    status, me = get("/users/@me", token)
    print(f"login: {status} " + (f"as {me.get('username')} (bot={me.get('bot')}, id={me.get('id')})" if status == 200 else str(me)))
    status, app = get("/applications/@me", token)
    if status == 200:
        flags = app.get("flags", 0)
        print(f"intents: members={'on' if flags & (1 << 15 | 1 << 14) else 'off'}, "
              f"message content={'on' if flags & (1 << 19 | 1 << 18) else 'off'}")
    status, g = get(f"/guilds/{guild}", token)
    print(f"server: {status} " + (f"'{g.get('name')}'" if status == 200 else str(g)))
    if status == 200:
        status, chans = get(f"/guilds/{guild}/channels", token)
        names = sorted(c["name"] for c in chans if c.get("type") == 0) if status == 200 else chans
        print(f"text channels: {names}")
        wanted = {"town-square", "news", "radio"}
        print(f"missing game channels: {sorted(wanted - set(names)) if status == 200 else '?'}")
