"""Create (or repair) the game's Discord channels. Idempotent: only adds what is missing.

Category "Survivors" with #town-square, #news and #radio:
- people can see the category; every other bot's integration role is denied View Channel (keeps capture
  bots such as Grysstof and any agents out of the game)
- #news and #radio: people can read but not post; Torch posts there (radio messages go through Torch so
  they stay anonymous)
- Torch itself is allowed view + send everywhere in the category

    python bot/tools/setup_channels.py            # show what it would do
    python bot/tools/setup_channels.py --apply    # do it
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_discord import API, env  # noqa: E402

VIEW, SEND, HISTORY = 1 << 10, 1 << 11, 1 << 16
PIN = 1 << 51            # PIN_MESSAGES: Torch pins its status board in #news (owner granted it there, 17 Oct 2026)
CATEGORY, TEXT = 4, 0
CHANNELS = [("town-square", "The open room: chat, bluff, ally and accuse as yourself. Play your moves here with "
                            "/scavenge, /steal, /guard, /investigate, /gift; Torch answers only you. Trust no one.", False),
            ("news", "The official record. Every morning Torch posts what happened overnight: robberies, catches, "
                     "exposures, who ran out of food. Who did what stays secret until the final reveal.", True),
            ("radio", "Anonymous whispers. Send one message a day with /radio and Torch posts it with the morning "
                      "news, with no name attached. Tips, accusations, lies: believe at your own risk.", True)]


def call(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": f"Bot {token}", "Content-Type": "application/json",
                                          "User-Agent": "TorchSetup (office-survivor, 0.1)",
                                          "X-Audit-Log-Reason": "Survivors game channels"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path}: {e.code} {e.read().decode()[:300]}")


def main(apply):
    token, guild = env()
    me = call("GET", "/users/@me", token)
    roles = call("GET", f"/guilds/{guild}/roles", token)
    other_bots = [r for r in roles if r.get("managed") and r.get("tags", {}).get("bot_id") not in (None, me["id"])]
    # A bot invited without permissions has no role, so deny bot *members* too, not only bot roles.
    members = call("GET", f"/guilds/{guild}/members?limit=1000", token)
    bot_members = [m["user"] for m in members if m["user"].get("bot") and m["user"]["id"] != me["id"]]
    everyone = guild  # the @everyone role has the guild's id
    base = [{"id": me["id"], "type": 1, "allow": str(VIEW | SEND | HISTORY), "deny": "0"}]
    base += [{"id": r["id"], "type": 0, "allow": "0", "deny": str(VIEW)} for r in other_bots]
    base += [{"id": u["id"], "type": 1, "allow": "0", "deny": str(VIEW)} for u in bot_members]
    print(f"Torch: {me['username']} | bot roles denied: {[r['name'] for r in other_bots] or 'none'} | "
          f"bot members denied: {sorted(u['username'] for u in bot_members) or 'none'}")

    chans = call("GET", f"/guilds/{guild}/channels", token)
    cat = next((c for c in chans if c["type"] == CATEGORY and c["name"].lower() == "survivors"), None)
    if not cat:
        print("create category Survivors")
        if apply:
            cat = call("POST", f"/guilds/{guild}/channels", token, {"name": "Survivors", "type": CATEGORY, "permission_overwrites": base})
    else:
        print(f"category Survivors exists ({cat['id']}); permissions reset to the standard set")
        if apply:
            call("PATCH", f"/channels/{cat['id']}", token, {"permission_overwrites": base})
    for name, topic, read_only in CHANNELS:
        over = list(base) + ([{"id": everyone, "type": 0, "allow": "0", "deny": str(SEND)}] if read_only else [])
        if name == "news":     # keep the pin right; leaving it out would quietly take it away again
            over[0] = {**over[0], "allow": str(VIEW | SEND | HISTORY | PIN)}
        existing = next((c for c in chans if c["type"] == TEXT and c["name"] == name and cat and c.get("parent_id") == cat.get("id")), None)
        body = {"name": name, "type": TEXT, "topic": topic, "permission_overwrites": over}
        if existing:
            print(f"#{name} exists; permissions and topic reset")
            if apply:
                call("PATCH", f"/channels/{existing['id']}", token, {"topic": topic, "permission_overwrites": over})
        else:
            print(f"create #{name}" + (" (people read-only)" if read_only else ""))
            if apply:
                call("POST", f"/guilds/{guild}/channels", token, {**body, "parent_id": cat["id"]})
    if not apply:
        print("dry run: nothing changed. Run with --apply to do it.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
