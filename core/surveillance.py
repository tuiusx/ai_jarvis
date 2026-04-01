import os
import cv2
import time
import threading
import torch
from ultralytics import YOLO
from core.face_recognition import FaceRecognizer
from core.surveillance_runtime import SurveillanceService

# força OpenCV a NÃO usar MSMF (evita bugs no Windows)
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"


class LegacySurveillanceService:
    def __init__(
        self,
        camera_index: int = 0,
        callback=None,
        detect_interval: float = 0.4,
        record_cooldown: int = 30
    ):
        self.camera_index = camera_index
        self.callback = callback
        self.detect_interval = detect_interval
        self.record_cooldown = record_cooldown

        self.running = False
        self.thread = None
        self.last_event_time = 0

        # detector de pessoas (YOLO)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.person_model = YOLO("yolov8n.pt").to(self.device)
        self.person_model.fuse()

        # detector de rostos
        self.face_recognizer = FaceRecognizer()

    # ==========================
    # CONTROLE
    # ==========================
    def start(self):
        if self.running:
            return "🛡️ Vigilância já está ativa."

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.thread.start()

        return "🛡️ Vigilância contínua iniciada."

    def stop(self):
        self.running = False
        return "🛑 Vigilância interrompida."

    # ==========================
    # LOOP PRINCIPAL
    # ==========================
    def _run(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("❌ Não foi possível abrir a câmera.")
            self.running = False
            return

        print("📷 Câmera iniciada em background.")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # ==========================
            # DETECÇÃO DE PESSOAS
            # ==========================
            results = self.person_model(
                frame,
                conf=0.5,
                classes=[0],  # pessoa
                verbose=False
            )

            person_detected = (
                results
                and results[0].boxes is not None
                and len(results[0].boxes) > 0
            )

            if person_detected:
                now = time.time()

                # evita flood de eventos
                if now - self.last_event_time > self.record_cooldown:
                    self.last_event_time = now

                    print("🚨 Pessoa detectada.")

                    # callback para o agente
                    if self.callback:
                        self.callback({
                            "event": "person_detected",
                            "timestamp": now
                        })

                # ==========================
                # DETECÇÃO DE ROSTOS
                # ==========================
                faces = self.face_recognizer.detect_faces(frame)
                for face in faces:
                    self.face_recognizer.save_unknown(frame, face)

            time.sleep(self.detect_interval)

        cap.release()
        print("📷 Câmera liberada.")
