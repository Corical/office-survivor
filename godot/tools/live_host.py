"""The second human in a live two-client game: creates a room, waits for the Godot client to join, starts the game and
plays varied legal moves (steal, gift, investigate, guard, scavenge, radio) to the end.

    python godot/tools/live_host.py --server ws://127.0.0.1:8791 [--seed 7]

Prints "ROOM <code>" as soon as the room exists (the runner passes it to Godot), then "HOST DONE ..." at the end.
Exit code 0 only if the game reached its `end` view. Needs `websockets`.
"""
import argparse
import asyncio
import json
import random
import sys

import websockets

UNTARGETED = ("scavenge", "guard")


async def play(url, seed):
    rng = random.Random(seed)
    codes, kinds_used, radios = set(), {}, 0
    started, picked, continued = False, set(), set()
    async with websockets.connect(url, max_size=1 << 20) as ws:
        async def send(**m):
            await ws.send(json.dumps(m))

        await send(t="hello", proto=1, client_build="live-host")
        async for raw in ws:
            m = json.loads(raw)
            t = m["t"]
            if t == "hello_ok":
                await send(t="create_room")
            elif t == "seat":
                print("ROOM", m["room_code"], flush=True)
            elif t == "lobby":
                if m["host"] and m["seats_taken"] >= 2 and not started:
                    started = True
                    await send(t="start")
            elif t == "round":
                r = m["round"]
                if r in picked or m["my_locked"]:
                    continue
                picked.add(r)
                legal = {k: v for k, v in m["legal"].items() if k in UNTARGETED or v}
                if "gift" in legal and not m["gift_amounts"]:
                    del legal["gift"]
                kind = rng.choice(sorted(legal))
                target = rng.choice(legal[kind]) if legal[kind] else None
                amount = rng.choice(m["gift_amounts"]) if kind == "gift" else 0
                kinds_used[kind] = kinds_used.get(kind, 0) + 1
                await send(t="pick", kind=kind, target=target, amount=amount)
                if m["radio_available"] and rng.random() < 0.6:
                    phrase = rng.choice(m["radio_phrases"])
                    about = rng.choice(m["aliases"]) if phrase["needs_player"] and m["aliases"] else None
                    await send(t="radio", phrase=phrase["key"], about=about)
                    radios += 1
                await send(t="lock")
            elif t == "reveal":
                for part in ("news", "private"):
                    for ln in m[part]:
                        codes.add(ln["code"])
                if m["round"] not in continued:
                    continued.add(m["round"])
                    await send(t="continue")
            elif t == "end":
                print("HOST DONE rounds=%d moves=%s radios=%d codes=%d" % (len(picked), json.dumps(kinds_used,
                      sort_keys=True), radios, len(codes)), flush=True)
                return 0
            elif t == "error":
                print("HOST error", m, flush=True)
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    sys.exit(asyncio.run(play(a.server, a.seed)))
