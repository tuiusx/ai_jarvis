import cv2
import os
from datetime import datetime

class RecorderTool:
    name = "start_recording"

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
