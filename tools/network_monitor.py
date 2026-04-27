from tools.base import Tool


class NetworkMonitorTool(Tool):
    name = "network_monitor"
    description = "Controla rastreamento de trafego de rede (start/stop/status/summary)."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="status", **kwargs):
        if self.service is None:
            return {"error": "Servico de monitor de rede nao configurado."}

        action = str(action or "status").strip().lower()
        if action == "start":
            return self.service.start()
        if action == "stop":
            return self.service.stop()
        if action == "status":
            return {"message": "Status do monitor de rede.", "status": self.service.status()}
        if action == "summary":
            return self.service.summary()
        return {"error": f"Acao '{action}' nao suportada no monitor de rede."}
