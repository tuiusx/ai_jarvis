import cv2
from tools.base import Tool

# detector global (ok ficar aqui)
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


class CameraTool(Tool):
    name = "detect_people"
    description = "Detecta pessoas em tempo real (otimizado)"

    def run(self, camera_index: int = 0, duration: int = 10):
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            return {
                "event": "error",
                "message": "Não foi possível acessar a câmera"
            }

        # reduz resolução (performance)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # warm-up da câmera (AGORA NO LUGAR CERTO)
        for _ in range(5):
            cap.read()

        start_time = cv2.getTickCount()
        freq = cv2.getTickFrequency()

        detected = False
        frame_count = 0
        boxes = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            if frame_count % 5 == 0:
                boxes, _ = hog.detectMultiScale(
                    frame,
                    winStride=(8, 8),
                    padding=(8, 8),
                    scale=1.05
                )

                if len(boxes) > 0:
                    detected = True

            for (x, y, w, h) in boxes:
                cv2.rectangle(
                    frame, (x, y),
                    (x + w, y + h),
                    (0, 255, 0), 2
                )

            cv2.imshow("Jarvis Vision", frame)

            elapsed = (cv2.getTickCount() - start_time) / freq
            if elapsed > duration or cv2.waitKey(1) & 0xFF == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

        if detected:
            return {
                "event": "person_detected",
                "message": "Pessoa detectada (modo rápido)"
            }

        return {
            "event": "no_detection",
            "message": "Nenhuma pessoa detectada"
        }
