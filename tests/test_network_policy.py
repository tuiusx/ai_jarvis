import unittest

from core.network_policy import NetworkPolicyGuard


class NetworkPolicyGuardTests(unittest.TestCase):
    def test_allows_when_disabled(self):
        guard = NetworkPolicyGuard(enabled=False)

        result = guard.authorize_command("ligar luz")

        self.assertTrue(result["allowed"])

    def test_blocks_untrusted_network_in_block_mode(self):
        guard = NetworkPolicyGuard(
            enabled=True,
            mode="block",
            allowed_cidrs=["192.168.10.0/24"],
            ip_provider=lambda: ["10.0.0.8"],
            check_interval_seconds=1,
        )

        result = guard.authorize_command("ligar luz")

        self.assertFalse(result["allowed"])
        self.assertIn("Rede nao confiavel", result["message"])

    def test_warns_untrusted_network_in_warn_mode(self):
        guard = NetworkPolicyGuard(
            enabled=True,
            mode="warn",
            allowed_cidrs=["192.168.10.0/24"],
            ip_provider=lambda: ["10.0.0.8"],
            check_interval_seconds=1,
        )

        result = guard.authorize_command("ligar luz")

        self.assertTrue(result["allowed"])
        self.assertTrue(result["warning"])

    def test_safe_commands_bypass_guard(self):
        guard = NetworkPolicyGuard(
            enabled=True,
            mode="block",
            allowed_cidrs=["192.168.10.0/24"],
            ip_provider=lambda: ["10.0.0.8"],
            check_interval_seconds=1,
        )

        result = guard.authorize_command("status")

        self.assertTrue(result["allowed"])

    def test_trusts_when_ip_is_inside_allowed_cidr(self):
        guard = NetworkPolicyGuard(
            enabled=True,
            mode="block",
            allowed_cidrs=["10.0.0.0/8"],
            ip_provider=lambda: ["10.1.1.7"],
            check_interval_seconds=1,
        )

        result = guard.authorize_command("ligar luz")

        self.assertTrue(result["allowed"])


if __name__ == "__main__":
    unittest.main()
