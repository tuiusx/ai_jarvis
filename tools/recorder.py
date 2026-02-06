import os
import cv2
import time
from datetime import datetime
from tools.base import Tool


class RecorderTool(Tool):
    name = "start_recording"
    description = "Inicia gravação real de vídeo usando webcam"

    def run(self, duration: int = 10, camera_index: int = 0):
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            return "Erro: não foi possível acessar a câmera."

        # configurações do vídeo
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = 20.0

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        recordings_dir = os.path.join(base_dir, "recordings")

        os.makedirs(recordings_dir, exist_ok=True)

        filename = os.path.join(
            recordings_dir,
            datetime.now().strftime("%Y%m%d_%H%M%S.mp4")
        )
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))

        start_time = time.time()

        while time.time() - start_time < duration:
            ret, frame = cap.read()
            if not ret:
                break

            out.write(frame)

        cap.release()
        out.release()
        cv2.destroyAllWindows()

        return f"🎥 Gravação concluída: {filename}"
