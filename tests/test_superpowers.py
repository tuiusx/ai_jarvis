import unittest
from pathlib import Path
from unittest.mock import patch

import superpowers


class SuperpowersChecksTests(unittest.TestCase):
    def test_sensitive_prefix_paths_are_detected(self):
        tracked = [
            "faces/unknown/person_1.jpg",
            "src/app.py",
            "runs/output.mp4",
        ]
        found = superpowers.find_sensitive_tracked_files(tracked)
        self.assertEqual(found, ["faces/unknown/person_1.jpg", "runs/output.mp4"])

    def test_sensitive_file_patterns_are_detected(self):
        tracked = [
            "weights/yolov8n.pt",
            "models/face_recognizer.task",
            "notes.txt",
        ]
        found = superpowers.find_sensitive_tracked_files(tracked)
        self.assertEqual(found, ["models/face_recognizer.task", "weights/yolov8n.pt"])

    def test_missing_ignore_rules(self):
        ignore_text = """
        # comment
        recordings/
        runs/
        faces/
        """
        rules = superpowers.parse_ignore_rules(ignore_text)
        missing = superpowers.find_missing_ignore_rules(rules)
        self.assertIn("state/", missing)
        self.assertIn("runs.zip", missing)

    def test_quick_mode_skips_pytest_execution(self):
        with patch("superpowers.run_pytest", side_effect=AssertionError("pytest nao deveria rodar")), patch(
            "superpowers.run_git_ls_files", return_value=[]
        ):
            ok, messages = superpowers.run_checks(cwd=Path.cwd(), skip_tests=False, quick=True)
            self.assertTrue(ok)
            self.assertTrue(any("QUICK" in line for line in messages))


if __name__ == "__main__":
    unittest.main()
