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

        self.surveillance = SurveillanceService(
            callback=self.handle_surveillance_event
        )

    def handle_surveillance_event(self, event: dict):
        if event.get("event") == "person_detected":
            self.tools.execute("start_recording", duration=20)

    def run(self, user_input: str):
        text = user_input.lower().strip()
        if not text:
            return None

        # comandos diretos
        if "vigiar ambiente" in text:
            return self.surveillance.start()

        if "parar vigilância" in text:
            return self.surveillance.stop()

        if "esse rosto é" in text:
            name = text.replace("esse rosto é", "").strip()
            if not name:
                return "Diga o nome depois de 'esse rosto é'."
            return self.surveillance.face_recognizer.label_last_face(name)

        # fluxo normal (LLM mock)
        self.short_memory.add("Usuário", user_input)
        response = self.llm.generate(user_input)
        self.short_memory.add("IA", response)
        return response
