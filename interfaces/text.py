import os
import time

from colorama import Back, Fore, Style, init

from core.agent import Agent
from core.audit import AuditLogger
from core.notifications import CriticalNotifier
from core.rate_limit import CommandRateLimiter
from core.settings import get_setting, load_settings


init(autoreset=True)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    print(f"{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}{'JARVIS - Assistente de IA Inteligente':^58}{Style.RESET_ALL}")
    print(f"{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Comandos disponiveis:")
    print(f"{Fore.YELLOW}  - 'sair' ou 'quit' - Encerra o assistente")
    print(f"{Fore.YELLOW}  - 'limpar' - Limpa a tela")
    print(f"{Fore.YELLOW}  - 'ajuda' - Mostra esta mensagem")
    print(f"{Fore.GREEN}Diga 'jarvis' para ativar reconhecimento de voz")
    print(f"{Back.BLUE}{Fore.WHITE}{'-' * 60}{Style.RESET_ALL}")
    print()


def chat():
    clear_screen()
    print_header()

    from core.llm import LocalLLM
    from core.memory import LongTermMemory, ShortTermMemory
    from core.planner import Planner
    from tools.camera import CameraTool
    from tools.home_automation import HomeAutomationTool
    from tools.manager import ToolManager
    from tools.network_discovery import NetworkDiscoveryTool
    from tools.recorder import RecorderTool
    from tools.surveillance_tool import SurveillanceTool

    settings = load_settings()
    short_limit = int(get_setting(settings, "memory.short_term_limit", 10))
    long_path = str(get_setting(settings, "memory.long_term_file", "state/memory.json"))
    long_limit = int(get_setting(settings, "memory.long_term_limit", 100))
    key_env = str(get_setting(settings, "memory.encryption_key_env", "JARVIS_MEMORY_KEY"))
    app_mode = str(get_setting(settings, "app.mode", "dev"))
    rate_seconds = float(get_setting(settings, "security.min_command_interval_seconds", 0.8))
    audit_path = str(get_setting(settings, "security.audit_log_file", "state/audit.log.jsonl"))
    audit_max_bytes = int(get_setting(settings, "security.audit_max_bytes", 5_242_880))
    audit_backup_count = int(get_setting(settings, "security.audit_backup_count", 3))
    dry_run = bool(get_setting(settings, "home_automation.dry_run", False))

    llm = LocalLLM()
    memory = ShortTermMemory(limit=short_limit)
    long_memory = LongTermMemory(file_path=long_path, limit=long_limit, encryption_key_env=key_env)
    planner = Planner()
    rate_limiter = CommandRateLimiter(min_interval_seconds=rate_seconds)
    notifier = CriticalNotifier(
        enabled=bool(get_setting(settings, "notifications.enabled", False)),
        channel=str(get_setting(settings, "notifications.channel", "console")),
        telegram_token_env=str(get_setting(settings, "notifications.telegram_bot_token_env", "JARVIS_TELEGRAM_BOT_TOKEN")),
        telegram_chat_id_env=str(get_setting(settings, "notifications.telegram_chat_id_env", "JARVIS_TELEGRAM_CHAT_ID")),
    )
    audit = AuditLogger(
        path=audit_path,
        max_bytes=audit_max_bytes,
        backup_count=audit_backup_count,
        notify_callback=notifier.notify,
    )

    tools = ToolManager()
    tools.register(CameraTool())
    tools.register(RecorderTool(output_dir=str(get_setting(settings, "recording.output_dir", "recordings"))))
    tools.register(HomeAutomationTool(dry_run=dry_run))
    tools.register(NetworkDiscoveryTool())
    tools.register(SurveillanceTool(callback=lambda evt: print(f"{Fore.MAGENTA}Evento de vigilancia: {evt}{Style.RESET_ALL}")))

    agent = Agent(
        llm=llm,
        memory=memory,
        long_memory=long_memory,
        planner=planner,
        tools=tools,
        interface=None,
        rate_limiter=rate_limiter,
        audit_logger=audit,
        app_mode=app_mode,
    )

    print(f"{Fore.GREEN}JARVIS online! Digite sua mensagem ou comando.{Style.RESET_ALL}")
    print()

    while True:
        try:
            user_input = input(f"{Fore.BLUE}Voce: {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.RED}Encerrando JARVIS...{Style.RESET_ALL}")
            break

        if not user_input:
            continue

        allowed, wait_seconds = rate_limiter.allow()
        if not allowed:
            print(f"{Fore.YELLOW}Aguarde {wait_seconds:.2f}s antes do proximo comando.{Style.RESET_ALL}")
            continue

        command = user_input.lower()

        if command in ["sair", "quit", "exit"]:
            print(f"{Fore.RED}Ate logo!{Style.RESET_ALL}")
            break
        if command == "limpar":
            clear_screen()
            print_header()
            continue
        if command in ["ajuda", "help", "?"]:
            print_header()
            continue
        if command == "status":
            status = agent.runtime_status()
            print(f"{Fore.CYAN}{agent.format_status_message(status)}{Style.RESET_ALL}")
            print()
            continue
        if command == "memoria":
            context = memory.get_context()
            if context:
                print(f"{Fore.CYAN}Memoria recente:{Style.RESET_ALL}")
                for line in context.split("\n"):
                    print(f"  {line}")
            else:
                print(f"{Fore.YELLOW}Nenhuma memoria recente.{Style.RESET_ALL}")
            print()
            continue

        try:
            perception = {
                "type": "text",
                "content": user_input,
                "confidence": 1.0,
                "timestamp": time.time(),
            }

            analysis = agent.analyze(perception)
            plan = agent.plan(analysis)
            results = agent.act(plan)
            agent.remember(perception, analysis, plan, results)

            response = analysis.get("response", "Entendi.")
            print(f"{Fore.GREEN}JARVIS: {response}{Style.RESET_ALL}")

            for result in results:
                if isinstance(result, dict) and "message" in result:
                    print(f"{Fore.MAGENTA}Acao: {result['message']}{Style.RESET_ALL}")
                elif isinstance(result, dict) and "error" in result:
                    print(f"{Fore.RED}Erro: {result['error']}{Style.RESET_ALL}")

            print()

        except Exception as exc:
            print(f"{Fore.RED}Erro: {str(exc)}{Style.RESET_ALL}")
            print()
