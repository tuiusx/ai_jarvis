from pathlib import Path

import yaml

from core.agent import Agent
from core.llm import LocalLLM
from core.memory import LongTermMemory, ShortTermMemory
from core.planner import Planner
from interfaces.multimodal import MultiModalInterface
from tools.camera import CameraTool
from tools.home_automation import HomeAutomationTool
from tools.manager import ToolManager
from tools.recorder import RecorderTool
from tools.surveillance_tool import SurveillanceTool


def _load_settings():
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


settings = _load_settings()
surveillance_cfg = settings.get("surveillance", {})
home_assistant_cfg = settings.get("home_assistant", {})

llm = LocalLLM()
memory = ShortTermMemory()
long_memory = LongTermMemory()
planner = Planner()

tools = ToolManager()
tools.register(CameraTool())
tools.register(RecorderTool())
tools.register(HomeAutomationTool(home_assistant=home_assistant_cfg))
tools.register(
    SurveillanceTool(
        callback=lambda evt: print(f"Evento de vigilancia: {evt}"),
        model_path=surveillance_cfg.get("model_path", "yolov8n.pt"),
        detect_interval=float(surveillance_cfg.get("detect_interval", 0.4)),
        record_cooldown=int(surveillance_cfg.get("record_cooldown", 30)),
    )
)

interface = MultiModalInterface()

agent = Agent(
    llm=llm,
    memory=memory,
    planner=planner,
    tools=tools,
    interface=interface,
)

agent.run()
