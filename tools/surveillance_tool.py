from tools.base import Tool
from core.surveillance import SurveillanceService


class SurveillanceTool(Tool):
    name = "surveillance"
    description = "Inicia/parada vigilância de câmera e detecção de rostos desconhecidos."

    def __init__(self, callback=None):
        self.callback = callback
        self.service = SurveillanceService(callback=self._handle_event)

    def _handle_event(self, event):
        if self.callback:
            self.callback(event)
        # Retorna um evento simples para logs
        print(f"[VIGILÂNCIA] Evento: {event}")

    def run(self, action="start", duration=20, **kwargs):
        if action == "start":
            result = self.service.start()
            if duration and isinstance(duration, (int, float)) and duration > 0:
                # Execução em thread background já está sendo feita pelo serviço
                return {"message": f"{result} (monitorando por {duration} segundos)."}
            return {"message": result}

        if action == "stop":
            result = self.service.stop()
            return {"message": result}

        return {"error": f"Ação '{action}' não reconhecida para vigilância."}
