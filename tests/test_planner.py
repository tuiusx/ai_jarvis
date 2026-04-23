import unittest

from core.planner import Planner


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def test_detects_surveillance_commands(self):
        self.assertEqual(
            self.planner.decide("vigiar ambiente")["type"],
            "start_surveillance",
        )
        self.assertEqual(
            self.planner.decide("parar vigilancia")["type"],
            "stop_surveillance",
        )

    def test_detects_face_labeling(self):
        decision = self.planner.decide("esse rosto e Ricardo")
        self.assertEqual(decision["type"], "label_face")
        self.assertEqual(decision["name"], "Ricardo")

    def test_detects_face_labeling_with_accent(self):
        decision = self.planner.decide("esse rosto é João")
        self.assertEqual(decision["type"], "label_face")
        self.assertEqual(decision["name"], "João")

    def test_detects_memory_commands(self):
        remember = self.planner.decide("lembre que a senha fica no cofre")
        self.assertEqual(remember["type"], "remember")
        self.assertEqual(remember["memory"], "a senha fica no cofre")

        recall = self.planner.decide("o que voce sabe sobre senha")
        self.assertEqual(recall["type"], "recall")
        self.assertEqual(recall["query"], "senha")

    def test_detects_known_faces_listing(self):
        decision = self.planner.decide("quais rostos conhecidos voce tem")
        self.assertEqual(decision["type"], "list_known_faces")


if __name__ == "__main__":
    unittest.main()
