"""Data processing functions for IMDb uploader.

This module handles CSV reading, text normalization, and IMDb matching logic.
"""

from __future__ import annotations

import csv
import difflib
import unicodedata
from typing import Any

try:
    # Cinemagoer is the modern fork/rename of IMDbPY
    from imdb import Cinemagoer as IMDbPYClient
except ImportError:
    try:
        from imdb import IMDb as IMDbPYClient
    except ImportError:
        IMDbPYClient = None

from .constants import (
    DIRECTOR_FETCH_CANDIDATE_MIN_SCORE,
    DIRECTOR_FETCH_LIMIT,
    DIRECTOR_LOOKUP_THRESHOLD,
    MAX_RETRIES,
    RATE_LIMIT_COOLDOWN_INITIAL,
    RATE_LIMIT_COOLDOWN_MAX,
    MovieItem,
)


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
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for raw_row in reader:
            # normalize keys: strip, lower-case and remove BOM if present
            row = {}
            for k, v in raw_row.items():
                if k is None:
                    continue
                key = k.strip().lower().lstrip("\ufeff")
                row[key] = v
            # Expect column 'title', 'year', 'user score'
            title = (row.get("title") or row.get("titulo") or "").strip()
            year = (row.get("year") or row.get("anio") or row.get("año") or "").strip()
            score = (
                row.get("user score")
                or row.get("user_score")
                or row.get("userscore")
                or row.get("puntuacion")
            )
            if not title:
                continue
            try:
                scorev = int(float(str(score).replace(",", ".")))
            except (ValueError, TypeError, AttributeError):
                scorev = None
            directors = row.get("directors") or row.get("director") or ""
            original_title = (
                row.get("original title")
                or row.get("original_title")
                or row.get("originaltitle")
                or ""
            ).strip()
            items.append(
                {
                    "title": title,
                    "year": year,
                    "score": scorev,
                    "directors": (directors or "").strip(),
                    "original_title": original_title,
                }
            )
    if not items:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"read_csv: no items parsed from {path}. Detected header fields: {reader.fieldnames}"
        )
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
        return ""
    s = s.strip().lower()
    # remove accents
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    # remove punctuation
    s = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in s)
    # remove common Spanish leading articles to help matching
    for prefix in ("el ", "la ", "los ", "las ", "un ", "una "):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    s = " ".join(s.split())
    return s


def find_imdb_match(
    title: str,
    year: str | None = None,
    ia: Any = None,
    director: str | None = None,
    original_title: str | None = None,
    topn: int = 6,
) -> dict[str, Any] | None:
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

    raw = title or ""
    queries.append(raw)
    # remove parenthetical parts: e.g. 'Pride (Orgullo)' -> 'Pride'
    if "(" in raw:
        queries.append(raw.split("(")[0].strip())
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
    all_candidates: list[dict[str, Any]] = []  # Store all candidates for user selection
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
                import logging

                logger = logging.getLogger(__name__)
                logger.info(f"[imdbpy] searching for: {q!r}")
                results = ia.search_movie(q) or []
                logger.info(f"[imdbpy] -> {len(results)} results for query: {q!r}")
                if results:
                    sample = []
                    for r in results[:5]:
                        try:
                            sample.append(f"{r.get('title')} ({r.get('year')})")
                        except Exception:
                            sample.append(str(r))
                    logger.debug(f"[imdbpy] sample results: {sample}")
                break  # Success, exit retry loop
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                error_str = str(e).lower()
                # Check for HTTP errors (500, 503, etc.) or rate limiting
                is_http_error = (
                    "http error 5" in error_str
                    or "500" in error_str
                    or "503" in error_str
                    or "internal server error" in error_str
                    or "service unavailable" in error_str
                    or "too many requests" in error_str
                    or "429" in error_str
                    or "httperror" in error_str
                )

                if is_http_error and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"[imdbpy] ⚠️  HTTP error detected, cooling down for {cooldown_seconds}s before retry ({attempt + 1}/{MAX_RETRIES})..."
                    )
                    import time

                    time.sleep(cooldown_seconds)
                    # Exponential backoff
                    cooldown_seconds = min(cooldown_seconds * 2, RATE_LIMIT_COOLDOWN_MAX)
                else:
                    logger.warning(f"[imdbpy] search exception for query {q!r}: {e}")
                results = []

        if not results:
            continue

        qnorm = normalize_text(q)

        # First pass: compute base score using title (and year boost) only
        candidates = []  # list of dicts: {cand, cand_title, cand_year, base_score, has_director_info}
        for cand in results[: max(topn, 10)]:
            try:
                cand_title = cand.get("title") or ""
                cand_year = str(cand.get("year") or "")
            except Exception:
                cand_title = ""
                cand_year = ""
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
                d = cand.get("director") or cand.get("directors") or None
                if d:
                    has_director_info = True
                    if isinstance(d, list):
                        for person in d:
                            cand_directors_list.append(
                                person.get("name") if hasattr(person, "get") else str(person)
                            )
                    else:
                        cand_directors_list.append(d.get("name") if hasattr(d, "get") else str(d))
            except Exception:
                has_director_info = False

            candidate_entry = {
                "cand": cand,
                "title": cand_title,
                "year": cand_year,
                "base_score": base_score,
                "has_dir": has_director_info,
                "directors": ", ".join(cand_directors_list) if cand_directors_list else "",
                "movieID": cand.movieID if hasattr(cand, "movieID") else None,
            }
            candidates.append(candidate_entry)

            # Also add to all_candidates for user selection (avoid duplicates by movieID)
            if candidate_entry["movieID"] and not any(
                c["movieID"] == candidate_entry["movieID"] for c in all_candidates
            ):
                all_candidates.append(candidate_entry)

            # keep a quick best based on base_score
            if best is None or base_score > best["score"]:
                best = {
                    "movieID": cand.movieID if hasattr(cand, "movieID") else None,
                    "title": cand_title,
                    "year": cand_year,
                    "score": base_score,
                    "query": q,
                    "result_count": len(results),
                }

        # If title+year alone is confident enough, skip director lookups
        if best and best["score"] >= DIRECTOR_LOOKUP_THRESHOLD:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"[imdbpy] high confidence ({best['score']:.3f}) from title+year; skipping director fetchs"
            )
            best["candidates"] = sorted(
                all_candidates, key=lambda x: x["base_score"], reverse=True
            )[:10]
            return best

        # If director is provided, try to improve score by fetching directors for top candidates
        if director:
            dnorm = normalize_text(director)
            # sort candidates by base_score desc and fetch limited number
            candidates_sorted = sorted(candidates, key=lambda x: x["base_score"], reverse=True)
            fetch_count = 0
            for entry in candidates_sorted:
                if fetch_count >= DIRECTOR_FETCH_LIMIT:
                    break
                if entry["base_score"] < DIRECTOR_FETCH_CANDIDATE_MIN_SCORE:
                    break
                cand = entry["cand"]
                cand_directors = []

                # if search result already included directors, use them first
                try:
                    d = cand.get("director") or cand.get("directors") or None
                    if d:
                        if isinstance(d, list):
                            for person in d:
                                cand_directors.append(
                                    person.get("name") if hasattr(person, "get") else str(person)
                                )
                        else:
                            cand_directors.append(d.get("name") if hasattr(d, "get") else str(d))
                    else:
                        # otherwise fetch details (network call) with retry on HTTP errors
                        for update_attempt in range(2):
                            try:
                                import logging

                                logger = logging.getLogger(__name__)
                                logger.debug(
                                    f"[imdbpy] fetching details for candidate {getattr(cand, 'movieID', '<unknown>')} to read directors"
                                )
                                ia.update(cand)
                                fetch_count += 1
                                d2 = cand.get("director") or cand.get("directors")
                                if d2:
                                    if isinstance(d2, list):
                                        for p in d2:
                                            cand_directors.append(
                                                p.get("name") if hasattr(p, "get") else str(p)
                                            )
                                    else:
                                        cand_directors.append(
                                            d2.get("name") if hasattr(d2, "get") else str(d2)
                                        )
                                break  # Success
                            except Exception as update_err:
                                import logging

                                logger = logging.getLogger(__name__)
                                error_str = str(update_err).lower()
                                is_http_error = (
                                    "http error 5" in error_str
                                    or "500" in error_str
                                    or "503" in error_str
                                    or "httperror" in error_str
                                )
                                if is_http_error and update_attempt == 0:
                                    import logging

                                    logger = logging.getLogger(__name__)
                                    logger.info(
                                        "[imdbpy] ⚠️  HTTP error on update, cooling down 5s..."
                                    )
                                    import time

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

                total_score = entry["base_score"] + director_boost
                # Update entry with director info if we fetched it
                if cand_directors and not entry["directors"]:
                    entry["directors"] = ", ".join(cand_directors)

                if total_score > best["score"]:
                    best = {
                        "movieID": cand.movieID if hasattr(cand, "movieID") else None,
                        "title": entry["title"],
                        "year": entry["year"],
                        "score": total_score,
                        "query": q,
                        "result_count": len(results),
                    }

        # If we already have a pretty good match, stop early
        if best and best["score"] >= DIRECTOR_LOOKUP_THRESHOLD:
            break

    # Add candidates to best result for user selection in ambiguous cases
    # Add candidates to best result for user selection in ambiguous cases
    if best:
        best["candidates"] = sorted(all_candidates, key=lambda x: x["base_score"], reverse=True)[
            :10
        ]
    return best
