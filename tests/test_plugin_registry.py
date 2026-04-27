import json
import tempfile
import unittest
from pathlib import Path

from core.plugin_registry import PluginRegistry
from tools.plugin_manager import PluginManagerTool


class PluginRegistryTests(unittest.TestCase):
    def test_loads_and_matches_plugin_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir) / "plugins"
            plugin_dir.mkdir(parents=True, exist_ok=True)
            (plugin_dir / "janela.json").write_text(
                json.dumps(
                    {
                        "name": "janela_plugin",
                        "commands": [
                            {
                                "trigger": "abrir janela suite",
                                "intent": "home_control",
                                "device": "janela_suite",
                                "action": "abrir",
                                "response": "Abrindo janela da suite.",
                                "needs_action": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            registry = PluginRegistry(directory=str(plugin_dir), enabled=True)
            matched = registry.match("abrir janela suite")

            self.assertIsNotNone(matched)
            self.assertEqual(matched["intent"], "home_control")
            self.assertEqual(matched["device"], "janela_suite")

    def test_plugin_manager_tool_lists_and_reloads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir) / "plugins"
            plugin_dir.mkdir(parents=True, exist_ok=True)
            (plugin_dir / "a.json").write_text(
                json.dumps({"name": "a", "commands": [{"trigger": "cmd a", "intent": "status"}]}),
                encoding="utf-8",
            )
            registry = PluginRegistry(directory=str(plugin_dir), enabled=True)
            tool = PluginManagerTool(registry=registry)

            listed = tool.run(action="list")
            self.assertIn("plugins", listed)
            self.assertEqual(len(listed["plugins"]), 1)

            (plugin_dir / "b.json").write_text(
                json.dumps({"name": "b", "commands": [{"trigger": "cmd b", "intent": "status"}]}),
                encoding="utf-8",
            )
            reloaded = tool.run(action="reload")
            self.assertIn("report", reloaded)
            self.assertEqual(reloaded["report"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
