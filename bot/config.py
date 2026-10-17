"""Where Torch reads its settings: game.json (rules, aliases, bot name), an env file (token, guild, GMs), env vars.

Env file (default .secrets/discord.env, on the Pi /etc/torch/torch.env):
  DISCORD_BOT_TOKEN=…   DISCORD_GUILD_ID=…   TORCH_GM_IDS=id,id (optional; the server owner is always GM)
Env vars: TORCH_ENV (env file path), TORCH_DATA (data folder, default bot/data), TORCH_GAME (game.json path).
"""
import json
import os
from dataclasses import dataclass, fields

from engine import Rules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_env(path):
    vals = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


@dataclass
class Config:
    token: str
    guild_id: int
    gm_ids: set
    data_dir: str
    rules: Rules
    aliases: list
    bot_name: str
    bot_emoji: str
    category: str = "Survivors"


def load():
    env = read_env(os.environ.get("TORCH_ENV", os.path.join(ROOT, ".secrets", "discord.env")))
    game = json.load(open(os.environ.get("TORCH_GAME", os.path.join(ROOT, "docs", "game.json")), encoding="utf-8"))
    known = {f.name for f in fields(Rules)}
    rules = Rules(**{k: v for k, v in game.get("rules", {}).items() if k in known})
    pres = game.get("presentation", {})
    aliases = pres.get("aliases") or pres.get("example_names") or []
    if len(aliases) < 20:
        import sys
        sys.path.insert(0, os.path.join(ROOT, "docs", "sim"))
        from survivors_sim import NAMES
        aliases = list(dict.fromkeys(list(aliases) + NAMES))
    return Config(token=env["DISCORD_BOT_TOKEN"], guild_id=int(env["DISCORD_GUILD_ID"]),
                  gm_ids={int(x) for x in env.get("TORCH_GM_IDS", "").split(",") if x.strip()},
                  data_dir=os.environ.get("TORCH_DATA", os.path.join(ROOT, "bot", "data")),
                  rules=rules, aliases=aliases, bot_name=pres.get("bot_name", "Torch"),
                  bot_emoji=pres.get("bot_emoji", "🔥"))
