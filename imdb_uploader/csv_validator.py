"""CSV format validation for FilmAffinity export files.

This module provides validation functions to check CSV files before processing,
ensuring they have the correct format, required columns, and valid data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of CSV validation.

    Attributes:
        valid: Whether the CSV is valid.
        errors: List of error messages.
        warnings: List of warning messages.
        row_count: Number of data rows (excluding header).
        detected_delimiter: The delimiter detected in the file.
        detected_columns: List of column names found.
    """

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    detected_delimiter: str = ";"
    detected_columns: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        """Add an error and mark validation as failed."""
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        """Add a warning (doesn't fail validation)."""
        self.warnings.append(msg)

    def __str__(self) -> str:
        """Format validation result as string."""
        lines = []
        if self.valid:
            lines.append("✓ CSV validation passed")
            lines.append(f"  Rows: {self.row_count}")
            lines.append(f"  Delimiter: '{self.detected_delimiter}'")
            lines.append(f"  Columns: {', '.join(self.detected_columns)}")
        else:
            lines.append("✗ CSV validation failed")
            for err in self.errors:
                lines.append(f"  ERROR: {err}")
        for warn in self.warnings:
            lines.append(f"  WARNING: {warn}")
        return "\n".join(lines)


# Column name variants (lowercase, normalized)
# Maps canonical name -> list of acceptable variants
COLUMN_VARIANTS = {
    "title": ["title", "titulo", "título"],
    "year": ["year", "anio", "año"],
    "score": ["user score", "user_score", "userscore", "puntuacion", "puntuación", "rating"],
    "directors": ["directors", "director", "directores"],
    "original_title": [
        "original title",
        "original_title",
        "originaltitle",
        "titulo original",
        "título original",
    ],
}

# Required columns (at least one variant must be present)
REQUIRED_COLUMNS = ["title"]

# Recommended columns (warnings if missing)
RECOMMENDED_COLUMNS = ["year", "score"]


def _normalize_column(name: str) -> str:
    """Normalize column name for comparison."""
    if name is None:
        return ""
    return name.strip().lower().lstrip("\ufeff")


def _detect_delimiter(file_path: Path, sample_size: int = 5) -> str:
    """Detect the delimiter used in a CSV file.

    Args:
        file_path: Path to the CSV file.
        sample_size: Number of lines to sample.

    Returns:
        Detected delimiter (';' or ',').
    """
    with open(file_path, encoding="utf-8") as f:
        sample = "".join(f.readline() for _ in range(sample_size))

    # Count occurrences of common delimiters
    semicolon_count = sample.count(";")
    comma_count = sample.count(",")

    # FilmAffinity uses semicolon by default
    if semicolon_count >= comma_count:
        return ";"
    return ","


def _find_column(columns: list[str], canonical_name: str) -> str | None:
    """Find a column matching the canonical name or its variants.

    Args:
        columns: List of normalized column names from the CSV.
        canonical_name: The canonical column name to find.

    Returns:
        The matching column name, or None if not found.
    """
    variants = COLUMN_VARIANTS.get(canonical_name, [canonical_name])
    for col in columns:
        if col in variants:
            return col
    return None


def validate_csv_format(
    file_path: str | Path, require_score: bool = False, max_preview_rows: int = 5
) -> ValidationResult:
    """Validate a CSV file for FilmAffinity/IMDb upload format.

    Checks:
    - File exists and is readable
    - File is valid CSV format
    - Correct delimiter (semicolon or comma)
    - Required columns present (title)
    - Recommended columns present (year, score) - warnings only
    - At least one data row
    - Data integrity (title not empty)

    Args:
        file_path: Path to the CSV file.
        require_score: If True, score column is required (not just recommended).
        max_preview_rows: Maximum rows to check for data validation.

    Returns:
        ValidationResult with errors, warnings, and metadata.
    """
    result = ValidationResult()
    path = Path(file_path)

    # Check file exists
    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    if not path.is_file():
        result.add_error(f"Not a file: {path}")
        return result

    # Check file size (not empty)
    if path.stat().st_size == 0:
        result.add_error("File is empty")
        return result

    # Try to detect delimiter
    try:
        result.detected_delimiter = _detect_delimiter(path)
    except Exception as e:
        result.add_error(f"Could not read file: {e}")
        return result

    # Try to parse as CSV
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=result.detected_delimiter)

            # Get and normalize column names
            if reader.fieldnames is None:
                result.add_error("Could not read CSV header")
                return result

            raw_columns = reader.fieldnames
            normalized_columns = [_normalize_column(c) for c in raw_columns]
            result.detected_columns = [c for c in normalized_columns if c]

            # Check for required columns
            for req_col in REQUIRED_COLUMNS:
                if _find_column(normalized_columns, req_col) is None:
                    variants = COLUMN_VARIANTS.get(req_col, [req_col])
                    result.add_error(
                        f"Missing required column '{req_col}'. "
                        f"Expected one of: {', '.join(variants)}"
                    )

            # Check for recommended columns
            for rec_col in RECOMMENDED_COLUMNS:
                if _find_column(normalized_columns, rec_col) is None:
                    variants = COLUMN_VARIANTS.get(rec_col, [rec_col])
                    if rec_col == "score" and require_score:
                        result.add_error(
                            f"Missing required column '{rec_col}'. "
                            f"Expected one of: {', '.join(variants)}"
                        )
                    else:
                        result.add_warning(
                            f"Missing recommended column '{rec_col}'. "
                            f"Expected one of: {', '.join(variants)}"
                        )

            # Check for data rows
            rows_checked = 0
            empty_title_count = 0

            for row in reader:
                result.row_count += 1
                rows_checked += 1

                # Normalize row keys
                normalized_row = {_normalize_column(k): v for k, v in row.items() if k is not None}

                # Check title
                title_col = _find_column(list(normalized_row.keys()), "title")
                if title_col:
                    title_value = (normalized_row.get(title_col) or "").strip()
                    if not title_value:
                        empty_title_count += 1

                # Only check first N rows for detailed validation
                if rows_checked >= max_preview_rows:
                    # Count remaining rows without detailed checks
                    for _ in reader:
                        result.row_count += 1

            if result.row_count == 0:
                result.add_error("No data rows found (only header)")

            if empty_title_count > 0:
                result.add_warning(f"{empty_title_count} row(s) have empty title (will be skipped)")

    except csv.Error as e:
        result.add_error(f"CSV parsing error: {e}")
    except UnicodeDecodeError as e:
        result.add_error(f"Encoding error (expected UTF-8): {e}")
    except Exception as e:
        result.add_error(f"Unexpected error reading CSV: {e}")

    return result


def validate_csv_strict(file_path: str | Path) -> ValidationResult:
    """Validate CSV with strict requirements (score required).

    Same as validate_csv_format but requires the score column.

    Args:
        file_path: Path to the CSV file.

    Returns:
        ValidationResult with errors, warnings, and metadata.
    """
    return validate_csv_format(file_path, require_score=True)


# Letterboxd CSV format specification
# https://letterboxd.com/about/importing-data/
# Note: Letterboxd uses PascalCase column names
LETTERBOXD_COLUMN_VARIANTS = {
    "title": ["title"],  # Expected: Title
    "year": ["year"],  # Expected: Year
    "rating": ["rating", "rating10"],  # Expected: Rating or Rating10 (1-10 scale)
    "watcheddate": ["watcheddate", "watched date"],  # Expected: WatchedDate
}

# Display names with proper casing for error messages
LETTERBOXD_DISPLAY_NAMES = {
    "title": "Title",
    "year": "Year",
    "rating": "Rating or Rating10",
    "watcheddate": "WatchedDate",
}

LETTERBOXD_REQUIRED_COLUMNS = ["title"]
LETTERBOXD_RECOMMENDED_COLUMNS = ["year", "rating"]


def validate_letterboxd_format(
    file_path: str | Path, max_preview_rows: int = 10
) -> ValidationResult:
    """Validate a CSV file for Letterboxd import format.

    Letterboxd format:
    - Comma-delimited (standard CSV)
    - Required columns: Title
    - Optional columns: Year, Rating10, WatchedDate
    - Rating10 should be 1-10 scale

    Args:
        file_path: Path to the CSV file.
        max_preview_rows: Maximum rows to check for data validation.

    Returns:
        ValidationResult with errors, warnings, and metadata.
    """
    result = ValidationResult()
    path = Path(file_path)

    # Check file exists
    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    if not path.is_file():
        result.add_error(f"Not a file: {path}")
        return result

    if path.stat().st_size == 0:
        result.add_error("File is empty")
        return result

    # Letterboxd uses comma delimiter
    result.detected_delimiter = ","

    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=",")

            if reader.fieldnames is None:
                result.add_error("Could not read CSV header")
                return result

            raw_columns = reader.fieldnames
            normalized_columns = [_normalize_column(c) for c in raw_columns]
            result.detected_columns = [c for c in normalized_columns if c]

            # Check for required columns
            for req_col in LETTERBOXD_REQUIRED_COLUMNS:
                variants = LETTERBOXD_COLUMN_VARIANTS.get(req_col, [req_col])
                display_name = LETTERBOXD_DISPLAY_NAMES.get(req_col, req_col)
                if not any(col in variants for col in normalized_columns):
                    result.add_error(f"Missing required column '{display_name}'")

            # Check for recommended columns
            for rec_col in LETTERBOXD_RECOMMENDED_COLUMNS:
                variants = LETTERBOXD_COLUMN_VARIANTS.get(rec_col, [rec_col])
                display_name = LETTERBOXD_DISPLAY_NAMES.get(rec_col, rec_col)
                if not any(col in variants for col in normalized_columns):
                    result.add_warning(f"Missing recommended column '{display_name}'")

            # Check data rows
            rows_checked = 0
            empty_title_count = 0
            invalid_rating_count = 0

            for row in reader:
                result.row_count += 1
                rows_checked += 1

                if rows_checked <= max_preview_rows:
                    normalized_row = {
                        _normalize_column(k): v for k, v in row.items() if k is not None
                    }

                    # Check title
                    title_value = (normalized_row.get("title") or "").strip()
                    if not title_value:
                        empty_title_count += 1

                    # Check rating is valid (1-10)
                    rating_value = (
                        normalized_row.get("rating10") or normalized_row.get("rating") or ""
                    ).strip()
                    if rating_value:
                        try:
                            rating_num = float(rating_value)
                            if rating_num < 0.5 or rating_num > 10:
                                invalid_rating_count += 1
                        except ValueError:
                            invalid_rating_count += 1
                else:
                    # Count remaining rows
                    for _ in reader:
                        result.row_count += 1

            if result.row_count == 0:
                result.add_error("No data rows found (only header)")

            if empty_title_count > 0:
                result.add_warning(f"{empty_title_count} row(s) have empty title")

            if invalid_rating_count > 0:
                result.add_warning(
                    f"{invalid_rating_count} row(s) have invalid rating " "(should be 0.5-10)"
                )

    except csv.Error as e:
        result.add_error(f"CSV parsing error: {e}")
    except UnicodeDecodeError as e:
        result.add_error(f"Encoding error (expected UTF-8): {e}")
    except Exception as e:
        result.add_error(f"Unexpected error reading CSV: {e}")

    return result


def quick_validate(file_path: str | Path) -> bool:
    """Quick validation check - returns True if valid, False otherwise.

    Args:
        file_path: Path to the CSV file.

    Returns:
        True if the CSV is valid, False otherwise.
    """
    result = validate_csv_format(file_path)
    return result.valid
