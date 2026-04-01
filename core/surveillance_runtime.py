import os
import time
import threading

os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"


class SurveillanceService:
    def __init__(
        self,
        camera_index: int = 0,
        callback=None,
        recorder=None,
        detect_interval: float = 0.4,
        record_cooldown: int = 30,
        model_name: str | None = None,
    ):
        self.camera_index = camera_index
        self.callback = callback
        self.recorder = recorder
        self.detect_interval = detect_interval
        self.record_cooldown = record_cooldown
        self.model_name = model_name or os.getenv("JARVIS_YOLO_MODEL", "yolov8n.pt")

        self.running = False
        self.thread = None
        self.last_event_time = 0.0

        self.cv2 = None
        self.YOLO = None
        self.device = None
        self.person_model = None
        self.face_recognizer = None

    def start(self):
        if self.running:
            return "Vigilancia ja esta ativa."

        try:
            self._ensure_runtime()
        except Exception as exc:
            return f"Falha ao carregar o detector de pessoas: {exc}"

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return "Vigilancia continua iniciada."

    def stop(self):
        if not self.running:
            if self.recorder:
                self.recorder.stop()
            return "Vigilancia ja estava parada."

        self.running = False
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2)
        if self.recorder:
            self.recorder.stop()
        return "Vigilancia interrompida."

    def _run(self):
        cv2 = self.cv2
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("Nao foi possivel abrir a camera.")
            self.running = False
            return

        camera_fps = cap.get(cv2.CAP_PROP_FPS)
        if not camera_fps or camera_fps < 1:
            camera_fps = 20.0

        last_detection_at = 0.0
        print("Camera iniciada em background.")

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                if self.recorder:
                    self.recorder.write_frame(frame)

                now = time.time()
                if now - last_detection_at < self.detect_interval:
                    time.sleep(0.01)
                    continue

                last_detection_at = now
                results = self.person_model(
                    frame,
                    conf=0.5,
                    classes=[0],
                    verbose=False,
                )

                person_detected = (
                    results
                    and results[0].boxes is not None
                    and len(results[0].boxes) > 0
                )
                if not person_detected:
                    time.sleep(0.01)
                    continue

                if now - self.last_event_time > self.record_cooldown:
                    self.last_event_time = now
                    print("Pessoa detectada.")
                    self._dispatch_event({
                        "event": "person_detected",
                        "timestamp": now,
                        "frame_size": (frame.shape[1], frame.shape[0]),
                        "fps": camera_fps,
                    })

                faces = self.face_recognizer.detect_faces(frame)
                for face in faces:
                    self.face_recognizer.save_unknown(frame, face)

                time.sleep(0.01)
        finally:
            cap.release()
            if self.recorder:
                self.recorder.stop()
            print("Camera liberada.")

    def _ensure_person_model(self):
        self._ensure_runtime()
        if self.person_model is not None:
            return

        model = self.YOLO(self.model_name)
        model.to(self.device)
        model.fuse()
        self.person_model = model

    def _dispatch_event(self, event: dict):
        if not self.callback:
            return

        threading.Thread(
            target=self.callback,
            args=(event,),
            daemon=True,
        ).start()

    def get_face_recognizer(self):
        self._ensure_runtime()
        return self.face_recognizer

    def _ensure_runtime(self):
        if self.cv2 is None:
            import cv2

            self.cv2 = cv2

        if self.YOLO is None:
            from ultralytics import YOLO

            self.YOLO = YOLO

        if self.device is None:
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.face_recognizer is None:
            from core.face_gallery import FaceRecognizer

            self.face_recognizer = FaceRecognizer()
