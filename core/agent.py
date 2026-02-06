from core.memory import ShortTermMemory, LongTermMemory
from core.planner import Planner
from core.llm import LocalLLM
from tools.manager import ToolManager
from tools.recorder import RecorderTool
from tools.camera import CameraTool


class Agent:
    def __init__(self):
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.planner = Planner()
        self.llm = LocalLLM()
        self.tools = ToolManager()
        self.tools.register(RecorderTool())
        self.tools.register(CameraTool())




    def build_prompt(self, user_input: str) -> str:
        short_context = self.short_memory.get_context()
        long_context = "\n".join(self.long_memory.search(user_input))

        return f"""
Você é um agente de IA local, offline-first.

Memória relevante:
{long_context}

Contexto recente:
{short_context}

Usuário:
{user_input}

Responda de forma clara e objetiva.
"""

    def run(self, user_input: str) -> str:
        if not user_input.strip():
            return "Digite um comando válido."

        # salva input do usuário
        self.short_memory.add("Usuário", user_input)

        # constrói prompt e decisão
        prompt = self.build_prompt(user_input)
        decision = self.planner.decide(user_input)

        # decisão de resposta
        if decision["type"] == "respond":
            response = self.llm.generate(prompt)

        elif decision["type"] == "tool":
            result = self.tools.execute(
                decision["name"],
                **decision.get("args", {})
            )

            if isinstance(result, dict) and result.get("event") == "person_detected":
                record_response = self.tools.execute(
                    "start_recording",
                    duration=20
                )

                response = (
                    "🚨 Pessoa detectada.\n"
                    "🎥 Gravação iniciada automaticamente.\n"
                    f"{record_response}"
                )
            else:
                response = result

        else:
            response = "Decisão desconhecida"

        # salva resposta somente se válida
        if response and str(response).strip():
            self.short_memory.add("IA", response)
            self.long_memory.add(f"Usuário: {user_input} | IA: {response}")

        return response

