import importlib
import sys
import types
import unittest
from unittest.mock import patch


def load_llm_module():
    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = lambda stream: {}

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("fallback disabled in tests")

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAIClient:
        def __init__(self, api_key=None):
            self.chat = FakeChat()

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = FakeOpenAIClient

    with patch.dict(sys.modules, {"yaml": fake_yaml, "openai": fake_openai}):
        sys.modules.pop("core.llm", None)
        module = importlib.import_module("core.llm")
        return importlib.reload(module)


class LocalLLMTests(unittest.TestCase):
    def setUp(self):
        llm_module = load_llm_module()
        self.llm = llm_module.LocalLLM()

    def test_matches_light_command(self):
        result = self.llm.think({"content": "ligar a luz da casa"}, "")
        self.assertEqual(result["intent"], "home_control")
        self.assertEqual(result["device"], "luz")
        self.assertEqual(result["action"], "on")

    def test_matches_outlet_command(self):
        result = self.llm.think({"content": "desligar a tomada da casa"}, "")
        self.assertEqual(result["device"], "tomada")
        self.assertEqual(result["action"], "off")

    def test_matches_lock_and_unlock_commands(self):
        lock_result = self.llm.think({"content": "trancar a fechadura da casa"}, "")
        unlock_result = self.llm.think({"content": "destrancar a porta da casa"}, "")

        self.assertEqual(lock_result["device"], "fechadura")
        self.assertEqual(lock_result["action"], "lock")
        self.assertEqual(unlock_result["action"], "unlock")

    def test_matches_network_scan_command(self):
        result = self.llm.think({"content": "quero escanear a rede da casa"}, "")
        self.assertEqual(result["intent"], "network_scan")
        self.assertEqual(result["action"], "network_scan")

    def test_returns_safe_unknown_response_when_not_understood(self):
        result = self.llm.think({"content": "comando aleatorio"}, "")
        self.assertEqual(result["intent"], "unknown")
        self.assertIn("ligar a luz da casa", result["response"])


if __name__ == "__main__":
    unittest.main()
