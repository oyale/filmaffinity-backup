#!/usr/bin/env python3
"""
Upload ratings from a FilmAffinity CSV to IMDb.

Notes / usage:
- The CSV at `data/632051/watched.csv` uses `;` as delimiter and contains a `user score` column (1-10).
- IMDb supports multiple login methods (IMDb account, Amazon, Google, etc.). This script supports:
  - Manual login: start the script without `IMDB_USERNAME`/`IMDB_PASSWORD` env vars and it will open a browser and wait for you to sign in.
  - (Experimental) Automated login: set `IMDB_USERNAME` and `IMDB_PASSWORD` environment variables and pass `--auto-login` to attempt automatic sign-in with an IMDb account. This may fail depending on IMDb's current UI and multi-factor flows.
- Automatic rating via Selenium is best-effort: IMDb's DOM changes frequently. If automatic rating fails the script opens the movie page and waits for you to rate manually (press Enter to continue).

Requirements:
- `pip install -r requirements.txt` (script updates recommend `selenium` and `webdriver-manager`).

Usage examples:
  python3 scripts/upload_imdb.py --csv data/632051/watched.csv
  python3 scripts/upload_imdb.py --csv data/632051/watched.csv --headless  # headless browser (not recommended for manual login)
  IMDB_USERNAME=you IMDB_PASSWORD=pass python3 scripts/upload_imdb.py --csv data/632051/watched.csv --auto-login --auto-rate

Be careful: automated interactions with web services can violate terms of service. Use responsibly.
"""

from __future__ import annotations

import os
import sys
import re
import time
import json
import argparse
import csv
import urllib.parse
import difflib
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

if TYPE_CHECKING:
    from selenium.webdriver.chrome.webdriver import WebDriver

try:
    # Cinemagoer is the modern fork/rename of IMDbPY
    from imdb import Cinemagoer as IMDbPYClient
except ImportError:
    try:
        from imdb import IMDb as IMDbPYClient
    except ImportError:
        IMDbPYClient = None

# Import from modular structure
from .constants import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIDENCE_THRESHOLD,
    SKIP_AMBIGUOUS,
    SKIP_NOT_FOUND,
    SKIP_ALREADY_RATED,
    SKIP_SAME_RATING,
    SKIP_AUTO_RATE_FAILED,
    SKIP_USER_CHOICE,
    SKIP_REASON_TO_FILE,
    SELECTOR_CAPTCHA_INDICATORS,
    SELECTOR_SEARCH_RESULTS,
    SELECTOR_USER_RATING_UNRATED,
    SELECTOR_USER_RATING_SCORE,
    SELECTOR_USER_RATING_SECTION,
    SELECTOR_STAR_RATING_CLASS,
    SELECTOR_RATE_BUTTON_OPTIONS,
    SELECTOR_STAR_BUTTONS,
    SELECTOR_SUBMIT_RATE_BUTTON,
    SELECTOR_SUBMIT_BUTTON_FALLBACK,
    SELECTOR_STARBAR,
    SELECTOR_EMAIL_INPUT_OPTIONS,
    SELECTOR_PASSWORD_INPUT_OPTIONS,
    SELECTOR_CONTINUE_BUTTON,
    SELECTOR_USER_MENU,
    RATE_LIMIT_COOLDOWN_INITIAL,
    RATE_LIMIT_COOLDOWN_MAX,
    MAX_RETRIES,
    DIRECTOR_LOOKUP_THRESHOLD,
    DIRECTOR_FETCH_LIMIT,
    DIRECTOR_FETCH_CANDIDATE_MIN_SCORE,
    MovieItem,
    SkippedEntry,
    IMDbMatch,
    Stats,
)
from .config import (
    DEFAULT_CONFIG_PATHS,
    load_config,
    save_config,
    create_default_config,
    SessionState,
    retry_on_http_error,
    file_lock,
)
from .prompts import (
    beep,
    set_beep_enabled,
    parse_imdb_id,
    prompt_existing_rating,
    prompt_confirm_match,
    prompt_low_confidence_match,
    prompt_select_candidate,
)


# =============================================================================
# Custom Exceptions
# =============================================================================

class UploadIMDbError(Exception):
    """Base exception for upload_imdb errors."""
    pass


class BrowserStartError(UploadIMDbError):
    """Raised when the browser cannot be started."""
    pass


class LoginError(UploadIMDbError):
    """Raised when login fails."""
    pass


class RatingError(UploadIMDbError):
    """Raised when rating a movie fails."""
    pass


class CSVParseError(UploadIMDbError):
    """Raised when CSV parsing fails."""
    pass


class IMDbSearchError(UploadIMDbError):
    """Raised when IMDb search fails."""
    pass


# =============================================================================
# CSV and File Functions
# =============================================================================

# Import CSV constants from constants.py
from .constants import CSV_FIELDNAMES, CSV_FIELDNAMES_WITH_REASON, RETRY_CATEGORY_TO_FILE


def read_csv(path: str) -> list[MovieItem]:
    """Read a FilmAffinity CSV file and return a list of movie items.

    Args:
        path: Path to the CSV file (semicolon-delimited).

    Returns:
        List of movie item dictionaries with keys: title, year, score, directors, original_title.

    Notes:
        - Supports multiple column name variants (e.g., 'titulo' for Spanish exports).
        - Handles BOM character in headers.
        - Skips rows with empty titles.
    """
    items = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=';')
        for raw_row in reader:
            # normalize keys: strip, lower-case and remove BOM if present
            row = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                key = k.strip().lower().lstrip('\ufeff')
                row[key] = v
            # Expect column 'title', 'year', 'user score'
            title = (row.get('title') or row.get('titulo') or '').strip()
            year = (row.get('year') or row.get('anio') or row.get('año') or '').strip()
            score = row.get('user score') or row.get('user_score') or row.get('userscore') or row.get('puntuacion')
            if not title:
                continue
            try:
                scorev = int(float(str(score).replace(',', '.')))
            except (ValueError, TypeError, AttributeError):
                scorev = None
            directors = (row.get('directors') or row.get('director') or '')
            original_title = (row.get('original title') or row.get('original_title') or row.get('originaltitle') or '').strip()
            items.append({'title': title, 'year': year, 'score': scorev, 'directors': (directors or '').strip(), 'original_title': original_title})
    if not items:
        print(f"read_csv: no items parsed from {path}. Detected header fields: {reader.fieldnames}")
    return items


def normalize_text(s: str) -> str:
    """Normalize text for fuzzy matching.

    Args:
        s: Input string to normalize.

    Returns:
        Normalized string: lowercase, no accents, no punctuation,
        Spanish leading articles removed, whitespace collapsed.

    Examples:
        >>> normalize_text('El Señor de los Anillos')
        'senor de los anillos'
        >>> normalize_text('Amélie')
        'amelie'
    """
    if not s:
        return ''
    s = s.strip().lower()
    # remove accents
    s = unicodedata.normalize('NFD', s)
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    # remove punctuation
    s = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in s)
    # remove common Spanish leading articles to help matching
    for prefix in ('el ', 'la ', "los ", "las ", "un ", "una "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = ' '.join(s.split())
    return s


# `parse_imdb_id` implementation now lives in `imdb_uploader.prompts`
# and is imported at module level so callers should use that.


def find_imdb_match(
    title: str,
    year: Optional[str] = None,
    ia: Any = None,
    director: Optional[str] = None,
    original_title: Optional[str] = None,
    topn: int = 6
) -> Optional[IMDbMatch]:
    """Use IMDbPY (if available) to search `title` and return the best candidate.
    This version minimizes network calls: it computes title+year confidence first and
    only fetches candidate details (via `ia.update`) to read directors when the
    confidence is below a configured threshold.

    If original_title is provided (e.g., English title), it will be searched first
    as it often provides better matches on IMDb.

    Returns dict with keys: movieID, title, year, score (0..1), candidates (list) or None if no results.
    The 'candidates' list contains top matches for user selection in ambiguous cases.
    """
    if ia is None:
        return None

    # Try multiple query variants to handle localized titles and parentheticals
    queries = []

    # Prioritize original title (usually English/international) as it matches better on IMDb
    if original_title:
        queries.append(original_title)
        if year:
            queries.append(f"{original_title} {year}")

    raw = title or ''
    queries.append(raw)
    # remove parenthetical parts: e.g. 'Pride (Orgullo)' -> 'Pride'
    if '(' in raw:
        queries.append(raw.split('(')[0].strip())
    # normalized (no accents)
    norm = normalize_text(raw)
    if norm and norm != raw:
        queries.append(norm)
    # add year to queries to prioritize correct release
    if year:
        if raw:
            queries.append(f"{raw} {year}")
        if norm:
            queries.append(f"{norm} {year}")

    seen = set()
    best = None
    all_candidates = []  # Store all candidates for user selection
    cooldown_seconds = RATE_LIMIT_COOLDOWN_INITIAL

    for q in queries:
        if not q:
            continue
        if q in seen:
            continue
        seen.add(q)

        # Retry loop for handling HTTP errors with cooldown
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[imdbpy] searching for: {q!r}")
                results = ia.search_movie(q) or []
                print(f"[imdbpy] -> {len(results)} results for query: {q!r}")
                if results:
                    sample = []
                    for r in results[:5]:
                        try:
                            sample.append(f"{r.get('title')} ({r.get('year')})")
                        except Exception:
                            sample.append(str(r))
                    print(f"[imdbpy] sample results: {sample}")
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                # Check for HTTP errors (500, 503, etc.) or rate limiting
                is_http_error = (
                    'http error 5' in error_str or
                    '500' in error_str or
                    '503' in error_str or
                    'internal server error' in error_str or
                    'service unavailable' in error_str or
                    'too many requests' in error_str or
                    '429' in error_str or
                    'httperror' in error_str
                )

                if is_http_error and attempt < MAX_RETRIES - 1:
                    print(f"[imdbpy] ⚠️  HTTP error detected, cooling down for {cooldown_seconds}s before retry ({attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(cooldown_seconds)
                    # Exponential backoff
                    cooldown_seconds = min(cooldown_seconds * 2, RATE_LIMIT_COOLDOWN_MAX)
                else:
                    print(f"[imdbpy] search exception for query {q!r}: {e}")
                results = []

        if not results:
            continue

        qnorm = normalize_text(q)

        # First pass: compute base score using title (and year boost) only
        candidates = []  # list of dicts: {cand, cand_title, cand_year, base_score, has_director_info}
        for cand in results[:max(topn, 10)]:
            try:
                cand_title = cand.get('title') or ''
                cand_year = str(cand.get('year') or '')
            except Exception:
                cand_title = ''
                cand_year = ''
            cnorm = normalize_text(cand_title)
            base_score = difflib.SequenceMatcher(None, qnorm, cnorm).ratio()
            # boost if year matches
            if year and cand_year and year == cand_year:
                base_score += 0.8
            # penalize if year does not match for 2 years
            elif year and cand_year:
                try:
                    ydiff = abs(int(year) - int(cand_year))
                    if ydiff >= 2:
                        base_score -= 0.6
                except Exception:
                    pass

            # detect if search result already includes director info (avoid update)
            has_director_info = False
            cand_directors_list = []
            try:
                d = cand.get('director') or cand.get('directors') or None
                if d:
                    has_director_info = True
                    if isinstance(d, list):
                        for person in d:
                            cand_directors_list.append(person.get('name') if hasattr(person, 'get') else str(person))
                    else:
                        cand_directors_list.append(d.get('name') if hasattr(d, 'get') else str(d))
            except Exception:
                has_director_info = False

            candidate_entry = {
                'cand': cand,
                'title': cand_title,
                'year': cand_year,
                'base_score': base_score,
                'has_dir': has_director_info,
                'directors': ', '.join(cand_directors_list) if cand_directors_list else '',
                'movieID': cand.movieID if hasattr(cand, 'movieID') else None
            }
            candidates.append(candidate_entry)

            # Also add to all_candidates for user selection (avoid duplicates by movieID)
            if candidate_entry['movieID'] and not any(c['movieID'] == candidate_entry['movieID'] for c in all_candidates):
                all_candidates.append(candidate_entry)

            # keep a quick best based on base_score
            if best is None or base_score > best['score']:
                best = {'movieID': cand.movieID if hasattr(cand, 'movieID') else None,
                        'title': cand_title,
                        'year': cand_year,
                        'score': base_score,
                        'query': q,
                        'result_count': len(results)}

        # If title+year alone is confident enough, skip director lookups
        if best and best['score'] >= DIRECTOR_LOOKUP_THRESHOLD:
            print(f"[imdbpy] high confidence ({best['score']:.3f}) from title+year; skipping director fetchs")
            best['candidates'] = sorted(all_candidates, key=lambda x: x['base_score'], reverse=True)[:10]
            return best

        # If director is provided, try to improve score by fetching directors for top candidates
        if director:
            dnorm = normalize_text(director)
            # sort candidates by base_score desc and fetch limited number
            candidates_sorted = sorted(candidates, key=lambda x: x['base_score'], reverse=True)
            fetch_count = 0
            for entry in candidates_sorted:
                if fetch_count >= DIRECTOR_FETCH_LIMIT:
                    break
                if entry['base_score'] < DIRECTOR_FETCH_CANDIDATE_MIN_SCORE:
                    break
                cand = entry['cand']
                cand_directors = []

                # if search result already included directors, use them first
                try:
                    d = cand.get('director') or cand.get('directors') or None
                    if d:
                        if isinstance(d, list):
                            for person in d:
                                cand_directors.append(person.get('name') if hasattr(person, 'get') else str(person))
                        else:
                            cand_directors.append(d.get('name') if hasattr(d, 'get') else str(d))
                    else:
                        # otherwise fetch details (network call) with retry on HTTP errors
                        for update_attempt in range(2):
                            try:
                                print(f"[imdbpy] fetching details for candidate {getattr(cand, 'movieID', '<unknown>')} to read directors")
                                ia.update(cand)
                                fetch_count += 1
                                d2 = cand.get('director') or cand.get('directors')
                                if d2:
                                    if isinstance(d2, list):
                                        for p in d2:
                                            cand_directors.append(p.get('name') if hasattr(p, 'get') else str(p))
                                    else:
                                        cand_directors.append(d2.get('name') if hasattr(d2, 'get') else str(d2))
                                break  # Success
                            except Exception as update_err:
                                error_str = str(update_err).lower()
                                is_http_error = (
                                    'http error 5' in error_str or '500' in error_str or
                                    '503' in error_str or 'httperror' in error_str
                                )
                                if is_http_error and update_attempt == 0:
                                    print(f"[imdbpy] ⚠️  HTTP error on update, cooling down 5s...")
                                    time.sleep(5)
                                else:
                                    break  # Give up after retry
                except Exception:
                    pass

                # compute director boost
                director_boost = 0.0
                for cd in cand_directors:
                    if not cd:
                        continue
                    cdnorm = normalize_text(cd)
                    if dnorm and cdnorm:
                        if cdnorm.split()[-1] == dnorm.split()[-1]:
                            director_boost = max(director_boost, 0.35)
                        else:
                            sim = difflib.SequenceMatcher(None, dnorm, cdnorm).ratio()
                            if sim > 0.8:
                                director_boost = max(director_boost, 0.3)
                            elif sim > 0.6:
                                director_boost = max(director_boost, 0.15)

                total_score = entry['base_score'] + director_boost
                # Update entry with director info if we fetched it
                if cand_directors and not entry['directors']:
                    entry['directors'] = ', '.join(cand_directors)

                if total_score > best['score']:
                    best = {'movieID': cand.movieID if hasattr(cand, 'movieID') else None,
                            'title': entry['title'],
                            'year': entry['year'],
                            'score': total_score,
                            'query': q,
                            'result_count': len(results)}

        # If we already have a pretty good match, stop early
        if best and best['score'] >= DIRECTOR_LOOKUP_THRESHOLD:
            break

    # Add candidates to best result for user selection in ambiguous cases
    if best:
        best['candidates'] = sorted(all_candidates, key=lambda x: x['base_score'], reverse=True)[:10]
    return best


# Note: HTTP-based scraping fallback was removed per user request.


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
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Try multiple approaches to start Chrome
    driver = None

    # Approach 1: Use webdriver-manager with Chrome for Testing (CfT) for Chrome 115+
    try:
        from webdriver_manager.core.os_manager import ChromeType
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()),
            options=options
        )
    except Exception:
        pass

    # Approach 2: Try default webdriver-manager
    if driver is None:
        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
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
    print('Please sign in on the opened IMDb browser window. When done, press Enter in this terminal to continue...')
    input()


def try_automated_login(driver: WebDriver, username: str, password: str, timeout: int = 30) -> bool:
    """Try a heuristic automated login flow via IMDb account (not Amazon).
    Returns True if login likely succeeded, False otherwise.

    IMDb sign-in page shows multiple providers: IMDb, Amazon, Google, Apple, Facebook.
    This function specifically targets the "Sign in with IMDb" option.
    """
    # Go to the IMDb signin page
    driver.get('https://www.imdb.com/registration/signin')
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(2)

        # Step 0: Check if we're on the "Sign in to existing account" vs "Create new account" page
        # This page appears at /registration/signin/?r=true
        # We need to click "Sign in to an existing account" button
        try:
            existing_account_btn = None
            # Look for the button with text "Sign in to an existing account"
            buttons = driver.find_elements(By.CSS_SELECTOR, "button.ipc-btn, button[class*='ipc-btn'], a.ipc-btn")
            for btn in buttons:
                btn_text = btn.text.lower()
                if btn.is_displayed() and 'existing account' in btn_text:
                    existing_account_btn = btn
                    break

            # Also try finding by span text
            if not existing_account_btn:
                spans = driver.find_elements(By.XPATH, "//span[contains(@class, 'ipc-btn__text')]")
                for span in spans:
                    if 'existing account' in span.text.lower():
                        # Click the parent button
                        existing_account_btn = span.find_element(By.XPATH, "./..")
                        break

            if existing_account_btn and existing_account_btn.is_displayed():
                print("  [debug] Found 'Sign in to existing account' button, clicking...")
                existing_account_btn.click()
                time.sleep(2)
        except Exception as e:
            print(f"  [debug] No existing account button found or error: {e}")

        # Look for "Sign in with IMDb" button specifically
        # IMDb uses auth-provider buttons with different href patterns
        imdb_signin_clicked = False

        # Method 1: Look for button/link with text "IMDb" (case insensitive)
        provider_buttons = driver.find_elements(By.CSS_SELECTOR,
            ".auth-provider-button, a.list-group-item, .auth-provider, a[href*='imdb_us']")
        for btn in provider_buttons:
            try:
                btn_text = btn.text.lower()
                btn_href = (btn.get_attribute('href') or '').lower()
                # Look for IMDb-specific login (not Amazon)
                if btn.is_displayed() and ('imdb' in btn_text or 'imdb_us' in btn_href):
                    # Make sure it's not Amazon
                    if 'amazon' not in btn_text and 'amazon' not in btn_href:
                        print(f"  [debug] Found IMDb sign-in button: {btn_text[:50]}")
                        btn.click()
                        imdb_signin_clicked = True
                        time.sleep(2)
                        break
            except Exception:
                continue

        # Method 2: Try finding by partial link text
        if not imdb_signin_clicked:
            try:
                imdb_links = driver.find_elements(By.PARTIAL_LINK_TEXT, "IMDb")
                for link in imdb_links:
                    href = (link.get_attribute('href') or '').lower()
                    if link.is_displayed() and 'amazon' not in href:
                        print(f"  [debug] Found IMDb link by text")
                        link.click()
                        imdb_signin_clicked = True
                        time.sleep(2)
                        break
            except Exception:
                pass

        # Method 3: Look for the specific IMDb auth provider link pattern
        if not imdb_signin_clicked:
            try:
                # IMDb account login typically goes through a different URL pattern
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = link.get_attribute('href') or ''
                    text = link.text.lower()
                    if link.is_displayed() and ('imdb_us' in href or ('imdb' in text and 'amazon' not in text)):
                        print(f"  [debug] Found IMDb auth link: {href[:80]}")
                        link.click()
                        imdb_signin_clicked = True
                        time.sleep(2)
                        break
            except Exception:
                pass

        if not imdb_signin_clicked:
            print("  [debug] Could not find IMDb sign-in button, trying generic form...")

        # Wait for the login form (IMDb or Amazon form)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                "input[name='email'], input#ap_email, input[type='email'], input[name='username']"))
        )
        time.sleep(1)

        # Fill in email/username
        email_selectors = [
            "input[name='email']",
            "input#ap_email",
            "input[type='email']",
            "input[name='username']",
            "input#email"
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
            print(f"  [debug] Entered username/email")

        # Look for continue button or direct login form
        continue_btn = driver.find_elements(By.CSS_SELECTOR,
            "input#continue, input[type='submit'], button[type='submit'], .auth-button")
        if continue_btn:
            for btn in continue_btn:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    break

        # Fill in password
        pwd_selectors = [
            "input[name='password']",
            "input#ap_password",
            "input[type='password']",
            "input#password"
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
            print(f"  [debug] Entered password")

            # Submit the form
            pwd_input.send_keys(Keys.RETURN)
            time.sleep(5)

            # Check for CAPTCHA - if detected, ask user to solve it
            captcha_detected = detect_captcha(driver)
            if captcha_detected:
                beep()
                print("\n" + "="*60)
                print("🔒 CAPTCHA DETECTED")
                print("="*60)
                print("  A CAPTCHA challenge has appeared.")
                print("  Please solve it in the browser window.")
                input("  Press Enter here once you've completed the CAPTCHA...")
                time.sleep(2)

            # Check if we're logged in by looking for user menu
            user_menu = driver.find_elements(By.CSS_SELECTOR,
                ".imdb-header__account-toggle, .nav__user-menu, [data-testid='nav-link-logged-in'], "
                ".navbar__user, .ipc-button[aria-label*='Account']")
            if user_menu:
                print("  [debug] Login appears successful (found user menu)")
                return True

            # Also check if we're on the IMDb homepage (sometimes login redirects there)
            if 'imdb.com' in driver.current_url and 'signin' not in driver.current_url.lower():
                # Double check by looking for sign-in link (if present, we're not logged in)
                signin_links = driver.find_elements(By.CSS_SELECTOR,
                    "a[href*='signin'], a[href*='registration']")
                visible_signin = [l for l in signin_links if l.is_displayed() and 'sign in' in l.text.lower()]
                if not visible_signin:
                    print("  [debug] Login appears successful (no sign-in link visible)")
                    return True

    except Exception as e:
        print(f"  [debug] Auto-login exception: {e}")
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
        page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        captcha_phrases = [
            'enter the characters',
            'solve this puzzle',
            'verify you are human',
            'security check',
            'type the characters',
            'captcha',
            'robot'
        ]
        for phrase in captcha_phrases:
            if phrase in page_text:
                return True
    except Exception:
        pass

    return False


def imdb_search_and_open(driver: WebDriver, title: str, year: Optional[str] = None) -> bool:
    """Search IMDb for a title and open the first result.

    Args:
        driver: The WebDriver instance.
        title: Movie title to search for.
        year: Optional release year to narrow results.

    Returns:
        True if a result was found and opened, False otherwise.
    """
    query = title
    if year:
        query = f"{title} {year}"
    q = urllib.parse.quote_plus(query)
    url = f'https://www.imdb.com/find?q={q}&s=tt&ttype=ft&ref_=fn_ft'
    driver.get(url)
    try:
        # Wait for results
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table.findList, .findSection')))
        # Try to click the first result link in titles list
        for sel in SELECTOR_SEARCH_RESULTS:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                elems[0].click()
                time.sleep(1)
                return True
    except Exception:
        pass
    return False


def get_existing_rating(driver: WebDriver, debug: bool = False) -> Optional[int]:
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
    import re
    try:
        # IMDb 2024+ layout: The user rating section uses data-testid attributes:
        # - "hero-rating-bar__user-rating__unrated" when NOT rated (shows "Rate" button)
        # - "hero-rating-bar__user-rating__score" when rated (shows the rating number)

        # Quick check: if the "unrated" element exists, user hasn't rated this movie
        unrated_elem = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_UNRATED)
        if unrated_elem:
            if debug:
                print("  [debug] Found 'unrated' element - not rated")
            return None

        # Look for the rated score element
        rated_elem = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_SCORE)
        if rated_elem:
            text = rated_elem[0].text.strip()
            if debug:
                print(f"  [debug] Found 'score' element with text: {text!r}")
            if text.isdigit():
                rating = int(text)
                if 1 <= rating <= 10:
                    return rating

        # Fallback: check the user rating section more broadly
        user_rating_div = driver.find_elements(By.XPATH, SELECTOR_USER_RATING_SECTION)
        if not user_rating_div:
            if debug:
                print("  [debug] No user rating section found")
            return None

        user_section = user_rating_div[0]
        section_text = user_section.text.strip()
        if debug:
            print(f"  [debug] User rating section text: {section_text!r}")

        # If the section just says "Rate" or "YOUR RATING\nRate", user hasn't rated
        # A rated movie shows "YOUR RATING\n8" or similar
        section_lower = section_text.lower()
        if section_lower in ('rate', 'your rating\nrate', 'your rating rate'):
            if debug:
                print("  [debug] Section shows 'Rate' - not rated")
            return None

        # Method 1: Look for the blue star rating number specifically
        # When rated, there's a span with class containing 'ipc-rating-star--rating'
        # that shows just the number (e.g., "8")
        star_rating_elems = user_section.find_elements(
            By.XPATH, SELECTOR_STAR_RATING_CLASS
        )
        for elem in star_rating_elems:
            text = elem.text.strip()
            if debug:
                print(f"  [debug] Star rating element text: {text!r}")
            if text and text.isdigit():
                rating = int(text)
                if 1 <= rating <= 10:
                    if debug:
                        print(f"  [debug] Found rating via star element: {rating}")
                    return rating

        # Method 2: Check aria-label on the rating button
        buttons = user_section.find_elements(By.XPATH, ".//button")
        for btn in buttons:
            aria = btn.get_attribute('aria-label') or ''
            if debug:
                print(f"  [debug] Button aria-label: {aria!r}")
            # Look for "Your rating: 8" or "Rated 8" pattern
            # Avoid matching "Rate this" or "Click to rate"
            aria_lower = aria.lower()
            if ('your rating' in aria_lower or 'rated' in aria_lower) and 'rate this' not in aria_lower:
                match = re.search(r'(?:your rating|rated)[:\s]+(\d+)', aria_lower)
                if match:
                    rating = int(match.group(1))
                    if 1 <= rating <= 10:
                        if debug:
                            print(f"  [debug] Found rating via aria-label: {rating}")
                        return rating

        # Method 3: Parse the section text more carefully
        # Look for pattern like "YOUR RATING\n8" where 8 is on its own line
        lines = section_text.split('\n')
        if debug:
            print(f"  [debug] Section lines: {lines}")

        for line in lines:
            line = line.strip()
            # Skip common non-rating text
            if line.lower() in ('your rating', 'rate', ''):
                continue
            # If we find a standalone number 1-10, that's likely the rating
            if line.isdigit():
                rating = int(line)
                if 1 <= rating <= 10:
                    if debug:
                        print(f"  [debug] Found rating via text line: {rating}")
                    return rating

        # If we get here, the section exists but we couldn't find a clear rating
        # This likely means the user hasn't rated it yet
        if debug:
            print("  [debug] Could not find clear rating in user section")

    except Exception as e:
        print(f"  [debug] get_existing_rating exception: {e}")
    return None


# prompt_existing_rating, prompt_confirm_match, prompt_low_confidence_match,
# prompt_select_candidate are now imported from .prompts module


def try_rate_on_page(driver: WebDriver, score: int) -> bool:
    """Attempt to click the rating star for a given score.

    Args:
        driver: The WebDriver instance on an IMDb movie page.
        score: Rating to apply (1-10).

    Returns:
        True if rating was successfully clicked, False otherwise.

    Notes:
        This is best-effort; IMDb's widget structure changes frequently.
    """
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
                        print(f"  [debug] Opened rating modal")
                        time.sleep(1.5)
                        modal_opened = True
                        break
                except Exception:
                    continue
            if modal_opened:
                break
    except Exception as e:
        print(f"  [debug] Modal open exception: {e}")

    if not modal_opened:
        print("  [debug] Could not open rating modal")
        return False

    # Step 2: Click the star button with aria-label="Rate {score}"
    star_clicked = False
    try:
        time.sleep(0.5)
        # Use CSS selector for the star buttons
        star_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_STAR_BUTTONS)
        if star_buttons and len(star_buttons) >= score:
            # Stars are 0-indexed, so score 7 = index 6
            target_star = star_buttons[score - 1]
            js_click(target_star)
            star_clicked = True
            print(f"  [debug] Clicked star {score} (by index)")
            time.sleep(0.5)
        else:
            # Fallback: try aria-label selector
            star = driver.find_element(By.CSS_SELECTOR, f"button[aria-label='Rate {score}']")
            js_click(star)
            star_clicked = True
            print(f"  [debug] Clicked star {score} (by aria-label)")
            time.sleep(0.5)
    except Exception as e:
        print(f"  [debug] Star click exception: {e}")

    if not star_clicked:
        print("  [debug] Could not click star")
        return False

    # Step 3: Click the "Rate" submit button to save the rating
    # Wait for the button to become active after star selection
    time.sleep(0.8)

    submit_clicked = False
    try:
        # The exact Rate button class from IMDb's modal:
        # <button class="ipc-btn ... ipc-rating-prompt__rate-button">

        # Approach 1: Use the exact class selector (most reliable)
        rate_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_SUBMIT_RATE_BUTTON)
        for btn in rate_buttons:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    print(f"  [debug] Found Rate button with class 'ipc-rating-prompt__rate-button'")
                    js_click(btn)
                    submit_clicked = True
                    print(f"  [debug] Clicked Rate submit button")
                    time.sleep(1)
                    break
            except Exception:
                continue

        # Approach 2: Find button with text "Rate" that's NOT a star button
        if not submit_clicked:
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in all_buttons:
                try:
                    btn_text = btn.text.strip()
                    aria_label = btn.get_attribute('aria-label') or ''

                    # Skip star rating buttons (they have aria-label like "Rate 7")
                    if aria_label.startswith('Rate ') and aria_label.split()[-1].isdigit():
                        continue

                    # Look for the submit button - it just says "Rate"
                    if btn_text.lower() == 'rate' and btn.is_displayed() and btn.is_enabled():
                        js_click(btn)
                        submit_clicked = True
                        print(f"  [debug] Clicked Rate button (text match)")
                        time.sleep(1)
                        break
                except Exception:
                    continue

        # Approach 3: Try other IMDb button classes
        if not submit_clicked:
            prompt_buttons = driver.find_elements(By.CSS_SELECTOR, SELECTOR_SUBMIT_BUTTON_FALLBACK)
            for btn in prompt_buttons:
                try:
                    if 'rate' in btn.text.lower() and btn.is_displayed():
                        js_click(btn)
                        submit_clicked = True
                        print(f"  [debug] Clicked Rate button (prompt selector)")
                        time.sleep(1)
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
                    aria = btn.get_attribute('aria-label') or ''
                    if not (aria.startswith('Rate ') and aria.split()[-1].isdigit()):
                        if btn.is_displayed() and btn.is_enabled():
                            js_click(btn)
                            submit_clicked = True
                            print(f"  [debug] Clicked button near starbar")
                            time.sleep(1)
                            break
            except Exception:
                pass

    except Exception as e:
        print(f"  [debug] Submit button exception: {e}")

    if submit_clicked:
        return True

    # Step 4: Try pressing Enter as last resort
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(driver)
        actions.send_keys(Keys.RETURN).perform()
        print(f"  [debug] Pressed Enter to submit")
        time.sleep(1)
        return True
    except Exception:
        pass

    print("  [debug] Could not find/click submit button")
    return False


# =============================================================================
# Helper functions for main()
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments.

    Returns:
        Parsed argument namespace with all CLI options.

    Raises:
        SystemExit: If required arguments are missing.
    """
    parser = argparse.ArgumentParser(
        description='Upload ratings from a FilmAffinity CSV to IMDb.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--csv', help='Path to watched.csv (required unless using --retry or --resume)')
    parser.add_argument('--headless', action='store_true', help='Run browser headless')
    parser.add_argument('--auto-login', action='store_true', help='Try automated login using IMDB_USERNAME/IMDB_PASSWORD env vars')
    parser.add_argument('--auto-rate', action='store_true', help='Try automated rating clicks (best-effort). If fails, will prompt for manual rating.')
    parser.add_argument('--dry-run', action='store_true', help='Only map CSV titles to IMDb IDs via IMDbPY and produce a CSV mapping, then exit')
    parser.add_argument('--dry-run-output', default='imdb_matches.csv', help='Output path for dry-run CSV mapping')
    parser.add_argument('--start', type=int, default=0, help='Start index into CSV items')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of items (0 = all)')
    parser.add_argument('--confirm-threshold', type=float, default=DEFAULT_CONFIDENCE_THRESHOLD,
                        help=f'Confidence threshold below which LOW CONFIDENCE warning is shown (default: {DEFAULT_CONFIDENCE_THRESHOLD})')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompts for matches (use with caution)')
    parser.add_argument('--no-overwrite', action='store_true', help='Never overwrite existing IMDb ratings (auto-skip already rated movies)')
    parser.add_argument('--unattended', action='store_true', help='Run without user interaction: skip ambiguous matches, skip existing ratings, no manual prompts')
    parser.add_argument('--low-confidence-only', action='store_true',
                        help='Only process low-confidence/ambiguous matches (skip films that would auto-match). Useful for reviewing dubious matches.')
    parser.add_argument('--skipped-dir', default='skipped', help='Output directory for skipped movie CSV files by category (default: skipped/)')
    parser.add_argument('--retry', choices=['all', 'ambiguous', 'not_found', 'already_rated', 'auto_rate_failed', 'user_skipped'],
                        help='Re-run using previously skipped movies from --skipped-dir')
    parser.add_argument('--debug', action='store_true', help='Enable debug output for troubleshooting')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output (same as --debug)')
    parser.add_argument('--no-beep', action='store_true', help='Disable audible beeps when user input is required')

    # Configuration file options
    parser.add_argument('--config', help='Path to config file (JSON). Default: searches upload_imdb.json, ~/.config/upload_imdb/config.json')
    parser.add_argument('--save-config', metavar='PATH', help='Save current options to config file and exit')
    parser.add_argument('--show-config', action='store_true', help='Show current configuration and exit')

    # Session resume options
    parser.add_argument('--resume', action='store_true', help='Resume previous session (if available)')
    parser.add_argument('--clear-session', action='store_true', help='Clear saved session and start fresh')
    parser.add_argument('--session-file', default='.upload_imdb_session.json', help='Session file path (default: .upload_imdb_session.json)')

    args = parser.parse_args()

    # Handle special commands that don't need --csv
    if args.show_config or args.clear_session:
        return args

    if args.save_config:
        return args

    # Validate: either --csv, --retry, or --resume must be provided
    if not args.csv and not args.retry and not args.resume:
        parser.error('--csv is required unless using --retry or --resume')

    return args


def apply_config_to_args(args: argparse.Namespace, config: dict[str, Any]) -> None:
    """Apply config file values to args where args don't have explicit values.

    CLI arguments take precedence over config file values.

    Args:
        args: Parsed command line arguments (modified in place).
        config: Configuration dictionary from config file.
    """
    # Map config keys to args attributes
    config_mappings = {
        'headless': ('headless', False),
        'auto_login': ('auto_login', False),
        'auto_rate': ('auto_rate', False),
        'confirm_threshold': ('confirm_threshold', DEFAULT_CONFIDENCE_THRESHOLD),
        'no_confirm': ('no_confirm', False),
        'no_overwrite': ('no_overwrite', False),
        'unattended': ('unattended', False),
        'low_confidence_only': ('low_confidence_only', False),
        'skipped_dir': ('skipped_dir', 'skipped'),
        'session_file': ('session_file', '.upload_imdb_session.json'),
        'debug': ('debug', False),
        'verbose': ('verbose', False),
        'no_beep': ('no_beep', False),
    }

    for config_key, (arg_attr, default_val) in config_mappings.items():
        if config_key in config:
            current_value = getattr(args, arg_attr, None)
            # Only apply config if arg has its default value (wasn't set on CLI)
            if current_value == default_val:
                setattr(args, arg_attr, config[config_key])


def init_imdbpy_client() -> Any:
    """Initialize IMDbPY client for movie matching.

    Returns:
        IMDbPY client instance, or None if not available.
    """
    if IMDbPYClient is None:
        return None
    try:
        return IMDbPYClient('http')
    except Exception:
        try:
            return IMDbPYClient()
        except Exception:
            return None


def load_items(args: argparse.Namespace) -> list[MovieItem]:
    """Load items from CSV or retry directory.

    Args:
        args: Parsed command line arguments.

    Returns:
        List of movie items to process.
    """
    if args.retry:
        return load_retry_items(args.skipped_dir, args.retry)
    else:
        items = read_csv(args.csv)
        print(f'Read {len(items)} items from {args.csv}')
        return items


def load_retry_items(skipped_dir: str, retry_category: str) -> list[MovieItem]:
    """Load items from skipped category CSV files.

    Args:
        skipped_dir: Directory containing skipped CSV files.
        retry_category: Category to retry ('all' or specific category).

    Returns:
        List of movie items from the specified categories.
    """
    if retry_category == 'all':
        categories_to_load = list(RETRY_CATEGORY_TO_FILE.keys())
    else:
        categories_to_load = [retry_category]

    items = []
    for cat in categories_to_load:
        csv_file = os.path.join(skipped_dir, RETRY_CATEGORY_TO_FILE[cat])
        if os.path.exists(csv_file):
            cat_items = read_csv(csv_file)
            print(f'  Loaded {len(cat_items)} items from {csv_file}')
            items.extend(cat_items)
        else:
            print(f'  No file found: {csv_file}')

    if items:
        print(f'Retrying {len(items)} previously skipped items')
    else:
        print(f'No skipped items found to retry in {skipped_dir}/')

    return items


def apply_slice(items: list[MovieItem], start: int, limit: int) -> list[MovieItem]:
    """Apply start/limit slicing to items.

    Args:
        items: List of movie items.
        start: Starting index.
        limit: Maximum number of items (0 = no limit).

    Returns:
        Sliced list of movie items.
    """
    if limit > 0:
        return items[start:start + limit]
    return items[start:]


def run_dry_run(items: list[MovieItem], ia: Any, output_path: str) -> None:
    """Run dry-run mode: map titles to IMDb IDs without rating.

    Args:
        items: List of movie items to match.
        ia: IMDbPY client instance.
        output_path: Path for output CSV file.
    """
    print(f'Running dry-run mapping using IMDbPY; writing results to {output_path}')
    with open(output_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['local_title', 'local_year', 'local_director', 'imdb_id', 'imdb_title', 'imdb_year', 'score', 'query', 'result_count'])
        for it in items:
            title = it['title']
            year = it.get('year')
            director = it.get('directors')
            original_title = it.get('original_title')
            best = find_imdb_match(title, year, ia=ia, director=director, original_title=original_title)
            print(f'Best match for "{title}" ({year}) [director: {director}] [original: {original_title}]: {best}')
            if best:
                imdb_id = f"tt{best['movieID']}" if best.get('movieID') else ''
                w.writerow([title, year or '', director or '', imdb_id, best.get('title') or '', best.get('year') or '', f"{best.get('score'):.3f}", best.get('query') or '', best.get('result_count') or 0])
            else:
                w.writerow([title, year or '', director or '', '', '', '', '0.000', '', 0])
    print('Dry-run complete.')


def setup_browser_session(args: argparse.Namespace) -> WebDriver:
    """Set up browser and handle login.

    Args:
        args: Parsed command line arguments.

    Returns:
        Configured WebDriver instance with user logged in.
    """
    driver = start_driver(headless=args.headless)

    logged_in = False
    if args.auto_login:
        username = os.environ.get('IMDB_USERNAME')
        password = os.environ.get('IMDB_PASSWORD')
        if username and password:
            print('Attempting automated login...')
            logged_in = try_automated_login(driver, username, password)
            if not logged_in:
                print('Automated login failed or was inconclusive. Falling back to manual login flow.')
        else:
            print('IMDB_USERNAME/IMDB_PASSWORD not set; falling back to manual login.')

    if not logged_in:
        driver.get('https://www.imdb.com/')
        wait_for_login_manual(driver)

    return driver


def create_stats() -> Stats:
    """Create initial statistics dictionary.

    Returns:
        Dictionary with all stats initialized to zero/False.
    """
    return {
        'applied': 0,
        'skipped_ambiguous': 0,
        'skipped_not_found': 0,
        'skipped_already_rated': 0,
        'skipped_same_rating': 0,
        'skipped_user_choice': 0,
        'skipped_auto_rate_failed': 0,
        'quit_early': False
    }


def print_summary(stats: Stats, total_processed: int) -> None:
    """Print session summary to stdout.

    Args:
        stats: Statistics dictionary from the session.
        total_processed: Total number of items processed.
    """
    # Use .get() for backward compatibility with old session states
    total_skipped = (stats.get('skipped_ambiguous', 0) + stats.get('skipped_not_found', 0) +
                     stats.get('skipped_already_rated', 0) + stats.get('skipped_same_rating', 0) +
                     stats.get('skipped_user_choice', 0) + stats.get('skipped_auto_rate_failed', 0) +
                     stats.get('skipped_high_confidence', 0))
    print('\n' + '='*60)
    print('📊  SUMMARY')
    print('='*60)
    print(f'  Total items processed: {total_processed}')
    print(f'  ✅ Ratings applied:     {stats.get("applied", 0)}')
    print(f'  ⏭️  Total skipped:       {total_skipped}')
    if total_skipped > 0:
        print('     Breakdown:')
        if stats.get('skipped_high_confidence', 0) > 0:
            print(f'       - High confidence:   {stats["skipped_high_confidence"]}')
        if stats.get('skipped_ambiguous', 0) > 0:
            print(f'       - Ambiguous match:   {stats["skipped_ambiguous"]}')
        if stats.get('skipped_not_found', 0) > 0:
            print(f'       - Not found:         {stats["skipped_not_found"]}')
        if stats.get('skipped_already_rated', 0) > 0:
            print(f'       - Already rated:     {stats["skipped_already_rated"]}')
        if stats.get('skipped_same_rating', 0) > 0:
            print(f'       - Same rating:       {stats["skipped_same_rating"]}')
        if stats.get('skipped_user_choice', 0) > 0:
            print(f'       - User skipped:      {stats["skipped_user_choice"]}')
        if stats.get('skipped_auto_rate_failed', 0) > 0:
            print(f'       - Auto-rate failed:  {stats["skipped_auto_rate_failed"]}')
    if stats.get('quit_early'):
        print(f'  ⚠️  Quit early (remaining items not processed)')


def write_skipped_files(skipped_items: list[SkippedEntry], skipped_dir: str) -> None:
    """Write skipped items to separate CSV files by category.

    Args:
        skipped_items: List of skipped item entries with 'item' and 'reason' keys.
        skipped_dir: Directory to write CSV files to.

    Notes:
        Creates separate CSV files for each skip reason plus a combined file.
    """
    if not skipped_items:
        return

    os.makedirs(skipped_dir, exist_ok=True)

    # Group skipped items by reason
    by_reason = {}
    for entry in skipped_items:
        reason = entry['reason']
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(entry)

    print(f'\n  📄 Writing skipped items to: {skipped_dir}/')

    for reason, entries in by_reason.items():
        filename = SKIP_REASON_TO_FILE.get(reason, f'skipped_{reason}.csv')
        filepath = os.path.join(skipped_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, delimiter=';')
            writer.writeheader()
            for entry in entries:
                item = entry['item']
                writer.writerow({
                    'title': item.get('title', ''),
                    'year': item.get('year', ''),
                    'directors': item.get('directors', ''),
                    'user score': item.get('score', ''),
                    'original title': item.get('original_title', ''),
                })
        print(f'       - {filename}: {len(entries)} items')

    # Write combined file
    combined_path = os.path.join(skipped_dir, 'skipped_all.csv')
    with open(combined_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES_WITH_REASON, delimiter=';')
        writer.writeheader()
        for entry in skipped_items:
            item = entry['item']
            writer.writerow({
                'title': item.get('title', ''),
                'year': item.get('year', ''),
                'directors': item.get('directors', ''),
                'user score': item.get('score', ''),
                'original title': item.get('original_title', ''),
                'skip_reason': entry['reason']
            })
    print(f'       - skipped_all.csv: {len(skipped_items)} items (combined)')

    print(f'\n  💡 Re-run options:')
    print(f'       --retry all              # Retry all skipped movies')
    print(f'       --retry ambiguous        # Retry only ambiguous matches')
    print(f'       --retry not_found        # Retry only not found')
    print(f'       --retry already_rated    # Retry only already rated')
    print(f'       --retry auto_rate_failed # Retry only auto-rate failures')
    print(f'       --retry user_skipped     # Retry only user-skipped')


def process_single_item(
    driver: WebDriver,
    ia: Any,
    item: MovieItem,
    args: argparse.Namespace,
    stats: Stats,
    skipped_items: list[SkippedEntry]
) -> str:
    """Process a single movie item.

    Args:
        driver: WebDriver instance.
        ia: IMDbPY client instance.
        item: Movie item dictionary.
        args: Parsed command line arguments.
        stats: Statistics dictionary to update.
        skipped_items: List to append skipped items to.

    Returns:
        'continue' to skip to next item, 'break' to stop processing, or 'ok' for success.
    """
    title = item['title']
    year = item.get('year')
    director = item.get('directors')
    score = item.get('score')
    original_title = item.get('original_title')

    if original_title:
        print(f'  Original title: {original_title}')

    # Find IMDb match
    imdb_match = None
    confidence = 0.0
    imdb_id = None
    imdb_title = None
    imdb_year = None

    if ia is not None:
        imdb_match = find_imdb_match(title, year, ia=ia, director=director, original_title=original_title)
        if imdb_match:
            confidence = imdb_match.get('score', 0.0)
            imdb_id = f"tt{imdb_match['movieID']}" if imdb_match.get('movieID') else None
            imdb_title = imdb_match.get('title')
            imdb_year = imdb_match.get('year')
            print(f'  IMDb match: {imdb_title} ({imdb_year}) [{imdb_id}] - confidence: {confidence:.1%}')

    # Check if exact match
    title_matches = imdb_title and title.lower().strip() == imdb_title.lower().strip()
    year_matches = (not year and not imdb_year) or (year and imdb_year and str(year).strip() == str(imdb_year).strip())
    is_exact_match = title_matches and year_matches

    # Check confidence level
    is_low_confidence = confidence < args.confirm_threshold

    # Skip high-confidence matches when --low-confidence-only is enabled
    if getattr(args, 'low_confidence_only', False) and imdb_match and not is_low_confidence and is_exact_match:
        print(f'  [low-confidence-only] Skipping high-confidence match ({confidence:.1%} >= {args.confirm_threshold:.1%})')
        stats['skipped_high_confidence'] = stats.get('skipped_high_confidence', 0) + 1
        return 'continue'

    # Handle confirmation for non-exact matches
    if imdb_match and not args.no_confirm and not is_exact_match:
        result = handle_match_confirmation(
            item, imdb_match, imdb_id, imdb_title, imdb_year, confidence,
            args, stats, skipped_items
        )
        if result == 'break':
            return 'break'
        elif result == 'continue':
            return 'continue'
        elif isinstance(result, dict):
            # User selected a different match
            imdb_id = result.get('imdb_id')
            imdb_title = result.get('imdb_title')
            imdb_year = result.get('imdb_year')

    # Navigate to IMDb page
    if imdb_id:
        url = f'https://www.imdb.com/title/{imdb_id}/'
        print(f'  Opening: {url}')
        driver.get(url)
        time.sleep(1)
    else:
        found = imdb_search_and_open(driver, title, year)
        if not found:
            print(f'  Could not find search results for "{title}". Skipping.')
            stats['skipped_not_found'] += 1
            skipped_items.append({'item': item, 'reason': SKIP_NOT_FOUND})
            return 'continue'

    # Check for existing rating
    time.sleep(1)
    existing_rating = get_existing_rating(driver, debug=args.debug)
    if existing_rating is not None:
        # If existing rating matches desired score, skip silently (already correct)
        if existing_rating == score:
            print(f'  ✓ Already rated {existing_rating}/10 (matches CSV score). Skipping.')
            stats['skipped_same_rating'] += 1
            skipped_items.append({'item': item, 'reason': SKIP_SAME_RATING})
            return 'continue'

        if args.unattended or args.no_overwrite:
            mode_str = '[unattended]' if args.unattended else '[no-overwrite]'
            print(f'  {mode_str} Skipping - already rated {existing_rating}/10 (CSV wants {score}/10).')
            stats['skipped_already_rated'] += 1
            skipped_items.append({'item': item, 'reason': SKIP_ALREADY_RATED})
            return 'continue'

        choice = prompt_existing_rating(title, year, score, existing_rating)
        if choice == 'quit':
            print('User requested quit.')
            stats['quit_early'] = True
            return 'break'
        elif choice == 'skip':
            print('  Skipping (keeping existing rating).')
            stats['skipped_already_rated'] += 1
            return 'continue'

    # Attempt to rate
    success = False
    if args.auto_rate and score:
        try:
            success = try_rate_on_page(driver, score)
        except Exception as e:
            print('  Auto-rate exception:', e)
            success = False

    if not success:
        if args.unattended:
            print('  [unattended] Auto-rate failed, skipping.')
            stats['skipped_auto_rate_failed'] += 1
            skipped_items.append({'item': item, 'reason': SKIP_AUTO_RATE_FAILED})
            return 'continue'
        beep()
        print('  Could not auto-rate. The movie page is open in the browser.')
        input('  Please rate the movie manually in the browser, then press Enter here to continue...')
    else:
        print('  Rating applied (best-effort).')

    stats['applied'] += 1
    time.sleep(0.5)
    return 'ok'


def handle_match_confirmation(
    item: MovieItem,
    imdb_match: IMDbMatch,
    imdb_id: Optional[str],
    imdb_title: Optional[str],
    imdb_year: Optional[str],
    confidence: float,
    args: argparse.Namespace,
    stats: Stats,
    skipped_items: list[SkippedEntry]
) -> str | dict:
    """Handle user confirmation for ambiguous matches.

    Args:
        item: Movie item dictionary.
        imdb_match: IMDb match result dictionary.
        imdb_id: IMDb ID string.
        imdb_title: IMDb title.
        imdb_year: IMDb year.
        confidence: Match confidence score.
        args: Parsed command line arguments.
        stats: Statistics dictionary to update.
        skipped_items: List to append skipped items to.

    Returns:
        'break' to stop, 'continue' to skip, 'apply' to proceed, or dict with new match.
    """
    title = item['title']
    year = item.get('year')
    director = item.get('directors')
    score = item.get('score')

    if args.unattended:
        print('  [unattended] Skipping ambiguous match (title/year mismatch).')
        stats['skipped_ambiguous'] += 1
        skipped_items.append({'item': item, 'reason': SKIP_AMBIGUOUS})
        return 'continue'

    candidates = imdb_match.get('candidates', [])
    is_low_confidence = confidence < args.confirm_threshold

    if is_low_confidence and candidates:
        # Show candidate selection dialog
        choice = prompt_select_candidate(
            local_title=title,
            local_year=year,
            local_director=director,
            local_score=score,
            candidates=candidates
        )
        if choice == 'quit':
            print('User requested quit.')
            stats['quit_early'] = True
            return 'break'
        elif choice == 'skip':
            print('  Skipping this item.')
            stats['skipped_user_choice'] += 1
            skipped_items.append({'item': item, 'reason': SKIP_USER_CHOICE})
            return 'continue'
        elif isinstance(choice, dict):
            return {
                'imdb_id': f"tt{choice['movieID']}" if choice.get('movieID') else None,
                'imdb_title': choice.get('title'),
                'imdb_year': choice.get('year')
            }
    else:
        # Show simple confirm dialog
        while True:
            choice = prompt_confirm_match(
                local_title=title,
                local_year=year,
                local_director=director,
                local_score=score,
                imdb_title=imdb_title,
                imdb_year=imdb_year,
                imdb_id=imdb_id,
                confidence=confidence,
                is_low_confidence=is_low_confidence,
                candidates=candidates
            )
            if choice == 'quit':
                print('User requested quit.')
                stats['quit_early'] = True
                return 'break'
            elif choice == 'skip':
                print('  Skipping this item.')
                stats['skipped_user_choice'] += 1
                skipped_items.append({'item': item, 'reason': SKIP_USER_CHOICE})
                return 'continue'
            elif choice == 'select' and candidates:
                select_choice = prompt_select_candidate(
                    local_title=title,
                    local_year=year,
                    local_director=director,
                    local_score=score,
                    candidates=candidates
                )
                if select_choice == 'quit':
                    print('User requested quit.')
                    stats['quit_early'] = True
                    return 'break'
                elif select_choice == 'skip':
                    print('  Skipping this item.')
                    stats['skipped_user_choice'] += 1
                    skipped_items.append({'item': item, 'reason': SKIP_USER_CHOICE})
                    return 'continue'
                elif isinstance(select_choice, dict):
                    return {
                        'imdb_id': f"tt{select_choice['movieID']}" if select_choice.get('movieID') else None,
                        'imdb_title': select_choice.get('title'),
                        'imdb_year': select_choice.get('year')
                    }
            else:
                # 'apply' - proceed with original match
                return 'apply'

    return 'apply'


# =============================================================================
# Main entry point
# =============================================================================

def main():
    args = parse_arguments()

    # Load configuration file
    config = load_config(args.config)
    apply_config_to_args(args, config)

    # Handle --verbose as alias for --debug
    if args.verbose:
        args.debug = True

    # Handle --no-beep flag
    if args.no_beep:
        set_beep_enabled(False)

    # Handle special commands
    if args.show_config:
        print("Current configuration:")
        print(json.dumps(config, indent=2))
        return

    if args.save_config:
        # Build config from current args
        save_cfg = {
            'headless': args.headless,
            'auto_login': args.auto_login,
            'auto_rate': args.auto_rate,
            'confirm_threshold': args.confirm_threshold,
            'no_confirm': args.no_confirm,
            'no_overwrite': args.no_overwrite,
            'unattended': args.unattended,
            'skipped_dir': args.skipped_dir,
            'session_file': args.session_file,
            'debug': args.debug,
            'verbose': args.verbose,
            'no_beep': args.no_beep,
        }
        save_config(save_cfg, args.save_config)
        return

    # Initialize session state
    session = SessionState(args.session_file)

    if args.clear_session:
        session.clear()
        print(f"Session cleared: {args.session_file}")
        return

    # Handle resume mode
    start_index = args.start
    if args.resume:
        if session.load():
            if args.csv and not session.is_resumable(args.csv):
                beep()
                print(f"Warning: Saved session is for a different CSV file.")
                print(f"  Session CSV: {session.csv_path}")
                print(f"  Current CSV: {args.csv}")
                choice = input("Start fresh? [y/N]: ").strip().lower()
                if choice != 'y':
                    print("Aborting. Use --clear-session to start fresh.")
                    return
                session.clear()
            else:
                print(f"\n📂 Resuming previous session:")
                print(session.get_resume_info())
                start_index = session.current_index
                if not args.csv:
                    args.csv = session.csv_path
        else:
            print("No previous session found to resume.")
            if not args.csv:
                print("Error: --csv is required when no session exists.")
                return

    # Load items
    items = load_items(args)
    if not items:
        return

    # Store CSV path in session
    if args.csv:
        session.csv_path = args.csv

    items = apply_slice(items, start_index, args.limit)

    # Handle dry-run mode
    if args.dry_run:
        ia = init_imdbpy_client()
        if ia is None:
            print('IMDbPY not available. Install with: pip install imdbpy')
        run_dry_run(items, ia, args.dry_run_output)
        return

    # Initialize IMDbPY client
    ia = init_imdbpy_client()
    if ia is None:
        print('Warning: IMDbPY not available. Confidence-based matching will be disabled.')

    # Set up browser session
    driver = setup_browser_session(args)

    # Process items - restore stats from session if resuming
    if args.resume and session.stats:
        # Merge with default stats to ensure new keys exist (backward compatibility)
        stats = create_stats()
        stats.update(session.stats)
    else:
        stats = create_stats()

    # Restore skipped items from session if resuming
    if args.resume and session.skipped_items:
        skipped_items = session.skipped_items
    else:
        skipped_items = []

    idx = start_index

    try:
        for idx, item in enumerate(items, start=start_index + 1):
            title = item['title']
            year = item.get('year')
            score = item.get('score')
            print(f'\n[{idx}/{len(items) + start_index}] Processing: {title} ({year})  -> score: {score}')

            result = process_single_item(driver, ia, item, args, stats, skipped_items)

            # Update session after each item
            session.mark_processed(title, idx)
            session.stats = stats
            session.skipped_items = skipped_items
            session.save()

            if result == 'break':
                break
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Session saved.")
        session.stats = stats
        session.skipped_items = skipped_items
        session.save()
    finally:
        # Print summary and write skipped files
        print_summary(stats, idx)
        write_skipped_files(skipped_items, args.skipped_dir)

        print('='*60)
        print('Closing browser.')
        driver.quit()

        # Clear session if completed successfully without quit_early
        if not stats.get('quit_early') and idx >= len(items) + start_index:
            session.clear()
            print("✅ Session completed and cleared.")
        else:
            print(f"💾 Session saved. Use --resume to continue from item {idx}.")


if __name__ == '__main__':
    main()
