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
    options.add_argument("--window-size=1920,1080")

    # Make Chrome look like a normal browser.
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )

    # Don't wait for every image/analytics resource.
    options.page_load_strategy = "eager"

    driver = webdriver.Chrome(options=options)

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
    print(f"Checking {movie_name}...")
    print(f"URL: {url}")

    # --------------------------------------------------------
    # We give each movie its own Chrome session.
    # This helps prevent VOX from behaving differently on
    # the second movie because of the previous page/session.
    # --------------------------------------------------------

    driver = None

    try:

        print("Starting fresh Chrome session...")

        driver = create_driver()

        print("Chrome started successfully.")

        # Try the page twice if VOX gives us an ambiguous result.
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

                print("Retrying in 5 seconds...")
                time.sleep(5)
                continue

            # Give VOX's JavaScript a little time to render.
            time.sleep(5)

            try:

                body_text = driver.find_element(
                    By.TAG_NAME,
                    "body"
                ).text

            except Exception as e:

                print(
                    f"⚠️ Could not read page body: {e}"
                )

                if attempt == 2:
                    return None

                time.sleep(5)
                continue

            print("Chrome loaded the VOX page.")
            print("Page title:", driver.title)

            # ------------------------------------------------
            # CONFIRMED UNAVAILABLE
            # ------------------------------------------------

            if "No showtimes could be found" in body_text:

                print(
                    f"❌ {movie_name}: "
                    "August 14 is NOT available yet."
                )

                return False

            # ------------------------------------------------
            # LOOK FOR SHOWTIMES
            # ------------------------------------------------

            times = re.findall(
                r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b",
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
                    ", ".join(times[:20])
                )

                return True

            # ------------------------------------------------
            # CHECK FOR OTHER STRONG AVAILABILITY SIGNALS
            # ------------------------------------------------

            body_lower = body_text.lower()

            movie_present = (
                movie_name.lower() in body_lower
            )

            view_times_present = (
                "view times and book" in body_lower
            )

            # If the movie is clearly present but no times
            # were found, we still don't assume unavailable.
            if movie_present and view_times_present:

                print(
                    "⚠️ VOX page loaded, but no showtimes "
                    "were found yet."
                )

                if attempt == 2:

                    print(
                        "This is NOT treated as unavailable."
                    )

                    return None

            else:

                print(
                    "⚠️ VOX returned an ambiguous page."
                )

                print(
                    "This is NOT treated as unavailable."
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
            "This is NOT treated as unavailable."
        )

        return None

    finally:

        if driver:

            print("Closing Chrome...")

            try:
                driver.quit()
            except Exception:
                pass


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("VOX ALERT - SELENIUM CHECK")
    print("=" * 60)

    print("Target date: August 14, 2026")
    print("Cinema: City Centre Almaza")
    print("Check interval: Every 10 minutes")

    print("=" * 60)

    state = load_state()

    state_changed = False

    for movie_name, movie_slug in MOVIES.items():

        result = check_movie(
            movie_name,
            movie_slug
        )

        # ----------------------------------------------------
        # AVAILABLE
        # ----------------------------------------------------

        if result is True:

            if not state.get(movie_name, False):

                message = (
                    "🚨 VOX ALERT! 🚨\n\n"
                    f"🎬 {movie_name}\n"
                    "📅 Friday, August 14, 2026\n"
                    "📍 City Centre Almaza\n\n"
                    "The date is NOW AVAILABLE "
                    "for booking!\n\n"
                    "👉 Open VOX and book it now."
                )

                if send_telegram(message):

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
    print("Check complete.")
    print("=" * 60)

    if state_changed:
        print("Alert state updated.")


if __name__ == "__main__":
    main()
