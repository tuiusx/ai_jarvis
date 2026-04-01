import unittest

from core.agent import Agent


class FakeInterface:
    def __init__(self, inputs):
        self.inputs = list(inputs)
        self.outputs = []

    def get_input(self):
        if self.inputs:
            return self.inputs.pop(0)
        return {"mode": "text", "content": "sair", "confidence": 1.0}

    def output(self, message):
        self.outputs.append(message)


class FakeMemory:
    def __init__(self):
        self.store_calls = []

    def recall(self, perception):
        return "contexto"

    def store(self, experience):
        self.store_calls.append(experience)


class FakeLLM:
    def think(self, perception, context):
        return {"intent": "home_control", "response": "Ligando a luz."}


class FakePlanner:
    def create_plan(self, analysis):
        return {"steps": [{"tool": "home_control"}, {"action": "respond", "message": analysis["response"]}]}


class FakeTools:
    def __init__(self):
        self.executed_steps = []

    def execute(self, step):
        self.executed_steps.append(step)
        if step.get("tool") == "explode":
            raise RuntimeError("falhou")
        if step.get("tool") == "home_control":
            return {"message": "A luz da casa esta ligada."}
        return {"message": step.get("message", "ok")}


class AgentTests(unittest.TestCase):
    def test_perceive_stops_on_exit_command(self):
        interface = FakeInterface([{"mode": "text", "content": "sair", "confidence": 1.0}])
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface)

        perception = agent.perceive()

        self.assertIsNone(perception)
        self.assertFalse(agent.running)
        self.assertIn("Encerrando JARVIS...", interface.outputs)

    def test_act_collects_tool_errors(self):
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), FakeInterface([]))
        plan = {"steps": [{"tool": "explode"}]}

        results = agent.act(plan)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["error"], "falhou")

    def test_run_processes_command_and_stores_experience_once(self):
        interface = FakeInterface(
            [
                {"mode": "text", "content": "ligar a luz da casa", "confidence": 1.0},
                {"mode": "text", "content": "sair", "confidence": 1.0},
            ]
        )
        memory = FakeMemory()
        tools = FakeTools()
        agent = Agent(FakeLLM(), memory, FakePlanner(), tools, interface)

        agent.run()

        self.assertEqual(len(memory.store_calls), 1)
        self.assertEqual(len(tools.executed_steps), 2)
        self.assertIn("JARVIS online. Sempre escutando...", interface.outputs)
        self.assertIn("A luz da casa esta ligada.", interface.outputs)
        self.assertIn("Ligando a luz.", interface.outputs)


if __name__ == "__main__":
    unittest.main()
