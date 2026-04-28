import os
import time

from colorama import Back, Fore, Style, init

from core.app_factory import AppFactory
from core.first_run_setup import ensure_first_run_setup
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
    print(f"{Back.BLUE}{Fore.WHITE}{'-' * 60}{Style.RESET_ALL}")
    print()


def _authorize_shortcut(agent, user_input, output_callback):
    perception = agent.prepare_perception_from_data(
        data={
            "mode": "text",
            "content": user_input,
            "confidence": 1.0,
            "timestamp": time.time(),
        },
        output_callback=output_callback,
    )
    return perception is not None


def _handle_protected_shortcuts(command, *, user_input, agent, memory, output_callback):
    if command == "status":
        if not _authorize_shortcut(agent=agent, user_input=user_input, output_callback=output_callback):
            print()
            return True
        status = agent.runtime_status()
        print(f"{Fore.CYAN}{agent.format_status_message(status)}{Style.RESET_ALL}")
        print()
        return True

    if command == "memoria":
        if not _authorize_shortcut(agent=agent, user_input=user_input, output_callback=output_callback):
            print()
            return True
        context_text = memory.get_context()
        if context_text:
            print(f"{Fore.CYAN}Memoria recente:{Style.RESET_ALL}")
            for line in context_text.split("\n"):
                print(f"  {line}")
        else:
            print(f"{Fore.YELLOW}Nenhuma memoria recente.{Style.RESET_ALL}")
        print()
        return True

    return False


def chat():
    clear_screen()
    print_header()

    settings = load_settings()
    try:
        setup_summary = ensure_first_run_setup(settings=settings, root_dir=".")
    except Exception as exc:
        print(f"{Fore.RED}Falha na configuracao inicial: {exc}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Finalize o cadastro facial do administrador e reinicie o JARVIS.{Style.RESET_ALL}")
        return

    if setup_summary.get("status") == "configured":
        print(f"{Fore.GREEN}Administrador configurado: {setup_summary.get('owner_name')}{Style.RESET_ALL}")

    app_mode = str(get_setting(settings, "app.mode", "dev"))
    factory = AppFactory(settings=settings)
    context = factory.build(interface=None, retention_summary={})
    agent = context.agent
    memory = context.memory

    if context.network_monitor is not None and getattr(context.network_monitor, "auto_start", False):
        result = context.network_monitor.start()
        if "error" in result:
            print(f"{Fore.YELLOW}Aviso monitor de rede: {result['error']}{Style.RESET_ALL}")

    print(f"{Fore.GREEN}JARVIS online! Digite sua mensagem ou comando.{Style.RESET_ALL}")
    print()

    def emit_pipeline_message(message):
        print(f"{Fore.MAGENTA}{message}{Style.RESET_ALL}")

    while True:
        try:
            user_input = input(f"{Fore.BLUE}Voce: {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.RED}Encerrando JARVIS...{Style.RESET_ALL}")
            break

        if not user_input:
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
        if _handle_protected_shortcuts(
            command,
            user_input=user_input,
            agent=agent,
            memory=memory,
            output_callback=emit_pipeline_message,
        ):
            continue

        payload = agent.process_command_data(
            data={
                "mode": "text",
                "content": user_input,
                "confidence": 1.0,
                "timestamp": time.time(),
            },
            output_callback=emit_pipeline_message,
            auto_remember=True,
        )
        if payload.get("state") != "processed":
            print()
            continue

        analysis = payload.get("analysis", {}) or {}
        results = payload.get("results", []) or []
        response = analysis.get("response", "Entendi.")
        print(f"{Fore.GREEN}JARVIS: {response}{Style.RESET_ALL}")
        for result in results:
            if isinstance(result, dict) and "message" in result:
                print(f"{Fore.MAGENTA}Acao: {result['message']}{Style.RESET_ALL}")
            elif isinstance(result, dict) and "error" in result:
                print(f"{Fore.RED}Erro: {result['error']}{Style.RESET_ALL}")
        print()

    if context.network_monitor is not None:
        try:
            context.network_monitor.stop()
        except Exception:
            pass
    if context.automation_hub is not None:
        try:
            context.automation_hub.close()
        except Exception:
            pass
    if context.backup_manager is not None:
        try:
            context.backup_manager.close()
        except Exception:
            pass
    if getattr(context, "system_monitor", None) is not None:
        try:
            context.system_monitor.close()
        except Exception:
            pass
    if getattr(context, "maintenance_guard", None) is not None:
        try:
            context.maintenance_guard.close()
        except Exception:
            pass

    context.audit.log("app.stop_text_mode", mode=app_mode)
