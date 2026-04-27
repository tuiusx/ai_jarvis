import tempfile
import unittest
from pathlib import Path

from core.machine_registry import MachineRegistry


class MachineRegistryTests(unittest.TestCase):
    def test_register_and_resolve_machine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            registry = MachineRegistry(path=str(path))

            item = registry.register("Notebook Sala", "AA-BB-CC-DD-EE-FF")
            resolved = registry.resolve("notebook_sala")

            self.assertEqual(item["alias"], "notebook_sala")
            self.assertEqual(item["mac"], "aa:bb:cc:dd:ee:ff")
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved["mac"], "aa:bb:cc:dd:ee:ff")

    def test_rejects_invalid_mac(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            registry = MachineRegistry(path=str(path))

            with self.assertRaises(ValueError):
                registry.register("camera", "invalid")

    def test_unregister_machine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            registry = MachineRegistry(path=str(path))
            registry.register("camera", "00:11:22:33:44:55")

            removed = registry.unregister("camera")
            missing = registry.resolve("camera")

            self.assertIsNotNone(removed)
            self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
