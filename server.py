from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("message", "")

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": question,
            "stream": False
        }
    )

    answer = response.json()["response"]

    return jsonify({"reply": answer})

if __name__ == "__main__":
    app.run(port=5000, debug=True)