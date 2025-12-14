"""
Integration tests for FilmAffinity backup tool.

These tests require network access and interact with real FilmAffinity servers.
They are marked with @pytest.mark.integration and skipped by default.

Run with: pytest -m integration
Run all tests: pytest -m "integration or not integration"

WARNING: These tests make real HTTP requests. Running them too frequently
may result in rate limiting by FilmAffinity. If tests hang or fail with
connection errors, wait 10-15 minutes before retrying.
"""

import time
from typing import Any

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Module-level state to detect rate limiting
_rate_limited = False
_cached_movies: dict[str, Any] | None = None
_last_request_time: float = 0

# Configuration
TEST_USER_ID = "861134"  # Known public test user with ratings
REQUEST_TIMEOUT = 30  # seconds - if a request takes longer, assume rate limited
MIN_REQUEST_INTERVAL = 2  # seconds between requests


def _check_rate_limited():
    """Skip test if we've been rate limited."""
    if _rate_limited:
        pytest.skip("Skipping due to FilmAffinity rate limiting - wait 10-15 minutes")


def _throttle_request():
    """Ensure minimum interval between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL and _last_request_time > 0:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get_cached_movies() -> dict[str, Any] | None:
    """Get cached movies data, fetching once if needed.

    This fixture-like function ensures we only make ONE request to
    get_watched_movies across all tests that need movie data.
    """
    global _cached_movies, _rate_limited

    if _rate_limited:
        return None

    if _cached_movies is not None:
        return _cached_movies

    _throttle_request()

    try:
        import signal

        from filmaffinity import scraper

        # Set a timeout to detect rate limiting (hanging requests)
        def timeout_handler(signum, frame):
            raise TimeoutError("Request timed out - likely rate limited")

        # Only use signal on Unix (not Windows)
        use_signal = hasattr(signal, "SIGALRM")
        if use_signal:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(REQUEST_TIMEOUT)

        try:
            _cached_movies = scraper.get_watched_movies(
                TEST_USER_ID,
                max_page=1,
                lang="es",
            )
        finally:
            if use_signal:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        return _cached_movies

    except (TimeoutError, Exception) as e:
        error_str = str(e).lower()
        if "timeout" in error_str or "rate" in error_str or "429" in error_str:
            _rate_limited = True
            pytest.skip(
                f"FilmAffinity rate limiting detected: {e}\n"
                "Wait 10-15 minutes before running integration tests again."
            )
        raise


class TestFilmAffinityScraperIntegration:
    """Integration tests for FilmAffinity scraper with real network requests.

    These tests are ordered to minimize requests:
    1. First test checks user exists (1 request)
    2. Remaining tests use cached movie data (0 additional requests)
    """

    def test_check_user_exists(self):
        """Test checking a valid user exists (single request for both languages)."""
        _check_rate_limited()
        _throttle_request()

        from filmaffinity import scraper

        # Only test Spanish to reduce requests
        scraper.check_user(TEST_USER_ID, lang="es")

    def test_check_user_not_found(self):
        """Test that checking an invalid user raises UserNotFoundError."""
        _check_rate_limited()
        _throttle_request()

        from filmaffinity import scraper
        from filmaffinity.scraper import UserNotFoundError

        with pytest.raises(UserNotFoundError):
            scraper.check_user("999999999999", lang="es")

    def test_get_watched_movies_returns_expected_structure(self):
        """Test getting watched movies returns expected data structure."""
        _check_rate_limited()

        movies = _get_cached_movies()
        if movies is None:
            pytest.skip("Could not fetch movies (rate limited)")

        assert isinstance(movies, dict)
        if movies:
            expected_keys = {"title", "year", "user score"}
            assert expected_keys.issubset(set(movies.keys()))
            if movies.get("title"):
                length = len(movies["title"])
                for key in movies:
                    assert len(movies[key]) == length

    def test_get_watched_movies_has_original_title(self):
        """Test that original title is included in movie data."""
        _check_rate_limited()

        movies = _get_cached_movies()
        if movies is None:
            pytest.skip("Could not fetch movies (rate limited)")

        if movies and movies.get("title"):
            assert "original title" in movies

    def test_scraper_has_rate_limiting_config(self):
        """Test that scraper has rate limiting mechanisms configured."""
        from filmaffinity import scraper

        assert hasattr(scraper, "DEFAULT_COOLDOWN")
        assert scraper.DEFAULT_COOLDOWN > 0
        assert hasattr(scraper, "RATE_LIMIT_COOLDOWN")
        assert scraper.RATE_LIMIT_COOLDOWN > 0


class TestFilmAffinityExporterIntegration:
    """Integration tests for the exporter module using cached data."""

    def test_export_to_letterboxd_format(self):
        """Test exporting scraped data to Letterboxd CSV format."""
        _check_rate_limited()

        import io

        from filmaffinity.exporters import export_to_letterboxd

        movies = _get_cached_movies()
        if movies is None or not movies.get("title"):
            pytest.skip("Could not fetch movies (rate limited or empty)")

        output = io.StringIO()
        export_to_letterboxd(movies, output)
        content = output.getvalue()
        output.close()

        assert "Title" in content
        assert "Year" in content
        assert "Rating10" in content


class TestIMDbIntegration:
    """Integration tests for IMDb-related functionality.

    Note: These tests do NOT actually rate movies or modify IMDb accounts.
    They only test the search/lookup functionality via cinemagoer.
    """

    def test_imdbpy_client_initialization(self):
        """Test that IMDbPY client can be initialized."""
        pytest.importorskip("imdb", reason="cinemagoer not installed")

        from imdb_uploader.uploader import init_imdbpy_client

        client = init_imdbpy_client()
        assert client is not None

    def test_imdbpy_search_movie(self):
        """Test searching for a movie on IMDb."""
        imdb = pytest.importorskip("imdb", reason="cinemagoer not installed")

        ia = imdb.Cinemagoer()
        results = ia.search_movie("The Godfather")

        assert len(results) > 0
        assert "godfather" in results[0]["title"].lower()

    def test_imdbpy_get_movie_details(self):
        """Test getting movie details from IMDb."""
        imdb = pytest.importorskip("imdb", reason="cinemagoer not installed")

        ia = imdb.Cinemagoer()
        movie = ia.get_movie("0068646")  # The Godfather

        assert movie is not None
        assert "godfather" in movie["title"].lower()
        assert movie["year"] == 1972


class TestCSVValidatorIntegration:
    """Integration tests for CSV validation with real exported files."""

    def test_validate_scraped_csv(self):
        """Test that CSV files exported by scraper pass validation."""
        _check_rate_limited()

        import csv
        import tempfile
        from pathlib import Path

        from imdb_uploader.csv_validator import validate_csv_format

        movies = _get_cached_movies()
        if movies is None or not movies.get("title"):
            pytest.skip("Could not fetch movies (rate limited or empty)")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["title", "original title", "year", "user score"])

            for i in range(min(5, len(movies["title"]))):  # Only write 5 rows for test
                writer.writerow(
                    [
                        movies["title"][i],
                        movies.get("original title", [""])[i]
                        if movies.get("original title")
                        else "",
                        movies["year"][i],
                        movies["user score"][i],
                    ]
                )
            temp_path = f.name

        try:
            result = validate_csv_format(temp_path)
            assert result.valid is True
            assert result.row_count > 0
        finally:
            Path(temp_path).unlink()


class TestEndToEndWorkflow:
    """End-to-end workflow tests using cached data."""

    def test_full_backup_workflow(self):
        """Test the full backup workflow: scrape → validate → export."""
        _check_rate_limited()

        import csv
        import io
        import tempfile
        from pathlib import Path

        from filmaffinity.exporters import export_to_letterboxd
        from imdb_uploader.csv_validator import (
            validate_csv_format,
            validate_letterboxd_format,
        )

        movies = _get_cached_movies()
        if movies is None or not movies.get("title"):
            pytest.skip("Could not fetch movies (rate limited or empty)")

        # Export to FilmAffinity CSV format (only 5 rows)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["title", "original title", "year", "user score"])

            for i in range(min(5, len(movies["title"]))):
                writer.writerow(
                    [
                        movies["title"][i],
                        movies.get("original title", [""])[i]
                        if movies.get("original title")
                        else "",
                        movies["year"][i],
                        movies["user score"][i],
                    ]
                )
            fa_csv_path = f.name

        try:
            # Validate FilmAffinity CSV
            fa_result = validate_csv_format(fa_csv_path)
            assert fa_result.valid is True

            # Export to Letterboxd format
            letterboxd_output = io.StringIO()
            export_to_letterboxd(movies, letterboxd_output)
            letterboxd_content = letterboxd_output.getvalue()
            letterboxd_output.close()

            # Validate Letterboxd CSV
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8"
            ) as f:
                f.write(letterboxd_content)
                lb_csv_path = f.name

            try:
                lb_result = validate_letterboxd_format(lb_csv_path)
                assert lb_result.valid is True
            finally:
                Path(lb_csv_path).unlink()

        finally:
            Path(fa_csv_path).unlink()
