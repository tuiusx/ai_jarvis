import tempfile
import unittest

from core.agent import Agent
from core.audit import AuditLogger
from core.rate_limit import CommandRateLimiter


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
    def recall(self, perception):
        return "ctx"

    def store(self, experience):
        return None


class FakeLLM:
    def think(self, perception, context):
        return {"intent": "home_control", "response": "Ligando luz", "needs_action": True}


class FakePlanner:
    def create_plan(self, analysis):
        return {"steps": [{"tool": "home_control", "device": "luz", "action": "on"}]}


class FakeTools:
    def execute(self, step):
        return {"message": "ok"}


class IntegrationFlowTests(unittest.TestCase):
    def test_rate_limit_blocks_fast_second_command(self):
        interface = FakeInterface(
            [
                {"mode": "text", "content": "ligar luz", "confidence": 1.0},
                {"mode": "text", "content": "ligar luz de novo", "confidence": 1.0},
            ]
        )
        limiter = CommandRateLimiter(min_interval_seconds=10.0)
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, rate_limiter=limiter)

        first = agent.perceive()
        second = agent.perceive()

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertTrue(any("evitar spam" in msg for msg in interface.outputs))

    def test_audit_logs_are_written_during_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit = AuditLogger(path=f"{temp_dir}/audit.log.jsonl")
            interface = FakeInterface([{"mode": "text", "content": "ligar luz", "confidence": 1.0}])
            agent = Agent(
                FakeLLM(),
                FakeMemory(),
                FakePlanner(),
                FakeTools(),
                interface,
                rate_limiter=CommandRateLimiter(0),
                audit_logger=audit,
            )

            perception = agent.perceive()
            analysis = agent.analyze(perception)
            plan = agent.plan(analysis)
            agent.act(plan)

            events = [entry["event"] for entry in audit.tail(limit=20)]
            self.assertIn("agent.perception", events)
            self.assertIn("agent.analysis", events)
            self.assertIn("tool.execute", events)


if __name__ == "__main__":
    unittest.main()
