import json
import re
import unicodedata
from pathlib import Path


class PluginRegistry:
    def __init__(self, directory: str = "state/plugins", enabled: bool = True):
        self.directory = Path(directory)
        self.enabled = bool(enabled)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._plugins = []
        self._commands = []
        self.reload()

    def reload(self):
        self._plugins = []
        self._commands = []
        if not self.enabled:
            return {"count": 0, "plugins": []}

        for file_path in sorted(self.directory.glob("*.json")):
            plugin = self._load_plugin(file_path)
            if plugin is None:
                continue
            self._plugins.append(plugin)
            for command in plugin.get("commands", []):
                item = self._normalize_command(command)
                if item is not None:
                    self._commands.append(item)

        return {"count": len(self._plugins), "plugins": [item.get("name", "") for item in self._plugins]}

    def list_plugins(self):
        return [dict(item) for item in self._plugins]

    def match(self, content: str):
        if not self.enabled:
            return None
        normalized = self._normalize(content)
        for item in self._commands:
            trigger = item.get("trigger", "")
            pattern = item.get("pattern")
            if trigger and normalized == trigger:
                return dict(item.get("payload", {}))
            if pattern is not None and pattern.match(normalized):
                return dict(item.get("payload", {}))
        return None

    def status(self):
        return {
            "enabled": self.enabled,
            "directory": str(self.directory),
            "plugin_count": len(self._plugins),
            "command_count": len(self._commands),
        }

    def _load_plugin(self, file_path: Path):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle) or {}
            if not isinstance(payload, dict):
                return None
            commands = payload.get("commands", [])
            if not isinstance(commands, list):
                return None
            return {
                "name": str(payload.get("name", file_path.stem)).strip() or file_path.stem,
                "file": str(file_path),
                "commands": commands,
            }
        except Exception:
            return None

    def _normalize_command(self, command: dict):
        if not isinstance(command, dict):
            return None
        payload = {
            "intent": str(command.get("intent", "")).strip(),
            "response": str(command.get("response", "")).strip(),
            "needs_action": bool(command.get("needs_action", True)),
        }
        for key in (
            "action",
            "device",
            "query",
            "alias",
            "mac",
            "memory",
            "token",
            "open_action",
            "close_action",
            "limit",
        ):
            if key in command:
                payload[key] = command.get(key)

        if not payload["intent"]:
            return None

        trigger = self._normalize(str(command.get("trigger", "")).strip())
        pattern_raw = str(command.get("pattern", "")).strip()
        compiled = None
        if pattern_raw:
            try:
                compiled = re.compile(pattern_raw, flags=re.IGNORECASE)
            except re.error:
                compiled = None

        if not trigger and compiled is None:
            return None

        if not payload.get("response"):
            payload["response"] = f"Plugin acionado: {payload['intent']}"

        return {
            "trigger": trigger,
            "pattern": compiled,
            "payload": payload,
        }

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text or "").lower())
        cleaned = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
