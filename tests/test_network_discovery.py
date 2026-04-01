import unittest
from unittest.mock import patch

from tools.network_discovery import NetworkDiscoveryTool


class NetworkDiscoveryToolTests(unittest.TestCase):
    def test_parses_arp_output(self):
        arp_output = """
Interface: 192.168.0.10 --- 0x7
  Internet Address      Physical Address      Type
  192.168.0.1           aa-bb-cc-dd-ee-ff     dynamic
  192.168.0.20          11-22-33-44-55-66     dynamic
"""
        with patch("subprocess.check_output", return_value=arp_output):
            result = NetworkDiscoveryTool().run()

        self.assertEqual(result["event"], "network_scan")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["devices"][0]["ip"], "192.168.0.1")
        self.assertEqual(result["devices"][0]["mac"], "aa-bb-cc-dd-ee-ff")

    def test_handles_command_error(self):
        with patch("subprocess.check_output", side_effect=RuntimeError("arp failure")):
            result = NetworkDiscoveryTool().run()

        self.assertIn("error", result)
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
