from tools.base import Tool


class SystemMonitorTool(Tool):
    name = "system_monitor"
    description = "Monitora CPU e memoria RAM (start/stop/status/summary/collect)."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="status", **kwargs):
        if self.service is None:
            return {"error": "Servico de monitoramento de sistema nao configurado."}

        normalized = str(action or "status").strip().lower()
        if normalized == "start":
            return self.service.start()
        if normalized == "stop":
            return self.service.stop()
        if normalized == "status":
            status = self.service.status()
            return {"message": "Status de CPU/RAM carregado.", "status": status}
        if normalized == "summary":
            return self.service.summary()
        if normalized == "collect":
            return self.service.collect_once()
        return {"error": f"Acao de monitoramento de sistema nao suportada: {action}"}
