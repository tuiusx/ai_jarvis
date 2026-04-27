import unittest

from core.planner import Planner
from tools.manager import ToolManager


class DummyTool:
    name = "dummy_tool"

    def run(self, **kwargs):
        return {"message": f"executado com {kwargs}"}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def test_creates_home_control_plan(self):
        plan = self.planner.create_plan(
            {
                "intent": "home_control",
                "device": "fechadura",
                "action": "lock",
                "response": "Trancando a fechadura.",
            }
        )

        self.assertEqual(plan["steps"][0]["tool"], "home_control")
        self.assertEqual(plan["steps"][0]["device"], "fechadura")
        self.assertEqual(plan["steps"][0]["action"], "lock")
        self.assertEqual(plan["steps"][1]["message"], "Trancando a fechadura.")

    def test_creates_surveillance_plan(self):
        plan = self.planner.create_plan({"intent": "surveillance_start", "duration": 15, "response": "Monitorando."})

        self.assertEqual(plan["steps"][0]["tool"], "surveillance")
        self.assertEqual(plan["steps"][0]["action"], "start")
        self.assertEqual(plan["steps"][0]["duration"], 15)

    def test_returns_default_response_plan(self):
        plan = self.planner.create_plan({"intent": "unknown", "response": "Entendi."})
        self.assertEqual(plan["steps"], [{"action": "respond", "message": "Entendi."}])

    def test_creates_network_scan_plan(self):
        plan = self.planner.create_plan({"intent": "network_scan", "response": "Escaneando."})
        self.assertEqual(plan["steps"][0]["tool"], "network_scan")
        self.assertEqual(plan["steps"][0]["limit"], 50)
        self.assertEqual(plan["steps"][1]["message"], "Escaneando.")

    def test_creates_network_search_plan(self):
        plan = self.planner.create_plan({"intent": "network_search", "query": "energia solar"})
        self.assertEqual(plan["steps"][0]["tool"], "web_search")
        self.assertEqual(plan["steps"][0]["query"], "energia solar")

    def test_creates_network_monitor_and_enforcement_plans(self):
        monitor_plan = self.planner.create_plan({"intent": "network_monitor_start"})
        block_plan = self.planner.create_plan({"intent": "network_block_internet"})
        machine_plan = self.planner.create_plan({"intent": "network_block_machine_internet", "alias": "tv_sala"})

        self.assertEqual(monitor_plan["steps"][0]["tool"], "network_monitor")
        self.assertEqual(monitor_plan["steps"][0]["action"], "start")
        self.assertEqual(block_plan["steps"][0]["tool"], "network_enforce")
        self.assertEqual(block_plan["steps"][0]["action"], "block_internet_global")
        self.assertEqual(machine_plan["steps"][0]["alias"], "tv_sala")

    def test_creates_question_answer_plan(self):
        plan = self.planner.create_plan({"intent": "question_answer", "response": "Resposta direta."})
        self.assertEqual(plan["steps"], [{"action": "respond", "message": "Resposta direta."}])

    def test_creates_remember_plan(self):
        plan = self.planner.create_plan({"intent": "remember", "memory": "a senha e 1234"})
        self.assertEqual(plan["steps"], [{"action": "remember", "text": "a senha e 1234"}])

    def test_creates_recall_plan(self):
        plan = self.planner.create_plan({"intent": "recall", "query": "senha", "limit": 2})
        self.assertEqual(plan["steps"], [{"action": "recall", "query": "senha", "limit": 2}])

    def test_creates_status_plan(self):
        plan = self.planner.create_plan({"intent": "status"})
        self.assertEqual(plan["steps"], [{"action": "status"}])

    def test_creates_memory_export_plan(self):
        plan = self.planner.create_plan({"intent": "memory_export", "path": "state/backup.enc", "password": "123"})
        self.assertEqual(plan["steps"], [{"action": "memory_export", "path": "state/backup.enc", "password": "123"}])

    def test_creates_memory_import_plan(self):
        plan = self.planner.create_plan({"intent": "memory_import", "path": "state/backup.enc", "password": "123"})
        self.assertEqual(plan["steps"], [{"action": "memory_import", "path": "state/backup.enc", "password": "123"}])

    def test_creates_custom_home_command_registration_plan(self):
        plan = self.planner.create_plan(
            {
                "intent": "home_register_device_commands",
                "device": "janela",
                "open_action": "abrir",
                "close_action": "fechar",
            }
        )
        self.assertEqual(plan["steps"][0]["tool"], "home_control")
        self.assertEqual(plan["steps"][0]["action"], "register_device")
        self.assertEqual(plan["steps"][0]["device"], "janela")
        self.assertEqual(plan["steps"][0]["open_action"], "abrir")
        self.assertEqual(plan["steps"][0]["close_action"], "fechar")

    def test_creates_critical_confirmation_plan(self):
        plan = self.planner.create_plan({"intent": "confirm_critical_action", "token": "abc12345"})
        self.assertEqual(
            plan["steps"],
            [{"action": "confirm_critical_action", "token": "abc12345", "pin": ""}],
        )

    def test_creates_automation_plans(self):
        scene_create = self.planner.create_plan(
            {
                "intent": "automation_scene_create",
                "scene": "boa_noite",
                "steps": [{"device": "luz", "action": "off"}],
            }
        )
        schedule_create = self.planner.create_plan(
            {
                "intent": "automation_schedule_create",
                "scene": "boa_noite",
                "delay_seconds": 30,
                "interval_seconds": 0,
            }
        )
        rule_create = self.planner.create_plan(
            {
                "intent": "automation_rule_create",
                "rule_name": "intrusao_noturna",
                "event_name": "intrusao_detectada",
                "scene": "boa_noite",
                "contains": "",
            }
        )
        backup = self.planner.create_plan({"intent": "backup_now"})
        plugins = self.planner.create_plan({"intent": "plugin_list"})

        self.assertEqual(scene_create["steps"][0]["tool"], "automation_hub")
        self.assertEqual(scene_create["steps"][0]["action"], "create_scene")
        self.assertEqual(schedule_create["steps"][0]["action"], "schedule_scene")
        self.assertEqual(rule_create["steps"][0]["action"], "create_rule")
        self.assertEqual(backup["steps"][0]["tool"], "backup_manager")
        self.assertEqual(plugins["steps"][0]["tool"], "plugin_manager")


class ToolManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = ToolManager()
        self.manager.register(DummyTool())

    def test_executes_registered_tool(self):
        result = self.manager.execute({"tool": "dummy_tool", "foo": "bar"})
        self.assertEqual(result["message"], "executado com {'foo': 'bar'}")

    def test_executes_respond_action(self):
        result = self.manager.execute({"action": "respond", "message": "ok"})
        self.assertEqual(result, {"message": "ok"})

    def test_returns_error_for_missing_tool(self):
        result = self.manager.execute({"tool": "missing"})
        self.assertIn("nao encontrada", result["error"])


if __name__ == "__main__":
    unittest.main()
