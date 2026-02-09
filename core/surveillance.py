import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

import cv2
import time
import threading
import torch
from ultralytics import YOLO
from core.face_recognition import FaceRecognizer


class SurveillanceService:
    def __init__(self, camera_index=0, callback=None):
        self.camera_index = camera_index
        self.callback = callback

        self.running = False
        self.thread = None

        # Preview
        self.show_window = False

        # Controle de inferência
        self.last_inference = 0
        self.inference_interval = 1.0  # segundos

        # Cooldown de eventos
        self.last_event_time = 0
        self.event_cooldown = 30  # segundos

        # GPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Modelos
        self.person_detector = YOLO("yolov8n.pt").to(self.device)
        self.face_recognizer = FaceRecognizer()

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

            # =============================
            # DETECÇÃO DE PESSOAS (YOLO)
            # =============================
            results = self.person_detector(
                frame,
                conf=0.5,
                classes=[0],  # pessoa
                device=0 if self.device == "cuda" else "cpu",
                verbose=False
            )

            person_detected = results and len(results[0].boxes) > 0

            # =============================
            # RECONHECIMENTO FACIAL
            # =============================
            if person_detected:
                faces = self.face_recognizer.recognize(frame)

                for face in faces:
                    if now - self.last_event_time < self.event_cooldown:
                        continue

                    self.last_event_time = now

                    if face["name"] == "unknown":
                        event_type = "unknown_person_detected"
                    else:
                        event_type = "known_person_detected"

                    if self.callback:
                        self.callback({
                            "event": event_type,
                            "name": face["name"],
                            "confidence": face["confidence"]
                        })

            # =============================
            # PREVIEW OPCIONAL
            # =============================
            if self.show_window:
                frame_show = frame.copy()

                if person_detected:
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
