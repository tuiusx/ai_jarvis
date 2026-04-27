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

    def test_matches_light_command_with_accents(self):
        result = self.llm.think({"content": "Ligar a lâmpada da casa"}, "")
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

    def test_matches_network_search_command(self):
        result = self.llm.think({"content": "pesquise na internet sobre energia solar residencial"}, "")
        self.assertEqual(result["intent"], "network_search")
        self.assertEqual(result["action"], "network_search")
        self.assertIn("energia solar", result["query"])

    def test_matches_network_monitor_and_block_commands(self):
        start = self.llm.think({"content": "iniciar rastreamento de rede"}, "")
        block = self.llm.think({"content": "bloquear internet da maquina tv sala"}, "")
        isolate = self.llm.think({"content": "bloquear maquina tv sala"}, "")
        list_blocks = self.llm.think({"content": "listar bloqueios de rede"}, "")

        self.assertEqual(start["intent"], "network_monitor_start")
        self.assertEqual(block["intent"], "network_block_machine_internet")
        self.assertEqual(isolate["intent"], "network_block_machine_isolate")
        self.assertEqual(list_blocks["intent"], "network_list_blocks")

    def test_matches_machine_registry_command(self):
        result = self.llm.think({"content": "registrar maquina notebook sala aa:bb:cc:dd:ee:ff"}, "")

        self.assertEqual(result["intent"], "network_register_machine")
        self.assertEqual(result["alias"], "notebook sala")
        self.assertEqual(result["mac"], "aa:bb:cc:dd:ee:ff")

    def test_matches_question_answer_intent(self):
        result = self.llm.think({"content": "qual a diferenca entre ram e rom?"}, "")
        self.assertEqual(result["intent"], "question_answer")
        self.assertTrue(result["response"])

    def test_matches_remember_intent(self):
        result = self.llm.think({"content": "lembre que a senha do cofre e azul"}, "")
        self.assertEqual(result["intent"], "remember")
        self.assertEqual(result["memory"], "a senha do cofre e azul")

    def test_matches_recall_intent(self):
        result = self.llm.think({"content": "o que voce sabe sobre senha do cofre?"}, "")
        self.assertEqual(result["intent"], "recall")
        self.assertEqual(result["query"], "senha do cofre")

    def test_status_intent_requests_runtime_summary(self):
        result = self.llm.think({"content": "status"}, "")
        self.assertEqual(result["intent"], "status")
        self.assertTrue(result["needs_action"])

    def test_matches_memory_export_command(self):
        result = self.llm.think({"content": "exportar memoria state/backup.enc senha segredo123"}, "")
        self.assertEqual(result["intent"], "memory_export")
        self.assertEqual(result["path"], "state/backup.enc")
        self.assertEqual(result["password"], "segredo123")

    def test_matches_memory_import_command(self):
        result = self.llm.think({"content": "importar memoria state/backup.enc senha segredo123"}, "")
        self.assertEqual(result["intent"], "memory_import")
        self.assertEqual(result["path"], "state/backup.enc")
        self.assertEqual(result["password"], "segredo123")

    def test_matches_periodic_tests_and_system_monitor_commands(self):
        tests_now = self.llm.think({"content": "executar testes agora"}, "")
        tests_status = self.llm.think({"content": "status testes"}, "")
        monitor_status = self.llm.think({"content": "status monitoramento de sistema"}, "")

        self.assertEqual(tests_now["intent"], "tests_run_now")
        self.assertEqual(tests_status["intent"], "tests_status")
        self.assertEqual(monitor_status["intent"], "system_monitor_status")

    def test_returns_safe_unknown_response_when_not_understood(self):
        result = self.llm.think({"content": "comando aleatorio"}, "")
        self.assertEqual(result["intent"], "unknown")
        self.assertIn("ligar a luz da casa", result["response"])


if __name__ == "__main__":
    unittest.main()
