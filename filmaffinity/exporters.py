"""Export FilmAffinity data to various formats."""

import csv
from itertools import zip_longest
from pathlib import Path
from typing import Any, TextIO, Union


def export_to_letterboxd(films: dict[str, list[Any]], output: Union[str, Path, TextIO]) -> None:
    """Export films dict to Letterboxd-compatible CSV.

    Letterboxd import format: https://letterboxd.com/about/importing-data/

    Args:
        films: Dict with keys 'title', 'year', 'user score', 'original title'
        output: File path or file-like object
    """
    fh: TextIO
    if isinstance(output, (str, Path)):
        fh = open(output, "w", newline="", encoding="utf-8")
        should_close = True
    else:
        fh = output
        should_close = False

    try:
        writer = csv.writer(fh)
        writer.writerow(["Title", "Year", "Rating10", "WatchedDate"])

        titles = films.get("title", [])
        original_titles = films.get("original title", [])
        years = films.get("year", [])
        scores = films.get("user score", [])

        for local, original, year, score in zip_longest(
            titles, original_titles, years, scores, fillvalue=""
        ):
            # Prefer original title if non-empty after stripping whitespace
            original_clean = original.strip() if original else ""
            title = original_clean if original_clean else local
            rating = str(score).strip() if score else ""

            writer.writerow([title, year, rating, ""])
    finally:
        if should_close:
            fh.close()
