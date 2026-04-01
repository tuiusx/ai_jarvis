import os
import time
from pathlib import Path

from colorama import Back, Fore, Style, init
import yaml

from core.agent import Agent

# Inicializar colorama
init(autoreset=True)


def clear_screen():
    """Limpa a tela"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """Imprime cabecalho estilizado"""
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

    # Inicializar componentes (simplificado para interface de texto)
    from core.llm import LocalLLM
    from core.memory import LongTermMemory, ShortTermMemory
    from core.planner import Planner
    from tools.camera import CameraTool
    from tools.home_automation import HomeAutomationTool
    from tools.manager import ToolManager
    from tools.network_discovery import NetworkDiscoveryTool
    from tools.recorder import RecorderTool
    from tools.surveillance_tool import SurveillanceTool

    settings = {}
    config_path = Path("config/settings.yaml")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file:
            settings = yaml.safe_load(file) or {}
    surveillance_cfg = settings.get("surveillance", {})
    home_assistant_cfg = settings.get("home_assistant", {})

    llm = LocalLLM()
    memory = ShortTermMemory()
    long_memory = LongTermMemory()
    planner = Planner()
    tools = ToolManager()
    tools.register(CameraTool())
    tools.register(RecorderTool())
    tools.register(NetworkDiscoveryTool())
    tools.register(HomeAutomationTool(home_assistant=home_assistant_cfg))
    tools.register(
        SurveillanceTool(
            callback=lambda evt: print(f"{Fore.MAGENTA}Evento de vigilancia: {evt}{Style.RESET_ALL}"),
            model_path=surveillance_cfg.get("model_path", "yolov8n.pt"),
            detect_interval=float(surveillance_cfg.get("detect_interval", 0.4)),
            record_cooldown=int(surveillance_cfg.get("record_cooldown", 30)),
        )
    )

    agent = Agent(llm=llm, memory=memory, planner=planner, tools=tools, interface=None)

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

            context = memory.get_context()
            analysis = llm.think(perception, context)
            plan = planner.create_plan(analysis)

            results = []
            if plan and "steps" in plan:
                for step in plan["steps"]:
                    if isinstance(step, dict):
                        if "action" in step and step["action"] == "respond":
                            results.append({"message": step.get("message", "Acao executada.")})
                        elif "tool" in step:
                            results.append(tools.execute(step))

            experience = {
                "perception": perception,
                "analysis": analysis,
                "plan": plan,
                "results": results,
                "timestamp": time.time(),
            }
            memory.store(experience)
            long_memory.add(f"Usuario: {user_input}")

            response = analysis.get("response", "Entendi.")
            print(f"{Fore.GREEN}JARVIS: {response}{Style.RESET_ALL}")

            for result in results:
                if isinstance(result, dict) and "message" in result:
                    print(f"{Fore.MAGENTA}Acao: {result['message']}{Style.RESET_ALL}")
                elif isinstance(result, dict) and "error" in result:
                    print(f"{Fore.RED}Erro: {result['error']}{Style.RESET_ALL}")

            print()

        except Exception as e:
            print(f"{Fore.RED}Erro: {str(e)}{Style.RESET_ALL}")
            print()
