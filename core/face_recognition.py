import cv2
import os
import time
import shutil
from datetime import datetime
from ultralytics import YOLO
from core.face_gallery import FaceRecognizer


class LegacyFaceRecognizer:
    def __init__(self):
        self.model = YOLO("yolov8n.pt")
        self.model.fuse()

        self.base_dir = "faces"
        self.unknown_dir = os.path.join(self.base_dir, "unknown")
        self.known_dir = os.path.join(self.base_dir, "known")

        os.makedirs(self.unknown_dir, exist_ok=True)
        os.makedirs(self.known_dir, exist_ok=True)

        self.last_saved = 0
        self.save_interval = 10
        self.last_unknown_face = None

    def detect_faces(self, frame):
        results = self.model(
            frame,
            conf=0.6,
            verbose=False
        )

        faces = []

        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])

                faces.append({
                    "bbox": (x1, y1, x2, y2),
                    "confidence": conf,
                    "name": "unknown"
                })

        return faces

    def save_unknown(self, frame, face):
        now = time.time()
        if now - self.last_saved < self.save_interval:
            return

        x1, y1, x2, y2 = face["bbox"]
        face_img = frame[y1:y2, x1:x2]

        if face_img.size == 0:
            return

        date_dir = datetime.now().strftime("%Y-%m-%d")
        path_dir = os.path.join(self.unknown_dir, date_dir)
        os.makedirs(path_dir, exist_ok=True)

        filename = datetime.now().strftime("%H-%M-%S") + ".jpg"
        path = os.path.join(path_dir, filename)

        cv2.imwrite(path, face_img)

        self.last_saved = now
        self.last_unknown_face = path

        print(f"📸 Rosto desconhecido salvo: {path}")

    def label_last_face(self, name: str):
        if not self.last_unknown_face or not os.path.exists(self.last_unknown_face):
            return "❌ Nenhum rosto recente para nomear."

        person_dir = os.path.join(self.known_dir, name.lower())
        os.makedirs(person_dir, exist_ok=True)

        count = len(os.listdir(person_dir)) + 1
        new_path = os.path.join(person_dir, f"{count:03}.jpg")

        shutil.move(self.last_unknown_face, new_path)
        self.last_unknown_face = None

        return f"✅ Rosto salvo como {name}."
