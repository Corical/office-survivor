"""Drive the real client: a real window, real taps, a real arena server, a whole game, screenshots.

    python godot/tools/drive.py [--out DIR]

Starts a local arena server (20 s rounds), opens the client window, plays all 10 rounds by tapping buttons with real
mouse events, then prints a summary. A window appears on screen for the length of the game. Exit code 0 only on
"DRIVE PASS". Screenshots go to --out (default: a temp folder, printed at the end).
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
GODOT = os.path.join(ROOT, "godot")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "drive-shots"))
    out = ap.parse_args().out
    os.makedirs(out, exist_ok=True)
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="drive-")
    srv = subprocess.Popen([sys.executable, "-m", "arena.server", "--data", os.path.join(tmp, "data"), "--port",
                            str(port), "--timer", "20"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t0 = time.time()
        while time.time() - t0 < 15:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.2)
        else:
            print("DRIVE FAIL: the arena server did not start")
            return 1
        r = subprocess.run(["godot_console", "--path", GODOT, "res://themes/flash/tools_snapshot/drive_flash.tscn", "--",
                            "--server=ws://127.0.0.1:%d" % port, "--out=" + out, "--log=" + os.path.join(tmp, "drive.log")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=480)
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("DRIVE", "  ", "shot"))))
        print("\n".join(l for l in r.stderr.splitlines() if "DRIVE problem" in l))
        print("screenshots:", out)
        return r.returncode
    finally:
        srv.terminate()


if __name__ == "__main__":
    sys.exit(main())
