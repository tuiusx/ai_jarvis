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
        plan = self.planner.create_plan(
            {"intent": "surveillance_start", "duration": 15, "response": "Monitorando."}
        )

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

    def test_creates_question_answer_plan(self):
        plan = self.planner.create_plan({"intent": "question_answer", "response": "Resposta direta."})
        self.assertEqual(plan["steps"], [{"action": "respond", "message": "Resposta direta."}])

    def test_creates_remember_plan(self):
        plan = self.planner.create_plan({"intent": "remember", "memory": "a senha e 1234"})
        self.assertEqual(plan["steps"], [{"action": "remember", "text": "a senha e 1234"}])

    def test_creates_recall_plan(self):
        plan = self.planner.create_plan({"intent": "recall", "query": "senha", "limit": 2})
        self.assertEqual(plan["steps"], [{"action": "recall", "query": "senha", "limit": 2}])


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
        self.assertIn("não encontrada", result["error"])


if __name__ == "__main__":
    unittest.main()
