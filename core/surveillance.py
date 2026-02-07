import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

import cv2
import time
import threading
import torch
from ultralytics import YOLO


class SurveillanceService:
    def __init__(self, camera_index=0, callback=None):
        self.camera_index = camera_index
        self.callback = callback
        self.running = False
        self.thread = None

        # Controle de inferência
        self.last_inference = 0
        self.inference_interval = 1.0  # segundos entre análises

        # Cooldown de eventos
        self.last_event_time = 0
        self.event_cooldown = 30  # segundos entre eventos

        # GPU / CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # YOLO leve e rápido (ideal para vigilância)
        self.model = YOLO("yolov8n.pt").to(self.device)

    def start(self):
        if self.running:
            return "🛡️ Vigilância já está ativa."

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        return "🛡️ Vigilância contínua iniciada."

    def stop(self):
        self.running = False
        return "🛑 Vigilância interrompida."

    def _run(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("❌ Não foi possível abrir a câmera.")
            self.running = False
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            now = time.time()

            # Limita inferência
            if now - self.last_inference < self.inference_interval:
                continue

            self.last_inference = now

            # YOLO
            results = self.model(
                frame,
                conf=0.5,
                classes=[0],  # apenas pessoas
                device=0 if self.device == "cuda" else "cpu",
                verbose=False
            )

            if results and len(results[0].boxes) > 0:
                confidence = float(results[0].boxes.conf[0])

                # Evita spam de eventos
                if confidence > 0.6 and now - self.last_event_time > self.event_cooldown:
                    self.last_event_time = now

                    if self.callback:
                        self.callback({
                            "event": "person_detected",
                            "confidence": confidence
                        })

            time.sleep(0.1)

        cap.release()
