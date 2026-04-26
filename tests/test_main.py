import unittest
import types
import sys
from unittest.mock import patch

if "interfaces.multimodal" not in sys.modules:
    multimodal_stub = types.ModuleType("interfaces.multimodal")
    multimodal_stub.MultiModalInterface = object
    sys.modules["interfaces.multimodal"] = multimodal_stub

import main as jarvis_main


class FakeAudit:
    def __init__(self):
        self.events = []

    def log(self, event, severity="info", **data):
        self.events.append((event, severity, data))

    @staticmethod
    def metrics():
        return {"total_events": 0}


class FakeAgent:
    def __init__(self):
        self.last_cleanup = {}
        self.ran = False

    def run(self):
        self.ran = True


class FakeContext:
    def __init__(self):
        self.audit = FakeAudit()
        self.agent = FakeAgent()
        self.network_monitor = None
        self.dry_run = False


class FakeAppFactory:
    last_instance = None

    def __init__(self, settings=None):
        self.settings = settings
        self.build_calls = []
        self.context = FakeContext()
        FakeAppFactory.last_instance = self

    def build(self, interface=None, retention_summary=None):
        self.build_calls.append(
            {
                "interface": interface,
                "retention_summary": retention_summary,
            }
        )
        return self.context


class FakeRetentionManager:
    last_audit_logger = None

    def __init__(self, settings, audit_logger=None):
        FakeRetentionManager.last_audit_logger = audit_logger

    @staticmethod
    def cleanup():
        return {"enabled": True, "deleted": 3}


class FakeInterface:
    def __init__(self, wake_word, min_command_interval):
        self.wake_word = wake_word
        self.min_command_interval = min_command_interval


class MainTests(unittest.TestCase):
    def test_startup_cleanup_uses_context_audit_logger(self):
        settings = {
            "app": {"mode": "dev"},
            "voice": {"wake_word": "jarvis"},
            "dashboard": {"enabled": False},
            "retention": {"auto_cleanup_on_start": True},
            "security": {
                "min_command_interval_seconds": 0.8,
                "access_control": {"enabled": False},
                "network_verification": {"enabled": False},
                "network_monitor": {"enabled": False},
                "network_enforcement": {"enabled": False},
            },
        }

        with (
            patch.object(jarvis_main, "load_settings", return_value=settings),
            patch.object(jarvis_main, "AppFactory", FakeAppFactory),
            patch.object(jarvis_main, "RetentionManager", FakeRetentionManager),
            patch.object(jarvis_main, "MultiModalInterface", FakeInterface),
        ):
            jarvis_main.main()

        factory = FakeAppFactory.last_instance
        context = factory.context

        self.assertIs(FakeRetentionManager.last_audit_logger, context.audit)
        self.assertEqual(factory.build_calls[0]["retention_summary"], {})
        self.assertEqual(context.agent.last_cleanup, {"enabled": True, "deleted": 3})
        self.assertTrue(context.agent.ran)


if __name__ == "__main__":
    unittest.main()
