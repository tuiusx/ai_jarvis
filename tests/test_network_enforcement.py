import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.machine_registry import MachineRegistry
from core.network_enforcement import NetworkEnforcementService, OpenWrtProvider


class FakeProvider:
    def __init__(self):
        self.available = True
        self.calls = []

    def block_internet_global(self):
        self.calls.append(("block_internet_global",))

    def unblock_internet_global(self):
        self.calls.append(("unblock_internet_global",))

    def block_machine_internet(self, alias, mac):
        self.calls.append(("block_machine_internet", alias, mac))

    def unblock_machine_internet(self, alias, mac):
        self.calls.append(("unblock_machine_internet", alias, mac))

    def block_machine_isolate(self, alias, mac):
        self.calls.append(("block_machine_isolate", alias, mac))

    def unblock_machine(self, alias, mac):
        self.calls.append(("unblock_machine", alias, mac))


class NetworkEnforcementTests(unittest.TestCase):
    def test_register_and_list_machines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = MachineRegistry(path=str(Path(temp_dir) / "registry.json"))
            service = NetworkEnforcementService(
                enabled=False,
                registry=registry,
                providers={},
                state_path=str(Path(temp_dir) / "state.json"),
            )

            saved = service.execute("register_machine", alias="tv sala", mac="aa:bb:cc:dd:ee:ff")
            listed = service.execute("list_machines")

            self.assertIn("registrada", saved["message"])
            self.assertEqual(len(listed["machines"]), 1)
            self.assertEqual(listed["machines"][0]["alias"], "tv_sala")

    def test_idempotent_block_and_unblock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = MachineRegistry(path=str(Path(temp_dir) / "registry.json"))
            registry.register("camera", "00:11:22:33:44:55")
            provider = FakeProvider()
            service = NetworkEnforcementService(
                enabled=True,
                registry=registry,
                providers={"openwrt": provider},
                provider_priority=["openwrt"],
                state_path=str(Path(temp_dir) / "state.json"),
            )

            first = service.execute("block_machine_internet", alias="camera")
            second = service.execute("block_machine_internet", alias="camera")
            third = service.execute("unblock_machine_internet", alias="camera")
            fourth = service.execute("unblock_machine_internet", alias="camera")

            self.assertIn("bloqueada", first["message"])
            self.assertIn("ja estava bloqueada", second["message"])
            self.assertIn("desbloqueada", third["message"])
            self.assertIn("ja estava liberada", fourth["message"])
            self.assertEqual(
                provider.calls,
                [
                    ("block_machine_internet", "camera", "00:11:22:33:44:55"),
                    ("unblock_machine_internet", "camera", "00:11:22:33:44:55"),
                ],
            )

    def test_openwrt_provider_builds_uci_commands(self):
        captured = []

        def fake_runner(args, check=False, timeout=15, input=None):
            captured.append({"args": args, "input": input})
            if args[-1] == "uci export firewall":
                return SimpleNamespace(returncode=0, stdout="config firewall", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        provider = OpenWrtProvider(
            host="192.168.1.1",
            username="root",
            command_runner=fake_runner,
        )
        provider.block_machine_internet(alias="camera sala", mac="aa:bb:cc:dd:ee:ff")

        joined_inputs = "\n".join((item.get("input") or "") for item in captured if item.get("input"))
        self.assertIn("uci -q delete firewall.jarvis_block_internet_camera_sala", joined_inputs)
        self.assertIn("uci set firewall.jarvis_block_internet_camera_sala.src_mac='aa:bb:cc:dd:ee:ff'", joined_inputs)


if __name__ == "__main__":
    unittest.main()
