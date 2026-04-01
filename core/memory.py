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
        self.data.append(f"{who}: {text.strip()}")
        self.data = self.data[-self.limit:]

    def get_context(self):
        return "\n".join(self.data)


class LongTermMemory:
    def __init__(self, storage_path: str = "state/long_term_memory.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.items = self._load()

    def add(self, text):
        cleaned = text.strip()
        item = {
            "text": cleaned,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tokens": self._tokenize(cleaned),
        }
        self.items.append(item)
        self._save()
        return item

    def search(self, query, limit: int = 3):
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        normalized_query = self._normalize(query)
        scored = []
        for item in self.items:
            item_tokens = set(item.get("tokens", []))
            normalized_text = self._normalize(item["text"])
            overlap = len(query_tokens & item_tokens)
            if overlap == 0 and normalized_query not in normalized_text:
                continue
            scored.append((overlap, item))

        scored.sort(
            key=lambda pair: (pair[0], pair[1].get("created_at", "")),
            reverse=True,
        )
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
            items.append({
                "text": text,
                "created_at": str(item.get("created_at", "")),
                "tokens": item.get("tokens") or self._tokenize(text),
            })
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
        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(
            char for char in normalized
            if unicodedata.category(char) != "Mn"
        )
