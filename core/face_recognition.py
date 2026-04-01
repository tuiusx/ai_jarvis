import cv2
import os
import time
import shutil
from datetime import datetime
import numpy as np
import face_recognition
from ultralytics import YOLO


class FaceRecognizer:
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

        # Carregar rostos conhecidos
        self.known_face_encodings = []
        self.known_face_names = []
        self._load_known_faces()

    def detect_faces(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Busca rostos no frame com face_recognition
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        faces = []
        for location, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = location
            name = "unknown"
            confidence = 1.0

            if self.known_face_encodings:
                distances = face_recognition.face_distance(self.known_face_encodings, encoding)
                best_index = int(np.argmin(distances))
                if distances[best_index] < 0.5:
                    name = self.known_face_names[best_index]
                    confidence = 1.0 - distances[best_index]

            faces.append({
                "bbox": (left, top, right, bottom),
                "confidence": confidence,
                "name": name
            })

        # Se não forem detectados rostos pela face_recognition, tenta YOLO como fallback
        if not faces:
            results = self.model(frame, conf=0.6, verbose=False)
            if results and results[0].boxes is not None:
                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    faces.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": float(box.conf[0]),
                        "name": "unknown"
                    })

        return faces

    def _load_known_faces(self):
        self.known_face_encodings = []
        self.known_face_names = []

        if not os.path.isdir(self.known_dir):
            return

        for person_name in os.listdir(self.known_dir):
            person_path = os.path.join(self.known_dir, person_name)
            if not os.path.isdir(person_path):
                continue

            for filename in os.listdir(person_path):
                if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_path = os.path.join(person_path, filename)
                    try:
                        image = face_recognition.load_image_file(image_path)
                        encodings = face_recognition.face_encodings(image)
                        if encodings:
                            self.known_face_encodings.append(encodings[0])
                            self.known_face_names.append(person_name)
                    except Exception as e:
                        print(f"⚠️ Erro carregando rosto conhecido '{image_path}': {e}")

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
