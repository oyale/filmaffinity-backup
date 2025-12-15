"""Reporting and output functions for IMDb uploader.

This module handles statistics tracking, dry-run processing, browser session setup,
and output formatting for the IMDb uploader.
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from selenium.webdriver.chrome.webdriver import WebDriver

from .constants import (
    CSV_FIELDNAMES,
    CSV_FIELDNAMES_WITH_REASON,
    SKIP_REASON_TO_FILE,
    Stats,
)
from .data_processing import find_imdb_match


def run_dry_run(items: list[dict[str, Any]], ia: Any, output_path: str) -> None:
    """Run dry-run mode: map titles to IMDb IDs without rating.

    Args:
        items: List of movie items to match.
        ia: IMDbPY client instance.
        output_path: Path for output CSV file.
    """
    print(f"Running dry-run mapping using IMDbPY; writing results to {output_path}")
    total_items = len(items)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "local_title",
                "local_year",
                "local_director",
                "imdb_id",
                "imdb_title",
                "imdb_year",
                "score",
                "query",
                "result_count",
            ]
        )
        for idx, it in enumerate(items, start=1):
            title = it["title"]
            year = it.get("year")
            director = it.get("directors")
            original_title = it.get("original_title")
            progress_pct = (idx / total_items) * 100
            best = find_imdb_match(
                title, year, ia=ia, director=director, original_title=original_title
            )
            print(
                f'[{idx}/{total_items}] ({progress_pct:.1f}%) Best match for "{title}" ({year}): {best.get("title") if best else "None"}'
            )
            if best:
                imdb_id = f"tt{best['movieID']}" if best.get("movieID") else ""
                w.writerow(
                    [
                        title,
                        year or "",
                        director or "",
                        imdb_id,
                        best.get("title") or "",
                        best.get("year") or "",
                        f"{best.get('score'):.3f}",
                        best.get("query") or "",
                        best.get("result_count") or 0,
                    ]
                )
            else:
                w.writerow([title, year or "", director or "", "", "", "", "0.000", "", 0])
    print("Dry-run complete.")


def setup_browser_session(args: argparse.Namespace, config: dict[str, Any]) -> WebDriver:
    """Set up browser and handle login.

    Args:
        args: Parsed command line arguments.

    Returns:
        Configured WebDriver instance with user logged in.
    """
    from .browser_automation import start_driver, try_automated_login, wait_for_login_manual

    driver = start_driver(headless=args.headless)

    logged_in = False
    if args.auto_login:
        username = os.environ.get("IMDB_USERNAME")
        password = os.environ.get("IMDB_PASSWORD")
        if username and password:
            print("Attempting automated login...")
            logged_in = try_automated_login(
                driver,
                username,
                password,
                debug=args.debug,
                login_wait=config.get("login_wait", 2.0),
                page_load_wait=config.get("page_load_wait", 2.0),
                element_wait=config.get("element_wait", 0.5),
                captcha_wait=config.get("captcha_wait", 5.0),
            )
            if not logged_in:
                print(
                    "Automated login failed or was inconclusive. Falling back to manual login flow."
                )
        else:
            print("IMDB_USERNAME/IMDB_PASSWORD not set; falling back to manual login.")

    if not logged_in:
        driver.get("https://www.imdb.com/")
        wait_for_login_manual(driver)

    return driver


def create_stats() -> Stats:
    """Create initial statistics dictionary.

    Returns:
        Dictionary with all stats initialized to zero/False.
    """
    return {
        "applied": 0,
        "skipped_ambiguous": 0,
        "skipped_not_found": 0,
        "skipped_already_rated": 0,
        "skipped_same_rating": 0,
        "skipped_user_choice": 0,
        "skipped_auto_rate_failed": 0,
        "quit_early": False,
    }


def print_summary(stats: Stats, total_processed: int) -> None:
    """Print session summary to stdout.

    Args:
        stats: Statistics dictionary from the session.
        total_processed: Total number of items processed.
    """
    # Use .get() for backward compatibility with old session states
    total_skipped = (
        stats.get("skipped_ambiguous", 0)
        + stats.get("skipped_not_found", 0)
        + stats.get("skipped_already_rated", 0)
        + stats.get("skipped_same_rating", 0)
        + stats.get("skipped_user_choice", 0)
        + stats.get("skipped_auto_rate_failed", 0)
        + stats.get("skipped_high_confidence", 0)
    )
    print("\n" + "=" * 60)
    print("📊  SUMMARY")
    print("=" * 60)
    print(f"  Total items processed: {total_processed}")
    print(f'  ✅ Ratings applied:     {stats.get("applied", 0)}')
    print(f"  ⏭️  Total skipped:       {total_skipped}")
    if total_skipped > 0:
        print("     Breakdown:")
        if stats.get("skipped_high_confidence", 0) > 0:
            print(f'       - High confidence:   {stats["skipped_high_confidence"]}')
        if stats.get("skipped_ambiguous", 0) > 0:
            print(f'       - Ambiguous match:   {stats["skipped_ambiguous"]}')
        if stats.get("skipped_not_found", 0) > 0:
            print(f'       - Not found:         {stats["skipped_not_found"]}')
        if stats.get("skipped_already_rated", 0) > 0:
            print(f'       - Already rated:     {stats["skipped_already_rated"]}')
        if stats.get("skipped_same_rating", 0) > 0:
            print(f'       - Same rating:       {stats["skipped_same_rating"]}')
        if stats.get("skipped_user_choice", 0) > 0:
            print(f'       - User skipped:      {stats["skipped_user_choice"]}')
        if stats.get("skipped_auto_rate_failed", 0) > 0:
            print(f'       - Auto-rate failed:  {stats["skipped_auto_rate_failed"]}')
    if stats.get("quit_early"):
        print("  ⚠️  Quit early (remaining items not processed)")


def write_skipped_files(skipped_items: list[dict[str, Any]], skipped_dir: str) -> None:
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
    by_reason: dict[str, list[dict[str, Any]]] = {}
    for entry in skipped_items:
        reason = entry["reason"]
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(entry)

    print(f"\n  📄 Writing skipped items to: {skipped_dir}/")

    for reason, entries in by_reason.items():
        filename = SKIP_REASON_TO_FILE.get(reason, f"skipped_{reason}.csv")
        filepath = os.path.join(skipped_dir, filename)
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES, delimiter=";")
            writer.writeheader()
            for entry in entries:
                item = entry["item"]
                writer.writerow(
                    {
                        "title": item.get("title", ""),
                        "year": item.get("year", ""),
                        "directors": item.get("directors", ""),
                        "user score": item.get("score", ""),
                        "original title": item.get("original_title", ""),
                    }
                )
        print(f"       - {filename}: {len(entries)} items")

    # Write combined file
    combined_path = os.path.join(skipped_dir, "skipped_all.csv")
    with open(combined_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES_WITH_REASON, delimiter=";")
        writer.writeheader()
        for entry in skipped_items:
            item = entry["item"]
            writer.writerow(
                {
                    "title": item.get("title", ""),
                    "year": item.get("year", ""),
                    "directors": item.get("directors", ""),
                    "user score": item.get("score", ""),
                    "original title": item.get("original_title", ""),
                    "skip_reason": entry["reason"],
                }
            )
    print(f"       - skipped_all.csv: {len(skipped_items)} items (combined)")

    print("\n  💡 Re-run options:")
    print("       --retry all              # Retry all skipped movies")
    print("       --retry user_skipped     # Retry only user-skipped")
