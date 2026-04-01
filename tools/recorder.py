import os
import time
import threading
from datetime import datetime

import cv2

from tools.base import Tool
from tools.stream_recorder import RecorderTool

class LegacyRecorderTool(Tool):
    name = "start_recording"
    description = "Grava o stream atual sem reabrir a camera"

    def run(self, duration=20):
        os.makedirs("recordings", exist_ok=True)

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
        path = os.path.join("recordings", filename)

        out = cv2.VideoWriter(path, fourcc, 20.0, (640, 480))

        for _ in range(int(20 * duration)):
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)

        cap.release()
        out.release()

        return f"🎥 Gravação concluída: {path}"
