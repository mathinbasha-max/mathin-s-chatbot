import streamlit as st
import google.genai as genai

st.set_page_config(page_title="My AI Chatbot")

st.title("🤖 My AI Chatbot")
st.caption("Powered by Gemini")

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question
    )

    answer = response.text

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    with st.chat_message("assistant"):
        st.write(answer)
