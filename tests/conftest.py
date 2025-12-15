"""
Pytest configuration and global fixtures for FilmAffinity backup tests.

This file is automatically loaded by pytest and provides global setup
for all test modules, including mocking of external dependencies.
"""

import sys
from unittest.mock import MagicMock


def _setup_selenium_mocking():
    """Set up comprehensive selenium mocking for all tests."""
    # Create a hierarchical mock structure for selenium
    selenium_mock = MagicMock()
    webdriver_mock = MagicMock()
    chrome_mock = MagicMock()
    service_mock = MagicMock()
    webdriver_module_mock = MagicMock()
    common_mock = MagicMock()
    support_mock = MagicMock()

    # Set up the hierarchy
    selenium_mock.webdriver = webdriver_mock
    webdriver_mock.chrome = chrome_mock
    webdriver_mock.common = common_mock
    webdriver_mock.support = support_mock
    chrome_mock.service = service_mock
    chrome_mock.webdriver = webdriver_module_mock

    # Mock all selenium modules
    sys.modules["selenium"] = selenium_mock
    sys.modules["selenium.webdriver"] = webdriver_mock
    sys.modules["selenium.webdriver.chrome"] = chrome_mock
    sys.modules["selenium.webdriver.chrome.service"] = service_mock
    sys.modules["selenium.webdriver.chrome.webdriver"] = webdriver_module_mock
    sys.modules["selenium.webdriver.common"] = common_mock
    sys.modules["selenium.webdriver.common.by"] = common_mock.by
    sys.modules["selenium.webdriver.common.keys"] = common_mock.keys
    sys.modules["selenium.webdriver.support"] = support_mock
    sys.modules["selenium.webdriver.support.ui"] = support_mock.ui
    sys.modules["selenium.webdriver.support.expected_conditions"] = support_mock.expected_conditions

    # Mock webdriver_manager with proper submodule structure
    webdriver_manager_mock = MagicMock()
    chrome_wdm_mock = MagicMock()
    core_mock = MagicMock()
    os_manager_mock = MagicMock()
    download_manager_mock = MagicMock()

    # Set up webdriver_manager hierarchy
    webdriver_manager_mock.chrome = chrome_wdm_mock
    webdriver_manager_mock.core = core_mock
    core_mock.os_manager = os_manager_mock
    core_mock.download_manager = download_manager_mock

    sys.modules["webdriver_manager"] = webdriver_manager_mock
    sys.modules["webdriver_manager.chrome"] = chrome_wdm_mock
    sys.modules["webdriver_manager.core"] = core_mock
    sys.modules["webdriver_manager.core.os_manager"] = os_manager_mock
    sys.modules["webdriver_manager.core.download_manager"] = download_manager_mock


# Always mock selenium to prevent import errors during test collection
# Integration tests don't actually use selenium, so this is safe
_setup_selenium_mocking()
