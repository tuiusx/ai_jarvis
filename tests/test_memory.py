import os
import tempfile
import unittest
from pathlib import Path

from core.memory import Fernet, LongTermMemory, ShortTermMemory


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


if __name__ == "__main__":
    unittest.main()
