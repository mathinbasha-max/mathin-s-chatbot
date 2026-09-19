from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "My AI Chatbot Server is Running!"
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("message", "")

    api_key = os.environ.get("GEMINI_API_KEY")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"

    response = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "parts": [
                        {"text": question}
                    ]
                }
            ]
        }
    )

    result = response.json()

    answer = result["candidates"][0]["content"]["parts"][0]["text"]

    return jsonify({"reply": answer})


if __name__ == "__main__":
    app.run()
