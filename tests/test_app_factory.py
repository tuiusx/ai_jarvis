import tempfile
import unittest
from pathlib import Path

from core.app_factory import AppFactory
from core.settings import load_settings


class AppFactoryTests(unittest.TestCase):
    def test_builds_context_with_minimal_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "settings.yaml").write_text(
                """
app:
  mode: "dev"
memory:
  long_term_file: "state/test-memory.json"
  semantic:
    enabled: false
performance:
  lazy_init_enabled: true
security:
  network_monitor:
    enabled: false
  network_enforcement:
    enabled: false
""".strip(),
                encoding="utf-8",
            )

            settings = load_settings(temp_dir)
            factory = AppFactory(settings=settings)
            context = factory.build(interface=None, retention_summary={}, include_camera_tools=False)

            self.assertIsNotNone(context.agent)
            self.assertEqual(context.app_mode, "dev")
            self.assertIsNone(context.network_monitor)
            self.assertIsNone(context.network_enforcement)

    def test_builds_network_services_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "settings.yaml").write_text(
                """
app:
  mode: "dev"
memory:
  long_term_file: "state/test-memory.json"
  semantic:
    enabled: false
performance:
  lazy_init_enabled: true
security:
  network_monitor:
    enabled: true
  network_enforcement:
    enabled: true
""".strip(),
                encoding="utf-8",
            )

            settings = load_settings(temp_dir)
            factory = AppFactory(settings=settings)
            context = factory.build(interface=None, retention_summary={}, include_camera_tools=False)

            self.assertIsNotNone(context.network_monitor)
            self.assertIsNotNone(context.network_enforcement)


if __name__ == "__main__":
    unittest.main()
