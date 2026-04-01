import os
import threading
import time
from pathlib import Path

os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"


class SurveillanceService:
    def __init__(
        self,
        camera_index: int = 0,
        callback=None,
        detect_interval: float = 0.4,
        record_cooldown: int = 30,
        model_path: str = "yolov8n.pt",
    ):
        self.camera_index = camera_index
        self.callback = callback
        self.detect_interval = detect_interval
        self.record_cooldown = record_cooldown
        self.model_path = model_path

        self.running = False
        self.thread = None
        self.last_event_time = 0

        self.cv2 = None
        self.torch = None
        self.YOLO = None
        self.device = None
        self.person_model = None
        self.face_recognizer = None

    def start(self):
        if self.running:
            return "Vigilancia ja esta ativa."

        try:
            self._ensure_runtime()
        except FileNotFoundError as exc:
            return f"Falha ao iniciar vigilancia: {exc}"
        except Exception as exc:
            return f"Falha ao iniciar vigilancia: {exc}"

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return "Vigilancia continua iniciada."

    def stop(self):
        self.running = False
        return "Vigilancia interrompida."

    def _run(self):
        cv2 = self.cv2
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("Nao foi possivel abrir a camera.")
            self.running = False
            return

        print("Camera iniciada em background.")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            results = self.person_model(frame, conf=0.5, classes=[0], verbose=False)
            person_detected = results and results[0].boxes is not None and len(results[0].boxes) > 0

            if person_detected:
                now = time.time()
                if now - self.last_event_time > self.record_cooldown:
                    self.last_event_time = now
                    print("Pessoa detectada.")
                    if self.callback:
                        self.callback({"event": "person_detected", "timestamp": now})

                faces = self.face_recognizer.detect_faces(frame)
                for face in faces:
                    if face.get("name") == "unknown":
                        self.face_recognizer.save_unknown(frame, face)
                        if self.callback:
                            self.callback(
                                {
                                    "event": "intrusion_unknown_face",
                                    "timestamp": now,
                                    "bbox": face.get("bbox"),
                                    "message": "Rosto desconhecido detectado!",
                                }
                            )
                    else:
                        if self.callback:
                            self.callback(
                                {
                                    "event": "known_person",
                                    "timestamp": now,
                                    "name": face.get("name"),
                                    "message": f"Pessoa conhecida detectada: {face.get('name')}",
                                }
                            )

            time.sleep(self.detect_interval)

        cap.release()
        print("Camera liberada.")

    def _ensure_runtime(self):
        self._ensure_ultralytics_dirs()

        if self.cv2 is None:
            import cv2

            self.cv2 = cv2

        if self.torch is None:
            import torch

            self.torch = torch

        if self.YOLO is None:
            from ultralytics import YOLO

            self.YOLO = YOLO

        if self.device is None:
            self.device = "cuda" if self.torch.cuda.is_available() else "cpu"

        if self.person_model is None:
            model_file = Path(self.model_path)
            if not model_file.exists():
                raise FileNotFoundError(
                    f"modelo YOLO nao encontrado em '{self.model_path}'. Coloque o arquivo no projeto ou configure outro caminho."
                )

            self.person_model = self.YOLO(str(model_file)).to(self.device)
            self.person_model.fuse()

        if self.face_recognizer is None:
            from core.face_recognition import FaceRecognizer

            self.face_recognizer = FaceRecognizer()

    @staticmethod
    def _ensure_ultralytics_dirs():
        base_dir = Path.cwd() / ".ultralytics"
        base_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(base_dir))
        os.environ.setdefault("ULTRALYTICS_SETTINGS_DIR", str(base_dir))
