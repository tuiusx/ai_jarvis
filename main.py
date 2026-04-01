from interfaces.multimodal import MultiModalInterface
from core.agent import Agent
from core.llm import LocalLLM
from core.memory import ShortTermMemory, LongTermMemory
from core.planner import Planner
from tools.manager import ToolManager
from tools.camera import CameraTool
from tools.recorder import RecorderTool

# Inicializações
llm = LocalLLM()
memory = ShortTermMemory()
long_memory = LongTermMemory()
planner = Planner()

tools = ToolManager()
tools.register(CameraTool())
tools.register(RecorderTool())
from tools.home_automation import HomeAutomationTool
from tools.surveillance_tool import SurveillanceTool

tools.register(HomeAutomationTool())
tools.register(SurveillanceTool(callback=lambda evt: print(f"🔔 Evento de vigilância: {evt}")))

interface = MultiModalInterface()

agent = Agent(
    llm=llm,
    memory=memory,
    planner=planner,
    tools=tools,
    interface=interface
)

agent.run()
