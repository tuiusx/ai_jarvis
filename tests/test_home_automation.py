import tempfile
import unittest
from pathlib import Path

from tools.home_automation import HomeAutomationTool


class HomeAutomationToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        custom_path = Path(self.temp_dir.name) / "state" / "home_custom_devices.json"
        self.tool = HomeAutomationTool(custom_devices_path=str(custom_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_controls_light_and_outlet(self):
        light = self.tool.run(device="luz", action="on")
        outlet = self.tool.run(device="tomada", action="off")

        self.assertEqual(light["status"], "on")
        self.assertIn("ligada", light["message"])
        self.assertEqual(outlet["status"], "off")
        self.assertIn("desligada", outlet["message"])

    def test_controls_lock_and_toggle(self):
        locked = self.tool.run(device="fechadura", action="lock")
        unlocked = self.tool.run(device="fechadura", action="unlock")
        toggled = self.tool.run(device="fechadura", action="toggle")

        self.assertEqual(locked["status"], "locked")
        self.assertEqual(unlocked["status"], "unlocked")
        self.assertEqual(toggled["status"], "locked")
        self.assertIn("trancada", toggled["message"])

    def test_rejects_unknown_device_and_invalid_action(self):
        unknown_device = self.tool.run(device="garagem", action="on")
        invalid_action = self.tool.run(device="luz", action="lock")

        self.assertIn("nao gerenciado", unknown_device["error"])
        self.assertIn("nao suportada", invalid_action["error"])

    def test_dry_run_does_not_change_internal_state(self):
        custom_path = Path(self.temp_dir.name) / "state" / "home_custom_devices_dry.json"
        tool = HomeAutomationTool(dry_run=True, custom_devices_path=str(custom_path))
        before = dict(tool.state)
        result = tool.run(device="luz", action="on")
        after = dict(tool.state)

        self.assertTrue(result["dry_run"])
        self.assertEqual(before, after)
        self.assertIn("simulacao", result["message"].lower())

    def test_registers_custom_device_and_controls_it(self):
        register = self.tool.run(
            action="register_device",
            device="janela",
            open_action="abrir",
            close_action="fechar",
        )
        open_result = self.tool.run(device="janela", action="abrir")
        close_result = self.tool.run(device="janela", action="fechar")

        self.assertIn("cadastrados", register["message"].lower())
        self.assertEqual(open_result["status"], "aberta")
        self.assertEqual(close_result["status"], "fechada")

    def test_dispatches_iot_webhook_when_enabled(self):
        custom_path = Path(self.temp_dir.name) / "state" / "home_custom_devices_webhook.json"
        calls = []

        def fake_sender(url, payload, timeout):
            calls.append((url, payload, timeout))
            return True

        tool = HomeAutomationTool(
            custom_devices_path=str(custom_path),
            iot_webhook_enabled=True,
            iot_webhook_url="https://iot.local/event",
            webhook_sender=fake_sender,
        )
        result = tool.run(device="luz", action="on")

        self.assertIn("iot", result)
        self.assertTrue(result["iot"]["sent"])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
