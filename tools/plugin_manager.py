from tools.base import Tool


class PluginManagerTool(Tool):
    name = "plugin_manager"
    description = "Gerencia plugins locais declarativos de comandos."

    def __init__(self, registry=None):
        self.registry = registry

    def run(self, action="list", **kwargs):
        if self.registry is None:
            return {"error": "Registry de plugins nao configurado."}

        normalized = str(action or "list").strip().lower()
        if normalized == "list":
            plugins = self.registry.list_plugins()
            if not plugins:
                return {"message": "Nenhum plugin carregado.", "plugins": []}
            names = ", ".join(item.get("name", "plugin") for item in plugins)
            return {"message": f"Plugins ativos: {names}", "plugins": plugins}

        if normalized == "reload":
            report = self.registry.reload()
            return {
                "message": f"Plugins recarregados ({report.get('count', 0)}).",
                "report": report,
            }

        if normalized == "status":
            status = self.registry.status()
            return {"message": "Status dos plugins carregado.", "status": status}

        return {"error": f"Acao de plugin nao suportada: {action}"}
