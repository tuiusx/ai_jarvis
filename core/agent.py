from core.memory import ShortTermMemory, LongTermMemory
from core.planner import Planner
from core.llm import LocalLLM
from core.surveillance_runtime import SurveillanceService
from tools.manager import ToolManager
from tools.stream_recorder import RecorderTool


class LegacyAgent:
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


class Agent:
    def __init__(self):
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory()
        self.planner = Planner()
        self.llm = LocalLLM()

        self.tools = ToolManager()
        recorder = RecorderTool()
        self.tools.register(recorder)

        self.surveillance = SurveillanceService(
            callback=self.handle_surveillance_event,
            recorder=recorder,
        )

    def handle_surveillance_event(self, event: dict):
        if event.get("event") == "person_detected":
            self.tools.execute(
                "start_recording",
                duration=20,
                frame_size=event.get("frame_size"),
                fps=event.get("fps", 20.0),
            )

    def run(self, user_input: str):
        if not user_input or not user_input.strip():
            return None

        decision = self.planner.decide(user_input)
        action = decision.get("type")

        if action == "ignore":
            return None

        if action == "start_surveillance":
            return self.surveillance.start()

        if action == "stop_surveillance":
            return self.surveillance.stop()

        if action == "label_face":
            try:
                recognizer = self.surveillance.get_face_recognizer()
            except Exception as exc:
                return f"Reconhecimento facial indisponivel: {exc}"
            name = decision.get("name", "").strip()
            if not name:
                return "Diga o nome depois de 'esse rosto e'."
            return recognizer.label_last_face(name)

        if action == "list_known_faces":
            try:
                recognizer = self.surveillance.get_face_recognizer()
            except Exception as exc:
                return f"Reconhecimento facial indisponivel: {exc}"
            known_people = recognizer.list_known_people()
            if not known_people:
                return "Ainda nao ha rostos conhecidos cadastrados."
            return "Rostos conhecidos: " + ", ".join(known_people)

        if action == "remember":
            memory_text = decision.get("memory", "").strip()
            if not memory_text:
                return "Diga o que devo guardar."
            self.long_memory.add(memory_text)
            return f"Memoria registrada: {memory_text}"

        if action == "recall":
            query = decision.get("query", "").strip()
            matches = self.long_memory.search(query)
            if not matches:
                return f"Nao encontrei nada salvo sobre '{query}'."
            summary = "; ".join(item["text"] for item in matches)
            return f"Encontrei na memoria: {summary}"

        self.short_memory.add("Usuario", user_input)
        related_memories = [
            item["text"]
            for item in self.long_memory.search(user_input)
        ]
        response = self.llm.generate(
            user_input,
            context=self.short_memory.get_context(),
            memories=related_memories,
        )
        self.short_memory.add("IA", response)
        return response
