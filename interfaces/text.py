from core.agent import Agent

agent = Agent()

def chat():
    print("IA Local iniciada. Digite 'sair' para encerrar.")
    while True:
        user_input = input("Você: ")
        if user_input.lower() == "sair":
            break
        response = agent.run(user_input)
        print("IA:", response)
