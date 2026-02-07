from core.agent import Agent

def chat():
    agent = Agent()
    print("IA Local iniciada. Digite 'sair' para encerrar.")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando Jarvis...")
            agent.surveillance.stop()
            break

        if not user_input:
            continue

        if user_input.lower() == "sair":
            agent.surveillance.stop()
            print("Jarvis desligado.")
            break

        response = agent.run(user_input)
        print("IA:", response)
