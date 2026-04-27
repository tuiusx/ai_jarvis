import unittest

from core.system_monitor import SystemMonitorService
from tools.system_monitor import SystemMonitorTool


class FakeAudit:
    def __init__(self):
        self.events = []

    def log(self, event, severity="info", **data):
        self.events.append((event, severity, data))


class SystemMonitorTests(unittest.TestCase):
    def test_collects_status_and_summary(self):
        samples = [
            {"timestamp": "2026-01-01T00:00:00Z", "cpu_percent": 21.5, "memory_percent": 48.2, "memory_used_mb": 1200, "memory_total_mb": 4000},
            {"timestamp": "2026-01-01T00:00:10Z", "cpu_percent": 40.0, "memory_percent": 52.0, "memory_used_mb": 1300, "memory_total_mb": 4000},
        ]
        iterator = iter(samples)

        def fake_sampler():
            return next(iterator, samples[-1])

        service = SystemMonitorService(enabled=True, auto_start=False, sampler=fake_sampler)
        collected = service.collect_once()
        self.assertIn("sample", collected)

        status = service.status()
        self.assertTrue(status["enabled"])
        self.assertIsNotNone(status["latest"])

        service.collect_once()
        summary = service.summary()
        self.assertEqual(summary["summary"]["samples"], 2)
        self.assertGreater(summary["summary"]["cpu_max_percent"], 20)

    def test_emits_alert_when_threshold_exceeded(self):
        audit = FakeAudit()

        def high_sampler():
            return {
                "timestamp": "2026-01-01T00:00:00Z",
                "cpu_percent": 95.0,
                "memory_percent": 91.0,
                "memory_used_mb": 3500,
                "memory_total_mb": 4000,
            }

        service = SystemMonitorService(
            enabled=True,
            auto_start=False,
            sampler=high_sampler,
            cpu_alert_percent=90,
            memory_alert_percent=90,
            alert_cooldown_seconds=1,
            audit_logger=audit,
        )
        service.collect_once()
        alert_events = [item for item in audit.events if item[0] == "system.resource_alert"]
        self.assertEqual(len(alert_events), 1)

    def test_tool_wrapper_actions(self):
        sample = {
            "timestamp": "2026-01-01T00:00:00Z",
            "cpu_percent": 33.0,
            "memory_percent": 44.0,
            "memory_used_mb": 1500,
            "memory_total_mb": 4000,
        }
        service = SystemMonitorService(enabled=True, auto_start=False, sampler=lambda: sample)
        tool = SystemMonitorTool(service=service)

        status = tool.run(action="status")
        summary = tool.run(action="summary")
        self.assertIn("status", status)
        self.assertIn("summary", summary)


if __name__ == "__main__":
    unittest.main()
