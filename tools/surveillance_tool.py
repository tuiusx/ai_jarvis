from tools.base import Tool

try:
    from core.surveillance import SurveillanceService
except Exception:
    SurveillanceService = None


class SurveillanceTool(Tool):
    name = "surveillance"
    description = "Inicia/parada vigilancia de camera e deteccao de rostos desconhecidos."

    def __init__(self, callback=None):
        self.callback = callback
        self.service = None
        self.dependency_error = None
        try:
            if SurveillanceService is None:
                raise ModuleNotFoundError("core.surveillance unavailable")
            self.service = SurveillanceService(callback=self._handle_event)
        except Exception as exc:
            self.dependency_error = str(exc)

    def _handle_event(self, event):
        if self.callback:
            self.callback(event)
        print(f"[VIGILANCIA] Evento: {event}")

    def run(self, action="start", duration=20, **kwargs):
        if self.service is None:
            return {"error": f"Servico de vigilancia indisponivel: {self.dependency_error}"}

        if action == "start":
            result = self.service.start()
            if duration and isinstance(duration, (int, float)) and duration > 0:
                return {"message": f"{result} (monitorando por {duration} segundos)."}
            return {"message": result}

        if action == "stop":
            result = self.service.stop()
            return {"message": result}

        return {"error": f"Acao '{action}' nao reconhecida para vigilancia."}
