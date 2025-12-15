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

import argparse
import json
import logging
import os
import sys
import time
from typing import TYPE_CHECKING, Any


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
from .config import (
    SessionState,
    load_config,
    save_config,
)
from .constants import (
    CAPTCHA_WAIT,
    DEFAULT_CONFIDENCE_THRESHOLD,
    ELEMENT_INTERACTION_WAIT,
    LOGIN_WAIT,
    MANUAL_INTERACTION_WAIT,
    PAGE_LOAD_WAIT,
    SKIP_ALREADY_RATED,
    SKIP_AMBIGUOUS,
    SKIP_AUTO_RATE_FAILED,
    SKIP_NOT_FOUND,
    SKIP_SAME_RATING,
    SKIP_USER_CHOICE,
    IMDbMatch,
    MovieItem,
    SkippedEntry,
    Stats,
)
from .csv_validator import validate_csv_format
from .prompts import (
    beep,
    prompt_confirm_match,
    prompt_existing_rating,
    prompt_select_candidate,
    set_beep_enabled,
)
from .data_processing import (
    find_imdb_match,
    read_csv,
)
from .browser_automation import (
    get_existing_rating,
    imdb_search_and_open,
    try_rate_on_page,
)
from .reporting import (
    create_stats,
    print_summary,
    run_dry_run,
    setup_browser_session,
    write_skipped_files,
)

# Set up logging
logger = logging.getLogger(__name__)

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

# Import CSV constants from constants.py (must be after custom exceptions are defined)
from .constants import RETRY_CATEGORY_TO_FILE  # noqa: E402


# Note: HTTP-based scraping fallback was removed per user request.


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
        description="Upload ratings from a FilmAffinity CSV to IMDb.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--csv", help="Path to watched.csv (required unless using --retry or --resume)"
    )
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument(
        "--auto-login",
        action="store_true",
        help="Try automated login using IMDB_USERNAME/IMDB_PASSWORD env vars",
    )
    parser.add_argument(
        "--auto-rate",
        action="store_true",
        help="Try automated rating clicks (best-effort). If fails, will prompt for manual rating.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only map CSV titles to IMDb IDs via IMDbPY and produce a CSV mapping, then exit",
    )
    parser.add_argument(
        "--dry-run-output", default="imdb_matches.csv", help="Output path for dry-run CSV mapping"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate CSV format and exit"
    )
    parser.add_argument("--skip-validation", action="store_true", help="Skip CSV format validation")
    parser.add_argument("--start", type=int, default=0, help="Start index into CSV items")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of items (0 = all)")
    parser.add_argument(
        "--confirm-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Confidence threshold below which LOW CONFIDENCE warning is shown (default: {DEFAULT_CONFIDENCE_THRESHOLD})",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompts for matches (use with caution)",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Never overwrite existing IMDb ratings (auto-skip already rated movies)",
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Run without user interaction: skip ambiguous matches, skip existing ratings, no manual prompts",
    )
    parser.add_argument(
        "--low-confidence-only",
        action="store_true",
        help="Only process low-confidence/ambiguous matches (skip films that would auto-match). Useful for reviewing dubious matches.",
    )
    parser.add_argument(
        "--skipped-dir",
        default="skipped",
        help="Output directory for skipped movie CSV files by category (default: skipped/)",
    )
    parser.add_argument(
        "--retry",
        choices=[
            "all",
            "ambiguous",
            "not_found",
            "already_rated",
            "auto_rate_failed",
            "user_skipped",
        ],
        help="Re-run using previously skipped movies from --skipped-dir",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output for troubleshooting"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output (same as --debug)"
    )
    parser.add_argument(
        "--no-beep", action="store_true", help="Disable audible beeps when user input is required"
    )

    # Configuration file options
    parser.add_argument(
        "--config",
        help="Path to config file (JSON). Default: searches upload_imdb.json, ~/.config/upload_imdb/config.json",
    )
    parser.add_argument(
        "--save-config", metavar="PATH", help="Save current options to config file and exit"
    )
    parser.add_argument(
        "--show-config", action="store_true", help="Show current configuration and exit"
    )

    # Session resume options
    parser.add_argument(
        "--resume", action="store_true", help="Resume previous session (if available)"
    )
    parser.add_argument(
        "--clear-session", action="store_true", help="Clear saved session and start fresh"
    )
    parser.add_argument(
        "--session-file",
        default=".upload_imdb_session.json",
        help="Session file path (default: .upload_imdb_session.json)",
    )

    args = parser.parse_args()

    # Handle special commands that don't need --csv
    if args.show_config or args.clear_session:
        return args

    if args.save_config:
        return args

    # Handle --validate-only (requires --csv, handled separately)
    if args.validate_only:
        return args

    # Validate: either --csv, --retry, or --resume must be provided
    if not args.csv and not args.retry and not args.resume:
        parser.error("--csv is required unless using --retry or --resume")

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
        "headless": ("headless", False),
        "auto_login": ("auto_login", False),
        "auto_rate": ("auto_rate", False),
        "confirm_threshold": ("confirm_threshold", DEFAULT_CONFIDENCE_THRESHOLD),
        "no_confirm": ("no_confirm", False),
        "no_overwrite": ("no_overwrite", False),
        "unattended": ("unattended", False),
        "low_confidence_only": ("low_confidence_only", False),
        "skipped_dir": ("skipped_dir", "skipped"),
        "session_file": ("session_file", ".upload_imdb_session.json"),
        "debug": ("debug", False),
        "verbose": ("verbose", False),
        "no_beep": ("no_beep", False),
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
        return IMDbPYClient("http")
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

    Raises:
        SystemExit: If CSV validation fails.
    """
    if args.retry:
        return load_retry_items(args.skipped_dir, args.retry)

    # Validate CSV format before processing (unless --skip-validation)
    skip_validation = getattr(args, "skip_validation", False)
    if not skip_validation:
        print(f"Validating CSV format: {args.csv}")
        validation = validate_csv_format(args.csv, require_score=True)
        print(validation)

        if not validation.valid:
            print("\n❌ CSV validation failed. Fix the errors above and try again.")
            print("   Use --skip-validation to bypass this check (not recommended).")
            sys.exit(1)

        if validation.warnings:
            print("\n⚠️  Validation passed with warnings (see above).")

    items = read_csv(args.csv)
    print(f"Read {len(items)} items from {args.csv}")
    return items


def load_retry_items(skipped_dir: str, retry_category: str) -> list[MovieItem]:
    """Load items from skipped category CSV files.

    Args:
        skipped_dir: Directory containing skipped CSV files.
        retry_category: Category to retry ('all' or specific category).

    Returns:
        List of movie items from the specified categories.
    """
    if retry_category == "all":
        categories_to_load = list(RETRY_CATEGORY_TO_FILE.keys())
    else:
        categories_to_load = [retry_category]

    items = []
    for cat in categories_to_load:
        csv_file = os.path.join(skipped_dir, RETRY_CATEGORY_TO_FILE[cat])
        if os.path.exists(csv_file):
            cat_items = read_csv(csv_file)
            logger.info(f"  Loaded {len(cat_items)} items from {csv_file}")
            items.extend(cat_items)
        else:
            logger.info(f"  No file found: {csv_file}")

    if items:
        logger.info(f"Retrying {len(items)} previously skipped items")
    else:
        logger.info(f"No skipped items found to retry in {skipped_dir}/")

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
        return items[start : start + limit]
    return items[start:]


# =============================================================================


def process_single_item(
    driver: WebDriver,
    ia: Any,
    item: MovieItem,
    args: argparse.Namespace,
    stats: Stats,
    skipped_items: list[SkippedEntry],
    page_load_wait: float = PAGE_LOAD_WAIT,
    element_wait: float = ELEMENT_INTERACTION_WAIT,
    rating_wait: float = MANUAL_INTERACTION_WAIT,
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
    title = item["title"]
    year = item.get("year")
    director = item.get("directors")
    score = item.get("score")
    original_title = item.get("original_title")

    if original_title:
        logger.debug(f"  Original title: {original_title}")

    # Find IMDb match
    imdb_match = None
    confidence = 0.0
    imdb_id = None
    imdb_title = None
    imdb_year = None

    if ia is not None:
        imdb_match = find_imdb_match(
            title, year, ia=ia, director=director, original_title=original_title
        )
        if imdb_match:
            confidence = imdb_match.get("score", 0.0)
            imdb_id = f"tt{imdb_match['movieID']}" if imdb_match.get("movieID") else None
            imdb_title = imdb_match.get("title")
            imdb_year = imdb_match.get("year")
            print(
                f"  IMDb match: {imdb_title} ({imdb_year}) [{imdb_id}] - confidence: {confidence:.1%}"
            )

    # Check if exact match
    title_matches = imdb_title and title.lower().strip() == imdb_title.lower().strip()
    year_matches = (not year and not imdb_year) or (
        year and imdb_year and str(year).strip() == str(imdb_year).strip()
    )
    is_exact_match = title_matches and year_matches

    # Check confidence level
    is_low_confidence = confidence < args.confirm_threshold

    # Skip high-confidence matches when --low-confidence-only is enabled
    if (
        getattr(args, "low_confidence_only", False)
        and imdb_match
        and not is_low_confidence
        and is_exact_match
    ):
        print(
            f"  [low-confidence-only] Skipping high-confidence match ({confidence:.1%} >= {args.confirm_threshold:.1%})"
        )
        stats["skipped_high_confidence"] = stats.get("skipped_high_confidence", 0) + 1
        return "continue"

    # Handle confirmation for non-exact matches
    if imdb_match and not args.no_confirm and not is_exact_match:
        result = handle_match_confirmation(
            item, imdb_match, imdb_id, imdb_title, imdb_year, confidence, args, stats, skipped_items
        )
        if result == "break":
            return "break"
        elif result == "continue":
            return "continue"
        elif isinstance(result, dict):
            # User selected a different match
            imdb_id = result.get("imdb_id")
            imdb_title = result.get("imdb_title")
            imdb_year = result.get("imdb_year")

    # Navigate to IMDb page
    if imdb_id:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        logger.debug(f"  Opening: {url}")
        driver.get(url)
        time.sleep(page_load_wait)
    else:
        found = imdb_search_and_open(driver, title, year, page_load_wait)
        if not found:
            print(f'  Could not find search results for "{title}". Skipping.')
            stats["skipped_not_found"] += 1
            skipped_items.append({"item": item, "reason": SKIP_NOT_FOUND})
            return "continue"

    # Check for existing rating
    time.sleep(element_wait)
    existing_rating = get_existing_rating(driver, debug=args.debug)
    if existing_rating is not None:
        # If existing rating matches desired score, skip silently (already correct)
        if existing_rating == score:
            print(f"  ✓ Already rated {existing_rating}/10 (matches CSV score). Skipping.")
            stats["skipped_same_rating"] += 1
            skipped_items.append({"item": item, "reason": SKIP_SAME_RATING})
            return "continue"

        if args.unattended or args.no_overwrite:
            mode_str = "[unattended]" if args.unattended else "[no-overwrite]"
            print(
                f"  {mode_str} Skipping - already rated {existing_rating}/10 (CSV wants {score}/10)."
            )
            stats["skipped_already_rated"] += 1
            skipped_items.append({"item": item, "reason": SKIP_ALREADY_RATED})
            return "continue"

        choice = prompt_existing_rating(title, year, score, existing_rating)
        if choice == "quit":
            print("User requested quit.")
            stats["quit_early"] = True
            return "break"
        elif choice == "skip":
            print("  Skipping (keeping existing rating).")
            stats["skipped_already_rated"] += 1
            return "continue"

    # Attempt to rate
    success = False
    if args.auto_rate and score:
        try:
            success = try_rate_on_page(driver, score, element_wait, rating_wait)
        except Exception as e:
            logger.warning(f"  Auto-rate exception: {e}")
            success = False

    if not success:
        if args.unattended:
            print("  [unattended] Auto-rate failed, skipping.")
            stats["skipped_auto_rate_failed"] += 1
            skipped_items.append({"item": item, "reason": SKIP_AUTO_RATE_FAILED})
            return "continue"
        beep()
        print("  Could not auto-rate. The movie page is open in the browser.")
        input(
            "  Please rate the movie manually in the browser, then press Enter here to continue..."
        )
    else:
        print("  Rating applied (best-effort).")

    stats["applied"] += 1
    time.sleep(element_wait)
    return "ok"


def handle_match_confirmation(
    item: MovieItem,
    imdb_match: IMDbMatch,
    imdb_id: str | None,
    imdb_title: str | None,
    imdb_year: str | None,
    confidence: float,
    args: argparse.Namespace,
    stats: Stats,
    skipped_items: list[SkippedEntry],
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
    title = item["title"]
    year = item.get("year")
    director = item.get("directors")
    score = item.get("score")

    if args.unattended:
        print("  [unattended] Skipping ambiguous match (title/year mismatch).")
        stats["skipped_ambiguous"] += 1
        skipped_items.append({"item": item, "reason": SKIP_AMBIGUOUS})
        return "continue"

    candidates = imdb_match.get("candidates", [])
    is_low_confidence = confidence < args.confirm_threshold

    if is_low_confidence and candidates:
        # Show candidate selection dialog
        choice = prompt_select_candidate(
            local_title=title,
            local_year=year,
            local_director=director,
            local_score=score,
            candidates=candidates,
        )
        if choice == "quit":
            print("User requested quit.")
            stats["quit_early"] = True
            return "break"
        elif choice == "skip":
            print("  Skipping this item.")
            stats["skipped_user_choice"] += 1
            skipped_items.append({"item": item, "reason": SKIP_USER_CHOICE})
            return "continue"
        elif isinstance(choice, dict):
            return {
                "imdb_id": f"tt{choice['movieID']}" if choice.get("movieID") else None,
                "imdb_title": choice.get("title"),
                "imdb_year": choice.get("year"),
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
                candidates=candidates,
            )
            if choice == "quit":
                print("User requested quit.")
                stats["quit_early"] = True
                return "break"
            elif choice == "skip":
                print("  Skipping this item.")
                stats["skipped_user_choice"] += 1
                skipped_items.append({"item": item, "reason": SKIP_USER_CHOICE})
                return "continue"
            elif choice == "select" and candidates:
                select_choice = prompt_select_candidate(
                    local_title=title,
                    local_year=year,
                    local_director=director,
                    local_score=score,
                    candidates=candidates,
                )
                if select_choice == "quit":
                    print("User requested quit.")
                    stats["quit_early"] = True
                    return "break"
                elif select_choice == "skip":
                    print("  Skipping this item.")
                    stats["skipped_user_choice"] += 1
                    skipped_items.append({"item": item, "reason": SKIP_USER_CHOICE})
                    return "continue"
                elif isinstance(select_choice, dict):
                    return {
                        "imdb_id": f"tt{select_choice['movieID']}"
                        if select_choice.get("movieID")
                        else None,
                        "imdb_title": select_choice.get("title"),
                        "imdb_year": select_choice.get("year"),
                    }
            else:
                # 'apply' - proceed with original match
                return "apply"

    return "apply"


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

    # Configure logging based on debug flag
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Handle --no-beep flag
    if args.no_beep:
        set_beep_enabled(False)

    # Handle special commands
    if args.show_config:
        print("Current configuration:")
        print(json.dumps(config, indent=2))
        return

    # Handle --validate-only: validate CSV and exit
    if args.validate_only:
        if not args.csv:
            print("Error: --csv is required with --validate-only")
            sys.exit(1)
        print(f"Validating CSV format: {args.csv}")
        validation = validate_csv_format(args.csv, require_score=True)
        print(validation)
        if validation.valid:
            print("\n✅ CSV is valid and ready for processing.")
            sys.exit(0)
        else:
            print("\n❌ CSV validation failed.")
            sys.exit(1)

    if args.save_config:
        # Build config from current args
        save_cfg = {
            "headless": args.headless,
            "auto_login": args.auto_login,
            "auto_rate": args.auto_rate,
            "confirm_threshold": args.confirm_threshold,
            "no_confirm": args.no_confirm,
            "no_overwrite": args.no_overwrite,
            "unattended": args.unattended,
            "skipped_dir": args.skipped_dir,
            "session_file": args.session_file,
            "debug": args.debug,
            "verbose": args.verbose,
            "no_beep": args.no_beep,
            # Timing settings
            "page_load_wait": config.get("page_load_wait", PAGE_LOAD_WAIT),
            "element_wait": config.get("element_wait", ELEMENT_INTERACTION_WAIT),
            "login_wait": config.get("login_wait", LOGIN_WAIT),
            "captcha_wait": config.get("captcha_wait", CAPTCHA_WAIT),
            "rating_wait": config.get("rating_wait", MANUAL_INTERACTION_WAIT),
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
                print("Warning: Saved session is for a different CSV file.")
                print(f"  Session CSV: {session.csv_path}")
                print(f"  Current CSV: {args.csv}")
                choice = input("Start fresh? [y/N]: ").strip().lower()
                if choice != "y":
                    print("Aborting. Use --clear-session to start fresh.")
                    return
                session.clear()
            else:
                print("\n📂 Resuming previous session:")
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
            print("IMDbPY not available. Install with: pip install imdbpy")
        run_dry_run(items, ia, args.dry_run_output)
        return

    # Initialize IMDbPY client
    ia = init_imdbpy_client()
    if ia is None:
        print("Warning: IMDbPY not available. Confidence-based matching will be disabled.")

    # Set up browser session
    driver = setup_browser_session(args, config)

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
    total_items = len(items) + start_index

    try:
        for idx, item in enumerate(items, start=start_index + 1):
            title = item["title"]
            year = item.get("year")
            score = item.get("score")
            progress_pct = (idx / total_items) * 100
            print(
                f"\n[{idx}/{total_items}] ({progress_pct:.1f}%) Processing: {title} ({year})  -> score: {score}"
            )

            result = process_single_item(
                driver,
                ia,
                item,
                args,
                stats,
                skipped_items,
                config.get("page_load_wait", PAGE_LOAD_WAIT),
                config.get("element_wait", ELEMENT_INTERACTION_WAIT),
                config.get("rating_wait", MANUAL_INTERACTION_WAIT),
            )

            # Update session after each item
            session.mark_processed(title, idx)
            session.stats = stats
            session.skipped_items = skipped_items
            session.save()

            if result == "break":
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

        print("=" * 60)
        print("Closing browser.")
        driver.quit()

        # Clear session if completed successfully without quit_early
        if not stats.get("quit_early") and idx >= len(items) + start_index:
            session.clear()
            print("✅ Session completed and cleared.")
        else:
            print(f"💾 Session saved. Use --resume to continue from item {idx}.")


if __name__ == "__main__":
    main()
