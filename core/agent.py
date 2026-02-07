import time
from core.memory import ShortTermMemory, LongTermMemory
from core.planner import Planner
from core.llm import LocalLLM
from tools.manager import ToolManager
from tools.recorder import RecorderTool
from core.surveillance import SurveillanceService


class Agent:
    def __init__(self):
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.planner = Planner()
        self.llm = LocalLLM()

        self.tools = ToolManager()
        self.tools.register(RecorderTool())

        self.last_record_time = 0
        self.record_cooldown = 30

        self.surveillance = SurveillanceService(
            callback=self.handle_surveillance_event
        )

    # =============================
    # EVENTOS DA VIGILÂNCIA
    # =============================

    def handle_surveillance_event(self, event: dict):
        now = time.time()

        if event.get("event") == "person_detected":
            if now - self.last_record_time < self.record_cooldown:
                return

            self.last_record_time = now
            print("\n🚨 Pessoa detectada – gravação iniciada.")

            self.tools.execute(
                "start_recording",
                duration=20
            )

    # =============================
    # PROMPT
    # =============================

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

    # =============================
    # LOOP PRINCIPAL
    # =============================

    def run(self, user_input: str) -> str:
        if not user_input.strip():
            return "Digite um comando válido."

        self.short_memory.add("Usuário", user_input)

        cmd = user_input.lower()

        # COMANDOS DIRETOS
        if "vigiar" in cmd:
            return self.surveillance.start()

        if "parar vigilância" in cmd:
            return self.surveillance.stop()

        if "mostrar câmera" in cmd:
            return self.surveillance.enable_preview()

        if "fechar câmera" in cmd:
            return self.surveillance.disable_preview()

        # LLM
        prompt = self.build_prompt(user_input)
        response = self.llm.generate(prompt)

        self.short_memory.add("IA", response)
        self.long_memory.add(f"Usuário: {user_input} | IA: {response}")

        return response
