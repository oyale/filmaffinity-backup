"""Constants and type definitions for the IMDb uploader.

This module contains all constants, selectors, and type aliases used across
the imdb_uploader package.
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Type Aliases
# =============================================================================

MovieItem = dict[str, Any]
SkippedEntry = dict[str, Any]
IMDbMatch = dict[str, Any]
Stats = dict[str, Any]


# =============================================================================
# Default Configuration
# =============================================================================

DEFAULT_CONFIG: dict[str, Any] = {
    "headless": False,
    "auto_login": False,
    "auto_rate": False,
    "confirm_threshold": 0.75,
    "no_confirm": False,
    "no_overwrite": False,
    "unattended": False,
    "skipped_dir": "skipped",
    "session_file": ".upload_imdb_session.json",
    "debug": False,
    "verbose": False,
    "no_beep": False,
    # Rate limiting settings
    "rate_limit_initial_cooldown": 5,
    "rate_limit_max_cooldown": 60,
    "max_retries": 3,
    # Timing settings
    "page_load_wait": 2.0,
    "element_interaction_wait": 0.5,
    "login_wait": 2.0,
    "captcha_wait": 5.0,
    "manual_interaction_wait": 1.0,
    "rating_wait": 1.0,
    "search_wait": 0.5,
    "element_wait": 0.5,
}


# =============================================================================
# Confidence Thresholds
# =============================================================================

DEFAULT_CONFIDENCE_THRESHOLD = 0.75
DIRECTOR_LOOKUP_THRESHOLD = 0.85
DIRECTOR_FETCH_CANDIDATE_MIN_SCORE = 0.4
DIRECTOR_FETCH_LIMIT = 3


# =============================================================================
# Rate Limiting
# =============================================================================

RATE_LIMIT_COOLDOWN_INITIAL = 5
RATE_LIMIT_COOLDOWN_MAX = 60
MAX_RETRIES = 3


# =============================================================================
# Timing Constants
# =============================================================================

PAGE_LOAD_WAIT = 2.0
ELEMENT_INTERACTION_WAIT = 0.5
LOGIN_WAIT = 2.0
CAPTCHA_WAIT = 5.0
MANUAL_INTERACTION_WAIT = 1.0


# =============================================================================
# Skip Reasons
# =============================================================================

SKIP_AMBIGUOUS = "ambiguous_match"
SKIP_NOT_FOUND = "not_found"
SKIP_ALREADY_RATED = "already_rated"
SKIP_SAME_RATING = "same_rating"
SKIP_AUTO_RATE_FAILED = "auto_rate_failed"
SKIP_USER_CHOICE = "user_choice"

# Mapping of skip reasons to CSV filenames
SKIP_REASON_TO_FILE = {
    SKIP_AMBIGUOUS: "skipped_ambiguous.csv",
    SKIP_NOT_FOUND: "skipped_not_found.csv",
    SKIP_ALREADY_RATED: "skipped_already_rated.csv",
    SKIP_SAME_RATING: "skipped_same_rating.csv",
    SKIP_AUTO_RATE_FAILED: "skipped_auto_rate_failed.csv",
    SKIP_USER_CHOICE: "skipped_user_choice.csv",
}

# Mapping of retry categories to CSV filenames
RETRY_CATEGORY_TO_FILE = {
    "ambiguous": "skipped_ambiguous.csv",
    "not_found": "skipped_not_found.csv",
    "already_rated": "skipped_already_rated.csv",
    "auto_rate_failed": "skipped_auto_rate_failed.csv",
    "user_skipped": "skipped_user_choice.csv",
}


# =============================================================================
# CSV Field Names
# =============================================================================

CSV_FIELDNAMES = ["title", "year", "directors", "user score", "original title"]
CSV_FIELDNAMES_WITH_REASON = CSV_FIELDNAMES + ["skip_reason"]


# =============================================================================
# Selenium Selectors
# =============================================================================
# Extracted for maintainability when IMDb DOM changes

# User rating detection selectors
SELECTOR_USER_RATING_UNRATED = "//*[contains(@data-testid,'user-rating__unrated')]"
SELECTOR_USER_RATING_SCORE = "//*[contains(@data-testid,'user-rating__score')]"
SELECTOR_USER_RATING_SECTION = "//div[contains(@data-testid,'hero-rating-bar__user-rating')]"
SELECTOR_STAR_RATING_CLASS = ".//span[contains(@class,'ipc-rating-star--rating')]"

# Rating modal selectors
SELECTOR_RATE_BUTTON_OPTIONS = [
    "[data-testid='hero-rating-bar__user-rating'] button",
    "[data-testid='hero-rating-bar__user-rating__score']",
    ".hero-rating-bar__user-rating button",
    ".ipc-btn[aria-label*='Rate']",
]
SELECTOR_STAR_BUTTONS = "button.ipc-starbar__rating__button"
SELECTOR_SUBMIT_RATE_BUTTON = "button.ipc-rating-prompt__rate-button"
SELECTOR_SUBMIT_BUTTON_FALLBACK = ".ipc-btn--core-accent1, button.ipc-btn--core-primary"
SELECTOR_STARBAR = ".ipc-starbar"

# Login selectors
SELECTOR_EMAIL_INPUT_OPTIONS = [
    "input[name='email']",
    "input#ap_email",
    "input[type='email']",
    "input[name='username']",
    "input#email",
]
SELECTOR_PASSWORD_INPUT_OPTIONS = [
    "input[name='password']",
    "input#ap_password",
    "input[type='password']",
    "input#password",
]
SELECTOR_CONTINUE_BUTTON = (
    "input#continue, input[type='submit'], button[type='submit'], .auth-button"
)
SELECTOR_USER_MENU = (
    ".imdb-header__account-toggle, .nav__user-menu, [data-testid='nav-link-logged-in'], "
    ".navbar__user, .ipc-button[aria-label*='Account']"
)

# CAPTCHA detection selectors
SELECTOR_CAPTCHA_INDICATORS = [
    "iframe[src*='captcha']",
    "iframe[src*='recaptcha']",
    "iframe[title*='captcha']",
    "iframe[title*='reCAPTCHA']",
    "#captcha",
    ".captcha",
    "[id*='captcha']",
    "[class*='captcha']",
    "img[src*='captcha']",
    "input[name*='captcha']",
    "#auth-captcha-image",
    ".a-box-inner img[src*='opfcaptcha']",
    ".g-recaptcha",
    "[data-sitekey]",
    "img[alt*='captcha']",
    "img[alt*='puzzle']",
]

# Search results selectors
SELECTOR_SEARCH_RESULTS = [
    "table.findList tr .result_text a",
    ".findList tr .result_text a",
    ".findSection .findResult .result_text a",
]
