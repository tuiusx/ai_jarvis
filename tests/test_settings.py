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

    def test_semantic_memory_defaults_are_available(self):
        settings = load_settings()
        self.assertTrue(get_setting(settings, "memory.semantic.enabled"))
        self.assertEqual(get_setting(settings, "memory.semantic.top_k"), 8)
        self.assertEqual(get_setting(settings, "memory.semantic.response_k"), 3)

    def test_access_control_defaults_are_available(self):
        settings = load_settings()
        self.assertFalse(get_setting(settings, "security.access_control.enabled"))
        self.assertEqual(get_setting(settings, "security.access_control.owner_name"), "owner")
        self.assertEqual(get_setting(settings, "security.access_control.permission_ttl_seconds"), 900)
        self.assertEqual(get_setting(settings, "security.access_control.roles_file"), "state/access_roles.json")
        self.assertTrue(get_setting(settings, "security.access_control.liveness_enabled"))
        self.assertEqual(get_setting(settings, "security.access_control.liveness_min_movement_pixels"), 4)
        self.assertEqual(get_setting(settings, "home_automation.custom_devices_path"), "state/home_custom_devices.json")
        self.assertFalse(get_setting(settings, "home_automation.iot_webhook.enabled"))

    def test_network_security_defaults_are_available(self):
        settings = load_settings()
        self.assertFalse(get_setting(settings, "security.network_verification.enabled"))
        self.assertEqual(get_setting(settings, "security.network_verification.mode"), "block")
        self.assertFalse(get_setting(settings, "security.network_monitor.enabled"))
        self.assertFalse(get_setting(settings, "security.network_enforcement.enabled"))
        self.assertTrue(get_setting(settings, "security.critical_confirmation.enabled"))
        self.assertEqual(get_setting(settings, "security.critical_confirmation.ttl_seconds"), 90)

    def test_performance_defaults_are_available(self):
        settings = load_settings()
        self.assertTrue(get_setting(settings, "performance.enabled_metrics"))
        self.assertEqual(get_setting(settings, "performance.slow_command_threshold_ms"), 700)
        self.assertTrue(get_setting(settings, "performance.lazy_init_enabled"))
        self.assertEqual(get_setting(settings, "performance.tool_retry_attempts"), 1)
        self.assertEqual(get_setting(settings, "performance.tool_retry_backoff_seconds"), 0.2)

    def test_first_run_setup_defaults_are_available(self):
        settings = load_settings()
        self.assertTrue(get_setting(settings, "setup.first_run_enabled"))
        self.assertEqual(get_setting(settings, "setup.state_file"), "state/first_run_setup.json")
        self.assertEqual(get_setting(settings, "setup.capture_timeout_seconds"), 20)

    def test_automation_backup_and_plugins_defaults(self):
        settings = load_settings()
        self.assertTrue(get_setting(settings, "plugins.enabled"))
        self.assertEqual(get_setting(settings, "plugins.directory"), "state/plugins")
        self.assertTrue(get_setting(settings, "automation.enabled"))
        self.assertTrue(get_setting(settings, "backup.enabled"))
        self.assertEqual(get_setting(settings, "backup.password_env"), "JARVIS_BACKUP_PASSWORD")
        self.assertTrue(get_setting(settings, "backup.periodic_tests.enabled"))
        self.assertEqual(get_setting(settings, "backup.periodic_tests.command"), "python -m pytest -q")
        self.assertTrue(get_setting(settings, "monitoring.system_resources.enabled"))


if __name__ == "__main__":
    unittest.main()
