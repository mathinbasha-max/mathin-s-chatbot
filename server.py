from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import requests
import os
import uuid
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from supabase import create_client
import dateparser
from dateparser.search import search_dates
from dotenv import load_dotenv


# =========================================================
# LOAD .ENV FILE
# =========================================================

load_dotenv()


# =========================================================
# APP SETUP
# =========================================================

app = Flask(__name__)
CORS(app)

IST = ZoneInfo("Asia/Kolkata")


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


# =========================================================
# SUPABASE CONNECTION
# =========================================================

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Supabase environment variables are missing.")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


# =========================================================
# GEMINI
# =========================================================

GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


# =========================================================
# USER ID
# =========================================================

def get_user_id():

    user_id = request.cookies.get("chat_user_id")

    if not user_id:
        user_id = str(uuid.uuid4())

    return user_id


# =========================================================
# CHAT MEMORY
# =========================================================

def get_chat_history(user_id):

    if not supabase:
        return []

    try:

        result = (
            supabase
            .table("chat_memory")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(30)
            .execute()
        )

        return result.data or []

    except Exception as e:

        print("Memory read error:", e)

        return []


def save_message(user_id, role, message):

    if not supabase:
        return

    try:

        supabase.table("chat_memory").insert({
            "user_id": user_id,
            "role": role,
            "message": message
        }).execute()

    except Exception as e:

        print("Memory save error:", e)


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
        return None

    try:

        result = (
            supabase
            .table("reminders")
            .insert({
                "user_id": user_id,
                "reminder_text": reminder_text,
                "reminder_date": reminder_date,
                "reminder_time": reminder_time,
                "completed": False,
                "notification_sent": False
            })
            .execute()
        )

        if result.data:
            return result.data[0]

        return None

    except Exception as e:

        print("Reminder save error:", e)

        return None


# =========================================================
# CHECK REMINDER REQUEST
# =========================================================

def is_reminder_request(message):

    message_lower = message.lower().strip()

    reminder_words = [
        "remind me",
        "reminder",
        "set a reminder",
        "set reminder",
        "remind"
    ]

    for word in reminder_words:

        if word in message_lower:
            return True

    return False


# =========================================================
# EXTRACT TIME
# =========================================================

def extract_time(text):

    text_lower = text.lower()

    # 12 hour format
    # 7 PM
    # 7:30 PM
    # 7.30 PM

    pattern_12 = r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b"

    match = re.search(
        pattern_12,
        text_lower
    )

    if match:

        hour = int(match.group(1))

        minute = int(
            match.group(2) or 0
        )

        period = match.group(3)

        if hour < 1 or hour > 12:
            return None

        if minute < 0 or minute > 59:
            return None

        if period == "pm" and hour != 12:
            hour += 12

        if period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}:00"


    # 24 hour format
    # 19:30
    # 19.30

    pattern_24 = r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b"

    match = re.search(
        pattern_24,
        text_lower
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2))

        return f"{hour:02d}:{minute:02d}:00"


    return None


# =========================================================
# EXTRACT DATE
# =========================================================

def extract_date(text):

    text_lower = text.lower()

    today = datetime.now(IST).date()


    # TODAY

    if re.search(r"\btoday\b", text_lower):
        return today


    # DAY AFTER TOMORROW
    # This must come BEFORE tomorrow.

    if re.search(
        r"\bday after tomorrow\b",
        text_lower
    ):
        return today + timedelta(days=2)


    # TOMORROW

    if re.search(
        r"\btomorrow\b",
        text_lower
    ):
        return today + timedelta(days=1)


    # WEEKDAYS

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }


    # NEXT MONDAY etc.

    match = re.search(
        r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text_lower
    )

    if match:

        target_day = weekdays[
            match.group(1)
        ]

        current_day = today.weekday()

        days_ahead = (
            target_day - current_day
        ) % 7

        if days_ahead == 0:
            days_ahead = 7

        return today + timedelta(
            days=days_ahead
        )


    # THIS MONDAY etc.

    match = re.search(
        r"\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text_lower
    )

    if match:

        target_day = weekdays[
            match.group(1)
        ]

        current_day = today.weekday()

        days_ahead = (
            target_day - current_day
        ) % 7

        return today + timedelta(
            days=days_ahead
        )


    # DATEPARSER

    try:

        results = search_dates(
            text,
            languages=["en"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(IST)
            }
        )

        if results:

            for found_text, parsed_date in results:

                lower_found = (
                    found_text.lower().strip()
                )

                if re.fullmatch(
                    r"\d{1,2}([:.]\d{2})?\s*(am|pm)?",
                    lower_found
                ):
                    continue

                return parsed_date.date()

    except Exception as e:

        print(
            "Date parsing error:",
            e
        )


    return None


# =========================================================
# EXTRACT REMINDER
# =========================================================

def extract_reminder(message):

    reminder_date = extract_date(
        message
    )

    reminder_time = extract_time(
        message
    )

    if not reminder_date or not reminder_time:
        return None


    text = message.strip()


    # Remove beginning phrases

    text = re.sub(
        r"^\s*can\s+you\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*please\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*remind\s+me\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*set\s+(?:a\s+)?reminder\s+",
        "",
        text,
        flags=re.IGNORECASE
    )


    # Remove date phrases

    date_patterns = [

        r"\bday after tomorrow\b",

        r"\btomorrow\b",

        r"\btoday\b",

        r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",

        r"\bthis\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    ]


    for pattern in date_patterns:

        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE
        )


    # Remove time

    text = re.sub(
        r"\b\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d\b",
        "",
        text,
        flags=re.IGNORECASE
    )


    # Remove connecting words

    text = re.sub(
        r"^\s*(at|on)\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*to\s+",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*for\s+",
        "",
        text,
        flags=re.IGNORECASE
    )


    # Clean spaces

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    text = text.strip(
        " ,.-"
    )


    if not text:

        text = "Complete the reminder"


    return {

        "text": text,

        "date": reminder_date.isoformat(),

        "time": reminder_time
    }


# =========================================================
# GET DUE REMINDERS
# =========================================================

def get_due_reminders():

    if not supabase:
        return []

    try:

        now = datetime.now(IST)

        today = now.date().isoformat()

        current_time = now.strftime(
            "%H:%M:%S"
        )


        result = (
            supabase
            .table("reminders")
            .select("*")
            .eq(
                "reminder_date",
                today
            )
            .eq(
                "notification_sent",
                False
            )
            .eq(
                "completed",
                False
            )
            .lte(
                "reminder_time",
                current_time
            )
            .execute()
        )


        return result.data or []


    except Exception as e:

        print(
            "Due reminder error:",
            e
        )

        return []


# =========================================================
# MARK NOTIFICATION SENT
# =========================================================

def mark_notification_sent(
    reminder_id
):

    if not supabase:
        return False

    try:

        (
            supabase
            .table("reminders")
            .update({
                "notification_sent": True
            })
            .eq(
                "id",
                reminder_id
            )
            .execute()
        )

        return True


    except Exception as e:

        print(
            "Notification update error:",
            e
        )

        return False


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        ".",
        "index.html"
    )


# =========================================================
# CSS
# =========================================================

@app.route("/style.css")
def css():

    return send_from_directory(
        ".",
        "style.css"
    )


# =========================================================
# JAVASCRIPT
# =========================================================

@app.route("/script.js")
def javascript():

    return send_from_directory(
        ".",
        "script.js"
    )


# =========================================================
# CHAT
# =========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "reply":
                "Please enter a message."
            })


        message = str(
            data.get(
                "message",
                ""
            )
        ).strip()


        if not message:

            return jsonify({
                "reply":
                "Please enter a message."
            })


        user_id = get_user_id()


        # =================================================
        # REMINDER
        # =================================================

        if is_reminder_request(
            message
        ):

            reminder = extract_reminder(
                message
            )


            if reminder:

                saved = save_reminder(

                    user_id=user_id,

                    reminder_text=reminder[
                        "text"
                    ],

                    reminder_date=reminder[
                        "date"
                    ],

                    reminder_time=reminder[
                        "time"
                    ]
                )


                if saved:

                    reply = (

                        "✅ Reminder saved!\n\n"

                        f"📝 {reminder['text']}\n"

                        f"📅 {reminder['date']}\n"

                        f"⏰ {reminder['time'][:5]}"
                    )


                    save_message(
                        user_id,
                        "user",
                        message
                    )

                    save_message(
                        user_id,
                        "assistant",
                        reply
                    )


                    response = make_response(
                        jsonify({
                            "reply": reply
                        })
                    )


                    response.set_cookie(
                        "chat_user_id",
                        user_id,
                        max_age=60 * 60 * 24 * 365,
                        httponly=True,
                        samesite="Lax",
                        secure=request.is_secure
                    )


                    return response


            # Missing date/time

            reply = (

                "⏰ I can set the reminder, "
                "but I need both the date and time.\n\n"

                "Example:\n"

                "Remind me tomorrow at 10 AM "
                "to submit my assignment."
            )


            response = make_response(
                jsonify({
                    "reply": reply
                })
            )


            response.set_cookie(
                "chat_user_id",
                user_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure
            )


            return response


        # =================================================
        # NORMAL CHAT
        # =================================================

        history = get_chat_history(
            user_id
        )


        conversation = ""


        for item in history:

            role = item.get(
                "role",
                "user"
            )

            msg = item.get(
                "message",
                ""
            )


            if role == "user":

                conversation += (
                    f"User: {msg}\n"
                )

            else:

                conversation += (
                    f"Assistant: {msg}\n"
                )


        system_instruction = """

You are a helpful personal AI assistant.

Your name is My AI Assistant.

Give clear, useful and friendly answers.

Remember information from the conversation
when it is available.

If the user asks a simple question,
answer simply.

If the user asks for coding help,
explain step by step.

Do not say that you cannot remember something
if the information is available in the conversation history.

"""


        prompt = (

            system_instruction

            + "\n\n"

            + conversation

            + "\nUser: "

            + message

            + "\nAssistant:"
        )


        if not GEMINI_API_KEY:

            reply = (
                "❌ Gemini API key is not "
                "configured on the server."
            )


        else:

            payload = {

                "contents": [

                    {

                        "parts": [

                            {

                                "text":
                                prompt

                            }

                        ]

                    }

                ]

            }


            reply = None


            for attempt in range(3):

                try:

                    response = requests.post(

                        GEMINI_URL,

                        headers={

                            "Content-Type":
                            "application/json",

                            "x-goog-api-key":
                            GEMINI_API_KEY

                        },

                        json=payload,

                        timeout=90
                    )


                    if response.status_code == 200:

                        result = response.json()


                        candidates = result.get(
                            "candidates",
                            []
                        )


                        if candidates:

                            parts = (

                                candidates[0]

                                .get(
                                    "content",
                                    {}
                                )

                                .get(
                                    "parts",
                                    []
                                )
                            )


                            if parts:

                                reply = (
                                    parts[0]
                                    .get(
                                        "text",
                                        ""
                                    )
                                    .strip()
                                )


                        if not reply:

                            reply = (
                                "I received an empty "
                                "response from the AI."
                            )

                        break


                    elif response.status_code == 503:

                        print(
                            f"Gemini busy. "
                            f"Attempt {attempt + 1}/3"
                        )


                        if attempt < 2:

                            time.sleep(3)


                        continue


                    else:

                        print(
                            "Gemini error:",
                            response.status_code,
                            response.text
                        )


                        reply = (
                            "❌ Gemini API error. "
                            "Please try again."
                        )

                        break


                except requests.exceptions.Timeout:

                    print(
                        f"Gemini timeout. "
                        f"Attempt {attempt + 1}/3"
                    )


                    if attempt < 2:

                        time.sleep(2)

                    else:

                        reply = (
                            "⏳ The AI took too long "
                            "to respond. Please try again."
                        )


                except Exception as e:

                    print(
                        "Gemini connection error:",
                        e
                    )


                    reply = (
                        "❌ Unable to connect "
                        "to the AI service."
                    )

                    break


        # =================================================
        # SAVE CHAT
        # =================================================

        save_message(
            user_id,
            "user",
            message
        )

        save_message(
            user_id,
            "assistant",
            reply
        )


        # =================================================
        # RESPONSE
        # =================================================

        response = make_response(
            jsonify({
                "reply": reply
            })
        )


        response.set_cookie(
            "chat_user_id",
            user_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure
        )


        return response


    except Exception as e:

        print(
            "Chat route error:",
            e
        )


        return jsonify({

            "reply":
            "❌ Something went wrong "
            "on the server."

        }), 500


# =========================================================
# CHECK DUE REMINDERS
# =========================================================

@app.route(
    "/check-reminders",
    methods=["GET"]
)
def check_reminders():

    try:

        due_reminders = (
            get_due_reminders()
        )


        reminders_to_send = []


        for reminder in due_reminders:

            reminders_to_send.append({

                "id":
                reminder.get("id"),

                "user_id":
                reminder.get("user_id"),

                "text":
                reminder.get(
                    "reminder_text"
                ),

                "date":
                reminder.get(
                    "reminder_date"
                ),

                "time":
                reminder.get(
                    "reminder_time"
                )

            })


        return jsonify({

            "success": True,

            "count":
            len(reminders_to_send),

            "reminders":
            reminders_to_send

        })


    except Exception as e:

        print(
            "Check reminders error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
            str(e)

        }), 500


# =========================================================
# MARK NOTIFICATION SENT
# =========================================================

@app.route(
    "/mark-notification-sent/<int:reminder_id>",
    methods=["POST"]
)
def mark_notification(
    reminder_id
):

    try:

        success = (
            mark_notification_sent(
                reminder_id
            )
        )


        if success:

            return jsonify({

                "success": True,

                "message":
                "Notification marked as sent."

            })


        return jsonify({

            "success": False,

            "message":
            "Could not update reminder."

        }), 500


    except Exception as e:

        print(
            "Mark notification error:",
            e
        )


        return jsonify({

            "success": False,

            "error":
            str(e)

        }), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=False
    )
