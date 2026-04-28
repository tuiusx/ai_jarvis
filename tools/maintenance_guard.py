from tools.base import Tool


class MaintenanceGuardTool(Tool):
    name = "maintenance_guard"
    description = "Executa diagnostico de manutencao e auto-reparo operacional."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="status", **kwargs):
        if self.service is None:
            return {"error": "Servico de manutencao nao configurado."}

        normalized = str(action or "status").strip().lower()
        if normalized == "status":
            status = self.service.status()
            return {"message": "Status da manutencao carregado.", "status": status}
        if normalized == "check_now":
            return self.service.check_now(reason=str(kwargs.get("reason", "manual")))
        if normalized == "start":
            return self.service.start()
        if normalized == "stop":
            return self.service.stop()
        return {"error": f"Acao de manutencao nao suportada: {action}"}
