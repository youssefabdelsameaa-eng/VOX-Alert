import os
import time
import requests
from threading import Thread
from flask import Flask


# ============================================================
# SETTINGS
# ============================================================

TOKEN = os.environ.get("VOX_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("VOX_BOT_TOKEN is not configured.")

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

WELCOME_MESSAGE = """👋 Welcome to VOX Almaza Alert!

✅ This bot is now active for you.

🎬 The Odyssey
🕷️ Spider-Man: Brand New Day

📅 We're monitoring Friday, August 14, 2026
📍 City Centre Almaza

🔔 You'll receive a notification as soon as the date becomes available for booking.

🍿 Good luck!"""


# ============================================================
# SIMPLE WEB SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "VOX Telegram Bot is running."


@app.route("/health")
def health():
    return "OK"


# ============================================================
# TELEGRAM
# ============================================================

def send_message(chat_id, text):

    try:

        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
            },
            timeout=15,
        )

        print(
            "Telegram response:",
            response.status_code,
        )

    except Exception as e:

        print(
            "Telegram send error:",
            e,
        )


def telegram_listener():

    print("Telegram listener started.")

    offset = None

    while True:

        try:

            params = {
                "timeout": 50,
            }

            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params=params,
                timeout=60,
            )

            data = response.json()

            if not data.get("ok"):
                print(
                    "Telegram API error:",
                    data,
                )

                time.sleep(5)
                continue

            for update in data.get("result", []):

                # Move offset forward so we don't process
                # the same Telegram message repeatedly.
                offset = update["update_id"] + 1

                message = update.get("message")

                if not message:
                    continue

                chat = message.get("chat")

                if not chat:
                    continue

                chat_id = chat["id"]

                text = message.get(
                    "text",
                    "",
                ).strip()

                print(
                    f"Received message "
                    f"from {chat_id}: {text}"
                )

                # ------------------------------------------------
                # ONLY COMMAND WE SUPPORT
                # ------------------------------------------------

                if text == "/start":

                    send_message(
                        chat_id,
                        WELCOME_MESSAGE,
                    )

        except Exception as e:

            print(
                "Telegram listener error:",
                e,
            )

            time.sleep(5)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    # Start Telegram listener in background.
    listener = Thread(
        target=telegram_listener,
        daemon=True,
    )

    listener.start()

    # Render expects the web service to listen on a port.
    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
