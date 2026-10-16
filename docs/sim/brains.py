"""
Smarter decision-makers for the Survivors simulator.

The default players follow fixed personality odds and never learn. These
brains replace that for some or all players:

  adaptive  free and offline. Each player starts from their personality's odds
            and shifts toward the moves that paid off for them so far.
  jev       TypeSafe's Jev (a System One model). Each night every smart player
            describes their situation in plain text and Jev picks one move from
            the legal options, returning a probability for each option. Costs
            money and needs an API key (TYPESAFE_API_KEY), so use it on small
            runs. --jev-mock exercises the same code path offline.

Jev wire format (TypeSafe System One API, as documented by LiteLLM's
pass-through docs, Oct 2026 - verify against TypeSafe's own API reference):
  POST {TYPESAFE_API_BASE or https://api.typesafe.ai}/v1/systemone
  {"model": "jev-latest", "state": "<text>",
   "questions": {"move": {"type": "choice", "instructions": "...",
                          "criteria": {"<option>": "<description>", ...}}}}
  -> {"model": "jev-1.x.y", "answers": {"move": {"type": "choice",
       "choice": "<option>", "probabilities": {...}, "confidence": 0.8}},
      "usage": {"input_tokens": N, "output_tokens": M}}
"""

import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

KINDS = ("scavenge", "steal", "guard", "investigate", "gift")
JEV_PRICE_PER_M_INPUT = 0.042   # USD per million input tokens, from TypeSafe's launch post; check current pricing


class AdaptiveBrain:
    """Learns per player: moves that gained rations become more likely (multiplicative weights)."""

    name = "adaptive"

    def __init__(self, arch_table, eta=0.35, floor=0.03):
        self.arch = arch_table
        self.eta = eta
        self.floor = floor
        self.w = {}

    def _weights(self, p):
        if p.pid not in self.w:
            prior = dict(zip(KINDS, self.arch[p.arch]["w"]))
            if sum(prior.values()) == 0:                 # pure test personalities: start even
                prior = {k: 1.0 for k in KINDS}
            self.w[p.pid] = {k: max(v, self.floor) for k, v in prior.items()}
        return self.w[p.pid]

    def decide_many(self, g, players):
        out = {}
        for p in players:
            opts = g.options_for(p)
            kinds = sorted({o["kind"] for o in opts})
            w = self._weights(p)
            kind = g.rng.choices(kinds, weights=[w.get(k, self.floor) for k in kinds])[0]
            out[p.pid] = g.action_from_kind(p, kind)
        return out

    def after_night(self, g, acts, start, start_bandit):
        for pid, a in acts.items():
            p = g.P(pid)
            if pid not in self.w or a[3]:
                continue                                  # not ours, or they missed the deadline
            # what the move itself earned: change in rations, not counting the night's meal
            reward = p.rations - start[pid] + (0 if start_bandit[pid] else g.r.eat)
            w = self.w[pid]
            w[a[0]] = min(50.0, max(self.floor, w[a[0]] * math.exp(self.eta * reward)))
            total = sum(w.values())
            for k in w:
                w[k] = max(self.floor, w[k] / total * len(w))


class JevBrain:
    """Asks Jev for each smart player's move. Thread-pooled per night; sampling happens on the game's RNG."""

    name = "jev"

    def __init__(self, arch_table, model="jev-latest", api_key=None, base=None, mock=False,
                 max_calls=3000, sample=True, workers=16, timeout=20.0):
        self.arch = arch_table
        self.model = model
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self.base = (base or os.environ.get("TYPESAFE_API_BASE") or "https://api.typesafe.ai").rstrip("/")
        self.mock = mock
        self.max_calls = max_calls
        self.sample = sample
        self.workers = workers
        self.timeout = timeout
        self.calls = 0
        self.input_tokens = 0
        self.seconds = 0.0
        self.versions = set()
        self.last = {}
        self._lock = threading.Lock()
        if not mock and not self.api_key:
            raise SystemExit("Jev brain needs TYPESAFE_API_KEY in the environment (or use --jev-mock to test offline).")

    # ---- transport
    def _post(self, payload):
        if self.mock:
            return self._mock_response(payload)
        req = urllib.request.Request(
            f"{self.base}/v1/systemone", data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST")
        delay = 1.0
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise SystemExit(f"Jev API error {e.code}: {body}")
            except urllib.error.URLError as e:
                if attempt < 3:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise SystemExit(f"Can't reach Jev at {self.base}: {e.reason}")

    def _mock_response(self, payload):
        """Offline stand-in: favours options in proportion to the personality odds written into the state."""
        crit = payload["questions"]["move"]["criteria"]
        prior = payload.get("metadata", {}).get("prior", {})
        raw = {k: max(0.02, prior.get(k.split(":")[0], 0.2)) / max(1, sum(1 for o in crit if o.split(":")[0] == k.split(":")[0]))
               for k in crit}
        total = sum(raw.values())
        probs = {k: v / total for k, v in raw.items()}
        choice = max(probs, key=probs.get)
        return {"model": "jev-mock", "answers": {"move": {"type": "choice", "choice": choice,
                                                         "probabilities": probs, "confidence": probs[choice]}},
                "usage": {"input_tokens": len(payload["state"]) // 4 + 20 * len(crit), "output_tokens": 0}}

    # ---- one player
    def _ask(self, state, options, prior):
        with self._lock:
            if self.calls >= self.max_calls:
                raise SystemExit(f"Stopped: Jev call cap of {self.max_calls} reached. Raise --max-calls to go further.")
            self.calls += 1
        payload = {
            "model": self.model,
            "state": state,
            "questions": {"move": {
                "type": "choice",
                "instructions": ("You are deciding for the player described in the state. Which single move would "
                                 "this person most plausibly make tonight, given their personality, secret goal, "
                                 "rations and everything they know? Play to win, the way a real colleague would."),
                "criteria": {o["key"]: o["desc"] for o in options}}},
            "metadata": {"prior": prior},
        }
        t0 = time.time()
        resp = self._post(payload)
        ans = resp["answers"]["move"]
        probs = ans.get("probabilities") or {ans["choice"]: 1.0}
        with self._lock:
            self.seconds += time.time() - t0
            self.input_tokens += int(resp.get("usage", {}).get("input_tokens", 0))
            self.versions.add(resp.get("model", "?"))
        return {k: float(v) for k, v in probs.items() if k in {o["key"] for o in options}} or {ans["choice"]: 1.0}

    def decide_many(self, g, players):
        jobs = []
        for p in players:
            opts = g.options_for(p)
            prior = dict(zip(KINDS, self.arch[p.arch]["w"]))
            jobs.append((p, opts, g.observation(p), prior))
        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(jobs)))) as ex:
            results = list(ex.map(lambda j: self._ask(j[2], j[1], j[3]), jobs))
        out = {}
        for (p, opts, _, _), probs in zip(jobs, results):        # sample in pid order, on the game RNG
            keys = sorted(probs)
            if self.sample:
                key = g.rng.choices(keys, weights=[probs[k] for k in keys])[0]
            else:
                key = max(keys, key=lambda k: probs[k])
            self.last[p.pid] = f"{key} (p={probs[key]:.2f})"
            out[p.pid] = g.action_from_key(p, key)
        return out

    def after_night(self, g, acts, start, start_bandit):
        pass

    def report(self):
        cost = self.input_tokens / 1e6 * JEV_PRICE_PER_M_INPUT
        avg = self.seconds / self.calls if self.calls else 0
        return (f"Jev: {self.calls} calls, {self.input_tokens:,} input tokens, about ${cost:.4f} "
                f"at ${JEV_PRICE_PER_M_INPUT}/M input, {avg * 1000:.0f} ms average per call, "
                f"models: {', '.join(sorted(self.versions)) or '-'}{' (MOCK)' if self.mock else ''}")


def make_brain_factory(kind, arch_table, **jev_kwargs):
    """Returns a function giving a fresh brain per game (adaptive keeps per-game memory), or None for rules."""
    if kind in (None, "rules"):
        return None
    if kind == "adaptive":
        return lambda: AdaptiveBrain(arch_table)
    if kind == "jev":
        shared = JevBrain(arch_table, **jev_kwargs)   # one client, so call counts and costs add up across games
        def factory():
            shared.last = {}
            return shared
        factory.shared = shared
        return factory
    raise SystemExit(f"Unknown brain '{kind}'. Use rules, adaptive or jev.")
