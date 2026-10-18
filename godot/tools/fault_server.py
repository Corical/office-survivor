"""A scripted server that misbehaves on purpose, to prove how the Godot client's REAL WebSocket path copes.

    python godot/tools/fault_server.py --mode burst_seat_gone --port 8792

Modes (the client sends hello first in every mode):
  burst_seat_gone     hello_ok, then an `error seat_gone` and close(4001) in the same instant
  burst_upgrade       `upgrade_required` and close(4002) in the same instant (no hello_ok)
  taken_over_1000     hello_ok, seat, `error taken_over`, close(1000): what the server does today
  oversize            hello_ok, then one 70,000-byte frame (the client's buffer is 64 KB)
  halfopen            hello_ok, then silence for every later message (a dead network path)
  slow_hello          accepts the connection and never answers hello
Prints one line per connection: "conn <n> mode=<mode>", so a runner can count reconnects.
"""
import argparse
import asyncio
import json
import sys

from websockets.asyncio.server import serve

conns = 0


async def handler(ws, mode):
    global conns
    conns += 1
    n = conns
    print(f"conn {n} mode={mode}", flush=True)
    try:
        hello = json.loads(await ws.recv())
        if hello.get("t") != "hello":
            return
        if mode == "slow_hello":
            await asyncio.sleep(60)
            return
        if mode == "burst_upgrade":
            await ws.send(json.dumps({"t": "upgrade_required", "min_proto": 2, "message": "update"}))
            await ws.close(4002, "upgrade_required")
            return
        await ws.send(json.dumps({"t": "hello_ok", "proto": 1}))
        if mode == "burst_seat_gone":
            await ws.recv()                                    # the client's resume
            await ws.send(json.dumps({"t": "error", "code": "seat_gone", "message": "That seat no longer exists."}))
            await ws.close(4001, "seat_gone")
        elif mode == "taken_over_1000":
            await ws.recv()
            await ws.send(json.dumps({"t": "seat", "token": "t", "room_code": "ABCD", "alias": "Mango", "host": True}))
            await ws.send(json.dumps({"t": "error", "code": "taken_over", "message": "Opened on another device."}))
            await ws.close(1000)
        elif mode == "oversize":
            await ws.recv()
            await ws.send(json.dumps({"t": "lobby", "room_code": "ABCD", "seats_taken": 1, "seats_total": 4,
                                      "host": True, "pad": "x" * 70000}))
            await asyncio.sleep(5)
        elif mode == "halfopen":
            async for _ in ws:
                pass                                           # read and never answer
    except Exception as e:                                     # a closed connection is the normal end here
        print(f"conn {n} ended: {type(e).__name__}", flush=True)


async def main(mode, port):
    async with serve(lambda ws: handler(ws, mode), "127.0.0.1", port):
        print(f"fault server {mode} on {port}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--port", type=int, default=8792)
    a = ap.parse_args()
    try:
        asyncio.run(main(a.mode, a.port))
    except KeyboardInterrupt:
        sys.exit(0)
