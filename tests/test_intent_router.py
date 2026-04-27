import json
import tempfile
import unittest
from pathlib import Path

from core.intent_router import IntentRouter


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_routes_home_control(self):
        result = self.router.route("ligar a luz da casa")
        self.assertEqual(result["intent"], "home_control")
        self.assertEqual(result["device"], "luz")
        self.assertEqual(result["action"], "on")

    def test_routes_network_monitor(self):
        result = self.router.route("iniciar rastreamento de rede")
        self.assertEqual(result["intent"], "network_monitor_start")

    def test_routes_network_block_by_machine(self):
        result = self.router.route("bloquear internet da maquina tv sala")
        self.assertEqual(result["intent"], "network_block_machine_internet")
        self.assertEqual(result["alias"], "tv sala")

    def test_routes_critical_confirmation_token(self):
        result = self.router.route("confirmar comando ab12cd34")
        self.assertEqual(result["intent"], "confirm_critical_action")
        self.assertEqual(result["token"], "ab12cd34")
        self.assertEqual(result["pin"], "")

    def test_routes_critical_confirmation_with_pin(self):
        result = self.router.route("confirmar comando ab12cd34 pin 4455")
        self.assertEqual(result["intent"], "confirm_critical_action")
        self.assertEqual(result["token"], "ab12cd34")
        self.assertEqual(result["pin"], "4455")

    def test_routes_memory_commands(self):
        export_result = self.router.route("exportar memoria state/backup.enc senha abc")
        import_result = self.router.route("importar memoria state/backup.enc senha abc")
        self.assertEqual(export_result["intent"], "memory_export")
        self.assertEqual(import_result["intent"], "memory_import")

    def test_looks_like_question(self):
        self.assertTrue(self.router.looks_like_question("qual a diferenca de cpu e gpu"))
        self.assertFalse(self.router.looks_like_question("ligar luz"))

    def test_routes_custom_device_registration(self):
        result = self.router.route("adicionar comando para dispositivo janela para abrir e fechar")
        self.assertEqual(result["intent"], "home_register_device_commands")
        self.assertEqual(result["device"], "janela")
        self.assertEqual(result["open_action"], "abrir")
        self.assertEqual(result["close_action"], "fechar")

    def test_routes_custom_device_control_from_registry_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "state" / "home_custom_devices.json"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(
                    {
                        "devices": {
                            "janela": {
                                "open_action": "abrir",
                                "close_action": "fechar",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            router = IntentRouter(custom_commands_path=str(registry_path))

            result = router.route("abrir janela")

            self.assertEqual(result["intent"], "home_control")
            self.assertEqual(result["device"], "janela")
            self.assertEqual(result["action"], "abrir")

    def test_routes_automation_scene_commands(self):
        create = self.router.route("criar cena boa noite com luz:off, fechadura:lock")
        run = self.router.route("executar cena boa noite")
        schedule = self.router.route("agendar cena boa noite em 5 minutos a cada 10 minutos")

        self.assertEqual(create["intent"], "automation_scene_create")
        self.assertEqual(create["scene"], "boa_noite")
        self.assertEqual(len(create["steps"]), 2)
        self.assertEqual(run["intent"], "automation_scene_run")
        self.assertEqual(schedule["intent"], "automation_schedule_create")
        self.assertEqual(schedule["delay_seconds"], 300)
        self.assertEqual(schedule["interval_seconds"], 600)

    def test_routes_backup_and_plugin_commands(self):
        backup = self.router.route("executar backup agora")
        status = self.router.route("status backup")
        list_plugins = self.router.route("listar plugins")
        reload_plugins = self.router.route("recarregar plugins")

        self.assertEqual(backup["intent"], "backup_now")
        self.assertEqual(status["intent"], "backup_status")
        self.assertEqual(list_plugins["intent"], "plugin_list")
        self.assertEqual(reload_plugins["intent"], "plugin_reload")

    def test_routes_periodic_tests_and_system_monitor_commands(self):
        tests_now = self.router.route("executar testes agora")
        tests_status = self.router.route("status testes")
        monitor_start = self.router.route("iniciar monitoramento de sistema")
        monitor_status = self.router.route("status monitoramento de sistema")
        monitor_summary = self.router.route("resumo recursos do sistema")

        self.assertEqual(tests_now["intent"], "tests_run_now")
        self.assertEqual(tests_status["intent"], "tests_status")
        self.assertEqual(monitor_start["intent"], "system_monitor_start")
        self.assertEqual(monitor_status["intent"], "system_monitor_status")
        self.assertEqual(monitor_summary["intent"], "system_monitor_summary")


if __name__ == "__main__":
    unittest.main()
