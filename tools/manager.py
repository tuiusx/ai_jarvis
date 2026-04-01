class ToolManager:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)

    def execute(self, step, **kwargs):
        if isinstance(step, dict):
            if "action" in step and step["action"] == "respond":
                return {"message": step.get("message", "Acao executada.")}

            if "tool" in step:
                tool_name = step["tool"]
                tool = self.get(tool_name)
                if tool is None:
                    return {"error": f"Ferramenta '{tool_name}' não encontrada."}
                payload = {k: v for k, v in step.items() if k != "tool"}
                return tool.run(**payload)

        elif isinstance(step, str):
            tool = self.get(step)
            if tool is None:
                raise KeyError(f"Ferramenta desconhecida: {step}")
            return tool.run(**kwargs)

        raise ValueError("Passo de execucao invalido.")
