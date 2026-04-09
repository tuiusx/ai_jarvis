from core.agent import Agent
from core.audit import AuditLogger
from core.dashboard import start_dashboard_in_background
from core.llm import LocalLLM
from core.memory import LongTermMemory, ShortTermMemory
from core.planner import Planner
from core.rate_limit import CommandRateLimiter
from core.retention import RetentionManager
from core.settings import get_setting, load_settings
from interfaces.multimodal import MultiModalInterface
from tools.camera import CameraTool
from tools.home_automation import HomeAutomationTool
from tools.manager import ToolManager
from tools.network_discovery import NetworkDiscoveryTool
from tools.recorder import RecorderTool
from tools.surveillance_tool import SurveillanceTool


def main():
    settings = load_settings()
    app_mode = get_setting(settings, "app.mode", "dev")

    short_limit = int(get_setting(settings, "memory.short_term_limit", 10))
    long_path = str(get_setting(settings, "memory.long_term_file", "state/memory.json"))
    long_limit = int(get_setting(settings, "memory.long_term_limit", 100))
    key_env = str(get_setting(settings, "memory.encryption_key_env", "JARVIS_MEMORY_KEY"))

    audit_path = str(get_setting(settings, "security.audit_log_file", "state/audit.log.jsonl"))
    rate_seconds = float(get_setting(settings, "security.min_command_interval_seconds", 0.8))
    wake_word = str(get_setting(settings, "voice.wake_word", "jarvis"))
    should_cleanup = bool(get_setting(settings, "retention.auto_cleanup_on_start", True))

    llm = LocalLLM()
    memory = ShortTermMemory(limit=short_limit)
    long_memory = LongTermMemory(file_path=long_path, limit=long_limit, encryption_key_env=key_env)
    planner = Planner()
    audit = AuditLogger(path=audit_path)
    limiter = CommandRateLimiter(min_interval_seconds=rate_seconds)

    if should_cleanup:
        RetentionManager(settings=settings, audit_logger=audit).cleanup()

    tools = ToolManager()
    tools.register(CameraTool())
    tools.register(RecorderTool(output_dir=str(get_setting(settings, "recording.output_dir", "recordings"))))
    tools.register(HomeAutomationTool())
    tools.register(NetworkDiscoveryTool())
    tools.register(SurveillanceTool(callback=lambda evt: print(f"Evento de vigilancia: {evt}")))

    if bool(get_setting(settings, "dashboard.enabled", True)):
        dash_host = str(get_setting(settings, "dashboard.host", "127.0.0.1"))
        dash_port = int(get_setting(settings, "dashboard.port", 8787))
        dash_max_events = int(get_setting(settings, "dashboard.max_events", 200))
        start_dashboard_in_background(
            host=dash_host,
            port=dash_port,
            audit_log_path=audit_path,
            app_mode=app_mode,
            max_events=dash_max_events,
        )
        print(f"Dashboard ativo em http://{dash_host}:{dash_port}")

    interface = MultiModalInterface(wake_word=wake_word, min_command_interval=rate_seconds)

    agent = Agent(
        llm=llm,
        memory=memory,
        long_memory=long_memory,
        planner=planner,
        tools=tools,
        interface=interface,
        rate_limiter=limiter,
        audit_logger=audit,
        app_mode=app_mode,
    )

    audit.log("app.start", mode=app_mode)
    agent.run()


if __name__ == "__main__":
    main()
