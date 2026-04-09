import tempfile
import unittest
from pathlib import Path

from core.settings import get_setting, load_settings


class SettingsTests(unittest.TestCase):
    def test_load_settings_merges_local_over_base(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "settings.yaml").write_text(
                "app:\n  mode: dev\nopenai:\n  model: gpt-4o-mini\n",
                encoding="utf-8",
            )
            (config_dir / "settings.local.yaml").write_text(
                "app:\n  mode: prod\nsecurity:\n  enforce_env_secrets: true\n",
                encoding="utf-8",
            )

            settings = load_settings(temp_dir)
            self.assertEqual(get_setting(settings, "app.mode"), "prod")
            self.assertEqual(get_setting(settings, "openai.model"), "gpt-4o-mini")
            self.assertTrue(get_setting(settings, "security.enforce_env_secrets"))


if __name__ == "__main__":
    unittest.main()
