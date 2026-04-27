import json
import tempfile
import unittest
from pathlib import Path

from core.first_run_setup import FirstRunSetup
from core.settings import load_settings


class _FakeStdin:
    def __init__(self, interactive: bool):
        self._interactive = interactive

    def isatty(self):
        return self._interactive


class FirstRunSetupTests(unittest.TestCase):
    def test_returns_already_configured_when_state_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(temp_dir)
            state_path = Path(temp_dir) / "state" / "first_run_setup.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "initialized": True,
                        "owner_name": "alice",
                    }
                ),
                encoding="utf-8",
            )

            setup = FirstRunSetup(settings=settings, root_dir=temp_dir, stdin=_FakeStdin(interactive=True))
            result = setup.ensure()

            self.assertEqual(result["status"], "already_configured")
            self.assertTrue(settings["security"]["access_control"]["enabled"])
            self.assertEqual(settings["security"]["access_control"]["owner_name"], "alice")

    def test_defers_when_terminal_is_not_interactive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(temp_dir)
            setup = FirstRunSetup(settings=settings, root_dir=temp_dir, stdin=_FakeStdin(interactive=False))

            result = setup.ensure()

            self.assertEqual(result["status"], "deferred")
            self.assertFalse((Path(temp_dir) / "state" / "first_run_setup.json").exists())
            self.assertFalse(settings["security"]["access_control"]["enabled"])

    def test_configures_admin_and_persists_first_run_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(temp_dir)
            captures = []

            def capture_face(owner_slug):
                path = Path(temp_dir) / "faces" / "known" / owner_slug / "001.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fake-jpg")
                captures.append(str(path))
                return str(path)

            answers = iter(["Alice Admin"])
            setup = FirstRunSetup(
                settings=settings,
                root_dir=temp_dir,
                stdin=_FakeStdin(interactive=True),
                input_fn=lambda _prompt: next(answers),
                capture_face_fn=capture_face,
                output_fn=lambda _message: None,
            )

            result = setup.ensure()
            state_path = Path(temp_dir) / "state" / "first_run_setup.json"
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "configured")
            self.assertEqual(result["owner_name"], "alice_admin")
            self.assertEqual(saved_state["owner_name"], "alice_admin")
            self.assertTrue(settings["security"]["access_control"]["enabled"])
            self.assertEqual(settings["security"]["access_control"]["owner_name"], "alice_admin")
            self.assertEqual(len(captures), 1)


if __name__ == "__main__":
    unittest.main()
