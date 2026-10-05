from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from supabase import create_client, Client
import requests
import os
import time
import uuid
import re
import dateparser
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
# CSS
# =========================================================

@app.route("/style.css")
def style():
    return send_from_directory(".", "style.css")


# =========================================================
# JAVASCRIPT
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
# GET CHAT HISTORY
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
# CHECK REMINDER REQUEST
# =========================================================

def is_reminder_request(question):

    text = question.lower().strip()

    reminder_patterns = [
        r"\bremind me\b",
        r"\bcan you remind me\b",
        r"\bplease remind me\b",
        r"\bset a reminder\b",
        r"\bset reminder\b"
    ]

    for pattern in reminder_patterns:

        if re.search(pattern, text):
            return True

    return False


# =========================================================
# EXTRACT TIME
# =========================================================

def extract_time(text):

    # Supports:
    # 7 PM
    # 7:30 PM
    # 7.30 PM
    # 07:30 PM
    # 19:30
    # 7.30

    time_pattern = re.compile(
        r"\b("
        r"(?:[0-1]?\d|2[0-3])"
        r"(?:\s*[:.]\s*[0-5]\d)?"
        r"\s*(?:AM|PM|am|pm)?"
        r")\b"
    )

    match = time_pattern.search(text)

    if not match:
        return None, None

    time_text = match.group(1).strip()

    # Convert 7.30 → 7:30
    normalized_time = time_text.replace(".", ":")

    # If AM/PM is missing
    # dateparser can still understand common values
    parsed_time = dateparser.parse(
        normalized_time,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": False
        }
    )

    if not parsed_time:
        return None, None

    return match, parsed_time


# =========================================================
# EXTRACT REMINDER
# =========================================================

def extract_reminder(question):

    try:

        now = datetime.now(INDIA_TZ)

        original = question.strip()

        # -------------------------------------------------
        # Remove reminder command
        # -------------------------------------------------

        cleaned = re.sub(
            r"^\s*(?:can you\s+|please\s+)?"
            r"(?:remind me|set a reminder|set reminder)"
            r"\s*",
            "",
            original,
            flags=re.IGNORECASE
        ).strip()


        # -------------------------------------------------
        # Find time
        # -------------------------------------------------

        time_match, parsed_time = extract_time(cleaned)

        if not time_match:

            return None

        time_text = time_match.group(1)

        # -------------------------------------------------
        # Remove time from sentence
        # -------------------------------------------------

        without_time = (
            cleaned[:time_match.start()]
            + " "
            + cleaned[time_match.end():]
        ).strip()


        # -------------------------------------------------
        # Find date words
        # -------------------------------------------------

        date_patterns = [
            r"\btoday\b",
            r"\btomorrow\b",
            r"\bday after tomorrow\b",
            r"\bnext\s+(?:monday|tuesday|wednesday|"
            r"thursday|friday|saturday|sunday)\b",
            r"\bthis\s+(?:monday|tuesday|wednesday|"
            r"thursday|friday|saturday|sunday)\b",
            r"\bon\s+\d{1,2}(?:st|nd|rd|th)?\s+"
            r"(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december)\b",
            r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"
        ]

        date_text = None
        date_match = None

        for pattern in date_patterns:

            match = re.search(
                pattern,
                without_time,
                flags=re.IGNORECASE
            )

            if match:

                date_match = match
                date_text = match.group(0)
                break


        # -------------------------------------------------
        # If no date specified, use today
        # -------------------------------------------------

        if date_text:

            parsed_date = dateparser.parse(
                date_text,
                settings={
                    "RELATIVE_BASE": now,
                    "PREFER_DATES_FROM": "future"
                }
            )

        else:

            parsed_date = now


        if not parsed_date:

            return None


        # -------------------------------------------------
        # Combine date + time
        # -------------------------------------------------

        hour = parsed_time.hour
        minute = parsed_time.minute


        # Detect AM/PM manually
        if re.search(r"\bPM\b", time_text, re.IGNORECASE):

            if hour < 12:
                hour += 12

        elif re.search(r"\bAM\b", time_text, re.IGNORECASE):

            if hour == 12:
                hour = 0

        else:

            # No AM/PM.
            # Keep entered hour as-is.

            pass


        reminder_datetime = datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            hour,
            minute,
            0,
            tzinfo=INDIA_TZ
        )


        # -------------------------------------------------
        # If "today" time already passed,
        # don't silently create a past reminder.
        # -------------------------------------------------

        if reminder_datetime <= now:

            if date_text and date_text.lower() == "today":

                return None


        # -------------------------------------------------
        # Remove date from task text
        # -------------------------------------------------

        task_text = without_time

        if date_match:

            task_text = (
                task_text[:date_match.start()]
                + " "
                + task_text[date_match.end():]
            )


        # -------------------------------------------------
        # Remove common words
        # -------------------------------------------------

        task_text = re.sub(
            r"^\s*(?:at|on|for|to)\s+",
            "",
            task_text,
            flags=re.IGNORECASE
        )

        task_text = re.sub(
            r"\b(?:at|on)\s*$",
            "",
            task_text,
            flags=re.IGNORECASE
        )

        task_text = task_text.strip(" ,.-")


        # -------------------------------------------------
        # Remove leading "to"
        # -------------------------------------------------

        if task_text.lower().startswith("to "):

            task_text = task_text[3:].strip()


        # -------------------------------------------------
        # If task is empty
        # -------------------------------------------------

        if not task_text:

            task_text = "Reminder"


        return {

            "text": task_text,

            "date": reminder_datetime.strftime(
                "%Y-%m-%d"
            ),

            "time": reminder_datetime.strftime(
                "%H:%M:%S"
            ),

            "datetime": reminder_datetime

        }


    except Exception as e:

        print(
            "REMINDER PARSING ERROR:",
            e
        )

        return None


# =========================================================
# CREATE RESPONSE WITH COOKIE
# =========================================================

def create_response(user_id, answer):

    response = make_response(
        jsonify({
            "reply": answer
        })
    )

    response.set_cookie(

        "chat_user_id",

        user_id,

        max_age=60 * 60 * 24 * 365 * 5,

        httponly=True,

        samesite="Lax",

        secure=True

    )

    return response


# =========================================================
# CHAT API
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:

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
        # USER ID
        # -------------------------------------------------

        user_id = get_user_id()


        # =================================================
        # REMINDER REQUEST
        # =================================================

        if is_reminder_request(question):

            reminder = extract_reminder(question)


            # -------------------------------------------------
            # Reminder could not be understood
            # -------------------------------------------------

            if not reminder:

                answer = (
                    "I couldn't understand the reminder "
                    "date or time.\n\n"
                    "Try something like:\n"
                    "\"Remind me tomorrow at 10 AM "
                    "to submit my assignment.\"\n\n"
                    "You can also use:\n"
                    "\"Remind me today at 8.30 PM "
                    "to call my grandmother.\""
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


                return create_response(
                    user_id,
                    answer
                )


            # -------------------------------------------------
            # SAVE REMINDER
            # -------------------------------------------------

            saved = save_reminder(

                user_id,

                reminder["text"],

                reminder["date"],

                reminder["time"]

            )


            if not saved:

                answer = (
                    "I understood your reminder, "
                    "but I couldn't save it to the database."
                )

                return create_response(
                    user_id,
                    answer
                )


            # -------------------------------------------------
            # DISPLAY DATE/TIME
            # -------------------------------------------------

            display_datetime = (
                reminder["datetime"]
                .strftime(
                    "%d %b %Y at %I:%M %p"
                )
            )


            answer = (
                "✅ Reminder saved successfully!\n\n"
                f"📝 {reminder['text']}\n"
                f"⏰ {display_datetime}"
            )


            # -------------------------------------------------
            # SAVE TO CHAT MEMORY
            # -------------------------------------------------

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


            return create_response(
                user_id,
                answer
            )


        # =================================================
        # NORMAL AI CHAT
        # =================================================

        history = get_chat_history(user_id)


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

Use previous information when it is relevant.

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
        # GEMINI URL
        # -------------------------------------------------

        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/"
            "gemini-3.6-flash:"
            "generateContent"
        )


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


                    return create_response(
                        user_id,
                        answer
                    )


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
            # 503 RETRY
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


        # -------------------------------------------------
        # ALL RETRIES FAILED
        # -------------------------------------------------

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
    # OTHER ERROR
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
