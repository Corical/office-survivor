"""Run the live tests: the Godot client's real WebSocket path against a real arena server and the fault server.

    python godot/tools/run_live_tests.py [--only game|faults]

Starts what it needs on free local ports, runs godot headless for each scenario (120 s cap each), stops everything.
Needs: godot_console on PATH, the project imported (`godot --headless --path godot --import`), `websockets`.
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GODOT_DIR = os.path.join(ROOT, "godot")
FAULT_MODES = ["burst_seat_gone", "burst_upgrade", "taken_over_1000", "oversize", "halfopen", "slow_hello"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, seconds=15):
    t0 = time.time()
    while time.time() - t0 < seconds:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def godot(scene, args, log):
    r = subprocess.run(["godot_console", "--headless", "--path", GODOT_DIR, scene, "--", *args, "--log=" + log],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout


def run_varied(tmp):
    """Two humans: a Python host plays varied moves; the Godot client joins, varies its moves, drops once, resumes."""
    port = free_port()
    env = dict(os.environ, ARENA_TIMER="20")
    srv = subprocess.Popen([sys.executable, "-m", "arena.server", "--data", os.path.join(tmp, "data2"),
                            "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    host = None
    try:
        if not wait_port(port):
            print("LIVE2 FAIL: the arena server did not start")
            return 1
        url = "ws://127.0.0.1:%d" % port
        host = subprocess.Popen([sys.executable, os.path.join(GODOT_DIR, "tools", "live_host.py"), "--server", url],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace")
        room = ""
        for line in host.stdout:                   # the first line the host prints is the room code
            if line.startswith("ROOM "):
                room = line.split()[1]
                break
        if not room:
            print("LIVE2 FAIL: the host never created a room")
            return 1
        code, out = godot("res://tests/live/live_varied.tscn", ["--server=" + url, "--join=" + room, "--drop-at=4"],
                          os.path.join(tmp, "varied.log"))
        print("\n".join(l for l in out.splitlines() if l.startswith(("LIVE2", "  "))))
        try:
            rest, _ = host.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            host.kill()
            rest = "(host did not finish)"
        host_line = [l for l in rest.splitlines() if l.startswith("HOST")]
        print("\n".join(host_line) or "HOST: no summary line")
        return 0 if code == 0 and host.returncode == 0 else 1
    finally:
        if host and host.poll() is None:
            host.kill()
        srv.terminate()


def run_rooms(tmp):
    """The open-camps list against a real arena server. A server that cannot list camps makes the scene print SKIP and
    still pass (the old-server promise); one that can must give a clean list and accept a named public create."""
    port = free_port()
    env = dict(os.environ, ARENA_TIMER="20")
    srv = subprocess.Popen([sys.executable, "-m", "arena.server", "--data", os.path.join(tmp, "data3"), "--port",
                            str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(port):
            print("LIVE3 FAIL: the arena server did not start")
            return 1
        code, out = godot("res://tests/live/live_rooms.tscn", ["--server=ws://127.0.0.1:%d" % port],
                          os.path.join(tmp, "rooms.log"))
        print("\n".join(l for l in out.splitlines() if l.startswith(("LIVE3", "  "))))
        return 0 if code == 0 else 1
    finally:
        srv.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["game", "faults", "varied", "rooms"])
    only = ap.parse_args().only
    tmp = tempfile.mkdtemp(prefix="live-")
    failed = 0
    if only in (None, "varied"):
        failed += run_varied(tmp)
    if only in (None, "rooms"):
        failed += run_rooms(tmp)
    if only in (None, "game"):
        port = free_port()
        env = dict(os.environ, ARENA_TIMER="20")
        srv = subprocess.Popen([sys.executable, "-m", "arena.server", "--data", os.path.join(tmp, "data"),
                                "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        try:
            if not wait_port(port):
                print("LIVE FAIL: the arena server did not start")
                failed += 1
            else:
                code, out = godot("res://tests/live/live_game.tscn", ["--server=ws://127.0.0.1:%d" % port],
                                  os.path.join(tmp, "game.log"))
                print("\n".join(l for l in out.splitlines() if l.startswith(("LIVE", "  "))))
                failed += code != 0
        finally:
            srv.terminate()
    if only in (None, "faults"):
        for mode in FAULT_MODES:
            port = free_port()
            srv = subprocess.Popen([sys.executable, os.path.join(GODOT_DIR, "tools", "fault_server.py"),
                                    "--mode", mode, "--port", str(port)], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
            try:
                if not wait_port(port):
                    print("FAULT %s FAIL: server did not start" % mode)
                    failed += 1
                    continue
                code, out = godot("res://tests/live/live_fault.tscn",
                                  ["--server=ws://127.0.0.1:%d" % port, "--mode=" + mode],
                                  os.path.join(tmp, mode + ".log"))
                print("\n".join(l for l in out.splitlines() if l.startswith(("FAULT", "  "))))
                failed += code != 0
            finally:
                srv.terminate()
    print("\nlive tests:", "ALL PASS" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
