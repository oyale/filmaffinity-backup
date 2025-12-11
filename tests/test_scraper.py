"""
Unit tests for filmaffinity/scraper.py

Tests for the FilmAffinity scraper functions.
These are mostly integration tests that require network access.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, Mock

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


class TestScraperExceptions:
    """Test that exception classes are properly defined and exported."""

    def test_exception_classes_exist(self):
        from filmaffinity import scraper
        assert hasattr(scraper, 'ScraperError')
        assert hasattr(scraper, 'NetworkError')
        assert hasattr(scraper, 'ConnectionFailedError')
        assert hasattr(scraper, 'TimeoutError')
        assert hasattr(scraper, 'RateLimitError')
        assert hasattr(scraper, 'UserNotFoundError')
        assert hasattr(scraper, 'ParseError')

    def test_exception_hierarchy(self):
        from filmaffinity.scraper import (
            ScraperError, NetworkError, ConnectionFailedError,
            TimeoutError, RateLimitError, UserNotFoundError, ParseError
        )
        # All exceptions should inherit from ScraperError
        assert issubclass(NetworkError, ScraperError)
        assert issubclass(ConnectionFailedError, NetworkError)
        assert issubclass(TimeoutError, NetworkError)
        assert issubclass(RateLimitError, NetworkError)
        assert issubclass(UserNotFoundError, ScraperError)
        assert issubclass(ParseError, ScraperError)

    def test_exceptions_importable_from_package(self):
        from filmaffinity import (
            ScraperError, NetworkError, ConnectionFailedError,
            TimeoutError, RateLimitError, UserNotFoundError, ParseError
        )
        assert ScraperError is not None
        assert NetworkError is not None

    def test_user_not_found_error_attributes(self):
        from filmaffinity.scraper import UserNotFoundError
        error = UserNotFoundError(user_id='12345', url='http://example.com')
        assert error.user_id == '12345'
        assert error.url == 'http://example.com'
        assert '12345' in str(error)

    def test_network_error_attributes(self):
        from filmaffinity.scraper import NetworkError
        cause = Exception("original error")
        error = NetworkError("Test error", url='http://example.com', cause=cause)
        assert error.url == 'http://example.com'
        assert error.cause == cause
        assert "Test error" in str(error)


class TestNetworkErrorFormatting:
    """Test the _format_network_error helper function."""

    def test_format_dns_error(self):
        from filmaffinity.scraper import _format_network_error
        from requests.exceptions import ConnectionError

        error = ConnectionError("Name or service not known")
        message = _format_network_error(error, "http://example.com")

        assert "DNS resolution failed" in message
        assert "No internet connection" in message

    def test_format_connection_refused(self):
        from filmaffinity.scraper import _format_network_error
        from requests.exceptions import ConnectionError

        error = ConnectionError("Connection refused")
        message = _format_network_error(error, "http://example.com")

        assert "Connection refused" in message
        assert "FilmAffinity is down" in message

    def test_format_timeout_error(self):
        from filmaffinity.scraper import _format_network_error
        from requests.exceptions import Timeout

        error = Timeout("Read timed out")
        message = _format_network_error(error, "http://example.com")

        assert "timed out" in message
        assert "Slow or unstable" in message

    def test_format_generic_connection_error(self):
        from filmaffinity.scraper import _format_network_error
        from requests.exceptions import ConnectionError

        error = ConnectionError("Some other error")
        message = _format_network_error(error, "http://example.com")

        assert "Unable to connect" in message
        assert "http://example.com" in message


class TestRequestWithRetry:
    """Test the request_with_retry function."""

    def test_function_exists(self):
        from filmaffinity import scraper
        assert callable(scraper.request_with_retry)

    @patch('filmaffinity.scraper.session')
    def test_successful_request(self, mock_session):
        from filmaffinity.scraper import request_with_retry

        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        response = request_with_retry("http://example.com")
        assert response.status_code == 200

    @patch('filmaffinity.scraper.session')
    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.print')
    def test_rate_limit_retry(self, mock_print, mock_sleep, mock_session):
        from filmaffinity.scraper import request_with_retry, RateLimitError

        mock_response_429 = Mock()
        mock_response_429.status_code = 429

        # Return 429 for all attempts
        mock_session.get.return_value = mock_response_429

        with pytest.raises(RateLimitError) as exc_info:
            request_with_retry("http://example.com", max_retries=2)

        assert "Rate limited" in str(exc_info.value)
        assert mock_session.get.call_count == 2

    @patch('filmaffinity.scraper.session')
    @patch('filmaffinity.scraper.print')
    def test_connection_error_raises_custom_exception(self, mock_print, mock_session):
        from filmaffinity.scraper import request_with_retry, ConnectionFailedError
        from requests.exceptions import ConnectionError

        mock_session.get.side_effect = ConnectionError("Connection refused")

        with pytest.raises(ConnectionFailedError) as exc_info:
            request_with_retry("http://example.com", max_retries=1)

        assert exc_info.value.url == "http://example.com"

    @patch('filmaffinity.scraper.session')
    @patch('filmaffinity.scraper.print')
    def test_timeout_raises_custom_exception(self, mock_print, mock_session):
        from filmaffinity.scraper import request_with_retry, TimeoutError
        from requests.exceptions import Timeout

        mock_session.get.side_effect = Timeout("Read timed out")

        with pytest.raises(TimeoutError) as exc_info:
            request_with_retry("http://example.com", max_retries=1)

        assert exc_info.value.url == "http://example.com"


class TestCheckUser:
    """Test the check_user function error handling."""

    @patch('filmaffinity.scraper.request_with_retry')
    def test_user_not_found_raises_exception(self, mock_request):
        from filmaffinity.scraper import check_user, UserNotFoundError

        mock_response = Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        with pytest.raises(UserNotFoundError) as exc_info:
            check_user("invalid_user")

        assert exc_info.value.user_id == "invalid_user"

    @patch('filmaffinity.scraper.request_with_retry')
    def test_unexpected_status_raises_network_error(self, mock_request):
        from filmaffinity.scraper import check_user, NetworkError

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_request.return_value = mock_response

        with pytest.raises(NetworkError) as exc_info:
            check_user("some_user")

        assert "500" in str(exc_info.value)

    @patch('filmaffinity.scraper.request_with_retry')
    def test_success_returns_none(self, mock_request):
        from filmaffinity.scraper import check_user

        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        # Should not raise
        result = check_user("valid_user")
        assert result is None


class TestScraperConstants:
    """Test scraper configuration constants."""

    def test_constants_exist(self):
        from filmaffinity import scraper
        assert hasattr(scraper, 'DEFAULT_COOLDOWN')
        assert hasattr(scraper, 'RATE_LIMIT_COOLDOWN')
        assert hasattr(scraper, 'MAX_RETRIES')
        assert hasattr(scraper, 'MAX_PAGINATION_PAGES')
        assert hasattr(scraper, 'MAX_CONSECUTIVE_EMPTY_PAGES')

    def test_cooldown_values(self):
        from filmaffinity import scraper
        assert scraper.DEFAULT_COOLDOWN > 0
        assert scraper.RATE_LIMIT_COOLDOWN > scraper.DEFAULT_COOLDOWN

    def test_pagination_safety_values(self):
        from filmaffinity import scraper
        assert scraper.MAX_PAGINATION_PAGES > 0
        assert scraper.MAX_CONSECUTIVE_EMPTY_PAGES > 0
        # Safety limit should be reasonable
        assert scraper.MAX_PAGINATION_PAGES >= 100
        assert scraper.MAX_PAGINATION_PAGES <= 1000


class TestPaginationEdgeCases:
    """Tests for pagination edge case handling."""

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_user_lists_handles_empty_container(self, mock_print, mock_request, mock_sleep):
        """Test that get_user_lists handles missing fa-list-group gracefully."""
        from filmaffinity import scraper

        # Return HTML without fa-list-group
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><div>No lists here</div></body></html>'
        mock_request.return_value = mock_response

        result = scraper.get_user_lists('12345', max_page=5)

        assert result == {}
        # Should have stopped after MAX_CONSECUTIVE_EMPTY_PAGES
        assert mock_request.call_count <= scraper.MAX_CONSECUTIVE_EMPTY_PAGES + 1

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_user_lists_handles_empty_list_items(self, mock_print, mock_request, mock_sleep):
        """Test that get_user_lists handles empty li elements gracefully."""
        from filmaffinity import scraper

        # Return HTML with fa-list-group but no li elements
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><div class="fa-list-group"></div></body></html>'
        mock_request.return_value = mock_response

        result = scraper.get_user_lists('12345', max_page=5)

        assert result == {}

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_user_lists_respects_max_page_limit(self, mock_print, mock_request, mock_sleep):
        """Test that get_user_lists respects MAX_PAGINATION_PAGES."""
        from filmaffinity import scraper

        # Return valid HTML with lists
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html><body>
        <div class="fa-list-group">
            <li><a href="/list/1">List 1</a></li>
        </div>
        </body></html>
        '''
        mock_request.return_value = mock_response

        # Set a low max_page for testing
        result = scraper.get_user_lists('12345', max_page=2)

        # Should stop after 2 pages
        assert mock_request.call_count == 2

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_watched_movies_handles_empty_groups(self, mock_print, mock_request, mock_sleep):
        """Test that get_watched_movies handles empty rating groups gracefully."""
        from filmaffinity import scraper

        # Return HTML without user-ratings-list-resp
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><div>No movies</div></body></html>'
        mock_request.return_value = mock_response

        result = scraper.get_watched_movies('12345', max_page=5)

        assert result['title'] == []
        assert result['user score'] == []
        # Should have stopped after MAX_CONSECUTIVE_EMPTY_PAGES
        assert mock_request.call_count <= scraper.MAX_CONSECUTIVE_EMPTY_PAGES + 1

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_watched_movies_handles_missing_elements(self, mock_print, mock_request, mock_sleep):
        """Test that get_watched_movies skips movies with missing elements."""
        from filmaffinity import scraper

        # Return HTML with groups but incomplete movie data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html><body>
        <div class="user-ratings-list-resp">
            <div class="row mb-4">
                <!-- Missing fa-user-rat-box -->
                <div class="movie-card"></div>
            </div>
            <div class="row mb-4">
                <div class="fa-user-rat-box">8</div>
                <!-- Missing movie-card -->
            </div>
        </div>
        </body></html>
        '''
        mock_request.return_value = mock_response

        result = scraper.get_watched_movies('12345', max_page=5)

        # Should have skipped both invalid movies
        assert result['user score'] == []

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_list_movies_handles_empty_container(self, mock_print, mock_request, mock_sleep):
        """Test that get_list_movies handles missing movie container gracefully."""
        from filmaffinity import scraper

        # Return HTML without fa-list-group
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><span class="fs-5">List: My List</span></body></html>'
        mock_request.return_value = mock_response

        title, result = scraper.get_list_movies('http://example.com/list?id=1', max_page=5)

        assert result['title'] == []
        assert result['user score'] == []

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_get_list_movies_handles_missing_title(self, mock_print, mock_request, mock_sleep):
        """Test that get_list_movies handles missing title element gracefully."""
        from filmaffinity import scraper

        # Return HTML without fs-5 title span, and movie card without data-movie-id
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html><body>
        <ul class="fa-list-group">
            <li>
                <div class="fa-user-rat-box">8</div>
                <div class="movie-card">
                    <div class="mc-title"><a href="/film123.html">Test Movie</a></div>
                </div>
            </li>
        </ul>
        </body></html>
        '''
        mock_request.return_value = mock_response

        title, result = scraper.get_list_movies('http://example.com/list?id=1', max_page=1)

        # Title should be empty string, not crash
        assert title == ''
        # Movie without data-movie-id should be skipped
        assert result['title'] == []

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_pagination_stops_on_http_error(self, mock_print, mock_request, mock_sleep):
        """Test that pagination stops cleanly on HTTP errors."""
        from filmaffinity import scraper

        # First page succeeds, second fails
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.text = '''
        <html><body>
        <div class="fa-list-group">
            <li><a href="/list/1">List 1</a></li>
        </div>
        </body></html>
        '''

        mock_response_error = MagicMock()
        mock_response_error.status_code = 500

        mock_request.side_effect = [mock_response_ok, mock_response_error]

        result = scraper.get_user_lists('12345')

        assert 'List 1' in result
        assert mock_request.call_count == 2

    @patch('filmaffinity.scraper.time.sleep')
    @patch('filmaffinity.scraper.request_with_retry')
    @patch('filmaffinity.scraper.print')
    def test_no_infinite_loop_on_malformed_response(self, mock_print, mock_request, mock_sleep):
        """Test that pagination doesn't loop infinitely on malformed responses."""
        from filmaffinity import scraper

        # Return same malformed response every time
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>Malformed page</body></html>'
        mock_request.return_value = mock_response

        # This should NOT loop 500 times (MAX_PAGINATION_PAGES)
        result = scraper.get_user_lists('12345')

        # Should stop after MAX_CONSECUTIVE_EMPTY_PAGES
        assert mock_request.call_count <= scraper.MAX_CONSECUTIVE_EMPTY_PAGES + 1
        assert result == {}


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
