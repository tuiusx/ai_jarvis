import os
import re
import unittest
from unittest.mock import patch

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


class FakeLongMemory:
    def __init__(self):
        self.items = []

    def add(self, text):
        self.items.append({"text": text})
        return {"text": text}

    def search(self, query, limit=3):
        matches = [item for item in self.items if query in item["text"]]
        return matches[:limit]

    def export_encrypted(self, path, password):
        if not password:
            raise ValueError("senha obrigatoria")
        return path

    def import_encrypted(self, path, password):
        if not password:
            raise ValueError("senha obrigatoria")
        return {"imported": 1, "total": len(self.items)}


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


class FlakyTools:
    def __init__(self, fails_before_success=1):
        self.fails_before_success = int(fails_before_success)
        self.calls = 0

    def execute(self, step):
        self.calls += 1
        if self.calls <= self.fails_before_success:
            raise RuntimeError("falha transitoria")
        return {"message": "acao executada"}


class FakeAccessController:
    def __init__(self, responses):
        self.responses = list(responses)
        self.enabled = True

    def authorize_command(self, command_text):
        if self.responses:
            return self.responses.pop(0)
        return {"allowed": True, "handled": False, "user": "owner"}


class FakeNetworkGuard:
    def __init__(self, responses):
        self.responses = list(responses)
        self.enabled = True

    def authorize_command(self, command_text):
        if self.responses:
            return self.responses.pop(0)
        return {"allowed": True}


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
        self.assertTrue(any(msg.startswith("JARVIS online") for msg in interface.outputs))
        self.assertIn("A luz da casa esta ligada.", interface.outputs)
        self.assertIn("Ligando a luz.", interface.outputs)

    def test_act_handles_remember_and_recall_actions(self):
        memory = FakeMemory()
        long_memory = FakeLongMemory()
        agent = Agent(FakeLLM(), memory, FakePlanner(), FakeTools(), FakeInterface([]), long_memory=long_memory)

        remember_result = agent.act({"steps": [{"action": "remember", "text": "a senha e 1234"}]})
        recall_result = agent.act({"steps": [{"action": "recall", "query": "senha"}]})

        self.assertEqual(remember_result[0]["message"], "Memoria registrada: a senha e 1234")
        self.assertIn("Encontrei na memoria", recall_result[0]["message"])

    def test_act_handles_status_and_memory_backup_actions(self):
        memory = FakeMemory()
        long_memory = FakeLongMemory()
        long_memory.add("senha backup")
        agent = Agent(FakeLLM(), memory, FakePlanner(), FakeTools(), FakeInterface([]), long_memory=long_memory)

        status_result = agent.act({"steps": [{"action": "status"}]})
        export_result = agent.act(
            {"steps": [{"action": "memory_export", "path": "state/backup.enc", "password": "segredo"}]}
        )
        import_result = agent.act(
            {"steps": [{"action": "memory_import", "path": "state/backup.enc", "password": "segredo"}]}
        )

        self.assertIn("uptime", status_result[0]["status"])
        self.assertIn("Backup", export_result[0]["message"])
        self.assertIn("importado", import_result[0]["message"].lower())

    def test_recall_formats_semantic_top_results_with_timestamp(self):
        memory = FakeMemory()
        long_memory = FakeLongMemory()
        long_memory.search = lambda query, limit=3: [
            {
                "text": "A chave da garagem fica no armario azul",
                "timestamp": "2026-04-25T08:10:00",
                "source": "semantic",
                "score": 0.88,
            },
            {
                "text": "A lampada da entrada e automatica",
                "timestamp": "2026-04-24T22:00:00",
                "source": "semantic",
                "score": 0.84,
            },
        ]
        agent = Agent(FakeLLM(), memory, FakePlanner(), FakeTools(), FakeInterface([]), long_memory=long_memory)

        recall_result = agent.act({"steps": [{"action": "recall", "query": "garagem"}]})

        self.assertIn("Resumo", recall_result[0]["message"])
        self.assertIn("2026-04-25", recall_result[0]["message"])

    def test_perceive_blocks_command_when_access_is_denied(self):
        interface = FakeInterface([{"mode": "text", "content": "ligar luz", "confidence": 1.0}])
        access = FakeAccessController(
            [{"allowed": False, "handled": False, "user": "maria", "message": "Acesso negado."}]
        )
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, access_controller=access)

        perception = agent.perceive()

        self.assertIsNone(perception)
        self.assertIn("Acesso negado.", interface.outputs)

    def test_perceive_handles_owner_permission_command_without_execution(self):
        interface = FakeInterface([{"mode": "text", "content": "autorizar maria", "confidence": 1.0}])
        access = FakeAccessController(
            [
                {
                    "allowed": False,
                    "handled": True,
                    "user": "owner",
                    "message": "Permissao concedida para maria.",
                }
            ]
        )
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, access_controller=access)

        perception = agent.perceive()

        self.assertIsNone(perception)
        self.assertIn("Permissao concedida para maria.", interface.outputs)

    def test_perceive_includes_authorized_user(self):
        interface = FakeInterface([{"mode": "text", "content": "ligar luz", "confidence": 1.0}])
        access = FakeAccessController([{"allowed": True, "handled": False, "user": "maria"}])
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, access_controller=access)

        perception = agent.perceive()

        self.assertIsNotNone(perception)
        self.assertEqual(perception["user"], "maria")

    def test_perceive_blocks_command_when_network_is_untrusted(self):
        interface = FakeInterface([{"mode": "text", "content": "ligar luz", "confidence": 1.0}])
        network_guard = FakeNetworkGuard([{"allowed": False, "message": "Rede nao confiavel."}])
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, network_guard=network_guard)

        perception = agent.perceive()

        self.assertIsNone(perception)
        self.assertIn("Rede nao confiavel.", interface.outputs)

    def test_perceive_allows_command_when_network_warns(self):
        interface = FakeInterface([{"mode": "text", "content": "ligar luz", "confidence": 1.0}])
        network_guard = FakeNetworkGuard([{"allowed": True, "warning": True, "message": "Rede nao confiavel."}])
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface, network_guard=network_guard)

        perception = agent.perceive()

        self.assertIsNotNone(perception)
        self.assertIn("Rede nao confiavel.", interface.outputs)

    def test_process_command_data_returns_timings_and_updates_status(self):
        memory = FakeMemory()
        agent = Agent(
            FakeLLM(),
            memory,
            FakePlanner(),
            FakeTools(),
            interface=None,
            performance_config={"enabled_metrics": True, "slow_command_threshold_ms": 1},
        )

        payload = agent.process_command_data(
            data={"mode": "text", "content": "ligar luz", "confidence": 1.0},
            auto_remember=True,
        )
        status = agent.runtime_status()

        self.assertEqual(payload["state"], "processed")
        self.assertIn("total_ms", payload["timings_ms"])
        self.assertGreaterEqual(status["performance"]["commands_timed"], 1)
        self.assertIn("home_control", status["performance"]["intent_counts"])

    def test_act_requires_confirmation_for_critical_network_step(self):
        tools = FakeTools()
        agent = Agent(
            FakeLLM(),
            FakeMemory(),
            FakePlanner(),
            tools,
            interface=None,
            critical_confirmation_require_pin=False,
        )
        first_results = agent.act(
            {"steps": [{"tool": "network_enforce", "action": "block_internet_global"}]},
            perception={"user": "owner"},
        )

        self.assertEqual(len(tools.executed_steps), 0)
        self.assertIn("confirmar comando", first_results[0]["message"].lower())
        token_match = re.search(r"confirmar comando ([a-f0-9]{8})", first_results[0]["message"].lower())
        self.assertIsNotNone(token_match)

        token = token_match.group(1)
        confirm_results = agent.act(
            {"steps": [{"action": "confirm_critical_action", "token": token}]},
            perception={"user": "owner"},
        )

        self.assertEqual(len(tools.executed_steps), 1)
        self.assertIn("[CONFIRMADO]", confirm_results[0]["message"])

    def test_execute_tool_with_retry_succeeds_after_transient_error(self):
        tools = FlakyTools(fails_before_success=1)
        agent = Agent(
            FakeLLM(),
            FakeMemory(),
            FakePlanner(),
            tools,
            interface=None,
            tool_retry_attempts=1,
            tool_retry_backoff_seconds=0.0,
            critical_confirmation_enabled=False,
        )

        results = agent.act({"steps": [{"tool": "home_control", "device": "luz", "action": "on"}]})

        self.assertEqual(results[0]["message"], "acao executada")
        self.assertEqual(tools.calls, 2)

    def test_confirm_critical_action_requires_pin_when_enabled(self):
        tools = FakeTools()
        agent = Agent(
            FakeLLM(),
            FakeMemory(),
            FakePlanner(),
            tools,
            interface=None,
            critical_confirmation_require_pin=True,
            critical_confirmation_pin_env="JARVIS_TEST_PIN",
        )

        with patch.dict(os.environ, {"JARVIS_TEST_PIN": "4455"}, clear=False):
            first_results = agent.act(
                {"steps": [{"tool": "network_enforce", "action": "block_internet_global"}]},
                perception={"user": "owner"},
            )
            token_match = re.search(r"confirmar comando ([a-f0-9]{8})", first_results[0]["message"].lower())
            self.assertIsNotNone(token_match)
            token = token_match.group(1)

            missing_pin = agent.act(
                {"steps": [{"action": "confirm_critical_action", "token": token}]},
                perception={"user": "owner"},
            )
            self.assertIn("pin obrigatorio", missing_pin[0]["error"].lower())

            wrong_pin = agent.act(
                {"steps": [{"action": "confirm_critical_action", "token": token, "pin": "9999"}]},
                perception={"user": "owner"},
            )
            self.assertIn("pin invalido", wrong_pin[0]["error"].lower())

            ok_pin = agent.act(
                {"steps": [{"action": "confirm_critical_action", "token": token, "pin": "4455"}]},
                perception={"user": "owner"},
            )
            self.assertIn("[CONFIRMADO]", ok_pin[0]["message"])

    def test_device_wizard_registers_custom_command(self):
        tools = FakeTools()
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), tools, interface=None)

        start = agent.act({"steps": [{"action": "device_wizard_start", "device": "janela"}]}, perception={"user": "owner"})
        set_open = agent.act({"steps": [{"action": "device_wizard_set_open", "open_action": "abrir"}]}, perception={"user": "owner"})
        set_close = agent.act({"steps": [{"action": "device_wizard_set_close", "close_action": "fechar"}]}, perception={"user": "owner"})
        finish = agent.act({"steps": [{"action": "device_wizard_finish"}]}, perception={"user": "owner"})

        self.assertIn("assistente iniciado", start[0]["message"].lower())
        self.assertIn("abrir", set_open[0]["message"])
        self.assertIn("fechar", set_close[0]["message"])
        self.assertEqual(tools.executed_steps[-1]["action"], "register_device")
        self.assertIn("message", finish[0])

    def test_process_command_data_includes_trace_id(self):
        agent = Agent(FakeLLM(), FakeMemory(), FakePlanner(), FakeTools(), interface=None)
        payload = agent.process_command_data(
            data={"mode": "text", "content": "ligar luz", "confidence": 1.0},
            auto_remember=False,
        )
        self.assertEqual(payload["state"], "processed")
        self.assertTrue(payload.get("trace_id"))


if __name__ == "__main__":
    unittest.main()
