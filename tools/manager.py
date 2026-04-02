class ToolManager:
    def __init__(self):
        self.tools = {}

    def register(self, tool):
        self.tools[tool.name] = tool

    def execute(self, step):
        if isinstance(step, dict):
            # Prioriza ferramenta para nao perder passos com "action" e "tool".
            if "tool" in step:
                tool_name = step["tool"]
                if tool_name in self.tools:
                    kwargs = {k: v for k, v in step.items() if k != "tool"}
                    return self.tools[tool_name].run(**kwargs)
                return {"error": f"Ferramenta '{tool_name}' não encontrada."}

            if step.get("action") == "respond":
                return {"message": step.get("message", "Ação executada.")}

            return {"error": f"Acao '{step.get('action')}' nao suportada no ToolManager."}

        return self.execute_legacy(step)

    def execute_legacy(self, name, **kwargs):
        return self.tools[name].run(**kwargs)
