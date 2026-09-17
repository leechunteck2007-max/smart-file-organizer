from pathlib import Path
from app.safety.policy import TEMP_EXT

class StabilityTracker:
    def __init__(self, seconds=10): self.seconds = seconds; self.observed = {}; self.delivered = {}
    def ready(self, records, now):
        ready = []; live = set()
        for r in records:
            path = r.current_path; live.add(path)
            if Path(path).suffix.lower() in TEMP_EXT or r.protected: continue
            signature = (r.size, r.modified_at)
            previous = self.observed.get(path)
            if previous is None or previous[0] != signature:
                self.observed[path] = (signature, now); continue
            if now-previous[1] >= self.seconds and self.delivered.get(path) != signature:
                ready.append(r); self.delivered[path] = signature
        for path in set(self.observed)-live:
            self.observed.pop(path, None); self.delivered.pop(path, None)
        return ready
