from core.agent import Agent

agent = Agent()

def chat():
    print("IA Local iniciada. Digite 'sair' para encerrar.")
    while True:
        user_input = input("Você: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ["sair", "exit", "quit"]:
            print("Encerrando IA...")
            break

        response = agent.run(user_input)
        print("IA:", response)
