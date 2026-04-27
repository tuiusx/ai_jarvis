import unittest

from core.command_pipeline import CommandFlowPipeline, CommandPrecheckPipeline


class FakeRateLimiter:
    def __init__(self, responses):
        self.responses = list(responses)

    def allow(self):
        if self.responses:
            return self.responses.pop(0)
        return True, 0.0


class FakeAccessController:
    def __init__(self, response):
        self.response = response

    def authorize_command(self, content):
        return dict(self.response)


class FakeNetworkGuard:
    def __init__(self, response):
        self.response = response

    def authorize_command(self, content):
        return dict(self.response)


class FakeAudit:
    def __init__(self):
        self.events = []

    def log(self, event, severity="info", **data):
        self.events.append((event, severity, data))


class CommandPipelineTests(unittest.TestCase):
    def test_parse_input_and_exit_detection(self):
        flow = CommandFlowPipeline()
        parsed = flow.parse_input({"mode": "text", "content": "ligar luz", "confidence": 1.0})
        self.assertEqual(parsed["content"], "ligar luz")
        self.assertTrue(flow.is_exit_command("sair"))

    def test_precheck_allow_warn_deny(self):
        audit = FakeAudit()
        allow = CommandPrecheckPipeline(
            rate_limiter=FakeRateLimiter([(True, 0.0)]),
            access_controller=FakeAccessController({"allowed": True, "handled": False, "user": "maria"}),
            network_guard=FakeNetworkGuard({"allowed": True}),
            audit_logger=audit,
        ).evaluate("ligar luz")
        self.assertEqual(allow["status"], "allow")
        self.assertEqual(allow["user"], "maria")

        warn = CommandPrecheckPipeline(
            rate_limiter=FakeRateLimiter([(True, 0.0)]),
            access_controller=FakeAccessController({"allowed": True, "handled": False, "user": "maria"}),
            network_guard=FakeNetworkGuard({"allowed": True, "warning": True, "message": "rede instavel"}),
            audit_logger=audit,
        ).evaluate("ligar luz")
        self.assertEqual(warn["status"], "warn")
        self.assertIn("rede instavel", warn["warnings"])

        deny = CommandPrecheckPipeline(
            rate_limiter=FakeRateLimiter([(False, 1.5)]),
            access_controller=None,
            network_guard=None,
            audit_logger=audit,
        ).evaluate("ligar luz")
        self.assertEqual(deny["status"], "deny")
        self.assertEqual(deny["reason"], "rate_limit")

    def test_precheck_skips_access_and_network(self):
        precheck = CommandPrecheckPipeline(
            rate_limiter=FakeRateLimiter([(True, 0.0)]),
            access_controller=FakeAccessController({"allowed": False, "handled": False, "message": "negado"}),
            network_guard=FakeNetworkGuard({"allowed": False, "message": "rede"}),
        )
        result = precheck.evaluate("sair", skip_access_network=True)
        self.assertEqual(result["status"], "allow")


if __name__ == "__main__":
    unittest.main()
