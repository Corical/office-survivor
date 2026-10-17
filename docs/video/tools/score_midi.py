"""Stage 5 music: a generated score, timed from build/scenes.json, played by SoundCraft's built-in synths.

Writes work/music/score.mid (format 1, 96 bpm): track 1 a low eighth-note bass pulse (A A F G) under the
voice, track 2 a quiet kick/hat heartbeat on GM drum notes. Following style.audio.music, the bed cuts out
at the scene 13 drumroll, the drums play a snare roll into a crash on the curtain, and the bed comes back
for scene 14 and fades out at the end. Standard library only.

    python tools/score_midi.py
"""
import json
import os
import struct

VIDEO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = json.load(open(os.path.join(VIDEO, "build", "scenes.json"), encoding="utf-8"))
SC = {s["id"]: s for s in BUILD["scenes"]}
TOTAL = BUILD["total_duration_s"]
BPM, PPQ = 96, 480
TICKS_PER_S = BPM / 60 * PPQ
KICK, SNARE, HAT, CRASH = 36, 38, 42, 49

s13, s14 = SC["scene_13"], SC["scene_14"]
DRUMROLL = s13["start_s"] + s13["beats"][3]["at_s"]   # "MUSIC CUT. Drumroll."
CURTAIN = s13["start_s"] + s13["beats"][4]["at_s"]    # curtain pulls open
RESUME = s14["start_s"]


def tick(t):
    return int(round(t * TICKS_PER_S))


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def track(events, name):
    """events: (tick, kind, a, b, ch) with kind 'on'/'off'. Returns an MTrk chunk."""
    data = b"\x00\xff\x03" + vlq(len(name)) + name.encode()
    now = 0
    for t, kind, note, vel, ch in sorted(events, key=lambda e: (e[0], e[1] == "on")):
        status = (0x90 if kind == "on" else 0x80) | ch
        data += vlq(t - now) + bytes([status, note, vel])
        now = t
    data += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + data


def note(events, t0, length_ticks, pitch, vel, ch):
    events.append((t0, "on", pitch, max(1, min(127, vel)), ch))
    events.append((t0 + length_ticks, "off", pitch, 0, ch))


def bed_spans():
    return [(0.0, DRUMROLL), (RESUME, TOTAL)]


def bass():
    ev, eighth, bar = [], PPQ // 2, PPQ * 4
    roots = [33, 33, 29, 31]  # A1 A1 F1 G1
    for a, b in bed_spans():
        t, end = tick(a), tick(b)
        fade_in, fade_out = (tick(a) + bar * 2, end - bar * 2) if b == TOTAL else (tick(a) + bar * 2, end)
        while t + eighth <= end:
            root = roots[(t // bar) % 4]
            v = 92 if (t // eighth) % 2 == 0 else 70
            if t < fade_in and a == 0:
                v = int(v * (0.35 + 0.65 * (t - tick(a)) / (fade_in - tick(a))))
            if b == TOTAL and t > fade_out:
                v = int(v * max(0.1, (end - t) / (end - fade_out)))
            note(ev, t, eighth - 40, root, v, 0)
            t += eighth
    return ev


def drums():
    ev, beat = [], PPQ
    for a, b in bed_spans():
        t, end = tick(a) + beat * 4, tick(b)   # one bar of bass alone, then the heartbeat
        while t + beat <= end:
            note(ev, t, 120, KICK, 64, 9)
            note(ev, t + beat // 2, 60, HAT, 34, 9)
            t += beat
    t, end, n = tick(DRUMROLL), tick(CURTAIN), 0
    steps = max(1, (end - t) // 60)
    while t < end:
        note(ev, t, 50, SNARE, 40 + int(80 * n / steps), 9)
        t += 60
        n += 1
    note(ev, tick(CURTAIN), 960, CRASH, 112, 9)
    note(ev, tick(CURTAIN), 240, KICK, 110, 9)
    return ev


if __name__ == "__main__":
    tempo = b"\x00\xff\x51\x03" + (60_000_000 // BPM).to_bytes(3, "big") + b"\x00\xff\x58\x04\x04\x02\x18\x08" + b"\x00\xff\x2f\x00"
    chunks = [b"MTrk" + struct.pack(">I", len(tempo)) + tempo, track(bass(), "Bass"), track(drums(), "Drums")]
    out = os.path.join(VIDEO, "work", "music", "score.mid")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ))
        f.write(b"".join(chunks))
    print(f"{out}: bed 0-{DRUMROLL:.1f}s and {RESUME:.1f}-{TOTAL:.1f}s, drumroll {DRUMROLL:.1f}-{CURTAIN:.1f}s, crash {CURTAIN:.1f}s")
