import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.backup_manager import BackupManagerService


class FakeLongMemory:
    def __init__(self):
        self.exports = []

    def export_encrypted(self, target_path, password):
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        Path(target_path).write_text(f"encrypted:{password}", encoding="utf-8")
        self.exports.append((target_path, password))
        return target_path


class BackupManagerTests(unittest.TestCase):
    def test_runs_encrypted_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BackupManagerService(
                long_memory=FakeLongMemory(),
                output_dir=str(Path(temp_dir) / "exports"),
                password_env="JARVIS_TEST_BACKUP_PASSWORD",
                interval_minutes=0,
            )

            with patch.dict(os.environ, {"JARVIS_TEST_BACKUP_PASSWORD": "segredo"}, clear=False):
                result = service.run_now(reason="unit")
                self.assertIn("Backup criptografado", result["message"])
                self.assertTrue(Path(result["path"]).exists())

    def test_requires_backup_password_env(self):
        service = BackupManagerService(
            long_memory=FakeLongMemory(),
            output_dir="state/exports-test",
            password_env="JARVIS_TEST_BACKUP_PASSWORD_MISSING",
            interval_minutes=0,
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_TEST_BACKUP_PASSWORD_MISSING", None)
            result = service.run_now(reason="unit")
        self.assertIn("Senha de backup", result["error"])

    def test_runs_periodic_tests_now(self):
        def fake_runner(args, timeout, workdir):
            return SimpleNamespace(returncode=0, stdout="155 passed in 2.34s", stderr="")

        service = BackupManagerService(
            long_memory=FakeLongMemory(),
            output_dir="state/exports-test",
            periodic_tests_enabled=True,
            tests_interval_minutes=0,
            tests_command="python -m pytest -q",
            command_runner=fake_runner,
        )
        result = service.run_tests_now(reason="unit")

        self.assertIn("sucesso", result["message"].lower())
        self.assertEqual(result["report"]["status"], "ok")
        self.assertIn("passed", result["report"]["summary"])

    def test_tests_status_reports_failures(self):
        def fake_runner(args, timeout, workdir):
            return SimpleNamespace(returncode=1, stdout="2 failed, 153 passed", stderr="")

        service = BackupManagerService(
            long_memory=FakeLongMemory(),
            output_dir="state/exports-test",
            periodic_tests_enabled=True,
            tests_interval_minutes=0,
            tests_command="python -m pytest -q",
            command_runner=fake_runner,
        )
        result = service.run_tests_now(reason="unit")

        self.assertIn("falhas", result["message"].lower())
        self.assertEqual(result["report"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
