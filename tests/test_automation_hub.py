import tempfile
import unittest
from pathlib import Path

from core.automation_hub import AutomationHubService


class FakeHomeTool:
    def __init__(self):
        self.calls = []

    def run(self, device="", action="", **kwargs):
        self.calls.append((device, action))
        return {"message": f"{device}:{action}"}


class AutomationHubTests(unittest.TestCase):
    def test_creates_and_runs_scene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_tool = FakeHomeTool()
            service = AutomationHubService(
                home_tool=home_tool,
                state_path=str(Path(temp_dir) / "automation.json"),
                auto_start=False,
            )
            created = service.create_scene(
                scene="boa noite",
                steps=[{"device": "luz", "action": "off"}, {"device": "fechadura", "action": "lock"}],
            )
            self.assertIn("criada", created["message"])

            executed = service.run_scene("boa noite")
            self.assertIn("executada", executed["message"])
            self.assertEqual(len(home_tool.calls), 2)

    def test_schedule_and_rule_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_tool = FakeHomeTool()
            service = AutomationHubService(
                home_tool=home_tool,
                state_path=str(Path(temp_dir) / "automation.json"),
                auto_start=False,
            )
            service.create_scene(scene="alerta", steps=[{"device": "luz", "action": "on"}])

            schedule = service.schedule_scene(scene="alerta", delay_seconds=1, interval_seconds=0)
            self.assertIn("schedule", schedule)
            listed = service.list_schedules()
            self.assertEqual(len(listed["schedules"]), 1)

            cancel = service.cancel_schedule(schedule["schedule"]["id"])
            self.assertIn("cancelado", cancel["message"])

            rule = service.create_rule(
                rule_name="intrusao_rule",
                event_name="intrusao_detectada",
                scene="alerta",
                contains="sala",
            )
            self.assertIn("rule", rule)
            triggered = service.trigger_event("intrusao_detectada", payload="movimento na sala")
            self.assertEqual(len(triggered["triggered_rules"]), 1)


if __name__ == "__main__":
    unittest.main()
