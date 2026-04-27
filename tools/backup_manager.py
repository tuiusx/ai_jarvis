from tools.base import Tool


class BackupManagerTool(Tool):
    name = "backup_manager"
    description = "Executa e monitora backups criptografados da memoria."

    def __init__(self, service=None):
        self.service = service

    def run(self, action="status", **kwargs):
        if self.service is None:
            return {"error": "Servico de backup nao configurado."}

        normalized = str(action or "status").strip().lower()
        if normalized == "run_now":
            return self.service.run_now(reason=str(kwargs.get("reason", "manual")))
        if normalized == "status":
            status = self.service.status()
            return {"message": "Status do backup carregado.", "status": status}
        if normalized == "start":
            return self.service.start()
        if normalized == "stop":
            return self.service.stop()
        return {"error": f"Acao de backup nao suportada: {action}"}
