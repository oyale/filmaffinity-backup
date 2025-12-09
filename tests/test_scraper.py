"""
Unit tests for filmaffinity/scraper.py

Tests for the FilmAffinity scraper functions.
These are mostly integration tests that require network access.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock rich (may not be installed in test env)
sys.modules['rich'] = MagicMock()


class TestScraperImports:
    """Test that scraper module can be imported."""

    def test_import_scraper(self):
        from filmaffinity import scraper
        assert hasattr(scraper, 'check_user')
        assert hasattr(scraper, 'get_user_lists')
        assert hasattr(scraper, 'get_list_movies')
        assert hasattr(scraper, 'get_watched_movies')

    def test_import_package(self):
        import filmaffinity
        assert hasattr(filmaffinity, 'check_user')
        assert hasattr(filmaffinity, 'get_user_lists')


class TestScraperConstants:
    """Test scraper configuration constants."""

    def test_constants_exist(self):
        from filmaffinity import scraper
        assert hasattr(scraper, 'DEFAULT_COOLDOWN')
        assert hasattr(scraper, 'RATE_LIMIT_COOLDOWN')
        assert hasattr(scraper, 'MAX_RETRIES')

    def test_cooldown_values(self):
        from filmaffinity import scraper
        assert scraper.DEFAULT_COOLDOWN > 0
        assert scraper.RATE_LIMIT_COOLDOWN > scraper.DEFAULT_COOLDOWN


class TestRequestWithRetry:
    """Test the request_with_retry function."""

    def test_function_exists(self):
        from filmaffinity import scraper
        assert callable(scraper.request_with_retry)


# Integration tests (require network access)
# These are marked with pytest.mark.integration and skipped by default
# Run with: pytest -m integration

@pytest.mark.integration
class TestScraperIntegration:
    """Integration tests that require network access."""

    TEST_USER_ID = '861134'  # Known public test user

    def test_check_user_valid(self):
        from filmaffinity import scraper
        # Should not raise
        scraper.check_user(self.TEST_USER_ID, lang='es')

    def test_check_user_invalid(self):
        from filmaffinity import scraper
        with pytest.raises(Exception):
            scraper.check_user('invalid_user_id_12345', lang='es')

    def test_get_user_lists_max_page(self):
        from filmaffinity import scraper
        lists = scraper.get_user_lists(self.TEST_USER_ID, max_page=1, lang='es')
        assert isinstance(lists, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'not integration'])
