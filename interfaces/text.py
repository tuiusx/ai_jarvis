import os
import time

from colorama import Back, Fore, Style, init

from core.agent import Agent


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

    llm = LocalLLM()
    memory = ShortTermMemory()
    long_memory = LongTermMemory()
    planner = Planner()

    tools = ToolManager()
    tools.register(CameraTool())
    tools.register(RecorderTool())
    tools.register(HomeAutomationTool())
    tools.register(NetworkDiscoveryTool())
    tools.register(SurveillanceTool(callback=lambda evt: print(f"{Fore.MAGENTA}Evento de vigilancia: {evt}{Style.RESET_ALL}")))

    agent = Agent(llm=llm, memory=memory, long_memory=long_memory, planner=planner, tools=tools, interface=None)

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
