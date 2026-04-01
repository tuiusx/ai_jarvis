import unittest

from tools.home_automation import HomeAutomationTool


class HomeAutomationToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = HomeAutomationTool()

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


if __name__ == "__main__":
    unittest.main()
