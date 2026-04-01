from core.surveillance import SurveillanceService
from tools.base import Tool


class SurveillanceTool(Tool):
    name = "surveillance"
    description = "Inicia/parada vigilancia de camera e deteccao de rostos desconhecidos."

    def __init__(self, callback=None, model_path="yolov8n.pt", detect_interval=0.4, record_cooldown=30):
        self.callback = callback
        try:
            self.service = SurveillanceService(
                callback=self._handle_event,
                model_path=model_path,
                detect_interval=detect_interval,
                record_cooldown=record_cooldown,
            )
        except TypeError:
            # Compatibilidade com implementacoes/mocks antigos.
            self.service = SurveillanceService(callback=self._handle_event)

    def _handle_event(self, event):
        if self.callback:
            self.callback(event)
        print(f"[VIGILANCIA] Evento: {event}")

    def run(self, action="start", duration=20, **kwargs):
        if action == "start":
            result = self.service.start()
            if duration and isinstance(duration, (int, float)) and duration > 0:
                return {"message": f"{result} (monitorando por {duration} segundos)."}
            return {"message": result}

        if action == "stop":
            return {"message": self.service.stop()}

        return {"error": f"Acao '{action}' nao reconhecida para vigilancia."}
