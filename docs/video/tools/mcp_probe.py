import json, subprocess, sys

def probe(spec):
    exe, *extra = spec.split("|")
    p = subprocess.Popen([exe, "mcp", *extra], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    def send(o):
        p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()
    def recv():
        while True:
            line = p.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}}})
    init = recv()
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = recv()
    p.kill()
    name = init["result"]["serverInfo"]
    names = [t["name"] for t in tools["result"]["tools"]]
    backend = [l for l in init["result"].get("instructions", "").split(". ") if "Backend" in l or "bridge" in l.lower()][:1]
    print(f"{exe.split(chr(92))[-1]} {' '.join(extra)}: server={name['name']} tools={len(names)} | {backend}")

for exe in sys.argv[1:]:
    try:
        probe(exe)
    except Exception as e:
        print(exe, "FAILED", repr(e))
