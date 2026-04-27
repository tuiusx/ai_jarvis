import os
import tempfile
import unittest
from pathlib import Path

from core.memory import Fernet, LongTermMemory, ShortTermMemory


class FakeSemanticStore:
    def __init__(self, search_results=None, fail_search=False, needs_migration=False):
        self.search_results = list(search_results or [])
        self.fail_search = fail_search
        self.needs_migration_flag = needs_migration
        self.added_entries = []
        self.migration_calls = 0

    @property
    def ready(self):
        return True

    def add_entry(self, text, timestamp=None, entry_type="general"):
        self.added_entries.append({"text": text, "timestamp": timestamp, "type": entry_type})
        return 1

    def add_entries(self, entries):
        self.added_entries.extend(entries)
        return len(entries)

    def search(self, query, limit=5):
        if self.fail_search:
            raise RuntimeError("semantic offline")
        return self.search_results[:limit]

    def needs_migration(self):
        return self.needs_migration_flag

    def migrate_from_entries(self, entries, batch_size=256):
        self.migration_calls += 1
        self.needs_migration_flag = False
        return len(entries)


class MemoryTests(unittest.TestCase):
    def test_short_term_memory_respects_limit(self):
        memory = ShortTermMemory(limit=2)
        memory.add("Usuario", "primeira")
        memory.add("Usuario", "segunda")
        memory.add("IA", "terceira")

        self.assertEqual(memory.get_context(), "Usuario: segunda\nIA: terceira")

    def test_short_term_store_adds_user_and_agent_lines(self):
        memory = ShortTermMemory()
        memory.store(
            {
                "perception": {"content": "ligar a luz"},
                "results": [{"message": "A luz da casa esta ligada."}],
            }
        )

        context = memory.get_context()
        self.assertIn("user: ligar a luz", context)
        self.assertIn("agent: [{'message': 'A luz da casa esta ligada.'}]", context)

    def test_long_term_memory_persists_and_searches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "memory.json"
            memory = LongTermMemory(storage_path=str(storage_path))

            memory.add("Ricardo prefere cafe sem acucar")
            memory.add("A chave reserva fica na gaveta azul")

            results = memory.search("cafe")
            self.assertEqual(results[0]["text"], "Ricardo prefere cafe sem acucar")

            reloaded = LongTermMemory(storage_path=str(storage_path))
            reloaded_results = reloaded.search("gaveta azul")
            self.assertEqual(reloaded_results[0]["text"], "A chave reserva fica na gaveta azul")

    def test_long_term_memory_supports_file_path_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "memory.json")
            memory = LongTermMemory(file_path=file_path)
            memory.add("Usuario ligou a luz da casa")

            self.assertTrue(os.path.exists(file_path))
            results = memory.search("luz")
            self.assertEqual(results[0]["text"], "Usuario ligou a luz da casa")

    @unittest.skipIf(Fernet is None, "cryptography nao instalada neste ambiente")
    def test_long_term_memory_export_and_import_encrypted_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "memory.json")
            export_path = os.path.join(temp_dir, "backup", "memory.enc")

            memory = LongTermMemory(file_path=source_path)
            memory.add("evento critico de teste")

            generated = memory.export_encrypted(export_path, password="senha-forte")
            self.assertTrue(os.path.exists(generated))

            restored_path = os.path.join(temp_dir, "restored.json")
            restored = LongTermMemory(file_path=restored_path)
            report = restored.import_encrypted(generated, password="senha-forte")
            self.assertEqual(report["imported"], 1)
            self.assertEqual(len(restored.search("critico")), 1)

    def test_masks_sensitive_text_before_semantic_persist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_semantic = FakeSemanticStore()
            memory = LongTermMemory(
                file_path=os.path.join(temp_dir, "memory.json"),
                semantic_config={"enabled": True, "mask_sensitive": True},
                semantic_store=fake_semantic,
            )
            memory.add("senha: 1234 token abc123 cartao 4111111111111111 cpf 123.456.789-10")

            self.assertEqual(len(fake_semantic.added_entries), 1)
            persisted = fake_semantic.added_entries[0]["text"]
            self.assertNotIn("1234", persisted)
            self.assertNotIn("4111111111111111", persisted)
            self.assertNotIn("123.456.789-10", persisted)
            self.assertIn("***", persisted)

    def test_fallbacks_to_lexical_when_semantic_search_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = LongTermMemory(
                file_path=os.path.join(temp_dir, "memory.json"),
                semantic_config={"enabled": True, "mask_sensitive": True},
                semantic_store=FakeSemanticStore(fail_search=True),
            )
            memory.add("A chave do cofre fica na gaveta da cozinha")
            memory.add("Ligar a luz da garagem depois das 19h")

            results = memory.search("cofre", limit=3)
            self.assertTrue(results)
            self.assertEqual(results[0]["source"], "lexical")
            self.assertIn("cofre", results[0]["text"].lower())

    def test_semantic_migration_runs_on_startup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "memory.json")
            seed_memory = LongTermMemory(file_path=file_path)
            seed_memory.add("memoria antiga 1")
            seed_memory.add("memoria antiga 2")

            fake_semantic = FakeSemanticStore(needs_migration=True)
            LongTermMemory(
                file_path=file_path,
                semantic_config={"enabled": True, "batch_size": 256},
                semantic_store=fake_semantic,
            )
            self.assertEqual(fake_semantic.migration_calls, 1)

    def test_prefers_semantic_results_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            semantic_results = [
                {
                    "text": "A lampada da cozinha e controlada por voz",
                    "timestamp": "2026-04-25T10:00:00",
                    "type": "general",
                    "score": 0.92,
                    "source": "semantic",
                }
            ]
            memory = LongTermMemory(
                file_path=os.path.join(temp_dir, "memory.json"),
                semantic_config={"enabled": True},
                semantic_store=FakeSemanticStore(search_results=semantic_results),
            )
            memory.add("frase lexical de apoio")
            results = memory.search("iluminacao cozinha", limit=3)
            self.assertEqual(results[0]["source"], "semantic")
            self.assertIn("cozinha", results[0]["text"])


if __name__ == "__main__":
    unittest.main()
