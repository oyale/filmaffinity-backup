"""User interaction prompts for IMDb uploader."""

from __future__ import annotations

import re
import urllib.parse

__all__ = [
    "beep",
    "parse_imdb_id",
    "prompt_existing_rating",
    "prompt_confirm_match",
    "prompt_low_confidence_match",
    "prompt_select_candidate",
]

# Module-level flag to control beeping
_beep_enabled: bool = True


def set_beep_enabled(enabled: bool) -> None:
    """Enable or disable audible beeps globally.

    Args:
        enabled: If True, beep() will produce sound. If False, beep() is silent.
    """
    global _beep_enabled
    _beep_enabled = enabled


def is_beep_enabled() -> bool:
    """Check if audible beeps are enabled.

    Returns:
        True if beeps are enabled, False otherwise.
    """
    return _beep_enabled


def beep() -> None:
    """Play an audible beep to alert user that input is needed.

    Uses the terminal bell character which is cross-platform compatible.
    Can be disabled globally via set_beep_enabled(False).
    """
    if _beep_enabled:
        print("\a", end="", flush=True)


def parse_imdb_id(input_str: str) -> str | None:
    """Parse an IMDb ID from various input formats.

    Accepts:
        - Plain numeric ID: '1234567'
        - tt-prefixed ID: 'tt1234567'
        - IMDb URL: 'https://www.imdb.com/title/tt1234567/' or similar

    Args:
        input_str: User input that may contain an IMDb ID.

    Returns:
        The numeric IMDb ID (without 'tt' prefix) or None if not valid.

    Examples:
        >>> parse_imdb_id('tt1234567')
        '1234567'
        >>> parse_imdb_id('https://www.imdb.com/title/tt1234567/')
        '1234567'
        >>> parse_imdb_id('1234567')
        '1234567'
    """
    if not input_str:
        return None

    input_str = input_str.strip()

    # Try to extract from URL pattern
    try:
        parsed_url = urllib.parse.urlparse(input_str)
        host = parsed_url.hostname
        if host and (host == "imdb.com" or host.endswith(".imdb.com")):
            # Extract IMDb ID from path like /title/tt1234567/
            path_match = re.search(r"/title/tt(\d+)/?", parsed_url.path)
            if path_match:
                return path_match.group(1)
    except Exception:
        # Not a valid URL, continue with other patterns
        pass

    # Try tt-prefixed pattern
    tt_match = re.match(r"^tt(\d+)$", input_str, re.IGNORECASE)
    if tt_match:
        return tt_match.group(1)

    # Try plain numeric ID
    if input_str.isdigit() and len(input_str) >= 5:
        return input_str

    return None


def prompt_existing_rating(
    local_title: str, local_year: str | None, local_score: int | None, existing_rating: int
) -> str:
    """Prompt user to decide whether to overwrite an existing IMDb rating.

    Args:
        local_title: Title from the CSV file.
        local_year: Year from the CSV file.
        local_score: User's rating from the CSV file.
        existing_rating: Current rating on IMDb.

    Returns:
        'overwrite', 'skip', or 'quit'.
    """
    beep()
    print("\n" + "=" * 60)
    print("⚠️  EXISTING RATING DETECTED")
    print("=" * 60)
    print(f"  CSV:  '{local_title}' ({local_year}) -> Your new score: {local_score}")
    print(f"  IMDb: Already rated: {existing_rating}/10")
    print("-" * 60)
    while True:
        choice = input("  [O]verwrite / [S]kip / [Q]uit? ").strip().lower()
        if choice in ("o", "overwrite"):
            return "overwrite"
        elif choice in ("s", "skip"):
            return "skip"
        elif choice in ("q", "quit"):
            return "quit"
        print("  Invalid choice. Please enter O, S, or Q.")


def prompt_confirm_match(
    local_title: str,
    local_year: str | None,
    local_director: str | None,
    local_score: int | None,
    imdb_title: str,
    imdb_year: str | None,
    imdb_id: str,
    confidence: float,
    is_low_confidence: bool = False,
    candidates: list | None = None,
) -> str:
    """Prompt user to confirm a match before rating.

    Args:
        local_title: Title from the CSV file.
        local_year: Year from the CSV file.
        local_director: Director from the CSV file.
        local_score: User's rating from the CSV file.
        imdb_title: Matched IMDb title.
        imdb_year: Matched IMDb year.
        imdb_id: IMDb ID (e.g., 'tt1234567').
        confidence: Match confidence score (0-1).
        is_low_confidence: If True, show low confidence warning.
        candidates: Optional list of alternative candidates.

    Returns:
        'apply', 'skip', 'quit', or 'select' (to show candidate selection).
    """
    beep()
    print("\n" + "=" * 60)
    if is_low_confidence:
        print("⚠️  LOW CONFIDENCE MATCH - Please confirm")
    else:
        print("🎬  CONFIRM MATCH")
    print("=" * 60)
    print("  CSV Data (from FilmAffinity):")
    print(f"    Title:    {local_title}")
    print(f"    Year:     {local_year or 'N/A'}")
    print(f"    Director: {local_director or 'N/A'}")
    print(f"    Score:    {local_score}")
    print(f"  IMDb Match (confidence: {confidence:.1%}):")
    print(f"    Title:    {imdb_title}")
    print(f"    Year:     {imdb_year or 'N/A'}")
    print(f"    URL:      https://www.imdb.com/title/{imdb_id}/")
    print("-" * 60)

    has_candidates = candidates and len(candidates) > 1
    if has_candidates:
        prompt = "  [Y]es, rate this (default) / [S]kip / [L]ist other options / [Q]uit? "
    else:
        prompt = "  [Y]es, rate this (default) / [S]kip / [Q]uit? "

    while True:
        choice = input(prompt).strip().lower()
        if choice in ("y", "yes", "a", "apply", ""):
            return "apply"
        elif choice in ("s", "skip", "n", "no"):
            return "skip"
        elif choice in ("q", "quit"):
            return "quit"
        elif choice in ("l", "list", "o", "other", "options") and has_candidates:
            return "select"
        if has_candidates:
            print("  Invalid choice. Please enter Y, S, L, or Q (or press Enter for Yes).")
        else:
            print("  Invalid choice. Please enter Y, S, or Q (or press Enter for Yes).")


def prompt_low_confidence_match(
    local_title: str,
    local_year: str | None,
    local_director: str | None,
    local_score: int | None,
    imdb_title: str,
    imdb_year: str | None,
    imdb_id: str,
    confidence: float,
) -> str:
    """Prompt user to confirm a low-confidence match.

    This is a convenience wrapper for backward compatibility.

    Returns:
        'apply', 'skip', or 'quit'.
    """
    return prompt_confirm_match(
        local_title,
        local_year,
        local_director,
        local_score,
        imdb_title,
        imdb_year,
        imdb_id,
        confidence,
        is_low_confidence=True,
    )


def prompt_select_candidate(
    local_title: str,
    local_year: str | None,
    local_director: str | None,
    local_score: int | None,
    candidates: list[dict],
) -> str | dict:
    """Display a list of IMDb candidates and let user select the correct one.

    Args:
        local_title: Title from the CSV file.
        local_year: Year from the CSV file.
        local_director: Director from the CSV file.
        local_score: User's rating from the CSV file.
        candidates: List of candidate dictionaries from IMDbPY.

    Returns:
        Dict with selected candidate info, 'skip', or 'quit'.
    """
    beep()
    print("\n" + "=" * 70)
    print("🔍  AMBIGUOUS MATCH - Please select the correct movie")
    print("=" * 70)
    print("  CSV Data (from FilmAffinity):")
    print(f"    Title:    {local_title}")
    print(f"    Year:     {local_year or 'N/A'}")
    print(f"    Director: {local_director or 'N/A'}")
    print(f"    Score:    {local_score}")
    print("-" * 70)
    print("  IMDb Candidates:")
    print("-" * 70)

    # Filter and display candidates
    valid_candidates = [c for c in candidates if c.get("movieID")][:8]  # Max 8 options

    if not valid_candidates:
        print("  No candidates found.")
        print("-" * 70)
        print("  [M]anual IMDb ID / [S]kip / [Q]uit?")
        while True:
            choice = input("  Your choice: ").strip().lower()
            if choice in ("s", "skip"):
                return "skip"
            elif choice in ("q", "quit"):
                return "quit"
            elif choice in ("m", "manual"):
                # Prompt for manual IMDb ID entry
                print(
                    "  Enter IMDb ID (e.g., tt1234567) or URL (e.g., https://www.imdb.com/title/tt1234567/):"
                )
                manual_input = input("  IMDb ID/URL: ").strip()
                parsed_id = parse_imdb_id(manual_input)
                if parsed_id:
                    print(f"  Using IMDb ID: tt{parsed_id}")
                    return {
                        "movieID": parsed_id,
                        "title": "Manual Entry",
                        "year": None,
                        "score": 1.0,
                        "selected_by_user": True,
                        "manual_entry": True,
                    }
                else:
                    print("  Invalid IMDb ID or URL. Please try again.")
                    continue
            print("  Invalid choice. Enter M, S, or Q.")

    for i, cand in enumerate(valid_candidates, start=1):
        title = cand.get("title", "Unknown")
        year = cand.get("year", "N/A")
        directors = cand.get("directors", "")
        movie_id = cand.get("movieID", "")
        score = cand.get("base_score", 0)

        # Format the display with clickable IMDb URL
        director_str = f" - {directors}" if directors else ""
        imdb_url = f"https://www.imdb.com/title/tt{movie_id}/"
        print(f"  [{i}] {title} ({year}){director_str}")
        print(f"      {imdb_url}  (confidence: {score:.1%})")

    print("-" * 70)
    print(f"  Enter 1-{len(valid_candidates)} to select, [M]anual IMDb ID, [S]kip, or [Q]uit")

    while True:
        choice = input("  Your choice: ").strip()

        # Check for number selection
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(valid_candidates):
                selected = valid_candidates[num - 1]
                return {
                    "movieID": selected["movieID"],
                    "title": selected["title"],
                    "year": selected["year"],
                    "score": selected["base_score"],
                    "selected_by_user": True,
                }
            else:
                print(f"  Please enter a number between 1 and {len(valid_candidates)}")
                continue

        choice_lower = choice.lower()
        if choice_lower in ("s", "skip"):
            return "skip"
        elif choice_lower in ("q", "quit"):
            return "quit"
        elif choice_lower in ("m", "manual"):
            # Prompt for manual IMDb ID entry
            print(
                "  Enter IMDb ID (e.g., tt1234567) or URL (e.g., https://www.imdb.com/title/tt1234567/):"
            )
            manual_input = input("  IMDb ID/URL: ").strip()
            parsed_id = parse_imdb_id(manual_input)
            if parsed_id:
                print(f"  Using IMDb ID: tt{parsed_id}")
                return {
                    "movieID": parsed_id,
                    "title": "Manual Entry",
                    "year": None,
                    "score": 1.0,
                    "selected_by_user": True,
                    "manual_entry": True,
                }
            else:
                print("  Invalid IMDb ID or URL. Please try again.")
                continue

        print(f"  Invalid choice. Enter 1-{len(valid_candidates)}, M, S, or Q.")
