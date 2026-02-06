class ToolManager:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def list_tools(self):
        return {
            name: tool.description
            for name, tool in self.tools.items()
        }

    def execute(self, name: str, **kwargs):
        if name not in self.tools:
            return f"Ferramenta '{name}' não encontrada."

        try:
            return self.tools[name].run(**kwargs)
        except Exception as e:
            return f"Erro ao executar ferramenta '{name}': {e}"
