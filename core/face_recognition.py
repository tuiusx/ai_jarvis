import os
import cv2
import numpy as np


class FaceRecognizer:
    def __init__(self, known_faces_dir="faces/known", threshold=70):
        self.known_faces_dir = known_faces_dir
        self.threshold = threshold

        # Detector de rosto
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Reconhecedor LBPH
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()

        self.labels = {}
        self._train()

    # =============================
    # TREINAMENTO
    # =============================
    def _train(self):
        faces = []
        labels = []
        label_id = 0

        if not os.path.exists(self.known_faces_dir):
            print("⚠️ Pasta faces/known não encontrada.")
            return

        for person in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person)
            if not os.path.isdir(person_dir):
                continue

            self.labels[label_id] = person

            for img_name in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_name)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                faces.append(img)
                labels.append(label_id)

            label_id += 1

        if faces:
            self.recognizer.train(faces, np.array(labels))
            print(f"✅ Rostos treinados: {len(self.labels)}")
        else:
            print("⚠️ Nenhum rosto encontrado para treinamento.")

    # =============================
    # RECONHECIMENTO
    # =============================
    def recognize(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detected_faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=5
        )

        results = []

        for (x, y, w, h) in detected_faces:
            roi = gray[y:y+h, x:x+w]
            label, confidence = self.recognizer.predict(roi)

            if confidence < self.threshold:
                name = self.labels.get(label, "unknown")
            else:
                name = "unknown"

            results.append({
                "name": name,
                "confidence": confidence,
                "bbox": (x, y, x+w, y+h)
            })

        return results
