import os
import json
import re
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


# ============================================================
# SETTINGS
# ============================================================

TARGET_DATE = "20260812"
CINEMA = "city-centre-almaza"

MOVIES = {
    "The Odyssey": "the-odyssey",
    "Spider-Man: Brand New Day": "spider-man-brand-new-day",
}

VOX_BASE = "https://egy.voxcinemas.com/showtimes"

STATE_FILE = Path("alert_state.json")
SUBSCRIBERS_FILE = Path("subscribers.json")
TELEGRAM_OFFSET_FILE = Path("telegram_offset.txt")


# ============================================================
# TELEGRAM
# ============================================================

def get_bot_token():

    token = os.environ.get("VOX_BOT_TOKEN")

    if not token:
        print("ERROR: VOX_BOT_TOKEN is not set.")
        return None

    return token


def telegram_request(method, params=None):

    token = get_bot_token()

    if not token:
        return None

    url = f"https://api.telegram.org/bot{token}/{method}"

    try:

        response = requests.post(
            url,
            data=params or {},
            timeout=20,
        )

        if response.ok:
            return response.json()

        print(
            f"Telegram API error ({method}):",
            response.text,
        )

        return None

    except Exception as e:

        print(
            f"Telegram connection error ({method}):",
            e,
        )

        return None


def send_telegram(chat_id, message):

    result = telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": message,
        },
    )

    if result and result.get("ok"):

        print(
            f"Telegram notification sent to {chat_id}."
        )

        return True

    return False


# ============================================================
# SUBSCRIBERS
# ============================================================

def load_subscribers():

    if not SUBSCRIBERS_FILE.exists():

        # Your existing Telegram chat ID.
        return ["762509099"]

    try:

        with open(
            SUBSCRIBERS_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            subscribers = json.load(f)

            if not isinstance(subscribers, list):
                return ["762509099"]

            return subscribers

    except Exception:

        return ["762509099"]


def save_subscribers(subscribers):

    # Remove duplicate IDs.
    subscribers = list(
        dict.fromkeys(
            str(x) for x in subscribers
        )
    )

    with open(
        SUBSCRIBERS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            subscribers,
            f,
            indent=2,
        )


# ============================================================
# TELEGRAM /START HANDLER
# ============================================================

def load_telegram_offset():

    if not TELEGRAM_OFFSET_FILE.exists():
        return None

    try:

        with open(
            TELEGRAM_OFFSET_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            return int(
                f.read().strip()
            )

    except Exception:

        return None


def save_telegram_offset(offset):

    with open(
        TELEGRAM_OFFSET_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(str(offset))


def process_telegram_commands():

    print()
    print(
        "Checking Telegram for new /start messages..."
    )

    subscribers = load_subscribers()

    offset = load_telegram_offset()

    params = {
        "timeout": 1,
        "allowed_updates": json.dumps(
            ["message"]
        ),
    }

    if offset is not None:
        params["offset"] = offset

    result = telegram_request(
        "getUpdates",
        params,
    )

    if not result or not result.get("ok"):

        print(
            "Could not retrieve Telegram updates."
        )

        return subscribers, False

    updates = result.get(
        "result",
        [],
    )

    if not updates:

        print(
            "No new Telegram messages."
        )

        return subscribers, False

    changed = False

    for update in updates:

        # Advance the offset so this update
        # won't be processed again.
        update_id = update.get(
            "update_id"
        )

        if update_id is not None:

            save_telegram_offset(
                update_id + 1
            )

        message = update.get("message")

        if not message:
            continue

        text = message.get(
            "text",
            "",
        ).strip().lower()

        chat = message.get("chat")

        if not chat:
            continue

        chat_id = str(
            chat.get("id")
        )

        print(
            f"Received message "
            f"from {chat_id}: {text}"
        )

        # ----------------------------------------------------
        # ONLY COMMAND WE SUPPORT
        # ----------------------------------------------------

        if text == "/start":

            print(
                f"New /start from chat {chat_id}"
            )

            if chat_id not in subscribers:

                subscribers.append(chat_id)

                changed = True

                welcome_message = (
                    "👋 Welcome to VOX Almaza Alert!\n\n"
                    "✅ This bot is now active for you.\n\n"
                    "🎬 The Odyssey\n"
                    "🕷️ Spider-Man: Brand New Day\n\n"
                    "📅 We're monitoring "
                    "Friday, August 14, 2026\n"
                    "📍 City Centre Almaza\n\n"
                    "🔔 You'll receive a notification "
                    "as soon as the date becomes "
                    "available for booking.\n\n"
                    "🍿 Good luck!"
                )

                send_telegram(
                    chat_id,
                    welcome_message,
                )

            else:

                print(
                    f"Chat {chat_id} is already subscribed."
                )

    if changed:

        save_subscribers(
            subscribers
        )

        print(
            f"Subscribers updated: "
            f"{len(subscribers)}"
        )

    return subscribers, changed


# ============================================================
# ALERT STATE
# ============================================================

def load_state():

    if not STATE_FILE.exists():

        return {
            "The Odyssey": False,
            "Spider-Man: Brand New Day": False,
        }

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "The Odyssey": False,
            "Spider-Man: Brand New Day": False,
        }


def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
        )


# ============================================================
# SELENIUM
# ============================================================

def create_driver():

    options = Options()

    # GitHub Actions runs without a visible desktop.
    options.add_argument("--headless=new")

    # Required for GitHub's Linux environment.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Normal desktop browser size.
    options.add_argument(
        "--window-size=1920,1080"
    )

    # Make Chrome look like a normal browser.
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )

    # Don't wait for every image/analytics resource.
    options.page_load_strategy = "eager"

    driver = webdriver.Chrome(
        options=options
    )

    driver.set_page_load_timeout(60)

    return driver


# ============================================================
# VOX CHECK
# ============================================================

def check_movie(movie_name, movie_slug):

    url = (
        f"{VOX_BASE}"
        f"?c={CINEMA}"
        f"&m={movie_slug}"
        f"&d={TARGET_DATE}"
    )

    print()
    print(
        f"Checking {movie_name}..."
    )

    print(
        f"URL: {url}"
    )

    # Each movie gets its own Chrome session.
    driver = None

    try:

        print(
            "Starting fresh Chrome session..."
        )

        driver = create_driver()

        print(
            "Chrome started successfully."
        )

        # Try twice if VOX gives us an ambiguous result.
        for attempt in range(1, 3):

            print(
                f"VOX page attempt {attempt}/2..."
            )

            try:

                driver.get(url)

            except Exception as e:

                print(
                    f"⚠️ Page load error: "
                    f"{type(e).__name__}: {e}"
                )

                if attempt == 2:
                    return None

                print(
                    "Retrying in 5 seconds..."
                )

                time.sleep(5)

                continue

            # Give VOX JavaScript time to render.
            time.sleep(5)

            try:

                body_text = driver.find_element(
                    By.TAG_NAME,
                    "body",
                ).text

            except Exception as e:

                print(
                    f"⚠️ Could not read page body: {e}"
                )

                if attempt == 2:
                    return None

                time.sleep(5)

                continue

            print(
                "Chrome loaded the VOX page."
            )

            print(
                "Page title:",
                driver.title,
            )

            # ------------------------------------------------
            # CONFIRMED UNAVAILABLE
            # ------------------------------------------------

            if (
                "No showtimes could be found"
                in body_text
            ):

                print(
                    f"❌ {movie_name}: "
                    "August 14 is NOT available yet."
                )

                return False

            # ------------------------------------------------
            # LOOK FOR SHOWTIMES
            # ------------------------------------------------

            times = re.findall(
                r"\b\d{1,2}:\d{2}\s*"
                r"(?:am|pm)\b",
                body_text,
                re.IGNORECASE,
            )

            if times:

                print(
                    f"🚨 {movie_name}: "
                    "AUGUST 14 IS AVAILABLE!"
                )

                print(
                    "Showtimes found:",
                    ", ".join(times[:20]),
                )

                return True

            # ------------------------------------------------
            # OTHER AVAILABILITY SIGNALS
            # ------------------------------------------------

            body_lower = body_text.lower()

            movie_present = (
                movie_name.lower()
                in body_lower
            )

            view_times_present = (
                "view times and book"
                in body_lower
            )

            if (
                movie_present
                and view_times_present
            ):

                print(
                    "⚠️ VOX page loaded, "
                    "but no showtimes were found yet."
                )

                if attempt == 2:

                    print(
                        "This is NOT treated "
                        "as unavailable."
                    )

                    return None

            else:

                print(
                    "⚠️ VOX returned an "
                    "ambiguous page."
                )

                print(
                    "This is NOT treated "
                    "as unavailable."
                )

                if attempt == 2:
                    return None

            # ------------------------------------------------
            # RETRY
            # ------------------------------------------------

            print(
                "Waiting 5 seconds before retry..."
            )

            time.sleep(5)

        return None

    except Exception as e:

        print(
            f"⚠️ Selenium/VOX error: "
            f"{type(e).__name__}: {e}"
        )

        print(
            "This is NOT treated "
            "as unavailable."
        )

        return None

    finally:

        if driver:

            print(
                "Closing Chrome..."
            )

            try:
                driver.quit()
            except Exception:
                pass


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)

    print(
        "VOX ALERT - SELENIUM CHECK"
    )

    print("=" * 60)

    print(
        "Target date: August 14, 2026"
    )

    print(
        "Cinema: City Centre Almaza"
    )

    print(
        "Check interval: Every 10 minutes"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # FIRST: CHECK TELEGRAM
    # --------------------------------------------------------

    subscribers, subscribers_changed = (
        process_telegram_commands()
    )

    print(
        f"Current subscribers: "
        f"{len(subscribers)}"
    )

    # --------------------------------------------------------
    # THEN: CHECK VOX
    # --------------------------------------------------------

    state = load_state()

    state_changed = False

    for movie_name, movie_slug in MOVIES.items():

        result = check_movie(
            movie_name,
            movie_slug,
        )

        # ----------------------------------------------------
        # AVAILABLE
        # ----------------------------------------------------

        if result is True:

            if not state.get(
                movie_name,
                False,
            ):

                message = (
                    "🚨 VOX ALERT! 🚨\n\n"
                    f"🎬 {movie_name}\n"
                    "📅 Friday, August 14, 2026\n"
                    "📍 City Centre Almaza\n\n"
                    "The date is NOW AVAILABLE "
                    "for booking!\n\n"
                    "👉 Open VOX and book it now."
                )

                successful_sends = 0

                for chat_id in subscribers:

                    if send_telegram(
                        chat_id,
                        message,
                    ):

                        successful_sends += 1

                print(
                    f"Alert sent to "
                    f"{successful_sends}/"
                    f"{len(subscribers)} subscribers."
                )

                # Mark as alerted only after at least
                # one notification was successfully sent.
                if successful_sends > 0:

                    state[movie_name] = True

                    state_changed = True

            else:

                print(
                    f"Already notified about "
                    f"{movie_name}."
                )

        # ----------------------------------------------------
        # CONFIRMED UNAVAILABLE
        # ----------------------------------------------------

        elif result is False:

            print(
                f"{movie_name}: still waiting "
                "for August 14."
            )

        # ----------------------------------------------------
        # UNKNOWN / FAILED
        # ----------------------------------------------------

        else:

            print(
                f"{movie_name}: unable to "
                "determine status."
            )

    # --------------------------------------------------------
    # SAVE STATE
    # --------------------------------------------------------

    save_state(state)

    print()

    print("=" * 60)

    print(
        "Check complete."
    )

    print("=" * 60)

    if subscribers_changed:

        print(
            "Subscriber list updated."
        )

    if state_changed:

        print(
            "Alert state updated."
        )


if __name__ == "__main__":

    main()
