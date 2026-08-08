import os
import json
import re
from pathlib import Path

import requests


# ============================================================
# SETTINGS
# ============================================================

CHAT_ID = "762509099"

TARGET_DATE = "20260814"
CINEMA = "city-centre-almaza"

MOVIES = {
    "The Odyssey": "the-odyssey",
    "Spider-Man: Brand New Day": "spider-man-brand-new-day",
}

VOX_BASE = "https://egy.voxcinemas.com/showtimes"

STATE_FILE = Path("alert_state.json")


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://egy.voxcinemas.com/",
}

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    token = os.environ.get("VOX_BOT_TOKEN")

    if not token:
        print("ERROR: VOX_BOT_TOKEN is not set.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message,
            },
            timeout=20,
        )

        if response.ok:
            print("Telegram notification sent.")
            return True

        print("Telegram error:", response.text)
        return False

    except Exception as e:
        print("Telegram error:", e)
        return False


# ============================================================
# STATE
# ============================================================

def load_state():

    if not STATE_FILE.exists():
        return {
            "The Odyssey": False,
            "Spider-Man: Brand New Day": False,
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "The Odyssey": False,
            "Spider-Man: Brand New Day": False,
        }


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


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

    print(f"\nChecking {movie_name}...")

    for attempt in range(1, 4):

        try:

            print(f"VOX request attempt {attempt}/3...")

            response = session.get(
                url,
                timeout=30,
            )

            print(f"VOX response: HTTP {response.status_code}")

            if response.status_code != 200:

                print(
                    f"⚠️ VOX returned HTTP {response.status_code}"
                )

                continue

            page = response.text

            # ------------------------------------------------
            # Confirmed NOT available
            # ------------------------------------------------

            if "No showtimes could be found" in page:

                print(
                    f"❌ {movie_name}: August 14 is NOT available yet."
                )

                return False

            # ------------------------------------------------
            # Look for actual showtime-looking values.
            #
            # Examples:
            # 11:15am
            # 3:00pm
            # 10:30pm
            # ------------------------------------------------

            times = re.findall(
                r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b",
                page,
                re.IGNORECASE,
            )

            if times:

                print(
                    f"🚨 {movie_name}: AUGUST 14 IS AVAILABLE!"
                )

                print(
                    "Showtime indicators found:",
                    ", ".join(times[:10])
                )

                return True

            # ------------------------------------------------
            # We got a page, but cannot confidently determine
            # availability.
            # ------------------------------------------------

            print(
                "⚠️ VOX responded, but availability could not "
                "be determined."
            )

            print(
                "This is NOT treated as unavailable."
            )

            return None

        except requests.exceptions.RequestException as e:

            print(
                f"⚠️ VOX request failed: {e}"
            )

    print("❌ Could not reach VOX.")
    print("This is NOT treated as unavailable.")

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("VOX ALERT - GITHUB CHECK")
    print("=" * 60)
    print("Target date: August 14, 2026")
    print("Cinema: City Centre Almaza")
    print("=" * 60)

    state = load_state()

    state_changed = False

    for movie_name, movie_slug in MOVIES.items():

        result = check_movie(
            movie_name,
            movie_slug
        )

        # ----------------------------------------------------
        # Available
        # ----------------------------------------------------

        if result is True:

            # Only notify if we haven't already notified
            # about this movie.

            if not state.get(movie_name, False):

                message = (
                    "🚨 VOX ALERT! 🚨\n\n"
                    f"🎬 {movie_name}\n"
                    "📅 Friday, August 14, 2026\n"
                    "📍 City Centre Almaza\n\n"
                    "The date is NOW AVAILABLE for booking!\n\n"
                    "👉 Open VOX and book it now."
                )

                if send_telegram(message):

                    state[movie_name] = True
                    state_changed = True

            else:

                print(
                    f"Already notified about {movie_name}."
                )

        # ----------------------------------------------------
        # Confirmed unavailable
        # ----------------------------------------------------

        elif result is False:

            print(
                f"{movie_name}: still waiting for August 14."
            )

        # ----------------------------------------------------
        # Unknown / connection problem
        # ----------------------------------------------------

        else:

            print(
                f"{movie_name}: unable to determine status."
            )

    # --------------------------------------------------------
    # Save state
    # --------------------------------------------------------

    save_state(state)

    print()
    print("=" * 60)
    print("Check complete.")
    print("=" * 60)

    if state_changed:
        print("Alert state updated.")

    print("GitHub Actions will run the next check automatically.")


if __name__ == "__main__":
    main()
