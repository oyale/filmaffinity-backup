"""
Pytest configuration and global fixtures for FilmAffinity backup tests.

This file is automatically loaded by pytest and provides global setup
for all test modules, including mocking of external dependencies.
"""

import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    """Configure pytest with global mocks for external dependencies."""
    # Only mock selenium if it's not already available
    # This allows local environments with selenium installed to use the real thing
    try:
        import selenium  # noqa: F401
    except ImportError:
        # Mock selenium before any test module imports it
        # This prevents ModuleNotFoundError in CI environments
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
