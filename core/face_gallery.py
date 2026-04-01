import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class FaceRecognizer:
    def __init__(
        self,
        base_dir: str = "faces",
        recognition_size=(64, 64),
        match_threshold: float = 0.8,
    ):
        self.base_dir = Path(base_dir)
        self.unknown_dir = self.base_dir / "unknown"
        self.known_dir = self.base_dir / "known"
        self.unknown_dir.mkdir(parents=True, exist_ok=True)
        self.known_dir.mkdir(parents=True, exist_ok=True)

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(cascade_path)
        if self.detector.empty():
            raise RuntimeError("Nao foi possivel carregar o detector facial do OpenCV.")

        self.recognition_size = recognition_size
        self.match_threshold = match_threshold
        self.hog = cv2.HOGDescriptor(
            recognition_size,
            (16, 16),
            (8, 8),
            (8, 8),
            9,
        )

        self.last_saved = 0.0
        self.save_interval = 10.0
        self.last_unknown_face = None
        self.known_embeddings = {}
        self.reload_gallery()

    def detect_faces(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        detections = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48),
        )

        faces = []
        for (x, y, w, h) in detections:
            face_img = frame[y:y + h, x:x + w]
            name, confidence = self.recognize_face(face_img)
            faces.append({
                "bbox": (x, y, x + w, y + h),
                "confidence": confidence,
                "name": name,
            })
        return faces

    def save_unknown(self, frame, face):
        if face.get("name") != "unknown":
            return None

        now = time.time()
        if now - self.last_saved < self.save_interval:
            return None

        x1, y1, x2, y2 = self._clip_bbox(face["bbox"], frame.shape)
        face_img = frame[y1:y2, x1:x2]
        if face_img.size == 0:
            return None

        date_dir = datetime.now().strftime("%Y-%m-%d")
        path_dir = self.unknown_dir / date_dir
        path_dir.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("%H-%M-%S") + ".jpg"
        path = path_dir / filename
        cv2.imwrite(str(path), face_img)

        self.last_saved = now
        self.last_unknown_face = path
        print(f"Rosto desconhecido salvo: {path}")
        return str(path)

    def label_last_face(self, name: str):
        if self.last_unknown_face is None or not self.last_unknown_face.exists():
            return "Nenhum rosto recente para nomear."

        safe_name = self._sanitize_label(name)
        if not safe_name:
            return "Diga um nome valido para cadastrar o rosto."

        person_dir = self.known_dir / safe_name
        person_dir.mkdir(parents=True, exist_ok=True)

        count = self._count_samples(person_dir) + 1
        suffix = self.last_unknown_face.suffix.lower() or ".jpg"
        new_path = person_dir / f"{count:03d}{suffix}"

        shutil.move(str(self.last_unknown_face), str(new_path))
        self.last_unknown_face = None
        self.reload_gallery()
        return f"Rosto salvo como {safe_name}."

    def list_known_people(self):
        return sorted(self.known_embeddings.keys())

    def reload_gallery(self):
        self.known_embeddings = {}
        for person_dir in sorted(self.known_dir.iterdir()):
            if not person_dir.is_dir():
                continue

            embeddings = []
            for image_path in sorted(person_dir.iterdir()):
                if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                    continue

                image = cv2.imread(str(image_path))
                if image is None:
                    continue

                face_img = self._extract_primary_face(image)
                embedding = self._compute_embedding(face_img)
                if embedding is not None:
                    embeddings.append(embedding)

            if embeddings:
                self.known_embeddings[person_dir.name] = embeddings

    def recognize_face(self, face_img):
        embedding = self._compute_embedding(face_img)
        if embedding is None or not self.known_embeddings:
            return ("unknown", 0.0)

        best_name = "unknown"
        best_score = 0.0
        for name, samples in self.known_embeddings.items():
            score = max(float(np.dot(embedding, sample)) for sample in samples)
            if score > best_score:
                best_name = name
                best_score = score

        if best_score < self.match_threshold:
            return ("unknown", round(best_score, 3))

        return (best_name, round(best_score, 3))

    def _extract_primary_face(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        detections = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48),
        )

        if len(detections) == 0:
            return image

        x, y, w, h = max(detections, key=lambda box: box[2] * box[3])
        return image[y:y + h, x:x + w]

    def _compute_embedding(self, face_img):
        if face_img is None or face_img.size == 0:
            return None

        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        resized = cv2.resize(gray, self.recognition_size)
        descriptor = self.hog.compute(resized)
        if descriptor is None:
            return None

        vector = descriptor.flatten().astype(np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return None

        return vector / norm

    @staticmethod
    def _clip_bbox(bbox, frame_shape):
        frame_height, frame_width = frame_shape[:2]
        x1, y1, x2, y2 = bbox
        return (
            max(0, x1),
            max(0, y1),
            min(frame_width, x2),
            min(frame_height, y2),
        )

    @staticmethod
    def _count_samples(person_dir: Path):
        return sum(
            1
            for image_path in person_dir.iterdir()
            if image_path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )

    @staticmethod
    def _sanitize_label(name: str):
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower())
        return cleaned.strip("_")
