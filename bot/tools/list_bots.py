"""List every bot account that is a member of the test server (needs the Server Members intent). Read-only.

    python bot/tools/list_bots.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_discord import env, get  # noqa: E402

token, guild = env()
status, members = get(f"/guilds/{guild}/members?limit=1000", token)
if status != 200:
    raise SystemExit(f"members: {status} {members}")
bots = sorted((m["user"]["username"], len(m.get("roles", []))) for m in members if m["user"].get("bot"))
print(f"{len(members)} members, {len(bots)} bots:")
for name, nroles in bots:
    print(f"  {name} (roles: {nroles})")
