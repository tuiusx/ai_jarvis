import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.settings import get_setting


class FirstRunSetup:
    def __init__(
        self,
        settings: dict,
        root_dir: str = ".",
        input_fn=input,
        output_fn=print,
        capture_face_fn=None,
        stdin=None,
    ):
        self.settings = settings
        self.root_dir = Path(root_dir)
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.capture_face_fn = capture_face_fn
        self.stdin = stdin or sys.stdin

        self.state_path = self.root_dir / str(get_setting(settings, "setup.state_file", "state/first_run_setup.json"))
        self.face_base_dir = self.root_dir / str(get_setting(settings, "setup.face_base_dir", "faces"))
        self.capture_timeout_seconds = int(get_setting(settings, "setup.capture_timeout_seconds", 20))

    def ensure(self):
        if not bool(get_setting(self.settings, "setup.first_run_enabled", True)):
            return {"status": "disabled"}

        current_state = self._read_state()
        if current_state.get("initialized", False):
            self._apply_runtime_security(current_state.get("owner_name", "owner"))
            return {"status": "already_configured", "owner_name": current_state.get("owner_name", "owner")}

        if not self._is_interactive():
            return {
                "status": "deferred",
                "reason": "non_interactive_terminal",
            }

        self.output_fn("=== Configuracao Inicial do JARVIS ===")
        self.output_fn("Primeiro acesso: vamos cadastrar o dono administrador.")
        owner_name = self._ask_owner_name()
        owner_slug = self._sanitize_name(owner_name)

        self.output_fn("Olhe para a camera. Vou capturar seu rosto para liberar acesso de administrador.")
        face_path = self._capture_owner_face(owner_slug)

        state = {
            "initialized": True,
            "owner_name": owner_slug,
            "owner_display_name": owner_name,
            "face_path": str(face_path),
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_state(state)
        self._apply_runtime_security(owner_slug)

        return {
            "status": "configured",
            "owner_name": owner_slug,
            "face_path": str(face_path),
        }

    def _is_interactive(self):
        try:
            return bool(self.stdin and self.stdin.isatty())
        except Exception:
            return False

    def _ask_owner_name(self):
        while True:
            value = str(self.input_fn("Digite seu nome de administrador: ")).strip()
            if self._sanitize_name(value):
                return value
            self.output_fn("Nome invalido. Use letras, numeros, espaco, _ ou -.")

    def _capture_owner_face(self, owner_slug: str):
        if callable(self.capture_face_fn):
            result = self.capture_face_fn(owner_slug)
            if not result:
                raise RuntimeError("Falha ao capturar rosto do administrador.")
            return Path(result)

        return self._capture_owner_face_with_camera(owner_slug)

    def _capture_owner_face_with_camera(self, owner_slug: str):
        try:
            import cv2
        except Exception as exc:
            raise RuntimeError(f"OpenCV indisponivel para cadastro facial: {exc}") from exc

        from core.face_gallery import FaceRecognizer

        camera_index = int(
            get_setting(
                self.settings,
                "security.access_control.camera_index",
                get_setting(self.settings, "camera.default_index", 0),
            )
        )

        recognizer = FaceRecognizer(base_dir=str(self.face_base_dir))
        capture = cv2.VideoCapture(camera_index)
        if not capture or not capture.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir a camera (indice={camera_index}).")

        deadline = time.time() + max(5, int(self.capture_timeout_seconds))
        try:
            while time.time() < deadline:
                ok, frame = capture.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                face = self._extract_primary_detection(recognizer, frame)
                if face is None:
                    time.sleep(0.05)
                    continue

                owner_dir = self.face_base_dir / "known" / owner_slug
                owner_dir.mkdir(parents=True, exist_ok=True)
                image_path = self._next_owner_image_path(owner_dir)
                cv2.imwrite(str(image_path), face)
                recognizer.reload_gallery()
                return image_path
        finally:
            try:
                capture.release()
            except Exception:
                pass

        raise RuntimeError("Nao detectei seu rosto a tempo. Tente novamente em um ambiente com melhor iluminacao.")

    @staticmethod
    def _extract_primary_detection(recognizer, frame):
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        detections = recognizer.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(48, 48),
        )
        if len(detections) == 0:
            return None

        x, y, w, h = max(detections, key=lambda box: box[2] * box[3])
        return frame[y : y + h, x : x + w]

    @staticmethod
    def _next_owner_image_path(owner_dir: Path):
        existing = [
            p
            for p in owner_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        return owner_dir / f"{len(existing) + 1:03d}.jpg"

    def _read_state(self):
        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_state(self, data: dict):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def _apply_runtime_security(self, owner_name: str):
        security = self.settings.setdefault("security", {})
        access = security.setdefault("access_control", {})
        access["enabled"] = True
        access["owner_name"] = self._sanitize_name(owner_name) or "owner"

    @staticmethod
    def _sanitize_name(name: str):
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\s]+", "", str(name or "").strip().lower())
        cleaned = re.sub(r"\s+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned)
        return cleaned.strip("_")


def ensure_first_run_setup(settings: dict, root_dir: str = ".", input_fn=input, output_fn=print):
    setup = FirstRunSetup(
        settings=settings,
        root_dir=root_dir,
        input_fn=input_fn,
        output_fn=output_fn,
    )
    return setup.ensure()
