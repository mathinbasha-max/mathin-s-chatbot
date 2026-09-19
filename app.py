import requests

print("Chatbot started! Type 'exit' to quit.")

conversation = []

while True:
    question = input("You: ")

    if question.strip().lower() == "exit":
        print("Goodbye!")
        break

    conversation.append("User: " + question)

    prompt = """You are a helpful chatbot.
Remember the previous conversation and use it to answer the user's questions.

Conversation:
""" + "\n".join(conversation) + "\nAssistant:"

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    answer = response.json()["response"].strip()

    print("Bot:", answer)

    conversation.append("Assistant: " + answer)