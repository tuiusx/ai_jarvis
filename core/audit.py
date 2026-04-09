import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, event: str, severity: str = "info", **data):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "severity": severity,
            "data": data,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry

    def tail(self, limit: int = 100):
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()

        entries = []
        for raw in lines[-max(1, int(limit)):]:
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return entries
