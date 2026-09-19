import streamlit as st
import requests

st.set_page_config(
    page_title="My AI Chatbot",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 My AI Chatbot")
st.caption("Powered by Llama 3.2 + Ollama")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input("Ask me anything...")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.write(question)

    prompt = """
You are a helpful and friendly AI assistant.

Conversation:
""" + "\n".join(
        f"{m['role']}: {m['content']}"
        for m in st.session_state.messages
    ) + "\nassistant:"

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    answer = response.json()["response"].strip()

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    with st.chat_message("assistant"):
        st.write(answer)
