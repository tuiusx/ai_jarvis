import json
import os
import unicodedata
from datetime import datetime


class ShortTermMemory:
    def __init__(self, limit=10):
        self.limit = limit
        self.data = []

    def add(self, who, text):
        self.data.append(f"{who}: {text}")
        self.data = self.data[-self.limit:]

    def get_context(self):
        return "\n".join(self.data)

    def recall(self, perception):
        return self.get_context()

    def store(self, experience):
        self.add("user", experience.get("perception", {}).get("content", ""))
        self.add("agent", str(experience.get("results", [])))


class LongTermMemory:
    def __init__(self, file_path="memory.json", storage_path=None):
        self.file_path = storage_path or file_path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as file:
                    return json.load(file)
            except Exception:
                return []
        return []

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def add(self, text):
        entry = {
            "text": str(text).strip(),
            "timestamp": datetime.now().isoformat(),
            "type": "general",
        }
        self.data.append(entry)
        self.data = self.data[-100:]
        self._save()
        return entry

    def search(self, query, limit=5):
        query_norm = self._normalize(query)
        if not query_norm:
            return []
        results = []

        for entry in self.data:
            text_norm = self._normalize(entry.get("text", ""))
            if query_norm in text_norm:
                results.append(entry)

        results.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return results[:limit]

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
