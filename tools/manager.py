class ToolManager:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def execute(self, name, **kwargs):
        return self.tools[name].run(**kwargs)
