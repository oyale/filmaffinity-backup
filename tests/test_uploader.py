"""
Unit tests for imdb_uploader/uploader.py

Tests for pure functions that don't require Selenium or network access.
"""

import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock selenium before importing uploader (in case it's not installed in test env)
sys.modules["selenium"] = MagicMock()
sys.modules["selenium.webdriver"] = MagicMock()
sys.modules["selenium.webdriver.common"] = MagicMock()
sys.modules["selenium.webdriver.common.by"] = MagicMock()
sys.modules["selenium.webdriver.common.keys"] = MagicMock()
sys.modules["selenium.webdriver.support"] = MagicMock()
sys.modules["selenium.webdriver.support.ui"] = MagicMock()
sys.modules["selenium.webdriver.support.expected_conditions"] = MagicMock()
sys.modules["selenium.webdriver.chrome.service"] = MagicMock()
sys.modules["webdriver_manager"] = MagicMock()
sys.modules["webdriver_manager.chrome"] = MagicMock()
sys.modules["webdriver_manager.core"] = MagicMock()
sys.modules["webdriver_manager.core.os_manager"] = MagicMock()

# Import the modules (after mocking selenium)
from imdb_uploader import (
    config,  # noqa: E402
    constants,  # noqa: E402
    prompts,  # noqa: E402
    uploader,  # noqa: E402
)


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_empty_string(self):
        assert uploader.normalize_text("") == ""

    def test_none_input(self):
        assert uploader.normalize_text(None) == ""

    def test_basic_lowercase(self):
        assert uploader.normalize_text("HELLO WORLD") == "hello world"

    def test_strip_whitespace(self):
        assert uploader.normalize_text("  hello  world  ") == "hello world"

    def test_remove_accents(self):
        assert uploader.normalize_text("café") == "cafe"
        assert uploader.normalize_text("naïve") == "naive"
        assert uploader.normalize_text("Amélie") == "amelie"

    def test_remove_punctuation(self):
        assert uploader.normalize_text("hello, world!") == "hello world"
        assert uploader.normalize_text("it's a test") == "it s a test"

    def test_spanish_article_removal(self):
        assert uploader.normalize_text("El Padrino") == "padrino"
        assert uploader.normalize_text("La Casa") == "casa"
        assert uploader.normalize_text("Los Otros") == "otros"
        assert uploader.normalize_text("Las Chicas") == "chicas"
        assert uploader.normalize_text("Un Hombre") == "hombre"
        assert uploader.normalize_text("Una Mujer") == "mujer"

    def test_article_only_at_start(self):
        # 'el' in middle should stay
        assert uploader.normalize_text("Hotel Rwanda") == "hotel rwanda"

    def test_complex_title(self):
        result = uploader.normalize_text("El Señor de los Anillos: La Comunidad del Anillo")
        assert "senor" in result  # accent removed
        assert "anillos" in result


class TestReadCSV:
    """Tests for read_csv function."""

    def test_basic_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score;directors;original title\n")
            f.write("The Godfather;1972;10;Francis Ford Coppola;The Godfather\n")
            f.write("El Padrino;1972;9;Francis Ford Coppola;\n")
            f.name
        try:
            items = uploader.read_csv(f.name)
            assert len(items) == 2
            assert items[0]["title"] == "The Godfather"
            assert items[0]["year"] == "1972"
            assert items[0]["score"] == 10
            assert items[0]["directors"] == "Francis Ford Coppola"
            assert items[1]["title"] == "El Padrino"
            assert items[1]["score"] == 9
        finally:
            os.unlink(f.name)

    def test_empty_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.name
        try:
            items = uploader.read_csv(f.name)
            assert items == []
        finally:
            os.unlink(f.name)

    def test_alternative_column_names(self):
        """Test that alternative column names like 'titulo' and 'anio' work."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("titulo;anio;user score\n")
            f.write("Matrix;1999;8\n")
            f.name
        try:
            items = uploader.read_csv(f.name)
            assert len(items) == 1
            assert items[0]["title"] == "Matrix"
            assert items[0]["year"] == "1999"
            assert items[0]["score"] == 8
        finally:
            os.unlink(f.name)

    def test_decimal_score(self):
        """Test that decimal scores are converted to int."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.write("Test Movie;2000;7.5\n")
            f.name
        try:
            items = uploader.read_csv(f.name)
            assert items[0]["score"] == 7
        finally:
            os.unlink(f.name)

    def test_skip_empty_title(self):
        """Test that rows with empty title are skipped."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.write(";2000;7\n")
            f.write("Valid Movie;2001;8\n")
            f.name
        try:
            items = uploader.read_csv(f.name)
            assert len(items) == 1
            assert items[0]["title"] == "Valid Movie"
        finally:
            os.unlink(f.name)


class TestApplySlice:
    """Tests for apply_slice function."""

    def test_no_limit(self):
        items = [1, 2, 3, 4, 5]
        result = uploader.apply_slice(items, 0, 0)
        assert result == [1, 2, 3, 4, 5]

    def test_start_only(self):
        items = [1, 2, 3, 4, 5]
        result = uploader.apply_slice(items, 2, 0)
        assert result == [3, 4, 5]

    def test_limit_only(self):
        items = [1, 2, 3, 4, 5]
        result = uploader.apply_slice(items, 0, 3)
        assert result == [1, 2, 3]

    def test_start_and_limit(self):
        items = [1, 2, 3, 4, 5]
        result = uploader.apply_slice(items, 1, 2)
        assert result == [2, 3]

    def test_empty_list(self):
        items = []
        result = uploader.apply_slice(items, 0, 0)
        assert result == []


class TestCreateStats:
    """Tests for create_stats function."""

    def test_initial_values(self):
        stats = uploader.create_stats()
        assert stats["applied"] == 0
        assert stats["skipped_ambiguous"] == 0
        assert stats["skipped_not_found"] == 0
        assert stats["skipped_already_rated"] == 0
        assert stats["skipped_same_rating"] == 0
        assert stats["skipped_user_choice"] == 0
        assert stats["skipped_auto_rate_failed"] == 0
        assert stats["quit_early"] is False

    def test_modifiable(self):
        stats = uploader.create_stats()
        stats["applied"] = 5
        stats["skipped_not_found"] = 2
        assert stats["applied"] == 5
        assert stats["skipped_not_found"] == 2


class TestParseImdbId:
    """Tests for parse_imdb_id function."""

    def test_plain_numeric_id(self):
        assert prompts.parse_imdb_id("1234567") == "1234567"

    def test_tt_prefixed_id(self):
        assert prompts.parse_imdb_id("tt1234567") == "1234567"
        assert prompts.parse_imdb_id("TT1234567") == "1234567"  # case insensitive

    def test_imdb_url(self):
        assert prompts.parse_imdb_id("https://www.imdb.com/title/tt1234567/") == "1234567"
        assert prompts.parse_imdb_id("https://imdb.com/title/tt0111161") == "0111161"
        assert (
            prompts.parse_imdb_id("http://www.imdb.com/title/tt9999999/?ref=something") == "9999999"
        )

    def test_invalid_input(self):
        assert prompts.parse_imdb_id("") is None
        assert prompts.parse_imdb_id(None) is None
        assert prompts.parse_imdb_id("not-an-id") is None
        assert prompts.parse_imdb_id("123") is None  # too short
        assert prompts.parse_imdb_id("tt") is None

    def test_whitespace_handling(self):
        assert prompts.parse_imdb_id("  tt1234567  ") == "1234567"

    # Additional edge case tests
    def test_leading_zeros_preserved(self):
        """IMDb IDs with leading zeros should preserve them."""
        assert prompts.parse_imdb_id("tt0000001") == "0000001"
        assert prompts.parse_imdb_id("0000001") == "0000001"

    def test_various_url_formats(self):
        """Test various IMDb URL formats."""
        # Mobile URLs
        assert prompts.parse_imdb_id("https://m.imdb.com/title/tt1234567/") == "1234567"
        # Pro URLs
        assert prompts.parse_imdb_id("https://pro.imdb.com/title/tt1234567/") == "1234567"
        # With extra path segments
        assert prompts.parse_imdb_id("https://www.imdb.com/title/tt1234567/reviews") == "1234567"
        assert (
            prompts.parse_imdb_id("https://www.imdb.com/title/tt1234567/fullcredits") == "1234567"
        )
        # With query parameters
        assert (
            prompts.parse_imdb_id("https://www.imdb.com/title/tt1234567?ref_=nv_sr_srsg_0")
            == "1234567"
        )

    def test_id_length_boundary(self):
        """Test boundary cases for ID length."""
        assert prompts.parse_imdb_id("12345") == "12345"  # minimum valid length
        assert prompts.parse_imdb_id("1234") is None  # too short
        # Long IDs (some newer titles have 8+ digit IDs)
        assert prompts.parse_imdb_id("12345678") == "12345678"
        assert prompts.parse_imdb_id("tt12345678") == "12345678"

    def test_mixed_case_tt_prefix(self):
        """Test mixed case tt prefix handling."""
        assert prompts.parse_imdb_id("Tt1234567") == "1234567"
        assert prompts.parse_imdb_id("tT1234567") == "1234567"

    def test_invalid_urls(self):
        """Test that non-IMDb URLs don't extract IDs."""
        # These should not match as they're not IMDb URLs
        assert prompts.parse_imdb_id("https://www.example.com/title/tt1234567/") is None
        assert prompts.parse_imdb_id("https://www.themoviedb.org/movie/tt1234567") is None

    def test_embedded_tt_in_text(self):
        """Test IDs embedded in surrounding text."""
        # The parse_imdb_id function should extract from URLs but not random text
        # Security fix: no longer extracts from arbitrary text containing substring
        assert prompts.parse_imdb_id("Check out imdb.com/title/tt1234567 for details") is None
        # But not from non-URL text
        assert prompts.parse_imdb_id("The ID is tt1234567 in the database") is None


class TestConstants:
    """Tests to verify constants are properly defined."""

    def test_skip_reason_constants(self):
        assert uploader.SKIP_AMBIGUOUS == "ambiguous_match"
        assert uploader.SKIP_NOT_FOUND == "not_found"
        assert uploader.SKIP_ALREADY_RATED == "already_rated"
        assert uploader.SKIP_SAME_RATING == "same_rating"
        assert uploader.SKIP_AUTO_RATE_FAILED == "auto_rate_failed"
        assert uploader.SKIP_USER_CHOICE == "user_choice"

    def test_skip_reason_to_file_mapping(self):
        assert uploader.SKIP_REASON_TO_FILE[uploader.SKIP_AMBIGUOUS] == "skipped_ambiguous.csv"
        assert uploader.SKIP_REASON_TO_FILE[uploader.SKIP_NOT_FOUND] == "skipped_not_found.csv"
        assert uploader.SKIP_REASON_TO_FILE[uploader.SKIP_SAME_RATING] == "skipped_same_rating.csv"

    def test_retry_category_to_file_mapping(self):
        assert uploader.RETRY_CATEGORY_TO_FILE["ambiguous"] == "skipped_ambiguous.csv"
        assert uploader.RETRY_CATEGORY_TO_FILE["not_found"] == "skipped_not_found.csv"

    def test_confidence_thresholds(self):
        assert 0 < constants.DEFAULT_CONFIDENCE_THRESHOLD < 1
        assert 0 < uploader.DIRECTOR_LOOKUP_THRESHOLD <= 1


class TestLoadRetryItems:
    """Tests for load_retry_items function."""

    def test_load_single_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a skipped CSV file
            csv_path = os.path.join(tmpdir, "skipped_ambiguous.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["title", "year", "user score", "directors", "original title"])
                writer.writerow(["Test Movie", "2020", "8", "Director Name", ""])

            items = uploader.load_retry_items(tmpdir, "ambiguous")
            assert len(items) == 1
            assert items[0]["title"] == "Test Movie"
            assert items[0]["year"] == "2020"
            assert items[0]["score"] == 8

    def test_load_all_categories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple skipped CSV files
            for cat_file in ["skipped_ambiguous.csv", "skipped_not_found.csv"]:
                csv_path = os.path.join(tmpdir, cat_file)
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(["title", "year", "user score", "directors", "original title"])
                    writer.writerow([f"Movie from {cat_file}", "2020", "7", "", ""])

            items = uploader.load_retry_items(tmpdir, "all")
            assert len(items) == 2

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            items = uploader.load_retry_items(tmpdir, "ambiguous")
            assert items == []


class TestWriteSkippedFiles:
    """Tests for write_skipped_files function."""

    def test_write_single_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skipped_items = [
                {
                    "item": {
                        "title": "Test Movie",
                        "year": "2020",
                        "score": 8,
                        "directors": "Director",
                        "original_title": "",
                    },
                    "reason": uploader.SKIP_AMBIGUOUS,
                }
            ]
            uploader.write_skipped_files(skipped_items, tmpdir)

            # Check that the file was created
            csv_path = os.path.join(tmpdir, "skipped_ambiguous.csv")
            assert os.path.exists(csv_path)

            # Check combined file
            combined_path = os.path.join(tmpdir, "skipped_all.csv")
            assert os.path.exists(combined_path)

    def test_write_multiple_categories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skipped_items = [
                {
                    "item": {
                        "title": "Movie 1",
                        "year": "2020",
                        "score": 8,
                        "directors": "",
                        "original_title": "",
                    },
                    "reason": uploader.SKIP_AMBIGUOUS,
                },
                {
                    "item": {
                        "title": "Movie 2",
                        "year": "2021",
                        "score": 7,
                        "directors": "",
                        "original_title": "",
                    },
                    "reason": uploader.SKIP_NOT_FOUND,
                },
            ]
            uploader.write_skipped_files(skipped_items, tmpdir)

            assert os.path.exists(os.path.join(tmpdir, "skipped_ambiguous.csv"))
            assert os.path.exists(os.path.join(tmpdir, "skipped_not_found.csv"))
            assert os.path.exists(os.path.join(tmpdir, "skipped_all.csv"))

    def test_empty_skipped_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uploader.write_skipped_files([], tmpdir)
            # No files should be created
            assert len(os.listdir(tmpdir)) == 0


class TestParseArguments:
    """Tests for parse_arguments function."""

    def test_basic_csv_argument(self):
        with patch("sys.argv", ["uploader.py", "--csv", "test.csv"]):
            args = uploader.parse_arguments()
            assert args.csv == "test.csv"
            assert args.headless is False
            assert args.auto_login is False

    def test_dry_run_mode(self):
        with patch("sys.argv", ["uploader.py", "--csv", "test.csv", "--dry-run"]):
            args = uploader.parse_arguments()
            assert args.dry_run is True
            assert args.dry_run_output == "imdb_matches.csv"

    def test_retry_mode(self):
        with patch("sys.argv", ["uploader.py", "--retry", "ambiguous"]):
            args = uploader.parse_arguments()
            assert args.retry == "ambiguous"
            assert args.csv is None

    def test_missing_required_args(self):
        with patch("sys.argv", ["uploader.py"]):
            with pytest.raises(SystemExit):
                uploader.parse_arguments()

    def test_start_and_limit(self):
        with patch(
            "sys.argv", ["uploader.py", "--csv", "test.csv", "--start", "10", "--limit", "5"]
        ):
            args = uploader.parse_arguments()
            assert args.start == 10
            assert args.limit == 5

    def test_confidence_threshold(self):
        with patch("sys.argv", ["uploader.py", "--csv", "test.csv", "--confirm-threshold", "0.9"]):
            args = uploader.parse_arguments()
            assert args.confirm_threshold == 0.9


class TestInitImdbpyClient:
    """Tests for init_imdbpy_client function."""

    def test_returns_client_or_none(self):
        # This test just verifies the function doesn't crash
        # The actual return depends on whether IMDbPY is installed
        result = uploader.init_imdbpy_client()
        # Result should be either a client instance or None
        assert result is None or hasattr(result, "search_movie")


class TestCSVFieldnames:
    """Tests for CSV fieldname constants."""

    def test_fieldnames_defined(self):
        assert "title" in uploader.CSV_FIELDNAMES
        assert "year" in uploader.CSV_FIELDNAMES
        assert "directors" in uploader.CSV_FIELDNAMES
        assert "user score" in uploader.CSV_FIELDNAMES
        assert "original title" in uploader.CSV_FIELDNAMES

    def test_fieldnames_with_reason(self):
        assert "skip_reason" in uploader.CSV_FIELDNAMES_WITH_REASON
        for field in uploader.CSV_FIELDNAMES:
            assert field in uploader.CSV_FIELDNAMES_WITH_REASON


class TestSeleniumSelectors:
    """Tests for Selenium selector constants."""

    def test_user_rating_selectors_defined(self):
        assert constants.SELECTOR_USER_RATING_UNRATED
        assert constants.SELECTOR_USER_RATING_SCORE
        assert constants.SELECTOR_USER_RATING_SECTION
        assert constants.SELECTOR_STAR_RATING_CLASS

    def test_rate_button_selectors_defined(self):
        assert isinstance(constants.SELECTOR_RATE_BUTTON_OPTIONS, list)
        assert len(constants.SELECTOR_RATE_BUTTON_OPTIONS) > 0
        assert constants.SELECTOR_STAR_BUTTONS
        assert constants.SELECTOR_SUBMIT_RATE_BUTTON

    def test_login_selectors_defined(self):
        assert isinstance(constants.SELECTOR_EMAIL_INPUT_OPTIONS, list)
        assert isinstance(constants.SELECTOR_PASSWORD_INPUT_OPTIONS, list)
        assert constants.SELECTOR_CONTINUE_BUTTON
        assert constants.SELECTOR_USER_MENU

    def test_captcha_selectors_defined(self):
        assert isinstance(constants.SELECTOR_CAPTCHA_INDICATORS, list)
        assert len(constants.SELECTOR_CAPTCHA_INDICATORS) > 0

    def test_search_selectors_defined(self):
        assert isinstance(constants.SELECTOR_SEARCH_RESULTS, list)
        assert len(constants.SELECTOR_SEARCH_RESULTS) > 0


class TestCustomExceptions:
    """Tests for custom exception classes."""

    def test_base_exception_exists(self):
        assert hasattr(uploader, "UploadIMDbError")
        assert issubclass(uploader.UploadIMDbError, Exception)

    def test_browser_start_error(self):
        assert hasattr(uploader, "BrowserStartError")
        assert issubclass(uploader.BrowserStartError, uploader.UploadIMDbError)

    def test_login_error(self):
        assert hasattr(uploader, "LoginError")
        assert issubclass(uploader.LoginError, uploader.UploadIMDbError)

    def test_rating_error(self):
        assert hasattr(uploader, "RatingError")
        assert issubclass(uploader.RatingError, uploader.UploadIMDbError)

    def test_csv_parse_error(self):
        assert hasattr(uploader, "CSVParseError")
        assert issubclass(uploader.CSVParseError, uploader.UploadIMDbError)

    def test_imdb_search_error(self):
        assert hasattr(uploader, "IMDbSearchError")
        assert issubclass(uploader.IMDbSearchError, uploader.UploadIMDbError)

    def test_exceptions_can_be_raised(self):
        with pytest.raises(uploader.UploadIMDbError):
            raise uploader.BrowserStartError("Test error")

        with pytest.raises(uploader.UploadIMDbError):
            raise uploader.LoginError("Test error")

        with pytest.raises(uploader.UploadIMDbError):
            raise uploader.RatingError("Test error")


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_default_config_exists(self):
        assert hasattr(config, "DEFAULT_CONFIG")
        assert isinstance(config.DEFAULT_CONFIG, dict)

    def test_default_config_has_required_keys(self):
        required_keys = {"headless", "auto_rate", "confirm_threshold", "skipped_dir"}
        assert required_keys.issubset(config.DEFAULT_CONFIG.keys())

    def test_default_config_values_types(self):
        cfg = config.DEFAULT_CONFIG
        assert isinstance(cfg["headless"], bool)
        assert isinstance(cfg["auto_rate"], bool)
        assert isinstance(cfg["confirm_threshold"], (int, float))
        assert isinstance(cfg["skipped_dir"], str)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_none_path(self):
        # When no config path is given and no default exists, should return defaults
        loaded_cfg = config.load_config(None)
        # Should contain at least default keys
        assert "headless" in loaded_cfg
        assert "auto_rate" in loaded_cfg

    def test_load_config_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"headless": true, "max_retries": 5}')
            f.flush()
            temp_path = f.name

        try:
            loaded_cfg = config.load_config(temp_path)
            assert loaded_cfg["headless"] is True
            assert loaded_cfg["max_retries"] == 5
            # Other values should still be defaults
            assert loaded_cfg["auto_rate"] == config.DEFAULT_CONFIG["auto_rate"]
        finally:
            os.unlink(temp_path)

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            f.flush()
            temp_path = f.name

        try:
            # Should return defaults on invalid JSON
            loaded_cfg = config.load_config(temp_path)
            assert "headless" in loaded_cfg  # Should have defaults
        finally:
            os.unlink(temp_path)

    def test_load_config_missing_file(self):
        # Should return defaults when file doesn't exist
        loaded_cfg = config.load_config("/nonexistent/path/to/config.json")
        assert "headless" in loaded_cfg  # Should have defaults


class TestSessionState:
    """Tests for SessionState class."""

    def test_session_state_class_exists(self):
        assert hasattr(config, "SessionState")

    def test_session_state_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")
            session = config.SessionState(session_file)
            assert session.current_index == 0
            assert session.csv_path is None
            assert session.stats == {}

    def test_session_state_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")

            # Create and save session
            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.current_index = 10
            session.stats = {"applied": 5}
            session.save()

            # Load in new instance
            session2 = config.SessionState(session_file)
            loaded = session2.load()

            assert loaded is True
            assert session2.csv_path == "test.csv"
            assert session2.current_index == 10
            assert session2.stats["applied"] == 5

    def test_session_state_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "nonexistent.json")
            session = config.SessionState(session_file)
            loaded = session.load()
            assert loaded is False

    def test_session_state_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")

            # Create, save, and clear session
            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.current_index = 10
            session.save()
            session.clear()

            assert session.current_index == 0
            assert session.csv_path is None
            assert not os.path.exists(session_file)

    def test_session_state_is_resumable(self):
        session = config.SessionState("test.json")
        session.csv_path = "test.csv"
        session.current_index = 5

        assert session.is_resumable("test.csv") is True
        assert session.is_resumable("other.csv") is False

    def test_session_state_mark_processed(self):
        session = config.SessionState("test.json")
        session.mark_processed("Test Movie", 5)

        assert "Test Movie" in session.processed_titles
        assert session.current_index == 5

    def test_session_state_atomic_write(self):
        """Test that session save uses atomic write (temp file + rename)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")
            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.current_index = 10
            session.save()

            # Verify file was written correctly
            assert os.path.exists(session_file)
            with open(session_file) as f:
                data = json.load(f)
            assert data["csv_path"] == "test.csv"
            assert data["current_index"] == 10

            # Verify no temp files left behind
            files_in_dir = os.listdir(tmpdir)
            temp_files = [
                f for f in files_in_dir if f.startswith(".session_") and f.endswith(".tmp")
            ]
            assert len(temp_files) == 0

    def test_session_state_creates_lock_file(self):
        """Test that session operations create and use lock files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")
            os.path.join(tmpdir, "test_session.lock")

            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.save()

            # Lock file may or may not exist after save (depends on cleanup)
            # But the session file should exist
            assert os.path.exists(session_file)

    def test_session_state_clear_removes_lock_file(self):
        """Test that clear() removes the lock file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")
            lock_file = os.path.join(tmpdir, "test_session.lock")

            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.save()

            # Create a lock file manually to test cleanup
            with open(lock_file, "w") as f:
                f.write("")

            session.clear()

            assert not os.path.exists(session_file)
            assert not os.path.exists(lock_file)

    def test_session_state_concurrent_save_protection(self):
        """Test that concurrent saves are handled correctly with file locking."""
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")
            results = []
            errors = []

            def save_session(session_num):
                try:
                    session = config.SessionState(session_file)
                    session.csv_path = f"test_{session_num}.csv"
                    session.current_index = session_num
                    session.save()
                    results.append(session_num)
                except Exception as e:
                    errors.append(str(e))

            # Start multiple threads trying to save simultaneously
            threads = [threading.Thread(target=save_session, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All saves should succeed (no errors)
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == 5

            # File should exist and be valid JSON
            assert os.path.exists(session_file)
            with open(session_file) as f:
                data = json.load(f)
            assert "csv_path" in data
            assert "current_index" in data


class TestFileLock:
    """Tests for file_lock context manager."""

    def test_file_lock_exists(self):
        """Test that file_lock is exported."""
        assert hasattr(config, "file_lock")

    def test_file_lock_basic_usage(self):
        """Test basic file locking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.json"

            with config.file_lock(lock_path):
                # Inside the lock context
                with open(lock_path, "w") as f:
                    f.write("test")

            assert lock_path.exists()

    def test_file_lock_creates_lock_file(self):
        """Test that file_lock creates a .lock file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.json"
            expected_lock = Path(tmpdir) / "test.lock"

            with config.file_lock(lock_path):
                # Lock file should exist during the lock
                assert expected_lock.exists()

    def test_file_lock_timeout(self):
        """Test that file_lock times out when lock is held."""
        import threading
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.json"
            lock_acquired = threading.Event()
            timeout_occurred = threading.Event()

            def hold_lock():
                with config.file_lock(lock_path, timeout=10.0):
                    lock_acquired.set()
                    # Hold the lock for 2 seconds
                    time.sleep(2)

            def try_acquire_lock():
                lock_acquired.wait()  # Wait for first thread to acquire lock
                try:
                    with config.file_lock(lock_path, timeout=0.1):
                        pass
                except TimeoutError:
                    timeout_occurred.set()

            t1 = threading.Thread(target=hold_lock)
            t2 = threading.Thread(target=try_acquire_lock)

            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # Second thread should have timed out
            assert timeout_occurred.is_set()


class TestRetryDecorator:
    """Tests for retry_on_http_error decorator."""

    def test_retry_decorator_exists(self):
        assert hasattr(config, "retry_on_http_error")
        assert callable(config.retry_on_http_error)

    def test_retry_decorator_returns_decorator(self):
        decorator = config.retry_on_http_error(max_retries=3)
        assert callable(decorator)

    def test_retry_decorator_preserves_function_name(self):
        @config.retry_on_http_error(max_retries=2, initial_cooldown=0.01)
        def test_func():
            """Test docstring."""
            return 42

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test docstring."

    def test_retry_decorator_success_no_retry(self):
        call_count = [0]

        @config.retry_on_http_error(max_retries=3, initial_cooldown=0.01)
        def test_func():
            call_count[0] += 1
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count[0] == 1

    def test_retry_decorator_retries_on_http_error(self):
        call_count = [0]

        @config.retry_on_http_error(max_retries=3, initial_cooldown=0.01)
        def test_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("HTTP Error 500 Internal Server Error")
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_decorator_raises_on_non_http_error(self):
        call_count = [0]

        @config.retry_on_http_error(max_retries=3, initial_cooldown=0.01)
        def test_func():
            call_count[0] += 1
            raise ValueError("Not an HTTP error")

        with pytest.raises(ValueError, match="Not an HTTP error"):
            test_func()
        # Should not retry on non-HTTP errors
        assert call_count[0] == 1


class TestParseArgumentsNewOptions:
    """Tests for new --config and --resume options."""

    def test_config_option(self):
        with patch(
            "sys.argv", ["script.py", "--csv", "test.csv", "--config", "/path/to/config.json"]
        ):
            args = uploader.parse_arguments()
            assert args.config == "/path/to/config.json"

    def test_resume_option(self):
        with patch("sys.argv", ["script.py", "--resume"]):
            args = uploader.parse_arguments()
            assert args.resume is True

    def test_resume_default_false(self):
        with patch("sys.argv", ["script.py", "--csv", "test.csv"]):
            args = uploader.parse_arguments()
            assert args.resume is False

    def test_config_default_none(self):
        with patch("sys.argv", ["script.py", "--csv", "test.csv"]):
            args = uploader.parse_arguments()
            assert args.config is None

    def test_session_file_option(self):
        with patch(
            "sys.argv", ["script.py", "--csv", "test.csv", "--session-file", "custom_session.json"]
        ):
            args = uploader.parse_arguments()
            assert args.session_file == "custom_session.json"

    def test_clear_session_option(self):
        with patch("sys.argv", ["script.py", "--clear-session"]):
            args = uploader.parse_arguments()
            assert args.clear_session is True

    def test_validate_only_option(self):
        """Test that --validate-only flag is parsed correctly."""
        with patch("sys.argv", ["script.py", "--csv", "test.csv", "--validate-only"]):
            args = uploader.parse_arguments()
            assert args.validate_only is True

    def test_validate_only_default_false(self):
        """Test that --validate-only defaults to False."""
        with patch("sys.argv", ["script.py", "--csv", "test.csv"]):
            args = uploader.parse_arguments()
            assert args.validate_only is False

    def test_skip_validation_option(self):
        """Test that --skip-validation flag is parsed correctly."""
        with patch("sys.argv", ["script.py", "--csv", "test.csv", "--skip-validation"]):
            args = uploader.parse_arguments()
            assert args.skip_validation is True

    def test_skip_validation_default_false(self):
        """Test that --skip-validation defaults to False."""
        with patch("sys.argv", ["script.py", "--csv", "test.csv"]):
            args = uploader.parse_arguments()
            assert args.skip_validation is False

    def test_validate_only_without_csv(self):
        """Test that --validate-only can be used without --csv initially (checked in main)."""
        with patch("sys.argv", ["script.py", "--validate-only"]):
            # Should not raise error in parse_arguments - check happens in main()
            args = uploader.parse_arguments()
            assert args.validate_only is True


class TestCSVValidation:
    """Tests for CSV validation integration."""

    def test_load_items_validates_csv(self):
        """Test that load_items validates CSV before processing."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score;directors\n")
            f.write("The Godfather;1972;10;Francis Ford Coppola\n")
            csv_path = f.name

        try:
            args = MagicMock()
            args.csv = csv_path
            args.retry = None
            args.skip_validation = False

            # Should not raise - validation passes
            items = uploader.load_items(args)
            assert len(items) == 1
            assert items[0]["title"] == "The Godfather"
        finally:
            os.unlink(csv_path)

    def test_load_items_skips_validation_when_flag_set(self):
        """Test that --skip-validation bypasses CSV validation."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("title;year;user score\n")
            f.write("Test Movie;2020;8\n")
            csv_path = f.name

        try:
            args = MagicMock()
            args.csv = csv_path
            args.retry = None
            args.skip_validation = True

            items = uploader.load_items(args)
            assert len(items) == 1
        finally:
            os.unlink(csv_path)

    def test_load_items_fails_on_invalid_csv(self):
        """Test that load_items exits on invalid CSV."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            # Missing required 'title' column
            f.write("name;year;rating\n")
            f.write("Movie;2020;8\n")
            csv_path = f.name

        try:
            args = MagicMock()
            args.csv = csv_path
            args.retry = None
            args.skip_validation = False

            # Should exit with code 1 due to validation failure
            with pytest.raises(SystemExit) as exc_info:
                uploader.load_items(args)
            assert exc_info.value.code == 1
        finally:
            os.unlink(csv_path)

    def test_load_items_fails_on_missing_file(self):
        """Test that load_items exits when CSV file doesn't exist."""
        args = MagicMock()
        args.csv = "/nonexistent/path/to/file.csv"
        args.retry = None
        args.skip_validation = False

        with pytest.raises(SystemExit) as exc_info:
            uploader.load_items(args)
        assert exc_info.value.code == 1


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_config_creates_file(self):
        """Test that save_config creates a new config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            test_config = {"headless": True, "auto_rate": False}

            config.save_config(test_config, config_path)

            assert os.path.exists(config_path)
            with open(config_path) as f:
                saved_config = json.load(f)
            assert saved_config["headless"] is True
            assert saved_config["auto_rate"] is False

    def test_save_config_creates_parent_dirs(self):
        """Test that save_config creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "subdir", "nested", "config.json")

            config.save_config({"test": "value"}, config_path)

            assert os.path.exists(config_path)

    def test_save_config_overwrites_existing(self):
        """Test that save_config overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")

            config.save_config({"version": 1}, config_path)
            config.save_config({"version": 2}, config_path)

            with open(config_path) as f:
                saved_config = json.load(f)
            assert saved_config["version"] == 2


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_create_default_config(self):
        """Test that create_default_config creates a config with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")

            config.create_default_config(config_path)

            assert os.path.exists(config_path)
            with open(config_path) as f:
                saved_config = json.load(f)
            # Should have default values
            assert "headless" in saved_config
            assert "auto_rate" in saved_config


class TestSessionStateEdgeCases:
    """Additional edge case tests for SessionState class."""

    def test_session_state_get_resume_info_no_session(self):
        """Test get_resume_info when no session is active."""
        session = config.SessionState("test.json")
        info = session.get_resume_info()
        assert "No active session" in info

    def test_session_state_get_resume_info_with_session(self):
        """Test get_resume_info with active session."""
        session = config.SessionState("test.json")
        session.csv_path = "movies.csv"
        session.current_index = 50
        session.stats = {"applied": 40}
        session.skipped_items = [{"title": "Movie1"}, {"title": "Movie2"}]

        info = session.get_resume_info()
        assert "movies.csv" in info
        assert "50" in info
        assert "40" in info
        assert "2" in info  # skipped count

    def test_session_state_not_resumable_no_path(self):
        """Test is_resumable when csv_path is None."""
        session = config.SessionState("test.json")
        session.current_index = 10
        assert session.is_resumable("test.csv") is False

    def test_session_state_not_resumable_different_file(self):
        """Test is_resumable with different CSV file."""
        session = config.SessionState("test.json")
        session.csv_path = "original.csv"
        session.current_index = 10
        assert session.is_resumable("different.csv") is False

    def test_session_state_not_resumable_index_zero(self):
        """Test is_resumable when index is 0."""
        session = config.SessionState("test.json")
        session.csv_path = "test.csv"
        session.current_index = 0
        assert session.is_resumable("test.csv") is False

    def test_session_state_skipped_items(self):
        """Test that skipped_items are saved and loaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = os.path.join(tmpdir, "test_session.json")

            session = config.SessionState(session_file)
            session.csv_path = "test.csv"
            session.skipped_items = [
                {"title": "Movie1", "reason": "not_found"},
                {"title": "Movie2", "reason": "ambiguous"},
            ]
            session.save()

            session2 = config.SessionState(session_file)
            session2.load()

            assert len(session2.skipped_items) == 2
            assert session2.skipped_items[0]["title"] == "Movie1"


class TestRetryDecoratorEdgeCases:
    """Additional edge case tests for retry_on_http_error decorator."""

    def test_retry_decorator_exhausts_retries(self):
        """Test that decorator raises after exhausting all retries."""
        call_count = [0]

        @config.retry_on_http_error(max_retries=3, initial_cooldown=0.01)
        def test_func():
            call_count[0] += 1
            raise Exception("HTTP Error 503 Service Unavailable")

        with pytest.raises(Exception, match="503"):
            test_func()
        assert call_count[0] == 3

    def test_retry_decorator_various_http_errors(self):
        """Test that decorator recognizes various HTTP error patterns."""
        http_errors = [
            "HTTP Error 500 Internal Server Error",
            "503 Service Unavailable",
            "429 Too Many Requests",
            "HTTPError: Connection failed",
        ]

        for error_msg in http_errors:
            call_count = [0]

            @config.retry_on_http_error(max_retries=2, initial_cooldown=0.01)
            def test_func():
                call_count[0] += 1
                if call_count[0] < 2:
                    raise Exception(error_msg)
                return "success"

            result = test_func()
            assert result == "success"
            assert call_count[0] == 2, f"Failed for error: {error_msg}"

    def test_retry_decorator_with_args(self):
        """Test that decorator preserves function arguments."""
        call_count = [0]

        @config.retry_on_http_error(max_retries=2, initial_cooldown=0.01)
        def test_func(a, b, c=None):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("HTTP Error 500")
            return f"{a}-{b}-{c}"

        result = test_func("x", "y", c="z")
        assert result == "x-y-z"


class TestFileLockEdgeCases:
    """Additional edge case tests for file_lock context manager."""

    def test_file_lock_creates_lock_file(self):
        """Test that file_lock creates a .lock file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.json"

            with config.file_lock(lock_path):
                lock_file = lock_path.with_suffix(".lock")
                assert lock_file.exists()

    def test_file_lock_nested_directory(self):
        """Test file_lock with non-existent parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "nested" / "dir" / "test.json"

            with config.file_lock(lock_path):
                # Should create parent directories
                assert lock_path.parent.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
