from core.agent import Agent

def chat():
    agent = Agent()
    print("IA Local iniciada. Digite 'sair' para encerrar.")

    while True:
        try:
            user_input = input("Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando.")
            break

        if user_input.lower() == "sair":
            break

        response = agent.run(user_input)
        if response:
            print("IA:", response)
