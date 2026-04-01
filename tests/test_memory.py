import tempfile
import unittest
from pathlib import Path

from core.memory import LongTermMemory, ShortTermMemory


class MemoryTests(unittest.TestCase):
    def test_short_term_memory_respects_limit(self):
        memory = ShortTermMemory(limit=2)
        memory.add("Usuario", "primeira")
        memory.add("Usuario", "segunda")
        memory.add("IA", "terceira")

        self.assertEqual(
            memory.get_context(),
            "Usuario: segunda\nIA: terceira",
        )

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
            self.assertEqual(
                reloaded_results[0]["text"],
                "A chave reserva fica na gaveta azul",
            )


if __name__ == "__main__":
    unittest.main()
