class ToolManager:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)

    def execute(self, name, **kwargs):
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Ferramenta desconhecida: {name}")
        return tool.run(**kwargs)
