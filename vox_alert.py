import os
import json
import re
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


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

    # Run Chrome without opening a visible browser window.
    options.add_argument("--headless=new")

    # Required for GitHub's Linux environment.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Make the browser look like a normal desktop browser.
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )

    # Don't wait unnecessarily for every resource.
    options.page_load_strategy = "eager"

    driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(45)

    return driver


# ============================================================
# VOX CHECK
# ============================================================

def check_movie(driver, movie_name, movie_slug):

    url = (
        f"{VOX_BASE}"
        f"?c={CINEMA}"
        f"&m={movie_slug}"
        f"&d={TARGET_DATE}"
    )

    print()
    print(f"Checking {movie_name}...")
    print(f"URL: {url}")

    try:

        driver.get(url)

        print("Chrome loaded the VOX page.")

        # Give the page a chance to finish loading its content.
        WebDriverWait(driver, 30).until(
            lambda d: d.find_element(By.TAG_NAME, "body")
        )

        body_text = driver.find_element(
            By.TAG_NAME,
            "body"
        ).text

        print("Page title:", driver.title)

        # ----------------------------------------------------
        # Confirmed unavailable
        # ----------------------------------------------------

        if "No showtimes could be found" in body_text:

            print(
                f"❌ {movie_name}: "
                "August 14 is NOT available yet."
            )

            return False

        # ----------------------------------------------------
        # Look for showtime values.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Page loaded but status unclear.
        # ----------------------------------------------------

        print(
            "⚠️ VOX page loaded, but I could not "
            "confidently determine availability."
        )

        print("This is NOT treated as unavailable.")

        return None

    except Exception as e:

        print(
            f"⚠️ Selenium/VOX error: {type(e).__name__}: {e}"
        )

        print(
            "This is NOT treated as unavailable."
        )

        return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("VOX ALERT - SELENIUM CHECK")
    print("=" * 60)

    print("Target date: August 14, 2026")
    print("Cinema: City Centre Almaza")

    print("=" * 60)

    state = load_state()
    state_changed = False

    driver = None

    try:

        print()
        print("Starting Chrome...")

        driver = create_driver()

        print("Chrome started successfully.")

        for movie_name, movie_slug in MOVIES.items():

            result = check_movie(
                driver,
                movie_name,
                movie_slug
            )

            # ------------------------------------------------
            # Available
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Confirmed unavailable
            # ------------------------------------------------

            elif result is False:

                print(
                    f"{movie_name}: still waiting "
                    "for August 14."
                )

            # ------------------------------------------------
            # Unknown / failed
            # ------------------------------------------------

            else:

                print(
                    f"{movie_name}: unable to "
                    "determine status."
                )

    finally:

        if driver:

            print()
            print("Closing Chrome...")

            driver.quit()

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


if __name__ == "__main__":
    main()
