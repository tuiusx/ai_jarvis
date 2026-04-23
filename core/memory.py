import base64
import hashlib
import json
import os
import unicodedata
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover - dependency opcional
    Fernet = None


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
    def __init__(
        self,
        file_path="state/memory.json",
        storage_path=None,
        limit: int = 100,
        encryption_key: str | None = None,
        encryption_key_env: str = "JARVIS_MEMORY_KEY",
    ):
        self.file_path = storage_path or file_path
        self.limit = max(1, int(limit))
        self._fernet = self._build_fernet(encryption_key or os.getenv(encryption_key_env, ""))
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "rb") as file:
                    raw = file.read()
                if not raw:
                    return []

                if self._fernet is not None:
                    try:
                        decrypted = self._fernet.decrypt(raw)
                        loaded = json.loads(decrypted.decode("utf-8"))
                        return loaded if isinstance(loaded, list) else []
                    except Exception:
                        pass

                decoded = raw.decode("utf-8")
                loaded = json.loads(decoded)
                return loaded if isinstance(loaded, list) else []
            except Exception:
                return []
        return []

    def _save(self):
        payload = json.dumps(self.data, ensure_ascii=False, indent=2).encode("utf-8")
        if self._fernet is not None:
            payload = self._fernet.encrypt(payload)
        with open(self.file_path, "wb") as file:
            file.write(payload)

    def add(self, text):
        entry = {
            "text": str(text).strip(),
            "timestamp": datetime.now().isoformat(),
            "type": "general",
        }
        self.data.append(entry)
        self.data = self.data[-self.limit:]
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

    def export_encrypted(self, target_path: str, password: str):
        fernet = self._build_fernet(password)
        if fernet is None:
            raise ValueError("Senha invalida para exportacao.")

        output = Path(target_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, ensure_ascii=False, indent=2).encode("utf-8")
        output.write_bytes(fernet.encrypt(payload))
        return str(output)

    def import_encrypted(self, source_path: str, password: str):
        fernet = self._build_fernet(password)
        if fernet is None:
            raise ValueError("Senha invalida para importacao.")

        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Arquivo de backup nao encontrado: {source_path}")

        decrypted = fernet.decrypt(source.read_bytes())
        loaded = json.loads(decrypted.decode("utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("Formato de backup invalido.")

        imported = 0
        for item in loaded:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            timestamp = str(item.get("timestamp", "")).strip() or datetime.now().isoformat()
            item_type = str(item.get("type", "general")).strip() or "general"
            if not text:
                continue
            self.data.append({"text": text, "timestamp": timestamp, "type": item_type})
            imported += 1

        self.data = self.data[-self.limit:]
        self._save()
        return {"imported": imported, "total": len(self.data)}

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    @staticmethod
    def _build_fernet(secret: str):
        secret = (secret or "").strip()
        if not secret or Fernet is None:
            return None
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)
