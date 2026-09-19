import streamlit as st
import requests

st.title("🤖 My LLM Chatbot")

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

    prompt = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in st.session_state.messages
    )

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    answer = response.json()["response"]

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    st.rerun()