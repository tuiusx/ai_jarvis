import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.maintenance_guard import MaintenanceGuardService
from tools.maintenance_guard import MaintenanceGuardTool


class FakeBackupManager:
    def __init__(self, payload):
        self.password_env = "JARVIS_BACKUP_PASSWORD"
        self._payload = dict(payload)
        self.start_calls = 0

    def status(self):
        return dict(self._payload)

    def start(self):
        self.start_calls += 1
        return {"message": "backup scheduler start called"}


class FakeSystemMonitor:
    def __init__(self, enabled=True, running=False):
        self.enabled = enabled
        self.running = running
        self.start_calls = 0

    def status(self):
        return {
            "enabled": self.enabled,
            "running": self.running,
        }

    def start(self):
        self.start_calls += 1
        self.running = True
        return {"message": "system monitor start called"}


class MaintenanceGuardServiceTests(unittest.TestCase):
    def test_reports_degraded_when_required_secrets_are_missing(self):
        now = datetime.now(timezone.utc).isoformat()
        backup = FakeBackupManager(
            {
                "status": "ok",
                "at": now,
                "periodic_tests_enabled": True,
                "tests": {"status": "ok", "at": now},
            }
        )
        monitor = FakeSystemMonitor(enabled=True, running=True)

        with patch.dict(os.environ, {}, clear=True):
            service = MaintenanceGuardService(
                enabled=True,
                auto_start=False,
                auto_repair=False,
                backup_manager=backup,
                system_monitor=monitor,
                admin_pin_env="JARVIS_ADMIN_PIN",
            )
            result = service.check_now(reason="unit")

        report = result["report"]
        self.assertEqual(report["overall_status"], "degraded")
        self.assertIn("backup_password_missing", report["issues"])
        self.assertIn("admin_pin_missing", report["issues"])

    def test_reports_ok_when_fresh_data_and_secrets_exist(self):
        now = datetime.now(timezone.utc).isoformat()
        backup = FakeBackupManager(
            {
                "status": "ok",
                "at": now,
                "periodic_tests_enabled": True,
                "tests": {"status": "ok", "at": now},
            }
        )
        monitor = FakeSystemMonitor(enabled=True, running=True)

        with patch.dict(
            os.environ,
            {
                "JARVIS_BACKUP_PASSWORD": "abc123",
                "JARVIS_ADMIN_PIN": "4455",
            },
            clear=True,
        ):
            service = MaintenanceGuardService(
                enabled=True,
                auto_start=False,
                auto_repair=False,
                backup_manager=backup,
                system_monitor=monitor,
                admin_pin_env="JARVIS_ADMIN_PIN",
                max_backup_age_minutes=60,
                max_tests_age_minutes=60,
            )
            result = service.check_now(reason="unit")

        report = result["report"]
        self.assertEqual(report["overall_status"], "ok")
        self.assertEqual(report["issues"], [])

    def test_auto_repair_attempts_to_start_services(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        backup = FakeBackupManager(
            {
                "status": "ok",
                "at": old,
                "periodic_tests_enabled": True,
                "tests_interval_minutes": 60,
                "interval_minutes": 60,
                "tests": {"status": "ok", "at": old},
            }
        )
        monitor = FakeSystemMonitor(enabled=True, running=False)

        with patch.dict(
            os.environ,
            {
                "JARVIS_BACKUP_PASSWORD": "abc123",
                "JARVIS_ADMIN_PIN": "4455",
            },
            clear=True,
        ):
            service = MaintenanceGuardService(
                enabled=True,
                auto_start=False,
                auto_repair=True,
                backup_manager=backup,
                system_monitor=monitor,
                admin_pin_env="JARVIS_ADMIN_PIN",
                max_backup_age_minutes=30,
                max_tests_age_minutes=30,
            )
            result = service.check_now(reason="unit")

        report = result["report"]
        self.assertEqual(report["overall_status"], "degraded")
        self.assertGreaterEqual(backup.start_calls, 1)
        self.assertGreaterEqual(monitor.start_calls, 1)
        self.assertTrue(report["auto_repair_result"]["attempted"])


class MaintenanceGuardToolTests(unittest.TestCase):
    def test_tool_routes_actions(self):
        class FakeService:
            def status(self):
                return {"running": True}

            def check_now(self, reason="manual"):
                return {"message": f"checked:{reason}"}

            def start(self):
                return {"message": "started"}

            def stop(self):
                return {"message": "stopped"}

        tool = MaintenanceGuardTool(service=FakeService())
        self.assertIn("status", tool.run(action="status"))
        self.assertEqual(tool.run(action="check_now")["message"], "checked:manual")
        self.assertEqual(tool.run(action="start")["message"], "started")
        self.assertEqual(tool.run(action="stop")["message"], "stopped")


if __name__ == "__main__":
    unittest.main()
