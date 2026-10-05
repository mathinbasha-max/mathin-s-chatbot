from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from supabase import create_client, Client
import requests
import os
import time
import uuid
import dateparser
from dateparser.search import search_dates
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
CORS(app)


# =========================================================
# TIMEZONE
# =========================================================

INDIA_TZ = ZoneInfo("Asia/Kolkata")


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
# SAVE CHAT MESSAGE
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
# SAVE REMINDER
# =========================================================

def save_reminder(
    user_id,
    reminder_text,
    reminder_date,
    reminder_time
):

    if not supabase:
        print("Supabase is not connected.")
        return False

    try:

        supabase.table("reminders").insert({

            "user_id": user_id,

            "reminder_text": reminder_text,

            "reminder_date": reminder_date,

            "reminder_time": reminder_time,

            "completed": False

        }).execute()

        return True

    except Exception as e:

        print("SUPABASE REMINDER SAVE ERROR:", e)

        return False


# =========================================================
# CHECK WHETHER MESSAGE IS A REMINDER REQUEST
# =========================================================

def is_reminder_request(question):

    text = question.lower().strip()

    reminder_words = [
        "remind me",
        "set a reminder",
        "set reminder",
        "remember to remind me"
    ]

    return any(
        word in text
        for word in reminder_words
    )


# =========================================================
# EXTRACT REMINDER DETAILS
# =========================================================

def extract_reminder(question):

    try:

        # Remove common reminder phrases
        cleaned_question = question.strip()

        prefixes = [
            "remind me",
            "set a reminder",
            "set reminder"
        ]

        for prefix in prefixes:

            if cleaned_question.lower().startswith(prefix):

                cleaned_question = (
                    cleaned_question[len(prefix):]
                    .strip()
                )

                break


        # Remove optional "to" before the actual task
        if cleaned_question.lower().startswith("to "):

            cleaned_question = cleaned_question[3:].strip()


        # Current time in India
        now = datetime.now(INDIA_TZ)


        # Find date/time inside the sentence
        matches = search_dates(

            cleaned_question,

            languages=["en"],

            settings={
                "RELATIVE_BASE": now,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future"
            }
        )


        if not matches:

            return None


        # Use the first detected date/time
        matched_text, parsed_datetime = matches[0]


        # Convert to India timezone
        if parsed_datetime.tzinfo is None:

            parsed_datetime = parsed_datetime.replace(
                tzinfo=INDIA_TZ
            )

        else:

            parsed_datetime = parsed_datetime.astimezone(
                INDIA_TZ
            )


        # Remove the detected date/time
        # from the original reminder text
        reminder_text = cleaned_question.replace(
            matched_text,
            ""
        ).strip()


        # Clean common leftover words
        reminder_text = reminder_text.strip(" ,.-")


        if reminder_text.lower().startswith("to "):

            reminder_text = reminder_text[3:].strip()


        if not reminder_text:

            reminder_text = "Reminder"


        # Make sure the reminder is in the future
        if parsed_datetime <= now:

            return None


        return {

            "text": reminder_text,

            "date": parsed_datetime.strftime(
                "%Y-%m-%d"
            ),

            "time": parsed_datetime.strftime(
                "%H:%M:%S"
            ),

            "datetime": parsed_datetime

        }


    except Exception as e:

        print(
            "REMINDER PARSING ERROR:",
            e
        )

        return None


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


        question = data.get(
            "message",
            ""
        ).strip()


        if not question:

            return jsonify({
                "reply": "Please enter a message."
            }), 400


        # -------------------------------------------------
        # GET USER ID
        # -------------------------------------------------

        user_id = get_user_id()


        # =================================================
        # REMINDER REQUEST
        # =================================================

        if is_reminder_request(question):

            reminder = extract_reminder(question)


            # ---------------------------------------------
            # Could not understand date/time
            # ---------------------------------------------

            if not reminder:

                answer = (
                    "I couldn't understand the reminder "
                    "date or time. Please use a format like: "
                    "\"Remind me tomorrow at 10 AM to "
                    "submit my assignment.\""
                )


                save_message(
                    user_id,
                    "user",
                    question
                )


                save_message(
                    user_id,
                    "assistant",
                    answer
                )


                flask_response = make_response(
                    jsonify({
                        "reply": answer
                    })
                )


                flask_response.set_cookie(

                    "chat_user_id",

                    user_id,

                    max_age=60 * 60 * 24 * 365 * 5,

                    httponly=True,

                    samesite="Lax",

                    secure=True
                )


                return flask_response


            # ---------------------------------------------
            # SAVE REMINDER
            # ---------------------------------------------

            saved = save_reminder(

                user_id,

                reminder["text"],

                reminder["date"],

                reminder["time"]

            )


            if not saved:

                return jsonify({

                    "reply":
                    "I understood the reminder, "
                    "but I couldn't save it. "
                    "Please try again."

                }), 500


            # ---------------------------------------------
            # FORMAT DISPLAY TIME
            # ---------------------------------------------

            display_datetime = (
                reminder["datetime"]
                .strftime("%d %b %Y at %I:%M %p")
            )


            answer = (
                "✅ Reminder saved successfully!\n\n"
                f"📝 {reminder['text']}\n"
                f"⏰ {display_datetime}"
            )


            # ---------------------------------------------
            # SAVE CHAT HISTORY TOO
            # ---------------------------------------------

            save_message(
                user_id,
                "user",
                question
            )


            save_message(
                user_id,
                "assistant",
                answer
            )


            flask_response = make_response(
                jsonify({
                    "reply": answer
                })
            )


            flask_response.set_cookie(

                "chat_user_id",

                user_id,

                max_age=60 * 60 * 24 * 365 * 5,

                httponly=True,

                samesite="Lax",

                secure=True
            )


            return flask_response


        # =================================================
        # NORMAL AI CHAT
        # =================================================

        history = get_chat_history(user_id)


        # -------------------------------------------------
        # BUILD CONVERSATION
        # -------------------------------------------------

        conversation_text = ""


        for item in history:

            role = item.get(
                "role",
                ""
            )

            message = item.get(
                "message",
                ""
            )


            if role == "user":

                conversation_text += (
                    "User: "
                    + message
                    + "\n"
                )


            elif role == "assistant":

                conversation_text += (
                    "Assistant: "
                    + message
                    + "\n"
                )


        # -------------------------------------------------
        # GEMINI PROMPT
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

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )


        if not api_key:

            return jsonify({

                "reply":
                "Gemini API key is not configured "
                "on the server."

            }), 500


        # -------------------------------------------------
        # GEMINI API URL
        # -------------------------------------------------

        url = (

            "https://generativelanguage.googleapis.com/"

            "v1beta/models/"
            "gemini-3.6-flash:"
            "generateContent"

        )


        # -------------------------------------------------
        # GEMINI PAYLOAD
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


        # =================================================
        # TRY GEMINI UP TO 3 TIMES
        # =================================================

        for attempt in range(3):

            response = requests.post(

                url,

                headers={

                    "x-goog-api-key":
                    api_key,

                    "Content-Type":
                    "application/json"

                },

                json=payload,

                timeout=60
            )


            result = response.json()


            print(
                "GEMINI RESPONSE:",
                result
            )


            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

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

                            "reply":
                            answer

                        })

                    )


                    # -----------------------------------------
                    # SAVE USER ID COOKIE
                    # -----------------------------------------

                    flask_response.set_cookie(

                        "chat_user_id",

                        user_id,

                        max_age=60 * 60 * 24 * 365 * 5,

                        httponly=True,

                        samesite="Lax",

                        secure=True

                    )


                    return flask_response


                except (
                    KeyError,
                    IndexError,
                    TypeError
                ):

                    return jsonify({

                        "reply":
                        "Gemini returned an "
                        "unexpected response."

                    }), 500


            # -------------------------------------------------
            # TEMPORARY 503 ERROR
            # -------------------------------------------------

            if response.status_code == 503:

                print(

                    f"Gemini is busy. "
                    f"Retry attempt "
                    f"{attempt + 1}/3"

                )


                time.sleep(
                    2 ** attempt
                )


                continue


            # -------------------------------------------------
            # OTHER GEMINI ERROR
            # -------------------------------------------------

            error_message = (

                result

                .get(
                    "error",
                    {}
                )

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


        # =================================================
        # ALL RETRIES FAILED
        # =================================================

        return jsonify({

            "reply":
            "The AI server is temporarily busy. "
            "Please try again in a few seconds."

        }), 503


    # =====================================================
    # TIMEOUT
    # =====================================================

    except requests.exceptions.Timeout:

        return jsonify({

            "reply":
            "The AI server took too long to respond. "
            "Please try again."

        }), 504


    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.exceptions.RequestException as e:

        print(
            "REQUEST ERROR:",
            e
        )


        return jsonify({

            "reply":
            "Unable to connect to the AI server."

        }), 500


    # =====================================================
    # OTHER SERVER ERROR
    # =====================================================

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
