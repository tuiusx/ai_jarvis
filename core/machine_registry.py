import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path


class MachineRegistry:
    def __init__(self, path: str = "state/machine_registry.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._data = {"machines": {}}
        self._load()

    def register(self, alias: str, mac: str):
        normalized_alias = self.normalize_alias(alias)
        normalized_mac = self.normalize_mac(mac)
        if not normalized_alias:
            raise ValueError("Alias de maquina invalido.")
        if not normalized_mac:
            raise ValueError("MAC invalido.")

        with self._lock:
            self._data.setdefault("machines", {})[normalized_alias] = {
                "alias": normalized_alias,
                "mac": normalized_mac,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_unlocked()
            return dict(self._data["machines"][normalized_alias])

    def unregister(self, alias: str):
        normalized_alias = self.normalize_alias(alias)
        with self._lock:
            removed = self._data.setdefault("machines", {}).pop(normalized_alias, None)
            self._save_unlocked()
            return removed

    def resolve(self, alias: str):
        normalized_alias = self.normalize_alias(alias)
        item = self._data.get("machines", {}).get(normalized_alias)
        return dict(item) if isinstance(item, dict) else None

    def list_all(self):
        machines = self._data.get("machines", {})
        return [dict(item) for _, item in sorted(machines.items())]

    def aliases(self):
        return [item["alias"] for item in self.list_all()]

    def _load(self):
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle) or {}
            if isinstance(data, dict) and isinstance(data.get("machines"), dict):
                self._data = data
        except Exception:
            self._data = {"machines": {}}

    def _save_unlocked(self):
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def normalize_alias(alias: str):
        value = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(alias or "").strip().lower())
        return value.strip("_")

    @staticmethod
    def normalize_mac(mac: str):
        value = str(mac or "").strip().lower().replace("-", ":")
        if not re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", value):
            return ""
        return value
