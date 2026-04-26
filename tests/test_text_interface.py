import io
import unittest
from contextlib import redirect_stdout

from interfaces import text as text_interface


class FakeAgent:
    def __init__(self, perception):
        self.perception = perception
        self.prepare_calls = []
        self.status_calls = 0

    def prepare_perception_from_data(self, data, output_callback=None):
        self.prepare_calls.append(dict(data))
        return self.perception

    def runtime_status(self):
        self.status_calls += 1
        return {
            "mode": "dev",
            "uptime": 1.2,
            "processed_commands": 1,
            "rate_limited_commands": 0,
            "short_term_entries": 0,
            "long_term_entries": 0,
            "last_cleanup": {},
            "semantic_memory": {"ready": False},
            "access_control_enabled": True,
            "network_guard_enabled": True,
            "performance": {"p95_total_ms": 0.0},
        }

    @staticmethod
    def format_status_message(status):
        return f"Status | mode={status.get('mode')}"


class FakeMemory:
    def __init__(self, context_text="linha 1"):
        self.context_text = context_text
        self.get_context_calls = 0

    def get_context(self):
        self.get_context_calls += 1
        return self.context_text


class TextInterfaceTests(unittest.TestCase):
    def test_status_shortcut_requires_precheck_before_showing_status(self):
        agent = FakeAgent(perception={"content": "status"})
        memory = FakeMemory()

        with redirect_stdout(io.StringIO()):
            handled = text_interface._handle_protected_shortcuts(
                "status",
                user_input="status",
                agent=agent,
                memory=memory,
                output_callback=lambda msg: msg,
            )

        self.assertTrue(handled)
        self.assertEqual(agent.status_calls, 1)
        self.assertEqual(len(agent.prepare_calls), 1)
        self.assertEqual(agent.prepare_calls[0]["content"], "status")

    def test_memoria_shortcut_requires_precheck_before_reading_memory(self):
        agent = FakeAgent(perception=None)
        memory = FakeMemory(context_text="segredo")

        with redirect_stdout(io.StringIO()):
            handled = text_interface._handle_protected_shortcuts(
                "memoria",
                user_input="memoria",
                agent=agent,
                memory=memory,
                output_callback=lambda msg: msg,
            )

        self.assertTrue(handled)
        self.assertEqual(len(agent.prepare_calls), 1)
        self.assertEqual(memory.get_context_calls, 0)

    def test_non_protected_shortcut_returns_false_without_precheck(self):
        agent = FakeAgent(perception={"content": "ligar luz"})
        memory = FakeMemory()

        handled = text_interface._handle_protected_shortcuts(
            "ligar luz",
            user_input="ligar luz",
            agent=agent,
            memory=memory,
            output_callback=lambda msg: msg,
        )

        self.assertFalse(handled)
        self.assertEqual(agent.prepare_calls, [])
        self.assertEqual(memory.get_context_calls, 0)


if __name__ == "__main__":
    unittest.main()
