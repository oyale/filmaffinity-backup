"""
Unit tests for imdb_uploader/reporting.py

Tests for output formatting, statistics, and file operations.
"""

# Selenium is mocked globally in conftest.py
import csv
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

# Add project root to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module
from imdb_uploader.constants import SKIP_AMBIGUOUS, SKIP_NOT_FOUND  # noqa: E402
from imdb_uploader.reporting import (  # noqa: E402
    create_stats,
    print_summary,
    run_dry_run,
    setup_browser_session,
    write_skipped_files,
)


class TestCreateStats:
    """Tests for create_stats function."""

    def test_initial_values(self):
        """Test that create_stats returns correct initial values."""
        stats = create_stats()

        assert isinstance(stats, dict)
        assert stats["applied"] == 0
        assert stats["skipped_ambiguous"] == 0
        assert stats["skipped_not_found"] == 0
        assert stats["skipped_already_rated"] == 0
        assert stats["skipped_same_rating"] == 0
        assert stats["skipped_user_choice"] == 0
        assert stats["skipped_auto_rate_failed"] == 0
        assert stats["quit_early"] is False

    def test_modifiable(self):
        """Test that the returned stats dict can be modified."""
        stats = create_stats()
        stats["applied"] = 5
        stats["skipped_not_found"] = 2

        assert stats["applied"] == 5
        assert stats["skipped_not_found"] == 2


class TestPrintSummary:
    """Tests for print_summary function."""

    @patch("builtins.print")
    def test_print_summary_basic(self, mock_print):
        """Test basic summary printing."""
        stats = {
            "applied": 5,
            "skipped_ambiguous": 1,
            "skipped_not_found": 2,
            "skipped_already_rated": 0,
            "skipped_same_rating": 0,
            "skipped_user_choice": 0,
            "skipped_auto_rate_failed": 0,
            "quit_early": False,
        }

        print_summary(stats, 8)

        # Check that print was called with expected content
        calls = mock_print.call_args_list
        assert len(calls) >= 5  # Should have multiple print calls

        # Check first few calls contain expected content
        assert "📊  SUMMARY" in str(calls[1])
        assert "Total items processed: 8" in str(calls[3])
        assert "✅ Ratings applied:     5" in str(calls[4])

    @patch("builtins.print")
    def test_print_summary_with_skips(self, mock_print):
        """Test summary printing with various skip reasons."""
        stats = {
            "applied": 3,
            "skipped_ambiguous": 1,
            "skipped_not_found": 2,
            "skipped_already_rated": 1,
            "skipped_same_rating": 0,
            "skipped_user_choice": 0,
            "skipped_auto_rate_failed": 1,
            "quit_early": False,
        }

        print_summary(stats, 8)

        calls = mock_print.call_args_list
        summary_text = " ".join(str(call) for call in calls)

        assert "Total skipped:       5" in summary_text
        assert "Ambiguous match:   1" in summary_text
        assert "Not found:         2" in summary_text
        assert "Already rated:     1" in summary_text
        assert "Auto-rate failed:  1" in summary_text

    @patch("builtins.print")
    def test_print_summary_quit_early(self, mock_print):
        """Test summary printing when quit early flag is set."""
        stats = {
            "applied": 2,
            "skipped_ambiguous": 0,
            "skipped_not_found": 0,
            "skipped_already_rated": 0,
            "skipped_same_rating": 0,
            "skipped_user_choice": 0,
            "skipped_auto_rate_failed": 0,
            "quit_early": True,
        }

        print_summary(stats, 5)

        calls = mock_print.call_args_list
        summary_text = " ".join(str(call) for call in calls)

        assert "⚠️  Quit early" in summary_text


class TestWriteSkippedFiles:
    """Tests for write_skipped_files function."""

    def test_write_skipped_files_empty(self):
        """Test that empty skipped items doesn't create files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skipped_files([], temp_dir)

            # Should not create any files
            files = os.listdir(temp_dir)
            assert len(files) == 0

    def test_write_skipped_files_single_category(self):
        """Test writing skipped files for a single category."""
        skipped_items = [
            {
                "item": {
                    "title": "Movie 1",
                    "year": "2020",
                    "directors": "Director 1",
                    "score": "8",
                    "original_title": "",
                },
                "reason": SKIP_NOT_FOUND,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            write_skipped_files(skipped_items, temp_dir)

            # Should create the category file and combined file
            files = os.listdir(temp_dir)
            assert "skipped_not_found.csv" in files
            assert "skipped_all.csv" in files

            # Check content of category file
            with open(os.path.join(temp_dir, "skipped_not_found.csv"), encoding="utf-8") as f:
                content = f.read()
                assert "Movie 1" in content
                assert "2020" in content
                assert "Director 1" in content

    def test_write_skipped_files_multiple_categories(self):
        """Test writing skipped files for multiple categories."""
        skipped_items = [
            {
                "item": {
                    "title": "Movie 1",
                    "year": "2020",
                    "directors": "Director 1",
                    "score": "8",
                    "original_title": "",
                },
                "reason": SKIP_NOT_FOUND,
            },
            {
                "item": {
                    "title": "Movie 2",
                    "year": "2021",
                    "directors": "Director 2",
                    "score": "7",
                    "original_title": "Original Title",
                },
                "reason": SKIP_AMBIGUOUS,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            write_skipped_files(skipped_items, temp_dir)

            files = os.listdir(temp_dir)
            assert "skipped_not_found.csv" in files
            assert "skipped_ambiguous.csv" in files
            assert "skipped_all.csv" in files

            # Check combined file has both entries
            with open(os.path.join(temp_dir, "skipped_all.csv"), encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                rows = list(reader)
                assert len(rows) == 2
                assert rows[0]["title"] == "Movie 1"
                assert rows[1]["title"] == "Movie 2"


class TestRunDryRun:
    """Tests for run_dry_run function."""

    @patch("builtins.open")
    @patch("imdb_uploader.reporting.csv.writer")
    def test_run_dry_run_basic(self, mock_csv_writer, mock_open):
        """Test basic dry run functionality."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_open.return_value.__exit__.return_value = None
        mock_writer = MagicMock()
        mock_csv_writer.return_value = mock_writer

        # Mock items
        items = [
            {"title": "The Matrix", "year": "1999", "directors": "Wachowski", "original_title": ""},
        ]

        # Mock IMDb match result
        mock_match = {
            "title": "The Matrix",
            "year": "1999",
            "score": 0.95,
            "query": "The Matrix 1999",
            "result_count": 1,
            "movieID": "0133093",
        }

        with patch("imdb_uploader.reporting.find_imdb_match", return_value=mock_match):
            run_dry_run(items, MagicMock(), "/tmp/test.csv")

            # Verify CSV writer was called correctly
            mock_writer.writerow.assert_any_call(
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

            # Verify data row was written
            mock_writer.writerow.assert_any_call(
                [
                    "The Matrix",
                    "1999",
                    "Wachowski",
                    "tt0133093",
                    "The Matrix",
                    "1999",
                    "0.950",
                    "The Matrix 1999",
                    1,
                ]
            )


class TestSetupBrowserSession:
    """Tests for setup_browser_session function."""

    @patch("imdb_uploader.browser_automation.start_driver")
    @patch("imdb_uploader.browser_automation.try_automated_login")
    @patch("imdb_uploader.browser_automation.wait_for_login_manual")
    def test_setup_browser_session_manual_login(
        self, mock_manual_login, mock_auto_login, mock_start_driver
    ):
        """Test browser session setup with manual login."""
        mock_driver = MagicMock()
        mock_start_driver.return_value = mock_driver

        # Mock args without auto-login
        mock_args = MagicMock()
        mock_args.headless = False
        mock_args.auto_login = False

        config = {}

        result = setup_browser_session(mock_args, config)

        assert result == mock_driver
        mock_start_driver.assert_called_once_with(headless=False)
        mock_auto_login.assert_not_called()
        mock_manual_login.assert_called_once_with(mock_driver)

    @patch("imdb_uploader.browser_automation.start_driver")
    @patch("imdb_uploader.browser_automation.try_automated_login")
    @patch("imdb_uploader.browser_automation.wait_for_login_manual")
    @patch("os.environ.get")
    def test_setup_browser_session_auto_login_success(
        self, mock_environ, mock_manual_login, mock_auto_login, mock_start_driver
    ):
        """Test browser session setup with successful auto-login."""
        mock_driver = MagicMock()
        mock_start_driver.return_value = mock_driver
        mock_auto_login.return_value = True  # Login successful

        # Mock environment variables
        mock_environ.side_effect = lambda key: {
            "IMDB_USERNAME": "user",
            "IMDB_PASSWORD": "pass",
        }.get(key)

        mock_args = MagicMock()
        mock_args.headless = True
        mock_args.auto_login = True
        mock_args.debug = False

        config = {"login_wait": 10, "page_load_wait": 5, "element_wait": 2, "captcha_wait": 30}

        result = setup_browser_session(mock_args, config)

        assert result == mock_driver
        mock_start_driver.assert_called_once_with(headless=True)
        mock_auto_login.assert_called_once()
        mock_manual_login.assert_not_called()

    @patch("imdb_uploader.browser_automation.start_driver")
    @patch("imdb_uploader.browser_automation.try_automated_login")
    @patch("imdb_uploader.browser_automation.wait_for_login_manual")
    @patch("os.environ.get")
    def test_setup_browser_session_auto_login_failed(
        self, mock_environ, mock_manual_login, mock_auto_login, mock_start_driver
    ):
        """Test browser session setup when auto-login fails."""
        mock_driver = MagicMock()
        mock_start_driver.return_value = mock_driver
        mock_auto_login.return_value = False  # Login failed

        mock_environ.return_value = None  # No env vars

        mock_args = MagicMock()
        mock_args.headless = False
        mock_args.auto_login = True

        config = {}

        result = setup_browser_session(mock_args, config)

        assert result == mock_driver
        mock_manual_login.assert_called_once_with(mock_driver)
