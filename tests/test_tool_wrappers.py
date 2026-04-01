import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def load_camera_module(opened=True, detections=None):
    detections = detections or []

    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.CAP_PROP_FRAME_WIDTH = 3
    fake_cv2.CAP_PROP_FRAME_HEIGHT = 4
    fake_cv2.tick_count = 0

    class FakeCapture:
        def __init__(self, camera_index):
            self.opened = opened
            self.read_count = 0

        def isOpened(self):
            return self.opened

        def set(self, prop, value):
            return True

        def read(self):
            self.read_count += 1
            return True, f"frame-{self.read_count}"

        def release(self):
            return True

    class FakeHOG:
        def setSVMDetector(self, detector):
            self.detector = detector

        def detectMultiScale(self, frame, **kwargs):
            return detections, None

    fake_cv2.VideoCapture = FakeCapture
    fake_cv2.HOGDescriptor = FakeHOG
    fake_cv2.HOGDescriptor_getDefaultPeopleDetector = lambda: "detector"
    fake_cv2.rectangle = lambda *args, **kwargs: None
    fake_cv2.imshow = lambda *args, **kwargs: None
    fake_cv2.waitKey = lambda value: 0
    fake_cv2.destroyAllWindows = lambda: None

    def get_tick_count():
        fake_cv2.tick_count += 10
        return fake_cv2.tick_count

    fake_cv2.getTickCount = get_tick_count
    fake_cv2.getTickFrequency = lambda: 10

    with patch.dict(sys.modules, {"cv2": fake_cv2}):
        sys.modules.pop("tools.camera", None)
        module = importlib.import_module("tools.camera")
        return importlib.reload(module)


def load_recorder_module():
    fake_cv2 = types.ModuleType("cv2")

    class FakeWriter:
        def __init__(self, path, fourcc, fps, size):
            self.path = path
            self.frames = []

        def isOpened(self):
            return True

        def write(self, frame):
            self.frames.append(frame)

        def release(self):
            return True

    fake_cv2.VideoWriter = FakeWriter
    fake_cv2.VideoWriter_fourcc = lambda *args: 1234
    fake_cv2.resize = lambda frame, size: frame

    with patch.dict(sys.modules, {"cv2": fake_cv2}):
        sys.modules.pop("tools.stream_recorder", None)
        module = importlib.import_module("tools.stream_recorder")
        module = importlib.reload(module)
        module._fake_cv2 = fake_cv2
        return module


def load_surveillance_tool_module():
    fake_surveillance = types.ModuleType("core.surveillance")

    class FakeService:
        def __init__(self, callback=None):
            self.callback = callback

        def start(self):
            return "Vigilancia iniciada"

        def stop(self):
            return "Vigilancia parada"

    fake_surveillance.SurveillanceService = FakeService

    with patch.dict(sys.modules, {"core.surveillance": fake_surveillance}):
        sys.modules.pop("tools.surveillance_tool", None)
        module = importlib.import_module("tools.surveillance_tool")
        return importlib.reload(module)


class CameraToolTests(unittest.TestCase):
    def test_returns_error_when_camera_is_unavailable(self):
        camera_module = load_camera_module(opened=False)
        tool = camera_module.CameraTool()

        result = tool.run()

        self.assertEqual(result["event"], "error")

    def test_reports_detected_person(self):
        camera_module = load_camera_module(opened=True, detections=[(1, 2, 3, 4)])
        tool = camera_module.CameraTool()

        result = tool.run(duration=10)

        self.assertEqual(result["event"], "person_detected")


class RecorderToolTests(unittest.TestCase):
    def test_returns_recording_path(self):
        recorder_module = load_recorder_module()
        tool = recorder_module.RecorderTool()
        tool.cv2 = recorder_module._fake_cv2

        with tempfile.TemporaryDirectory() as tmpdir:
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = tool.run(duration=1, frame_size=(640, 480))
            finally:
                os.chdir(current_dir)

        self.assertIn("recordings", result)
        self.assertTrue(result.endswith(".mp4"))


class SurveillanceToolTests(unittest.TestCase):
    def test_start_and_stop_actions(self):
        surveillance_module = load_surveillance_tool_module()
        tool = surveillance_module.SurveillanceTool()

        started = tool.run(action="start", duration=5)
        stopped = tool.run(action="stop")

        self.assertIn("Vigilancia iniciada", started["message"])
        self.assertEqual(stopped["message"], "Vigilancia parada")

    def test_rejects_invalid_action(self):
        surveillance_module = load_surveillance_tool_module()
        tool = surveillance_module.SurveillanceTool()

        result = tool.run(action="pause")

        self.assertIn("não reconhecida", result["error"])


if __name__ == "__main__":
    unittest.main()
