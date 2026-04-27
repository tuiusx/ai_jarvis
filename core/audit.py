import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:
    SEVERITY_ORDER = {
        "info": 0,
        "warning": 1,
        "error": 2,
        "critical": 3,
    }

    def __init__(
        self,
        path: str,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
        notify_callback=None,
        notify_min_severity: str = "critical",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(0, int(max_bytes))
        self.backup_count = max(0, int(backup_count))
        self.notify_callback = notify_callback
        self.notify_min_severity = str(notify_min_severity or "critical").lower()
        if self.notify_min_severity not in self.SEVERITY_ORDER:
            self.notify_min_severity = "critical"
        self._lock = threading.Lock()
        self._metrics = {
            "total_events": 0,
            "critical_events": 0,
            "error_events": 0,
            "rate_limited_events": 0,
            "tool_errors": 0,
            "network_packets_total": 0,
            "network_unique_ips": 0,
            "network_monitor_errors": 0,
            "network_untrusted_blocks": 0,
            "slow_commands": 0,
        }
        self._seen_network_ips = set()

    def log(self, event: str, severity: str = "info", **data):
        severity = str(severity or "info").lower()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "severity": severity,
            "data": data,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            self._rotate_if_needed(next_line_bytes=len(line.encode("utf-8")) + 1)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self._update_metrics(entry)

        if callable(self.notify_callback):
            try:
                if self.SEVERITY_ORDER.get(severity, -1) >= self.SEVERITY_ORDER.get(self.notify_min_severity, 3):
                    self.notify_callback(entry)
            except Exception:
                pass

        return entry

    def tail(self, limit: int = 100, severity: str | None = None):
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()

        entries = []
        severity_filter = str(severity).lower() if severity else None
        for raw in reversed(lines):
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if severity_filter and str(item.get("severity", "")).lower() != severity_filter:
                continue
            entries.append(item)
            if len(entries) >= max(1, int(limit)):
                break

        entries.reverse()
        return entries

    def metrics(self):
        with self._lock:
            snapshot = dict(self._metrics)
        snapshot["current_log_bytes"] = self.path.stat().st_size if self.path.exists() else 0
        snapshot["rotated_files"] = len(list(self.path.parent.glob(f"{self.path.name}.*")))
        return snapshot

    def _update_metrics(self, entry: dict):
        severity = str(entry.get("severity", "info")).lower()
        event = str(entry.get("event", ""))
        self._metrics["total_events"] += 1
        if severity == "critical":
            self._metrics["critical_events"] += 1
        if severity == "error":
            self._metrics["error_events"] += 1
        if event == "security.rate_limit_blocked":
            self._metrics["rate_limited_events"] += 1
        if event == "tool.execute" and severity == "error":
            self._metrics["tool_errors"] += 1
        if event == "network.monitor_packet":
            self._metrics["network_packets_total"] += 1
            data = entry.get("data", {})
            for key in ("src_ip", "dst_ip"):
                value = str(data.get(key, "")).strip()
                if value:
                    self._seen_network_ips.add(value)
            self._metrics["network_unique_ips"] = len(self._seen_network_ips)
        if event in {"network.monitor_autostart_failed", "network.monitor_error"}:
            self._metrics["network_monitor_errors"] += 1
        if event == "security.network_untrusted_blocked":
            self._metrics["network_untrusted_blocks"] += 1
        if event == "performance.slow_command":
            self._metrics["slow_commands"] += 1

    def _rotate_if_needed(self, next_line_bytes: int):
        if self.max_bytes <= 0 or not self.path.exists():
            return

        current_size = self.path.stat().st_size
        if current_size + next_line_bytes <= self.max_bytes:
            return

        if self.backup_count <= 0:
            self.path.unlink(missing_ok=True)
            return

        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self.backup_count - 1, 0, -1):
            src = self.path.with_name(f"{self.path.name}.{index}")
            dst = self.path.with_name(f"{self.path.name}.{index + 1}")
            if src.exists():
                src.rename(dst)
        self.path.rename(self.path.with_name(f"{self.path.name}.1"))
