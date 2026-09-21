from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import time

app = Flask(__name__)
CORS(app)


# ===============================
# HOME PAGE
# ===============================

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


# ===============================
# CSS FILE
# ===============================

@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")


# ===============================
# JAVASCRIPT FILE
# ===============================

@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js")


# ===============================
# CHAT API
# ===============================

@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "reply": "Please enter a message."
            }), 400

        question = data.get("message", "").strip()

        if not question:
            return jsonify({
                "reply": "Please enter a message."
            }), 400

        # Get Gemini API key from Render Environment Variables
        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            return jsonify({
                "reply": "Gemini API key is not configured on the server."
            }), 500

        # Gemini API URL
        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/gemini-3.6-flash:generateContent"
        )

        # Request data
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": question
                        }
                    ]
                }
            ]
        }

        # Try up to 3 times
        for attempt in range(3):

            response = requests.post(
                url,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )

            result = response.json()

            print("GEMINI RESPONSE:", result)

            # ===============================
            # SUCCESS
            # ===============================

            if "candidates" in result:

                try:
                    answer = (
                        result["candidates"][0]
                        ["content"]
                        ["parts"][0]
                        ["text"]
                    )

                    return jsonify({
                        "reply": answer
                    })

                except (KeyError, IndexError, TypeError):

                    return jsonify({
                        "reply": "Gemini returned an unexpected response."
                    }), 500

            # ===============================
            # TEMPORARY 503 ERROR
            # ===============================

            if response.status_code == 503:

                print(
                    f"Gemini is busy. Retry attempt "
                    f"{attempt + 1}/3"
                )

                # Wait 2, 4, 8 seconds
                time.sleep(2 ** attempt)

                continue

            # ===============================
            # OTHER GEMINI ERROR
            # ===============================

            error_message = (
                result
                .get("error", {})
                .get("message", "Unknown Gemini API error")
            )

            print("GEMINI ERROR:", error_message)

            return jsonify({
                "reply": "AI server error: " + error_message
            }), 500

        # ===============================
        # ALL RETRIES FAILED
        # ===============================

        return jsonify({
            "reply": (
                "The AI server is temporarily busy. "
                "Please try again in a few seconds."
            )
        }), 503

    except requests.exceptions.Timeout:

        return jsonify({
            "reply": "The AI server took too long to respond. Please try again."
        }), 504

    except requests.exceptions.RequestException as e:

        print("REQUEST ERROR:", e)

        return jsonify({
            "reply": "Unable to connect to the AI server."
        }), 500

    except Exception as e:

        print("SERVER ERROR:", e)

        return jsonify({
            "reply": "Something went wrong on the server."
        }), 500


# ===============================
# START SERVER
# ===============================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
