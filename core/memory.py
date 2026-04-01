import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


class ShortTermMemory:
    def __init__(self, limit: int = 10):
        self.limit = limit
        self.data = []

    def add(self, who, text):
        self.data.append(f"{who}: {str(text).strip()}")
        self.data = self.data[-self.limit:]

    def get_context(self):
        return "\n".join(self.data)

    def recall(self, perception):
        return self.get_context()

    def store(self, experience):
        self.add("user", experience.get("perception", {}).get("content", ""))
        self.add("agent", str(experience.get("results", [])))


class LongTermMemory:
    def __init__(self, storage_path: str = "state/long_term_memory.json", file_path: str | None = None):
        chosen_path = file_path or storage_path
        self.storage_path = Path(chosen_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.items = self._load()
        self.data = self.items

    def add(self, text):
        cleaned = str(text).strip()
        item = {
            "text": cleaned,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": datetime.now().isoformat(),
            "type": "general",
            "tokens": self._tokenize(cleaned),
        }
        self.items.append(item)
        self.items = self.items[-100:]
        self.data = self.items
        self._save()
        return item

    def search(self, query, limit: int = 5):
        query_tokens = set(self._tokenize(query))
        normalized_query = self._normalize(query)
        if not query_tokens and not normalized_query:
            return []

        scored = []
        for item in self.items:
            item_tokens = set(item.get("tokens", []))
            normalized_text = self._normalize(item.get("text", ""))
            overlap = len(query_tokens & item_tokens)
            if overlap == 0 and normalized_query not in normalized_text:
                continue
            scored.append((overlap, item))

        scored.sort(key=lambda pair: (pair[0], pair[1].get("created_at", pair[1].get("timestamp", ""))), reverse=True)
        return [item for _, item in scored[:limit]]

    def _load(self):
        if not self.storage_path.exists():
            return []

        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        items = []
        for item in data if isinstance(data, list) else []:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            items.append(
                {
                    "text": text,
                    "created_at": str(item.get("created_at", item.get("timestamp", ""))),
                    "timestamp": str(item.get("timestamp", item.get("created_at", ""))),
                    "type": str(item.get("type", "general")),
                    "tokens": item.get("tokens") or self._tokenize(text),
                }
            )
        return items

    def _save(self):
        payload = json.dumps(self.items, ensure_ascii=False, indent=2)
        self.storage_path.write_text(payload, encoding="utf-8")

    @classmethod
    def _tokenize(cls, text: str):
        normalized = cls._normalize(text)
        return re.findall(r"[a-z0-9]{2,}", normalized)

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
