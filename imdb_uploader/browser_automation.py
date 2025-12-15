"""Browser automation functions for IMDb uploader.

This module handles all Selenium WebDriver operations including browser setup,
login flows, rating submission, and IMDb navigation.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from typing import TYPE_CHECKING

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

if TYPE_CHECKING:
    from selenium.webdriver.chrome.webdriver import WebDriver

from .constants import (
    CAPTCHA_WAIT,
    ELEMENT_INTERACTION_WAIT,
    LOGIN_WAIT,
    MANUAL_INTERACTION_WAIT,
    PAGE_LOAD_WAIT,
    SELECTOR_CAPTCHA_INDICATORS,
    SELECTOR_RATE_BUTTON_OPTIONS,
    SELECTOR_SEARCH_RESULTS,
    SELECTOR_STAR_BUTTONS,
    SELECTOR_STAR_RATING_CLASS,
    SELECTOR_STARBAR,
    SELECTOR_SUBMIT_BUTTON_FALLBACK,
    SELECTOR_SUBMIT_RATE_BUTTON,
    SELECTOR_USER_RATING_SCORE,
    SELECTOR_USER_RATING_SECTION,
    SELECTOR_USER_RATING_UNRATED,
)
from .prompts import beep


class BrowserStartError(Exception):
    """Raised when the browser cannot be started."""

    pass


def start_driver(headless: bool = False) -> WebDriver:
    """Start a Chrome WebDriver instance.

    Args:
        headless: If True, run browser in headless mode (no visible window).

    Returns:
        A configured Chrome WebDriver instance.

    Raises:
        RuntimeError: If Chrome cannot be started after trying multiple approaches.

    Notes:
        Tries multiple approaches in order:
        1. webdriver-manager with Chromium
        2. webdriver-manager default
        3. Selenium auto-discovery (4.6+)
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Try multiple approaches to start Chrome
    driver = None

    # Approach 1: Use webdriver-manager with Chrome for Testing (CfT) for Chrome 115+
    try:
        from webdriver_manager.core.os_manager import ChromeType

        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()),
            options=options,
        )
    except Exception:
        pass

    # Approach 2: Try default webdriver-manager
    if driver is None:
        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()), options=options
            )
        except Exception:
            pass

    # Approach 3: Let Selenium find ChromeDriver automatically (Selenium 4.6+)
    if driver is None:
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            raise BrowserStartError(
                f"Could not start Chrome. Error: {e}\n"
                "Try one of:\n"
                "  1. Update webdriver-manager: pip install -U webdriver-manager\n"
                "  2. Update Selenium: pip install -U selenium\n"
                "  3. Install matching ChromeDriver manually"
            ) from e

    driver.set_window_size(1200, 900)
    return driver


def wait_for_login_manual(driver: WebDriver) -> None:
    """Wait for user to manually sign in to IMDb.

    Args:
        driver: The WebDriver instance with IMDb page open.
    """
    beep()
    print(
        "Please sign in on the opened IMDb browser window. When done, press Enter in this terminal to continue..."
    )
    input()


def try_automated_login(
    driver: WebDriver,
    username: str,
    password: str,
    timeout: int = 30,
    debug: bool = False,
    login_wait: float = LOGIN_WAIT,
    page_load_wait: float = PAGE_LOAD_WAIT,
    element_wait: float = ELEMENT_INTERACTION_WAIT,
    captcha_wait: float = CAPTCHA_WAIT,
) -> bool:
    """Try a heuristic automated login flow via IMDb account (not Amazon).
    Returns True if login likely succeeded, False otherwise.

    IMDb sign-in page shows multiple providers: IMDb, Amazon, Google, Apple, Facebook.
    This function specifically targets the "Sign in with IMDb" option.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Go to the IMDb signin page
    driver.get("https://www.imdb.com/registration/signin")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(page_load_wait)

        # Step 0: Check if we're on the "Sign in to existing account" vs "Create new account" page
        # This page appears at /registration/signin/?r=true
        # We need to click "Sign in to an existing account" button
        try:
            existing_account_btn = None
            # Look for the button with text "Sign in to an existing account"
            buttons = driver.find_elements(
                By.CSS_SELECTOR, "button.ipc-btn, button[class*='ipc-btn'], a.ipc-btn"
            )
            for btn in buttons:
                btn_text = btn.text.lower()
                if btn.is_displayed() and "existing account" in btn_text:
                    existing_account_btn = btn
                    break

            # Also try finding by span text
            if not existing_account_btn:
                spans = driver.find_elements(By.XPATH, "//span[contains(@class, 'ipc-btn__text')]")
                for span in spans:
                    if "existing account" in span.text.lower():
                        # Click the parent button
                        existing_account_btn = span.find_element(By.XPATH, "./..")
                        break

            if existing_account_btn and existing_account_btn.is_displayed():
                logger.debug("Found 'Sign in to existing account' button, clicking...")
                existing_account_btn.click()
                time.sleep(element_wait)
        except Exception as e:
            logger.debug(f"No existing account button found or error: {e}")

        # Look for "Sign in with IMDb" button specifically
        # IMDb uses auth-provider buttons with different href patterns
        imdb_signin_clicked = False

        # Method 1: Look for button/link with text "IMDb" (case insensitive)
        provider_buttons = driver.find_elements(
            By.CSS_SELECTOR,
            ".auth-provider-button, a.list-group-item, .auth-provider, a[href*='imdb_us']",
        )
        for btn in provider_buttons:
            try:
                btn_text = btn.text.lower()
                btn_href = (btn.get_attribute("href") or "").lower()
                # Look for IMDb-specific login (not Amazon)
                if btn.is_displayed() and ("imdb" in btn_text or "imdb_us" in btn_href):
                    # Make sure it's not Amazon
                    if "amazon" not in btn_text and "amazon" not in btn_href:
                        logger.debug(f"Found IMDb sign-in button: {btn_text[:50]}")
                        btn.click()
                        imdb_signin_clicked = True
                        time.sleep(element_wait)
                        break
            except Exception:
                continue

        # Method 2: Try finding by partial link text
        if not imdb_signin_clicked:
            try:
                imdb_links = driver.find_elements(By.PARTIAL_LINK_TEXT, "IMDb")
                for link in imdb_links:
                    href = (link.get_attribute("href") or "").lower()
                    if link.is_displayed() and "amazon" not in href:
                        logger.debug("Found IMDb link by text")
                        link.click()
                        imdb_signin_clicked = True
                        time.sleep(element_wait)
                        break
            except Exception:
                pass

        # Method 3: Look for the specific IMDb auth provider link pattern
        if not imdb_signin_clicked:
            try:
                # IMDb account login typically goes through a different URL pattern
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = link.get_attribute("href") or ""
                    text = link.text.lower()
                    if link.is_displayed() and (
                        "imdb_us" in href or ("imdb" in text and "amazon" not in text)
                    ):
                        logger.debug(f"Found IMDb auth link: {href[:80]}")
                        link.click()
                        imdb_signin_clicked = True
                        time.sleep(element_wait)
                        break
            except Exception:
                pass

        if not imdb_signin_clicked:
            logger.debug("Could not find IMDb sign-in button, trying generic form...")

        # Wait for the login form (IMDb or Amazon form)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[name='email'], input#ap_email, input[type='email'], input[name='username']",
                )
            )
        )
        time.sleep(element_wait)

        # Fill in email/username
        email_selectors = [
            "input[name='email']",
            "input#ap_email",
            "input[type='email']",
            "input[name='username']",
            "input#email",
        ]
        email_input = None
        for sel in email_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems and elems[0].is_displayed():
                email_input = elems[0]
                break

        if email_input:
            email_input.clear()
            email_input.send_keys(username)
            logger.debug("Entered username/email")

        # Look for continue button or direct login form
        continue_btn = driver.find_elements(
            By.CSS_SELECTOR,
            "input#continue, input[type='submit'], button[type='submit'], .auth-button",
        )
        if continue_btn:
            for btn in continue_btn:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(element_wait)
                    break

        # Fill in password
        pwd_selectors = [
            "input[name='password']",
            "input#ap_password",
            "input[type='password']",
            "input#password",
        ]
        pwd_input = None
        for sel in pwd_selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems and elems[0].is_displayed():
                pwd_input = elems[0]
                break

        if pwd_input:
            pwd_input.clear()
            pwd_input.send_keys(password)
            logger.debug("Entered password")

            # Submit the form
            pwd_input.send_keys(Keys.RETURN)
            time.sleep(login_wait)

            # Check for CAPTCHA - if detected, ask user to solve it
            captcha_detected = detect_captcha(driver)
            if captcha_detected:
                beep()
                print("\n" + "=" * 60)
                print("🔒 CAPTCHA DETECTED")
                print("=" * 60)
                print("  A CAPTCHA challenge has appeared.")
                print("  Please solve it in the browser window.")
                input("  Press Enter here once you've completed the CAPTCHA...")
                time.sleep(captcha_wait)

            # Check if we're logged in by looking for user menu
            user_menu = driver.find_elements(
                By.CSS_SELECTOR,
                ".imdb-header__account-toggle, .nav__user-menu, [data-testid='nav-link-logged-in'], "
                ".navbar__user, .ipc-button[aria-label*='Account']",
            )
            if user_menu:
                logger.debug("Login appears successful (found user menu)")
                return True

            # Also check if we're on the IMDb homepage (sometimes login redirects there)
            parsed_url = urllib.parse.urlparse(driver.current_url)
            host = parsed_url.hostname
            if (
                host
                and (host == "imdb.com" or host.endswith(".imdb.com"))
                and "signin" not in driver.current_url.lower()
            ):
                # Double check by looking for sign-in link (if present, we're not logged in)
                signin_links = driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='signin'], a[href*='registration']"
                )
                visible_signin = [
                    link
                    for link in signin_links
                    if link.is_displayed() and "sign in" in link.text.lower()
                ]
                if not visible_signin:
                    logger.debug("Login appears successful (no sign-in link visible)")
                    return True

    except Exception as e:
        logger.debug(f"Auto-login exception: {e}")
    return False


def detect_captcha(driver: WebDriver) -> bool:
    """Detect if a CAPTCHA challenge is present on the page.

    Args:
        driver: The WebDriver instance.

    Returns:
        True if CAPTCHA is detected, False otherwise.
    """
    for selector in SELECTOR_CAPTCHA_INDICATORS:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            if elems and any(e.is_displayed() for e in elems):
                return True
        except Exception:
            pass

    # Also check page text for CAPTCHA-related messages
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        captcha_phrases = [
            "enter the characters",
            "solve this puzzle",
            "verify you are human",
            "security check",
            "type the characters",
            "captcha",
            "robot",
        ]
        for phrase in captcha_phrases:
            if phrase in page_text:
                return True
    except Exception:
        pass

    return False


def imdb_search_and_open(
    driver: WebDriver, title: str, year: str | None = None, page_load_wait: float = PAGE_LOAD_WAIT
) -> bool:
    """Search IMDb for a title and open the first result.

    Args:
        driver: The WebDriver instance.
        title: Movie title to search for.
        year: Optional release year to narrow results.

    Returns:
        True if a result was found and opened, False otherwise.
    """
    import urllib.parse

    query = title
    if year:
        query = f"{title} {year}"
    q = urllib.parse.quote_plus(query)
    url = f"https://www.imdb.com/find?q={q}&s=tt&ttype=ft&ref_=fn_ft"
    driver.get(url)
    try:
        # Wait for results
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.findList, .findSection"))
        )
        # Try to click the first result link in titles list
        for sel in SELECTOR_SEARCH_RESULTS:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                elems[0].click()
                time.sleep(page_load_wait)
                return True
    except Exception:
        pass
    return False


def get_existing_rating(driver: WebDriver, debug: bool = False) -> int | None:
    """Check if the movie is already rated by the user on IMDb.

    Args:
        driver: The WebDriver instance on an IMDb movie page.
        debug: If True, print debug messages for troubleshooting.

    Returns:
        The existing rating (1-10) if found, or None if not rated.

    Notes:
        This function is conservative to avoid false positives - it only returns
        a rating when there's high confidence the user has actually rated the movie.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # IMDb 2024+ layout: The user rating section uses data-testid attributes:
        # - "hero-rating-bar__user-rating__unrated" when NOT rated (shows "Rate" button)
        # - "hero-rating-bar__user-rating__score" when rated (shows the rating number)

        # Quick check: if the "unrated" element exists, user hasn't rated this movie
        unrated_elem = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_UNRATED)
        if unrated_elem:
            if debug:
                logger.debug("Found 'unrated' element - not rated")
            return None

        # Look for the rated score element
        rated_elem = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_SCORE)
        if rated_elem:
            text = rated_elem[0].text.strip()
            if debug:
                logger.debug(f"Found 'score' element with text: {text!r}")
            if text.isdigit():
                rating = int(text)
                if 1 <= rating <= 10:
                    return rating

        # Fallback: check the user rating section more broadly
        user_rating_div = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_SECTION)
        if not user_rating_div:
            if debug:
                logger.debug("No user rating section found")
            return None

        user_section = user_rating_div[0]
        section_text = user_section.text.strip()
        if debug:
            logger.debug(f"User rating section text: {section_text!r}")

        # If the section just says "Rate" or "YOUR RATING\nRate", user hasn't rated
        # A rated movie shows "YOUR RATING\n8" or similar
        section_lower = section_text.lower()
        if section_lower in ("rate", "your rating\nrate", "your rating rate"):
            if debug:
                logger.debug("Section shows 'Rate' - not rated")
            return None

        # Method 1: Look for the blue star rating number specifically
        # When rated, there's a span with class containing 'ipc-rating-star--rating'
        # that shows just the number (e.g., "8")
        star_rating_elems = user_section.find_elements(By.XPATH, SELECTOR_STAR_RATING_CLASS)
        for elem in star_rating_elems:
            text = elem.text.strip()
            if debug:
                logger.debug(f"Star rating element text: {text!r}")
            if text and text.isdigit():
                rating = int(text)
                if 1 <= rating <= 10:
                    if debug:
                        logger.debug(f"Found rating via star element: {rating}")
                    return rating

        # Method 2: Check aria-label on the rating button
        buttons = user_section.find_elements(By.XPATH, ".//button")
        for btn in buttons:
            aria = btn.get_attribute("aria-label") or ""
            if debug:
                logger.debug(f"Button aria-label: {aria!r}")
            # Look for "Your rating: 8" or "Rated 8" pattern
            # Avoid matching "Rate this" or "Click to rate"
            aria_lower = aria.lower()
            if (
                "your rating" in aria_lower or "rated" in aria_lower
            ) and "rate this" not in aria_lower:
                match = re.search(r"(?:your rating|rated)[:\s]+(\d+)", aria_lower)
                if match:
                    rating = int(match.group(1))
                    if 1 <= rating <= 10:
                        if debug:
                            logger.debug(f"Found rating via aria-label: {rating}")
                        return rating

        # Method 3: Parse the section text more carefully
        # Look for pattern like "YOUR RATING\n8" where 8 is on its own line
        lines = section_text.split("\n")
        if debug:
            logger.debug(f"Section lines: {lines}")

        for line in lines:
            line = line.strip()
            # Skip common non-rating text
            if line.lower() in ("your rating", "rate", ""):
                continue
            # If we find a standalone number 1-10, that's likely the rating
            if line.isdigit():
                rating = int(line)
                if 1 <= rating <= 10:
                    if debug:
                        logger.debug(f"Found rating via text line: {rating}")
                    return rating

        # If we get here, the section exists but we couldn't find a clear rating
        # This likely means the user hasn't rated it yet
        if debug:
            logger.debug("Could not find clear rating in user section")

    except Exception as e:
        logger.debug(f"get_existing_rating exception: {e}")
    return None


def try_rate_on_page(
    driver: WebDriver,
    score: int,
    element_wait: float = ELEMENT_INTERACTION_WAIT,
    rating_wait: float = MANUAL_INTERACTION_WAIT,
) -> bool:
    """Attempt to click the rating star for a given score.

    Args:
        driver: The WebDriver instance on an IMDb movie page.
        score: Rating to apply (1-10).

    Returns:
        True if rating was successfully clicked, False otherwise.

    Notes:
        This is best-effort; IMDb's widget structure changes frequently.
    """
    import logging

    logger = logging.getLogger(__name__)

    if not score or not (1 <= score <= 10):
        return False

    # Helper to click using JavaScript (more reliable than Selenium click)
    def js_click(element):
        driver.execute_script("arguments[0].click();", element)

    # Step 1: Click the "Rate" button on the movie page to open the rating modal
    modal_opened = False
    try:
        for sel in SELECTOR_RATE_BUTTON_OPTIONS:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                try:
                    if btn.is_displayed():
                        js_click(btn)
                        logger.debug("Opened rating modal")
                        time.sleep(element_wait)
                        modal_opened = True
                        break
                except Exception:
                    continue
            if modal_opened:
                break
    except Exception as e:
        logger.debug(f"Modal open exception: {e}")

    if not modal_opened:
        logger.debug("Could not open rating modal")
        return False

    # Step 2: Click the star button with aria-label="Rate {score}"
    star_clicked = False
    try:
        time.sleep(element_wait)
        # Use CSS selector for the star buttons
        star_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_STAR_BUTTONS)
        if star_buttons and len(star_buttons) >= score:
            # Stars are 0-indexed, so score 7 = index 6
            target_star = star_buttons[score - 1]
            js_click(target_star)
            star_clicked = True
            logger.debug(f"Clicked star {score} (by index)")
            time.sleep(element_wait)
        else:
            # Fallback: try aria-label selector
            star = driver.find_element(By.CSS_SELECTOR, f"button[aria-label='Rate {score}']")
            js_click(star)
            star_clicked = True
            logger.debug(f"Clicked star {score} (by aria-label)")
            time.sleep(element_wait)
    except Exception as e:
        logger.debug(f"Star click exception: {e}")

    if not star_clicked:
        logger.debug("Could not click star")
        return False

    # Step 3: Click the "Rate" submit button to save the rating
    # Wait for the button to become active after star selection
    time.sleep(rating_wait)

    submit_clicked = False
    try:
        # The exact Rate button class from IMDb's modal:
        # <button class="ipc-btn ... ipc-rating-prompt__rate-button">

        # Approach 1: Use the exact class selector (most reliable)
        rate_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_SUBMIT_RATE_BUTTON)
        for btn in rate_buttons:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    logger.debug("Found Rate button with class 'ipc-rating-prompt__rate-button'")
                    js_click(btn)
                    submit_clicked = True
                    logger.debug("Clicked Rate submit button")
                    time.sleep(rating_wait)
                    break
            except Exception:
                continue

        # Approach 2: Find button with text "Rate" that's NOT a star button
        if not submit_clicked:
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in all_buttons:
                try:
                    btn_text = btn.text.strip()
                    aria_label = btn.get_attribute("aria-label") or ""

                    # Skip star rating buttons (they have aria-label like "Rate 7")
                    if aria_label.startswith("Rate ") and aria_label.split()[-1].isdigit():
                        continue

                    # Look for the submit button - it just says "Rate"
                    if btn_text.lower() == "rate" and btn.is_displayed() and btn.is_enabled():
                        js_click(btn)
                        submit_clicked = True
                        logger.debug("Clicked Rate button (text match)")
                        time.sleep(rating_wait)
                        break
                except Exception:
                    continue

        # Approach 3: Try other IMDb button classes
        if not submit_clicked:
            prompt_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_SUBMIT_BUTTON_FALLBACK)
            for btn in prompt_buttons:
                try:
                    if "rate" in btn.text.lower() and btn.is_displayed():
                        js_click(btn)
                        submit_clicked = True
                        logger.debug("Clicked Rate button (prompt selector)")
                        time.sleep(rating_wait)
                        break
                except Exception:
                    continue

        # Approach 4: Click the button that appears after the starbar
        if not submit_clicked:
            try:
                # Find the starbar container and look for sibling/following button
                starbar = driver.find_element(By.CSS_SELECTOR, SELECTOR_STARBAR)
                parent = starbar.find_element(By.XPATH, "..")
                buttons_near = parent.find_elements(By.TAG_NAME, "button")
                for btn in buttons_near:
                    aria = btn.get_attribute("aria-label") or ""
                    if not (aria.startswith("Rate ") and aria.split()[-1].isdigit()):
                        if btn.is_displayed() and btn.is_enabled():
                            js_click(btn)
                            submit_clicked = True
                            logger.debug("Clicked button near starbar")
                            time.sleep(rating_wait)
                            break
            except Exception:
                pass

    except Exception as e:
        logger.debug(f"Submit button exception: {e}")

    if submit_clicked:
        return True

    # Step 4: Try pressing Enter as last resort
    try:
        from selenium.webdriver.common.action_chains import ActionChains

        actions = ActionChains(driver)
        actions.send_keys(Keys.RETURN).perform()
        logger.debug("Pressed Enter to submit")
        time.sleep(rating_wait)
        return True
    except Exception:
        pass

    logger.debug("Could not find/click submit button")
    return False
