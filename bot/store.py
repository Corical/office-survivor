"""Storage ports and their default implementations.

EventStore: append-only records, one JSON object per line, fsync per append. A torn last line (power cut mid-write)
is cut off on load and reported. IdentityStore: who is who, kept apart from the game log (decision 17).
TextStore: radio and DM bodies by reference, so the log never holds them and they can be redacted.
"""
import json
import logging
import os

log = logging.getLogger("torch.store")


class MemoryEventStore:
    def __init__(self):
        self.records = []

    def load(self):
        return list(self.records)

    def append(self, rec):
        self.records.append(json.loads(json.dumps(rec)))   # same round trip as the file store


class JsonlEventStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def load(self):
        if not os.path.exists(self.path):
            return []
        out, good_bytes = [], 0
        with open(self.path, "rb") as f:
            data = f.read()
        for line in data.splitlines(keepends=True):
            try:
                out.append(json.loads(line))
                good_bytes += len(line)
            except json.JSONDecodeError:
                log.warning("torn record at byte %d of %s: cut off (%d bytes)", good_bytes, self.path,
                            len(data) - good_bytes)
                with open(self.path, "r+b") as f:
                    f.truncate(good_bytes)
                break
        log.info("loaded %d records from %s", len(out), self.path)
        return out

    def append(self, rec):
        line = (json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        with open(self.path, "ab") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        log.debug("appended %s", rec.get("type"))


class JsonFileMap:
    """A small key -> value map saved atomically (write temp, then replace). Mode 0600 where supported."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


class IdentityStore(JsonFileMap):
    """user key (Discord id, or 'sim:N') -> {"pid": int, "alias": str, "sim": bool}."""

    def get(self, key):
        return self.data.get(str(key))

    def put(self, key, pid, alias, sim=False):
        self.data[str(key)] = {"pid": pid, "alias": alias, "sim": sim}
        self.save()

    def key_for(self, pid):
        return next((k for k, v in self.data.items() if v["pid"] == pid), None)

    def remove(self, key):
        if self.data.pop(str(key), None) is not None:
            self.save()


class TextStore(JsonFileMap):
    def put(self, ref, text):
        self.data[ref] = text
        self.save()

    def get(self, ref):
        return self.data.get(ref)


class MemoryMap(JsonFileMap):
    def __init__(self):
        self.path, self.data = None, {}

    def save(self):
        pass


class MemoryIdentityStore(MemoryMap, IdentityStore):
    pass


class MemoryTextStore(MemoryMap, TextStore):
    pass
