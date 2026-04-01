class Jarvis:
    def __init__(self):
        print("🧠 Jarvis inicializando...")

    def start(self):
        print("🤖 Jarvis online. Aguardando comandos...")
        while True:
            comando = input("Você: ")
            if comando.lower() in ["sair", "exit", "quit"]:
                print("👋 Encerrando Jarvis.")
                break
            print(f"Jarvis: você disse '{comando}'")
