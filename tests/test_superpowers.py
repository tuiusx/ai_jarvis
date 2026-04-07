import unittest

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


if __name__ == "__main__":
    unittest.main()
