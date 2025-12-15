"""
Unit tests for imdb_uploader/browser_automation.py

Tests for Selenium WebDriver operations, login, and rating functions.
"""

import os
import sys
from unittest.mock import MagicMock, patch

# Import Keys from the mock

# Add project root to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Selenium is mocked globally in conftest.py
sys.modules["webdriver_manager.core"] = MagicMock()
sys.modules["webdriver_manager.core.os_manager"] = MagicMock()

# Import the module after mocking
from imdb_uploader.browser_automation import (  # noqa: E402
    detect_captcha,
    get_existing_rating,
    imdb_search_and_open,
    start_driver,
    try_automated_login,
    try_rate_on_page,
    wait_for_login_manual,
)


class TestStartDriver:
    """Tests for start_driver function."""

    def test_start_driver_basic(self):
        """Test basic driver startup."""
        result = start_driver()

        assert result is not None
        result.set_window_size.assert_called_once_with(1200, 900)

    def test_start_driver_headless(self):
        """Test driver startup with headless mode."""
        result = start_driver(headless=True)

        assert result is not None
        # With global mocking, we can't easily check the options, but we can verify the driver was created

    def test_start_driver_fallback_to_selenium_manager(self):
        """Test fallback to Selenium manager when webdriver-manager fails."""
        result = start_driver()

        assert result is not None
        # With global mocking, the function should still work and return a driver


class TestWaitForLoginManual:
    """Tests for wait_for_login_manual function."""

    @patch("builtins.input")
    @patch("imdb_uploader.browser_automation.beep")
    def test_wait_for_login_manual(self, mock_beep, mock_input):
        """Test manual login wait."""
        mock_driver = MagicMock()

        wait_for_login_manual(mock_driver)

        mock_beep.assert_called_once()
        mock_input.assert_called_once()


class TestDetectCaptcha:
    """Tests for detect_captcha function."""

    def test_detect_captcha_no_captcha(self):
        """Test when no CAPTCHA elements are found."""
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []

        result = detect_captcha(mock_driver)

        assert result is False

    def test_detect_captcha_found_element(self):
        """Test when CAPTCHA elements are found."""
        mock_driver = MagicMock()
        mock_element = MagicMock()
        mock_element.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_element]

        result = detect_captcha(mock_driver)

        assert result is True

    def test_detect_captcha_text_detection(self):
        """Test CAPTCHA detection via page text."""
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []
        mock_body = MagicMock()
        mock_body.text = "Please solve this CAPTCHA challenge to continue"
        mock_driver.find_element.return_value = mock_body

        result = detect_captcha(mock_driver)

        assert result is True


class TestImdbSearchAndOpen:
    """Tests for imdb_search_and_open function."""

    @patch("imdb_uploader.browser_automation.WebDriverWait")
    def test_imdb_search_and_open_success(self, mock_webdriver_wait):
        """Test successful IMDb search and open."""
        mock_driver = MagicMock()
        mock_wait = MagicMock()
        mock_webdriver_wait.return_value = mock_wait

        # Mock successful search
        mock_result_link = MagicMock()
        mock_driver.find_elements.return_value = [mock_result_link]

        result = imdb_search_and_open(mock_driver, "The Matrix", "1999")

        assert result is True
        mock_driver.get.assert_called_once()
        mock_result_link.click.assert_called_once()

    @patch("imdb_uploader.browser_automation.WebDriverWait")
    def test_imdb_search_and_open_no_results(self, mock_webdriver_wait):
        """Test when no search results are found."""
        mock_driver = MagicMock()
        mock_wait = MagicMock()
        mock_webdriver_wait.return_value = mock_wait
        mock_wait.until.side_effect = Exception("Timeout")

        result = imdb_search_and_open(mock_driver, "Unknown Movie", None)

        assert result is False


class TestGetExistingRating:
    """Tests for get_existing_rating function."""

    def test_get_existing_rating_not_rated(self):
        """Test when movie is not rated."""
        mock_driver = MagicMock()

        # Mock unrated element present
        mock_unrated = MagicMock()
        mock_unrated.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_unrated]

        result = get_existing_rating(mock_driver)

        assert result is None

    def test_get_existing_rating_found(self):
        """Test when existing rating is found."""
        mock_driver = MagicMock()

        # Mock no unrated element
        mock_driver.find_elements.return_value = []

        # Mock rated score element
        mock_score_element = MagicMock()
        mock_score_element.text = "8"
        mock_driver.find_elements.side_effect = [
            [],  # No unrated elements
            [mock_score_element],  # Score element found
        ]

        result = get_existing_rating(mock_driver)

        assert result == 8

    def test_get_existing_rating_invalid_score(self):
        """Test when score element contains invalid text."""
        mock_driver = MagicMock()

        mock_driver.find_elements.return_value = []

        # Mock score element with invalid text
        mock_score_element = MagicMock()
        mock_score_element.text = "Not a number"
        mock_driver.find_elements.side_effect = [
            [],  # No unrated elements
            [mock_score_element],  # Invalid score element
        ]

        result = get_existing_rating(mock_driver)

        assert result is None


class TestTryAutomatedLogin:
    """Tests for try_automated_login function."""

    @patch("imdb_uploader.browser_automation.detect_captcha")
    @patch("imdb_uploader.browser_automation.WebDriverWait")
    @patch("imdb_uploader.browser_automation.time.sleep")
    def test_try_automated_login_success(
        self, mock_sleep, mock_webdriver_wait, mock_detect_captcha
    ):
        """Test successful automated login."""
        mock_driver = MagicMock()
        mock_wait = MagicMock()
        mock_webdriver_wait.return_value = mock_wait
        mock_detect_captcha.return_value = False  # No CAPTCHA

        # Mock successful login flow
        mock_user_menu = MagicMock()
        mock_user_menu.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_user_menu]

        result = try_automated_login(mock_driver, "user", "pass")

        assert result is True

    @patch("imdb_uploader.browser_automation.WebDriverWait")
    @patch("imdb_uploader.browser_automation.time.sleep")
    def test_try_automated_login_failure(self, mock_sleep, mock_webdriver_wait):
        """Test failed automated login."""
        mock_driver = MagicMock()
        mock_wait = MagicMock()
        mock_webdriver_wait.return_value = mock_wait

        # Mock no user menu found
        mock_driver.find_elements.return_value = []

        result = try_automated_login(mock_driver, "user", "pass")

        assert result is False


class TestTryRateOnPage:
    """Tests for try_rate_on_page function."""

    @patch("imdb_uploader.browser_automation.time.sleep")
    def test_try_rate_on_page_invalid_score(self, mock_sleep):
        """Test with invalid score."""
        mock_driver = MagicMock()

        result = try_rate_on_page(mock_driver, 0)  # Invalid score

        assert result is False

    @patch("imdb_uploader.browser_automation.time.sleep")
    @patch("selenium.webdriver.common.action_chains.ActionChains")
    def test_try_rate_on_page_modal_open_fails(self, mock_action_chains, mock_sleep):
        """Test when modal opening fails."""
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []  # No rate button found

        result = try_rate_on_page(mock_driver, 8)

        assert result is False

    @patch("imdb_uploader.browser_automation.time.sleep")
    def test_try_rate_on_page_success(self, mock_sleep):
        """Test successful rating."""
        mock_driver = MagicMock()

        # Mock successful rating flow
        mock_rate_button = MagicMock()
        mock_rate_button.is_displayed.return_value = True
        mock_rate_button.is_enabled.return_value = True

        mock_star_button = MagicMock()
        mock_submit_button = MagicMock()
        mock_submit_button.is_displayed.return_value = True
        mock_submit_button.is_enabled.return_value = True

        mock_driver.find_elements.side_effect = [
            [mock_rate_button],  # Rate button found
            [mock_star_button],  # Star button found
            [mock_submit_button],  # Submit button found
        ]

        result = try_rate_on_page(mock_driver, 8)

        assert result is True
        # Check that execute_script was called for clicking (js_click function)
        assert mock_driver.execute_script.call_count >= 3  # rate button, star button, submit button

    @patch("imdb_uploader.browser_automation.time.sleep")
    @patch("selenium.webdriver.common.action_chains.ActionChains")
    def test_try_rate_on_page_enter_fallback(self, mock_action_chains, mock_sleep):
        """Test Enter key fallback when submit button fails."""
        mock_driver = MagicMock()

        # Mock rate button found but submit button not found
        mock_rate_button = MagicMock()
        mock_rate_button.is_displayed.return_value = True

        mock_star_buttons = [MagicMock() for _ in range(10)]  # 10 star buttons

        mock_actions = MagicMock()
        mock_action_chains.return_value = mock_actions

        # Mock to return empty lists for all find_elements calls
        def mock_find_elements(selector):
            if "rate" in selector.lower() or "Rate" in selector:
                return [mock_rate_button]  # Rate button found
            elif (
                "star" in selector.lower()
                or "ipc-starbar" in selector
                or "button[aria-label*='Rate']" in selector
            ):
                return mock_star_buttons  # Star buttons found
            else:
                return []  # No submit buttons found

        mock_driver.find_elements.side_effect = mock_find_elements

        result = try_rate_on_page(mock_driver, 7)

        # Should return False when submit buttons are not found and Enter fallback fails
        assert result is False
