from tools.base import Tool


class NetworkEnforcementTool(Tool):
    name = "network_enforce"
    description = "Aplica bloqueios de internet/rede e gerencia cadastro de maquinas."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="", alias=None, mac=None, **kwargs):
        if self.service is None:
            return {"error": "Servico de bloqueio de rede nao configurado."}
        return self.service.execute(action=action, alias=alias, mac=mac)
