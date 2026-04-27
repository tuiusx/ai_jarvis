import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import unicodedata
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
except Exception:  # pragma: no cover - dependency opcional
    np = None

try:
    import faiss
except Exception:  # pragma: no cover - dependency opcional
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - dependency opcional
    SentenceTransformer = None

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


class SemanticMemoryStore:
    MIGRATION_KEY = "semantic_migrated_v1"

    def __init__(
        self,
        enabled=True,
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        index_path="state/memory_semantic.faiss",
        db_path="state/memory_semantic.db",
        top_k=8,
        batch_size=256,
        score_threshold=0.45,
        hnsw_m=32,
        hnsw_ef_search=128,
        embedding_model=None,
        faiss_module=None,
        cache_size=1024,
        logger=None,
    ):
        self.enabled = bool(enabled)
        self.model_name = str(model_name)
        self.index_path = Path(index_path)
        self.db_path = Path(db_path)
        self.top_k = max(1, int(top_k))
        self.batch_size = max(1, int(batch_size))
        self.score_threshold = float(score_threshold)
        self.hnsw_m = max(4, int(hnsw_m))
        self.hnsw_ef_search = max(16, int(hnsw_ef_search))
        self.cache_size = max(1, int(cache_size))
        self.logger = logger or logging.getLogger(__name__)

        self.ready = False
        self.reason = "disabled"
        self.index = None
        self.dimension = 0
        self._model = None
        self._faiss = faiss_module if faiss_module is not None else faiss
        self._query_cache = OrderedDict()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

        if not self.enabled:
            return
        if np is None:
            self.reason = "numpy_unavailable"
            return
        if self._faiss is None:
            self.reason = "faiss_unavailable"
            return
        if embedding_model is not None:
            self._model = embedding_model
        else:
            if SentenceTransformer is None:
                self.reason = "sentence_transformers_unavailable"
                return
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:  # pragma: no cover - depende do ambiente
                self.reason = f"model_load_failed: {exc}"
                return

        self.dimension = self._resolve_dimension()
        if self.dimension <= 0:
            self.reason = "embedding_dimension_invalid"
            return

        try:
            self.index = self._load_or_create_index()
            self.ready = True
            self.reason = "ok"
        except Exception as exc:  # pragma: no cover - depende do ambiente
            self.reason = f"index_init_failed: {exc}"
            self.logger.warning("Falha ao iniciar indice semantico: %s", exc)

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def _init_tables(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_masked TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _resolve_dimension(self):
        if hasattr(self._model, "get_sentence_embedding_dimension"):
            try:
                return int(self._model.get_sentence_embedding_dimension())
            except Exception:
                pass

        sample = self._encode_texts(["dimensional probe"])
        if sample is None or len(sample) == 0:
            return 0
        return int(sample.shape[1])

    def _load_or_create_index(self):
        if self.index_path.exists():
            index = self._faiss.read_index(str(self.index_path))
            self._apply_hnsw_runtime_config(index)
            return index

        metric = getattr(self._faiss, "METRIC_INNER_PRODUCT", 0)
        try:
            base = self._faiss.IndexHNSWFlat(self.dimension, self.hnsw_m, metric)
        except TypeError:
            base = self._faiss.IndexHNSWFlat(self.dimension, self.hnsw_m)

        index = self._faiss.IndexIDMap2(base)
        self._apply_hnsw_runtime_config(index)
        return index

    def _apply_hnsw_runtime_config(self, index):
        base_index = getattr(index, "index", index)
        hnsw = getattr(base_index, "hnsw", None)
        if hnsw is not None and hasattr(hnsw, "efSearch"):
            hnsw.efSearch = self.hnsw_ef_search

    def _save_index(self):
        if self.ready and self.index is not None:
            self._faiss.write_index(self.index, str(self.index_path))

    def _normalize_text(self, text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    def _content_hash(self, text: str):
        normalized = self._normalize_text(text).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _encode_texts(self, texts):
        if not texts:
            return None

        try:
            vectors = self._model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=False,
            )
        except TypeError:
            vectors = self._model.encode(texts)

        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return self._normalize_vectors(matrix)

    @staticmethod
    def _normalize_vectors(matrix):
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return matrix / norms

    def _embed_query_cached(self, query):
        key = self._normalize_text(query).strip()
        if key in self._query_cache:
            self._query_cache.move_to_end(key)
            return self._query_cache[key]

        vectors = self._encode_texts([query])
        if vectors is None or len(vectors) == 0:
            return None
        vector = vectors[0]
        self._query_cache[key] = vector
        if len(self._query_cache) > self.cache_size:
            self._query_cache.popitem(last=False)
        return vector

    def get_meta(self, key, default=None):
        cursor = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        with self._conn:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def count_entries(self):
        cursor = self._conn.execute("SELECT COUNT(*) AS total FROM memory_entries")
        row = cursor.fetchone()
        return int(row["total"] if row else 0)

    def needs_migration(self):
        if not self.ready:
            return False
        migrated = self.get_meta(self.MIGRATION_KEY, "0") == "1"
        if migrated:
            return False
        if self.count_entries() > 0:
            return False
        if self.index is not None and getattr(self.index, "ntotal", 0) > 0:
            return False
        return True

    def add_entry(self, text, timestamp=None, entry_type="general"):
        return self.add_entries(
            [
                {
                    "text": text,
                    "timestamp": timestamp or datetime.now().isoformat(),
                    "type": entry_type,
                }
            ]
        )

    def add_entries(self, entries, batch_size=None):
        if not self.ready or not entries:
            return 0

        pending_ids = []
        pending_texts = []
        with self._conn:
            for entry in entries:
                text = str(entry.get("text", "")).strip()
                if not text:
                    continue
                timestamp = str(entry.get("timestamp", "")).strip() or datetime.now().isoformat()
                entry_type = str(entry.get("type", "general")).strip() or "general"
                content_hash = self._content_hash(text)
                try:
                    cursor = self._conn.execute(
                        """
                        INSERT INTO memory_entries(text_masked, timestamp, type, content_hash)
                        VALUES(?, ?, ?, ?)
                        """,
                        (text, timestamp, entry_type, content_hash),
                    )
                except sqlite3.IntegrityError:
                    continue
                pending_ids.append(int(cursor.lastrowid))
                pending_texts.append(text)

        if not pending_ids:
            return 0

        effective_batch = max(1, int(batch_size or self.batch_size))
        for start in range(0, len(pending_ids), effective_batch):
            batch_ids = pending_ids[start : start + effective_batch]
            batch_texts = pending_texts[start : start + effective_batch]
            vectors = self._encode_texts(batch_texts)
            if vectors is None or len(vectors) == 0:
                continue
            ids = np.asarray(batch_ids, dtype="int64")
            self.index.add_with_ids(vectors, ids)

        self._save_index()
        return len(pending_ids)

    def migrate_from_entries(self, entries, batch_size=256):
        if not self.ready:
            return 0
        if self.get_meta(self.MIGRATION_KEY, "0") == "1":
            return 0
        inserted = self.add_entries(entries, batch_size=batch_size)
        self.set_meta(self.MIGRATION_KEY, "1")
        return inserted

    def search(self, query, limit=8):
        if not self.ready or self.index is None or not query:
            return []

        total = int(getattr(self.index, "ntotal", 0))
        if total <= 0:
            return []

        limit = max(1, int(limit))
        query_vector = self._embed_query_cached(query)
        if query_vector is None:
            return []

        query_matrix = np.asarray([query_vector], dtype="float32")
        scores, indices = self.index.search(query_matrix, limit)
        matched_ids = [int(idx) for idx in indices[0] if int(idx) >= 0]
        if not matched_ids:
            return []

        placeholders = ",".join("?" for _ in matched_ids)
        rows = self._conn.execute(
            f"SELECT id, text_masked, timestamp, type FROM memory_entries WHERE id IN ({placeholders})",
            matched_ids,
        ).fetchall()
        rows_by_id = {int(row["id"]): row for row in rows}

        results = []
        for item_id, score in zip(indices[0], scores[0]):
            item_id = int(item_id)
            if item_id < 0:
                continue
            row = rows_by_id.get(item_id)
            if row is None:
                continue
            score_value = float(score)
            if score_value < self.score_threshold:
                continue
            results.append(
                {
                    "id": item_id,
                    "text": row["text_masked"],
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "score": score_value,
                    "source": "semantic",
                }
            )
        return results


class LongTermMemory:
    SENSITIVE_PATTERNS = (
        re.compile(r"(?i)\b(senha|password|token|apikey|api[_-]?key|chave)\b\s*[:=]?\s*([^\s,;]+)"),
        re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
    )

    def __init__(
        self,
        file_path="state/memory.json",
        storage_path=None,
        limit: int = 100,
        encryption_key: str | None = None,
        encryption_key_env: str = "JARVIS_MEMORY_KEY",
        semantic_config: dict | None = None,
        semantic_store=None,
        logger=None,
    ):
        self.file_path = storage_path or file_path
        self.limit = max(1, int(limit))
        self.logger = logger or logging.getLogger(__name__)
        self._fernet = self._build_fernet(encryption_key or os.getenv(encryption_key_env, ""))

        self.semantic_config = dict(semantic_config or {})
        self.semantic_enabled = bool(self.semantic_config.get("enabled", False))
        self.semantic_top_k = max(1, int(self.semantic_config.get("top_k", 8)))
        self.semantic_response_k = max(1, int(self.semantic_config.get("response_k", 3)))
        self.semantic_batch_size = max(1, int(self.semantic_config.get("batch_size", 256)))
        self.semantic_mask_sensitive = bool(self.semantic_config.get("mask_sensitive", True))

        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        self.data = self._load()

        self.semantic_store = semantic_store
        if self.semantic_store is None and self.semantic_enabled:
            self.semantic_store = SemanticMemoryStore(
                enabled=True,
                model_name=str(
                    self.semantic_config.get(
                        "model_name", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    )
                ),
                index_path=str(self.semantic_config.get("index_path", "state/memory_semantic.faiss")),
                db_path=str(self.semantic_config.get("db_path", "state/memory_semantic.db")),
                top_k=self.semantic_top_k,
                batch_size=self.semantic_batch_size,
                score_threshold=float(self.semantic_config.get("score_threshold", 0.45)),
                hnsw_m=int(self.semantic_config.get("hnsw_m", 32)),
                hnsw_ef_search=int(self.semantic_config.get("hnsw_ef_search", 128)),
            )

        self._migrate_semantic_if_needed()

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

    def _mask_sensitive_text(self, text: str):
        value = str(text)
        for pattern in self.SENSITIVE_PATTERNS:
            if "senha" in pattern.pattern.lower() or "password" in pattern.pattern.lower():
                value = pattern.sub(lambda m: f"{m.group(1)} ***", value)
            else:
                value = pattern.sub("***", value)
        return value

    def _prepare_semantic_entry(self, entry: dict):
        text = entry.get("text", "")
        if self.semantic_mask_sensitive:
            text = self._mask_sensitive_text(text)
        return {
            "text": text,
            "timestamp": entry.get("timestamp", datetime.now().isoformat()),
            "type": entry.get("type", "general"),
        }

    def _migrate_semantic_if_needed(self):
        if self.semantic_store is None:
            return

        try:
            ready = bool(getattr(self.semantic_store, "ready", True))
            if not ready:
                reason = getattr(self.semantic_store, "reason", "unknown")
                self.logger.warning("Memoria semantica indisponivel: %s", reason)
                return

            needs_migration = False
            if hasattr(self.semantic_store, "needs_migration"):
                needs_migration = bool(self.semantic_store.needs_migration())
            if not needs_migration:
                return

            if not self.data:
                return

            entries = [self._prepare_semantic_entry(item) for item in self.data if isinstance(item, dict)]
            migrated = self.semantic_store.migrate_from_entries(entries, batch_size=self.semantic_batch_size)
            self.logger.info("Migracao semantica concluida (%s itens).", migrated)
        except Exception as exc:
            self.logger.warning("Falha na migracao semantica automatica: %s", exc)

    def add(self, text):
        entry = {
            "text": str(text).strip(),
            "timestamp": datetime.now().isoformat(),
            "type": "general",
        }
        self.data.append(entry)
        self.data = self.data[-self.limit:]
        self._save()

        if self.semantic_store is not None:
            try:
                semantic_entry = self._prepare_semantic_entry(entry)
                self.semantic_store.add_entry(
                    semantic_entry["text"],
                    timestamp=semantic_entry["timestamp"],
                    entry_type=semantic_entry["type"],
                )
            except Exception as exc:
                self.logger.warning("Falha ao adicionar memoria semantica: %s", exc)

        return entry

    def _search_lexical(self, query, limit=5):
        query_norm = self._normalize(query)
        if not query_norm:
            return []
        results = []

        for entry in self.data:
            text_norm = self._normalize(entry.get("text", ""))
            if query_norm in text_norm:
                lexical_entry = dict(entry)
                lexical_entry["source"] = "lexical"
                results.append(lexical_entry)

        results.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return results[:limit]

    def search(self, query, limit=5, semantic=True):
        limit = max(1, int(limit))
        if semantic and self.semantic_store is not None:
            try:
                semantic_limit = max(limit, self.semantic_top_k)
                semantic_results = self.semantic_store.search(query, limit=semantic_limit)
                if semantic_results:
                    return semantic_results[:limit]
            except Exception as exc:
                self.logger.warning("Busca semantica indisponivel, aplicando fallback lexical: %s", exc)

        return self._search_lexical(query, limit=limit)

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

        imported_entries = []
        for item in loaded:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            timestamp = str(item.get("timestamp", "")).strip() or datetime.now().isoformat()
            item_type = str(item.get("type", "general")).strip() or "general"
            if not text:
                continue
            imported_entries.append({"text": text, "timestamp": timestamp, "type": item_type})
            self.data.append({"text": text, "timestamp": timestamp, "type": item_type})

        self.data = self.data[-self.limit:]
        self._save()

        if imported_entries and self.semantic_store is not None:
            try:
                prepared = [self._prepare_semantic_entry(item) for item in imported_entries]
                self.semantic_store.add_entries(prepared, batch_size=self.semantic_batch_size)
            except Exception as exc:
                self.logger.warning("Falha ao indexar backup importado no semantico: %s", exc)

        return {"imported": len(imported_entries), "total": len(self.data)}

    def semantic_status(self):
        if self.semantic_store is None:
            return {"enabled": False, "ready": False, "reason": "disabled"}
        return {
            "enabled": True,
            "ready": bool(getattr(self.semantic_store, "ready", True)),
            "reason": getattr(self.semantic_store, "reason", "ok"),
        }

    def close(self):
        if self.semantic_store is not None and hasattr(self.semantic_store, "close"):
            try:
                self.semantic_store.close()
            except Exception:
                pass

    def __del__(self):  # pragma: no cover - nao deterministico em testes
        self.close()

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
