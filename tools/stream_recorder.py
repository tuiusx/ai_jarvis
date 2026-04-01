import os
import time
import threading
from datetime import datetime

from tools.base import Tool


class RecorderTool(Tool):
    name = "start_recording"
    description = "Grava o stream atual sem reabrir a camera"

    def __init__(self, output_dir: str = "recordings"):
        self.output_dir = output_dir
        self._lock = threading.Lock()
        self._writer = None
        self._active_until = 0.0
        self._path = None
        self._frame_size = None
        self.cv2 = None

    def run(self, duration: int = 20, frame_size=None, fps: float = 20.0):
        with self._lock:
            normalized_size = self._normalize_frame_size(frame_size or self._frame_size)
            if normalized_size is None:
                return "Nao foi possivel iniciar a gravacao sem tamanho de frame."

            os.makedirs(self.output_dir, exist_ok=True)
            requested_until = time.time() + max(1, int(duration))

            if self._writer is not None:
                self._active_until = max(self._active_until, requested_until)
                return f"Gravacao estendida: {self._path}"

            filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
            path = os.path.join(self.output_dir, filename)
            cv2 = self._get_cv2()
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(path, fourcc, float(fps or 20.0), normalized_size)

            if not writer.isOpened():
                return "Nao foi possivel iniciar o gravador."

            self._writer = writer
            self._active_until = requested_until
            self._path = path
            self._frame_size = normalized_size
            return f"Gravacao iniciada: {path}"

    def write_frame(self, frame):
        with self._lock:
            if self._writer is None:
                return

            if time.time() >= self._active_until:
                self._close_writer_locked()
                return

            if frame is None:
                return

            target_width, target_height = self._frame_size
            height, width = frame.shape[:2]
            frame_to_write = frame

            if (width, height) != (target_width, target_height):
                cv2 = self._get_cv2()
                frame_to_write = cv2.resize(frame, (target_width, target_height))

            self._writer.write(frame_to_write)

    def stop(self):
        with self._lock:
            self._close_writer_locked()

    def _close_writer_locked(self):
        if self._writer is not None:
            self._writer.release()
        self._writer = None
        self._active_until = 0.0
        self._path = None

    @staticmethod
    def _normalize_frame_size(frame_size):
        if not frame_size or len(frame_size) < 2:
            return None

        width = int(frame_size[0])
        height = int(frame_size[1])
        if width <= 0 or height <= 0:
            return None

        return (width, height)

    def _get_cv2(self):
        if self.cv2 is None:
            import cv2

            self.cv2 = cv2
        return self.cv2
