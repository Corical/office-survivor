"""End-to-end smoke test of a running Arena over its real WebSocket: one human, three bots, a whole 10-round game, a drop
and resume at round 5, and the error paths. Needs only the `websockets` package, no Godot.

    python -m arena.tools.smoke wss://raspberrypi.tail87b476.ts.net:8470      # the Pi, from a tailnet machine
    python -m arena.tools.smoke ws://127.0.0.1:8765                           # a local server

It leaves one finished room behind (a folder under the server's data/rooms). On the Pi that is /var/lib/arena/rooms/<CODE>;
the printed room code says which. Remove test rooms with the service stopped, never by hand while it runs.
"""
import asyncio
import json
import sys
import time

from websockets.asyncio.client import connect

URL = sys.argv[1]


async def open_client():
    ws = await connect(URL, max_size=None, open_timeout=15)
    await ws.send(json.dumps({"t": "hello", "proto": 1, "client_build": "smoke"}))
    assert json.loads(await ws.recv())["t"] == "hello_ok"
    return ws


async def until(ws, t, pred=lambda m: True, timeout=60):
    end = time.time() + timeout
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, end - time.time())))
        if m["t"] == t and pred(m):
            return m
        if m["t"] == "error" and t != "error":
            raise RuntimeError(f"unexpected error: {m}")


async def main():
    t0 = time.time()
    rows = []
    ws = await open_client()
    rows.append(("connected over tailnet wss", f"{time.time() - t0:.2f}s"))
    await ws.send(json.dumps({"t": "create_room"}))
    seat = await until(ws, "seat")
    await until(ws, "lobby")
    rows.append(("room created", f"code {seat['room_code']}, alias {seat['alias']}, host={seat['host']}"))
    await ws.send(json.dumps({"t": "start"}))
    reconnected = False
    for n in range(1, 11):
        r = await until(ws, "round", lambda m: not m["my_locked"])
        if n == 1:
            rows.append(("round 1", f"{r['seconds_left']}s left, {len(r['legal'])} move kinds, {len(r['aliases'])} others"))
        kind = "scavenge" if "scavenge" in r["legal"] else sorted(r["legal"])[0]
        tgt = r["legal"][kind][0] if r["legal"][kind] else None
        await ws.send(json.dumps({"t": "pick", "kind": kind, "target": tgt, "amount": 0}))
        await ws.send(json.dumps({"t": "lock"}))
        if n == 5 and not reconnected:               # drop the connection mid-game and come back with the token
            await until(ws, "reveal", lambda m: m["round"] == 5)
            await ws.close()
            ws = await open_client()
            await ws.send(json.dumps({"t": "resume", "token": seat["token"]}))
            again = await until(ws, "seat")
            assert again["alias"] == seat["alias"]
            reconnected = True
            rows.append(("reconnect after round 5", "same alias, game continues"))
        else:
            await until(ws, "reveal", lambda m, n=n: m["round"] == n)
        await ws.send(json.dumps({"t": "continue"}))
    end = await until(ws, "end")
    rows.append(("game finished", f"{len(end['results'])} players, winners {end['winners']}, took {time.time() - t0:.0f}s"))
    # error paths
    await ws.send(json.dumps({"t": "fly_to_the_moon"}))
    rows.append(("unknown message", (await until(ws, "error"))["message"]))
    await ws.close()
    bad = await open_client()
    await bad.send(json.dumps({"t": "join_room", "code": "ZZZZ"}))
    rows.append(("unknown room", (await until(bad, "error"))["message"]))
    await bad.close()
    print(json.dumps({"room": seat["room_code"], "rows": rows}, ensure_ascii=False))


asyncio.run(main())
