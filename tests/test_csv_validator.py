"""
Unit tests for imdb_uploader/csv_validator.py

Tests for CSV validation functions used to validate FilmAffinity export files
before processing. These are pure functions without external dependencies.
"""

import tempfile
from pathlib import Path

from imdb_uploader.csv_validator import (
    COLUMN_VARIANTS,
    LETTERBOXD_COLUMN_VARIANTS,
    LETTERBOXD_REQUIRED_COLUMNS,
    RECOMMENDED_COLUMNS,
    REQUIRED_COLUMNS,
    ValidationResult,
    _detect_delimiter,
    _find_column,
    _normalize_column,
    quick_validate,
    validate_csv_format,
    validate_csv_strict,
    validate_letterboxd_format,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_default_values(self):
        result = ValidationResult()
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.row_count == 0
        assert result.detected_delimiter == ";"
        assert result.detected_columns == []

    def test_add_error(self):
        result = ValidationResult()
        result.add_error("Test error")
        assert result.valid is False
        assert "Test error" in result.errors

    def test_add_multiple_errors(self):
        result = ValidationResult()
        result.add_error("Error 1")
        result.add_error("Error 2")
        assert result.valid is False
        assert len(result.errors) == 2
        assert "Error 1" in result.errors
        assert "Error 2" in result.errors

    def test_add_warning(self):
        result = ValidationResult()
        result.add_warning("Test warning")
        assert result.valid is True  # Warnings don't fail validation
        assert "Test warning" in result.warnings

    def test_str_valid_result(self):
        result = ValidationResult()
        result.row_count = 10
        result.detected_delimiter = ";"
        result.detected_columns = ["title", "year"]
        output = str(result)
        assert "✓ CSV validation passed" in output
        assert "Rows: 10" in output
        assert "Delimiter: ';'" in output
        assert "title" in output
        assert "year" in output

    def test_str_invalid_result(self):
        result = ValidationResult()
        result.add_error("Missing required column")
        output = str(result)
        assert "✗ CSV validation failed" in output
        assert "ERROR: Missing required column" in output

    def test_str_with_warnings(self):
        result = ValidationResult()
        result.row_count = 5
        result.detected_columns = ["title"]
        result.add_warning("Missing recommended column 'year'")
        output = str(result)
        assert "WARNING: Missing recommended column 'year'" in output


class TestNormalizeColumn:
    """Tests for _normalize_column function."""

    def test_empty_string(self):
        assert _normalize_column("") == ""

    def test_none_input(self):
        assert _normalize_column(None) == ""

    def test_basic_lowercase(self):
        assert _normalize_column("TITLE") == "title"

    def test_strip_whitespace(self):
        assert _normalize_column("  title  ") == "title"

    def test_remove_bom(self):
        # BOM character at start of file
        assert _normalize_column("\ufefftitle") == "title"

    def test_combined_normalization(self):
        assert _normalize_column("  \ufeffTITLE  ") == "title"


class TestDetectDelimiter:
    """Tests for _detect_delimiter function."""

    def test_detect_semicolon(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")
            f.write("The Godfather;1972;10\n")
            f.flush()
            path = Path(f.name)
        try:
            assert _detect_delimiter(path) == ";"
        finally:
            path.unlink()

    def test_detect_comma(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title,year,score\n")
            f.write("The Godfather,1972,10\n")
            f.flush()
            path = Path(f.name)
        try:
            assert _detect_delimiter(path) == ","
        finally:
            path.unlink()

    def test_prefer_semicolon_when_equal(self):
        """FilmAffinity default is semicolon, so prefer it when counts are equal."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            # Equal counts: should prefer semicolon
            f.write("title;year\n")
            f.write("a,b\n")
            f.flush()
            path = Path(f.name)
        try:
            assert _detect_delimiter(path) == ";"
        finally:
            path.unlink()


class TestFindColumn:
    """Tests for _find_column function."""

    def test_exact_match(self):
        columns = ["title", "year", "score"]
        assert _find_column(columns, "title") == "title"

    def test_find_variant(self):
        columns = ["titulo", "anio", "puntuacion"]
        assert _find_column(columns, "title") == "titulo"
        assert _find_column(columns, "year") == "anio"
        assert _find_column(columns, "score") == "puntuacion"

    def test_not_found(self):
        columns = ["title", "year"]
        assert _find_column(columns, "score") is None

    def test_unknown_canonical_name(self):
        columns = ["foo", "bar"]
        assert _find_column(columns, "unknown") is None


class TestValidateCsvFormat:
    """Tests for validate_csv_format function."""

    def test_valid_csv_basic(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.write("The Godfather;1972;10\n")
            f.write("Pulp Fiction;1994;9\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert result.row_count == 2
            assert result.detected_delimiter == ";"
        finally:
            Path(path).unlink()

    def test_file_not_found(self):
        result = validate_csv_format("/nonexistent/path/file.csv")
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is False
            assert any("empty" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_missing_required_column(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("year;score\n")  # Missing 'title'
            f.write("1972;10\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is False
            assert any("title" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_missing_recommended_columns_warning(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title\n")  # Missing 'year' and 'score'
            f.write("The Godfather\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True  # Warnings don't fail validation
            assert len(result.warnings) >= 1  # Should have warnings for missing columns
        finally:
            Path(path).unlink()

    def test_no_data_rows(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")  # Header only
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is False
            assert any("no data rows" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_empty_title_warning(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year\n")
            f.write(";1972\n")  # Empty title
            f.write("Pulp Fiction;1994\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert result.row_count == 2
            assert any("empty title" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()

    def test_require_score_option(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year\n")  # Missing 'score'
            f.write("The Godfather;1972\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path, require_score=True)
            assert result.valid is False  # Score required, so should fail
        finally:
            Path(path).unlink()

    def test_spanish_column_names(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("titulo;año;puntuación\n")
            f.write("El Padrino;1972;10\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
        finally:
            Path(path).unlink()

    def test_directory_instead_of_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_csv_format(tmpdir)
            assert result.valid is False
            assert any("not a file" in e.lower() for e in result.errors)

    def test_comma_delimiter(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title,year,user score\n")
            f.write("The Godfather,1972,10\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert result.detected_delimiter == ","
        finally:
            Path(path).unlink()


class TestValidateCsvStrict:
    """Tests for validate_csv_strict function."""

    def test_strict_requires_score(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year\n")  # Missing 'score'
            f.write("The Godfather;1972\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_strict(path)
            assert result.valid is False
        finally:
            Path(path).unlink()

    def test_strict_with_score(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.write("The Godfather;1972;10\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_strict(path)
            assert result.valid is True
        finally:
            Path(path).unlink()


class TestValidateLetterboxdFormat:
    """Tests for validate_letterboxd_format function."""

    def test_valid_letterboxd_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10,WatchedDate\n")
            f.write("The Godfather,1972,10,2024-01-01\n")
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is True
            assert result.row_count == 1
            assert result.detected_delimiter == ","
        finally:
            Path(path).unlink()

    def test_letterboxd_missing_title(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Year,Rating10\n")  # Missing 'Title'
            f.write("1972,10\n")
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is False
            assert any("title" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_letterboxd_invalid_rating(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")
            f.write("The Godfather,1972,15\n")  # Rating > 10
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is True  # Invalid rating is a warning
            assert any("invalid rating" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()

    def test_letterboxd_file_not_found(self):
        result = validate_letterboxd_format("/nonexistent/file.csv")
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_letterboxd_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is False
            assert any("empty" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_letterboxd_empty_title_warning(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year\n")
            f.write(",1972\n")  # Empty title
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert any("empty title" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()

    def test_letterboxd_no_data_rows(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")  # Header only
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is False
            assert any("no data rows" in e.lower() for e in result.errors)
        finally:
            Path(path).unlink()

    def test_letterboxd_negative_rating(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")
            f.write("The Godfather,1972,-1\n")  # Negative rating
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert any("invalid rating" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()


class TestQuickValidate:
    """Tests for quick_validate function."""

    def test_quick_validate_valid_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")
            f.write("The Godfather;1972;10\n")
            f.flush()
            path = f.name
        try:
            assert quick_validate(path) is True
        finally:
            Path(path).unlink()

    def test_quick_validate_invalid_file(self):
        assert quick_validate("/nonexistent/file.csv") is False

    def test_quick_validate_missing_required_column(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("year;score\n")  # Missing title
            f.write("1972;10\n")
            f.flush()
            path = f.name
        try:
            assert quick_validate(path) is False
        finally:
            Path(path).unlink()


class TestModuleConstants:
    """Tests to verify module constants are properly defined."""

    def test_column_variants_has_title(self):
        assert "title" in COLUMN_VARIANTS
        assert "titulo" in COLUMN_VARIANTS["title"]

    def test_column_variants_has_year(self):
        assert "year" in COLUMN_VARIANTS
        assert "año" in COLUMN_VARIANTS["year"]

    def test_column_variants_has_score(self):
        assert "score" in COLUMN_VARIANTS
        assert "user score" in COLUMN_VARIANTS["score"]
        assert "puntuación" in COLUMN_VARIANTS["score"]

    def test_required_columns(self):
        assert "title" in REQUIRED_COLUMNS

    def test_recommended_columns(self):
        assert "year" in RECOMMENDED_COLUMNS
        assert "score" in RECOMMENDED_COLUMNS

    def test_letterboxd_column_variants(self):
        assert "title" in LETTERBOXD_COLUMN_VARIANTS
        assert "rating" in LETTERBOXD_COLUMN_VARIANTS

    def test_letterboxd_required_columns(self):
        assert "title" in LETTERBOXD_REQUIRED_COLUMNS


class TestValidateCsvFormatEdgeCases:
    """Additional edge case tests for validate_csv_format."""

    def test_csv_with_bom(self):
        """Test handling of UTF-8 BOM in CSV files."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            # Write UTF-8 BOM followed by content
            f.write(b"\xef\xbb\xbftitle;year;score\n")
            f.write(b"The Godfather;1972;10\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert "title" in result.detected_columns
        finally:
            Path(path).unlink()

    def test_csv_with_extra_columns(self):
        """Test CSV with additional columns beyond expected ones."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score;extra_col1;extra_col2\n")
            f.write("The Godfather;1972;10;value1;value2\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert "extra_col1" in result.detected_columns
        finally:
            Path(path).unlink()

    def test_csv_with_quoted_fields(self):
        """Test CSV with quoted fields containing delimiters."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")
            f.write('"Movie; with semicolon";1972;10\n')
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert result.row_count == 1
        finally:
            Path(path).unlink()

    def test_csv_with_unicode_content(self):
        """Test CSV with various Unicode characters."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")
            f.write("日本語タイトル;2020;9\n")
            f.write("Ελληνικός τίτλος;2021;8\n")
            f.write("Título español ñ;2022;7\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path)
            assert result.valid is True
            assert result.row_count == 3
        finally:
            Path(path).unlink()

    def test_csv_path_as_pathlib(self):
        """Test that Path objects work as input."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year\n")
            f.write("Test Movie;2020\n")
            f.flush()
            path = Path(f.name)
        try:
            result = validate_csv_format(path)  # Pass Path object
            assert result.valid is True
        finally:
            path.unlink()

    def test_csv_with_many_rows(self):
        """Test CSV with many rows exceeds max_preview_rows."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;score\n")
            for i in range(100):
                f.write(f"Movie {i};2020;8\n")
            f.flush()
            path = f.name
        try:
            result = validate_csv_format(path, max_preview_rows=5)
            assert result.valid is True
            assert result.row_count == 100
        finally:
            Path(path).unlink()


class TestValidateLetterboxdFormatEdgeCases:
    """Additional edge case tests for validate_letterboxd_format."""

    def test_letterboxd_with_decimal_rating(self):
        """Test Letterboxd CSV with decimal ratings (valid range 0.5-10)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")
            f.write("The Godfather,1972,9.5\n")
            f.write("Pulp Fiction,1994,8.5\n")
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is True
            assert len(result.warnings) == 0
        finally:
            Path(path).unlink()

    def test_letterboxd_with_non_numeric_rating(self):
        """Test Letterboxd CSV with non-numeric rating value."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")
            f.write("The Godfather,1972,excellent\n")
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert any("invalid rating" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()

    def test_letterboxd_using_rating_column(self):
        """Test Letterboxd CSV using 'Rating' instead of 'Rating10'."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating\n")
            f.write("The Godfather,1972,9\n")
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is True
        finally:
            Path(path).unlink()

    def test_letterboxd_directory_instead_of_file(self):
        """Test Letterboxd validation with directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_letterboxd_format(tmpdir)
            assert result.valid is False
            assert any("not a file" in e.lower() for e in result.errors)

    def test_letterboxd_rating_at_boundary(self):
        """Test Letterboxd ratings at valid boundaries (0.5 and 10)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("Title,Year,Rating10\n")
            f.write("Movie1,2020,0.5\n")  # Minimum valid
            f.write("Movie2,2021,10\n")  # Maximum valid
            f.flush()
            path = f.name
        try:
            result = validate_letterboxd_format(path)
            assert result.valid is True
            # Should have no invalid rating warnings
            assert not any("invalid rating" in w.lower() for w in result.warnings)
        finally:
            Path(path).unlink()
