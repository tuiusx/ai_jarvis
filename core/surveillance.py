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

        # Preview (janela)
        self.show_window = False

        # Controle de inferência
        self.last_inference = 0
        self.inference_interval = 1.0  # segundos

        # Cooldown de eventos
        self.last_event_time = 0
        self.event_cooldown = 30  # segundos

        # GPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # YOLO rápido e leve
        self.model = YOLO("yolov8n.pt").to(self.device)

    # =============================
    # CONTROLES EXTERNOS
    # =============================

    def start(self):
        if self.running:
            return "🛡️ Vigilância já está ativa."

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        return "🛡️ Vigilância contínua iniciada."

    def stop(self):
        self.running = False
        self.disable_preview()
        return "🛑 Vigilância interrompida."

    def enable_preview(self):
        self.show_window = True
        return "📺 Visualização da câmera ativada."

    def disable_preview(self):
        self.show_window = False
        cv2.destroyAllWindows()
        return "📴 Visualização da câmera desativada."

    # =============================
    # LOOP PRINCIPAL
    # =============================

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

            results = self.model(
                frame,
                conf=0.5,
                classes=[0],  # pessoas
                device=0 if self.device == "cuda" else "cpu",
                verbose=False
            )

            detected = False
            confidence = 0.0

            if results and len(results[0].boxes) > 0:
                detected = True
                confidence = float(results[0].boxes.conf[0])

            # EVENTO
            if detected and confidence > 0.6:
                if now - self.last_event_time > self.event_cooldown:
                    self.last_event_time = now

                    if self.callback:
                        self.callback({
                            "event": "person_detected",
                            "confidence": confidence
                        })

            # PREVIEW OPCIONAL
            if self.show_window:
                frame_show = frame.copy()

                if detected:
                    for box in results[0].boxes.xyxy:
                        x1, y1, x2, y2 = map(int, box)
                        cv2.rectangle(
                            frame_show,
                            (x1, y1),
                            (x2, y2),
                            (0, 0, 255),
                            2
                        )

                cv2.imshow("Jarvis - Vigilância", frame_show)

                if cv2.waitKey(1) & 0xFF == 27:
                    self.disable_preview()

            time.sleep(0.05)

        cap.release()
