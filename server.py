from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from supabase import create_client, Client
import requests
import os
import time
import uuid

app = Flask(__name__)
CORS(app)


# =========================================================
# SUPABASE CONNECTION
# =========================================================

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("WARNING: Supabase environment variables are missing.")
    supabase = None
else:
    supabase: Client = create_client(
        supabase_url,
        supabase_key
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


# =========================================================
# CSS FILE
# =========================================================

@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")


# =========================================================
# JAVASCRIPT FILE
# =========================================================

@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js")


# =========================================================
# GET OR CREATE USER ID
# =========================================================

def get_user_id():

    user_id = request.cookies.get("chat_user_id")

    if not user_id:
        user_id = str(uuid.uuid4())

    return user_id


# =========================================================
# GET PREVIOUS CHAT HISTORY
# =========================================================

def get_chat_history(user_id):

    if not supabase:
        return []

    try:

        result = (
            supabase
            .table("chat_memory")
            .select("role, message, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(30)
            .execute()
        )

        return result.data or []

    except Exception as e:

        print("SUPABASE READ ERROR:", e)

        return []


# =========================================================
# SAVE MESSAGE TO SUPABASE
# =========================================================

def save_message(user_id, role, message):

    if not supabase:
        print("Supabase is not connected.")
        return False

    try:

        supabase.table("chat_memory").insert({
            "user_id": user_id,
            "role": role,
            "message": message
        }).execute()

        return True

    except Exception as e:

        print("SUPABASE SAVE ERROR:", e)

        return False


# =========================================================
# CHAT API
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        # -------------------------------------------------
        # GET USER MESSAGE
        # -------------------------------------------------

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


        # -------------------------------------------------
        # GET USER ID
        # -------------------------------------------------

        user_id = get_user_id()


        # -------------------------------------------------
        # GET PREVIOUS MEMORY
        # -------------------------------------------------

        history = get_chat_history(user_id)


        # -------------------------------------------------
        # BUILD CONVERSATION FOR GEMINI
        # -------------------------------------------------

        conversation_text = ""

        for item in history:

            role = item.get("role", "")
            message = item.get("message", "")

            if role == "user":

                conversation_text += (
                    "User: " + message + "\n"
                )

            elif role == "assistant":

                conversation_text += (
                    "Assistant: " + message + "\n"
                )


        # -------------------------------------------------
        # ADD CURRENT QUESTION
        # -------------------------------------------------

        prompt = f"""
You are a helpful AI chatbot.

You have access to the previous conversation with this user.

Use the previous conversation when it is relevant.

Previous conversation:
{conversation_text}

Current user message:
{question}

Answer the current user message naturally and accurately.
"""


        # -------------------------------------------------
        # GEMINI API KEY
        # -------------------------------------------------

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:

            return jsonify({
                "reply": "Gemini API key is not configured on the server."
            }), 500


        # -------------------------------------------------
        # GEMINI API URL
        # -------------------------------------------------

        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/gemini-3.6-flash:generateContent"
        )


        # -------------------------------------------------
        # GEMINI REQUEST
        # -------------------------------------------------

        payload = {

            "contents": [

                {
                    "parts": [

                        {
                            "text": prompt
                        }

                    ]
                }

            ]

        }


        # -------------------------------------------------
        # TRY GEMINI UP TO 3 TIMES
        # -------------------------------------------------

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


            # =================================================
            # SUCCESS
            # =================================================

            if "candidates" in result:

                try:

                    answer = (
                        result["candidates"][0]
                        ["content"]
                        ["parts"][0]
                        ["text"]
                    ).strip()


                    # -----------------------------------------
                    # SAVE USER MESSAGE
                    # -----------------------------------------

                    save_message(
                        user_id,
                        "user",
                        question
                    )


                    # -----------------------------------------
                    # SAVE AI RESPONSE
                    # -----------------------------------------

                    save_message(
                        user_id,
                        "assistant",
                        answer
                    )


                    # -----------------------------------------
                    # CREATE RESPONSE
                    # -----------------------------------------

                    flask_response = make_response(
                        jsonify({
                            "reply": answer
                        })
                    )


                    # Save user ID in browser cookie
                    flask_response.set_cookie(

                        "chat_user_id",

                        user_id,

                        max_age=60 * 60 * 24 * 365 * 5,

                        httponly=True,

                        samesite="Lax",

                        secure=True
                    )


                    return flask_response


                except (KeyError, IndexError, TypeError):

                    return jsonify({

                        "reply":
                        "Gemini returned an unexpected response."

                    }), 500


            # =================================================
            # TEMPORARY 503 ERROR
            # =================================================

            if response.status_code == 503:

                print(
                    f"Gemini is busy. "
                    f"Retry attempt {attempt + 1}/3"
                )


                time.sleep(2 ** attempt)

                continue


            # =================================================
            # OTHER GEMINI ERROR
            # =================================================

            error_message = (

                result

                .get("error", {})

                .get(
                    "message",
                    "Unknown Gemini API error"
                )

            )


            print(
                "GEMINI ERROR:",
                error_message
            )


            return jsonify({

                "reply":
                "AI server error: "
                + error_message

            }), 500


        # =====================================================
        # ALL RETRIES FAILED
        # =====================================================

        return jsonify({

            "reply":
            "The AI server is temporarily busy. "
            "Please try again in a few seconds."

        }), 503


    # =========================================================
    # TIMEOUT ERROR
    # =========================================================

    except requests.exceptions.Timeout:

        return jsonify({

            "reply":
            "The AI server took too long to respond. "
            "Please try again."

        }), 504


    # =========================================================
    # REQUEST ERROR
    # =========================================================

    except requests.exceptions.RequestException as e:

        print(
            "REQUEST ERROR:",
            e
        )

        return jsonify({

            "reply":
            "Unable to connect to the AI server."

        }), 500


    # =========================================================
    # OTHER SERVER ERROR
    # =========================================================

    except Exception as e:

        print(
            "SERVER ERROR:",
            e
        )

        return jsonify({

            "reply":
            "Something went wrong on the server."

        }), 500


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )

    )
