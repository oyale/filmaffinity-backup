"""
Unit tests for filmaffinity/cli.py

Tests for the FilmAffinity CLI.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import rich here to make sure it's loaded before any mocking
# from other test files can interfere
import rich
from rich.panel import Panel


class TestCLIImports:
    """Test that CLI module can be imported."""

    def test_import_cli(self):
        from filmaffinity import cli
        assert hasattr(cli, 'app')
        assert hasattr(cli, 'backup')
        assert hasattr(cli, 'main')

    def test_import_version_helpers(self):
        from filmaffinity.cli import get_app_version, version_callback, qprint
        assert callable(get_app_version)
        assert callable(version_callback)
        assert callable(qprint)


class TestGetAppVersion:
    """Test the get_app_version function."""

    def test_returns_string(self):
        from filmaffinity.cli import get_app_version
        version = get_app_version()
        assert isinstance(version, str)

    def test_returns_dev_when_not_installed(self):
        """Test that 'dev' is returned when package is not installed."""
        from filmaffinity.cli import get_app_version
        from importlib.metadata import PackageNotFoundError

        with patch('filmaffinity.cli.get_version', side_effect=PackageNotFoundError()):
            version = get_app_version()
            assert version == "dev"

    def test_returns_version_when_installed(self):
        """Test that version is returned when package is installed."""
        from filmaffinity.cli import get_app_version

        with patch('filmaffinity.cli.get_version', return_value="1.2.3"):
            version = get_app_version()
            assert version == "1.2.3"


class TestVersionCallback:
    """Test the version_callback function."""

    def test_prints_version_and_exits(self):
        """Test that version callback prints version and exits."""
        from filmaffinity.cli import version_callback
        import typer

        with patch('filmaffinity.cli.get_app_version', return_value="1.0.0"):
            with patch('filmaffinity.cli.print') as mock_print:
                with pytest.raises(typer.Exit):
                    version_callback(True)
                mock_print.assert_called_once_with("fa-backup version 1.0.0")

    def test_does_nothing_when_false(self):
        """Test that version callback does nothing when value is False."""
        from filmaffinity.cli import version_callback

        # Should not raise, should return None
        result = version_callback(False)
        assert result is None


class TestQprint:
    """Test the qprint function."""

    def test_prints_when_quiet_mode_off(self):
        """Test that qprint prints when _quiet_mode is False."""
        from filmaffinity import cli

        original_quiet = cli._quiet_mode
        try:
            cli._quiet_mode = False
            with patch('filmaffinity.cli.print') as mock_print:
                cli.qprint("Hello", "World")
                mock_print.assert_called_once_with("Hello", "World")
        finally:
            cli._quiet_mode = original_quiet

    def test_does_not_print_when_quiet_mode_on(self):
        """Test that qprint does not print when _quiet_mode is True."""
        from filmaffinity import cli

        original_quiet = cli._quiet_mode
        try:
            cli._quiet_mode = True
            with patch('filmaffinity.cli.print') as mock_print:
                cli.qprint("Hello", "World")
                mock_print.assert_not_called()
        finally:
            cli._quiet_mode = original_quiet

    def test_passes_kwargs(self):
        """Test that qprint passes kwargs to print."""
        from filmaffinity import cli

        original_quiet = cli._quiet_mode
        try:
            cli._quiet_mode = False
            with patch('filmaffinity.cli.print') as mock_print:
                cli.qprint("test", end="", sep="-")
                mock_print.assert_called_once_with("test", end="", sep="-")
        finally:
            cli._quiet_mode = original_quiet


class TestCLIOptions:
    """Test CLI option definitions using typer.testing.CliRunner."""

    def test_version_option_short(self):
        """Test -V shows version."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["-V"], color=False)
        assert result.exit_code == 0
        assert "fa-backup version" in result.stdout

    def test_version_option_long(self):
        """Test --version shows version."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["--version"], color=False)
        assert result.exit_code == 0
        assert "fa-backup version" in result.stdout

    def test_help_shows_version_option(self):
        """Test that --version is documented in help."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"], color=False)
        assert result.exit_code == 0
        assert "--version" in result.stdout
        assert "-V" in result.stdout

    def test_backup_help_shows_quiet_option(self):
        """Test that --quiet is documented in backup help."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["backup", "--help"], color=False)
        assert result.exit_code == 0
        assert "--quiet" in result.stdout
        assert "-q" in result.stdout
        assert "Minimal output" in result.stdout


class TestBackupQuietMode:
    """Test the --quiet option in backup command."""

    @patch('filmaffinity.cli.scraper')
    def test_quiet_mode_suppresses_output(self, mock_scraper):
        """Test that --quiet suppresses normal output."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app
        import tempfile
        import shutil

        # Set up mock
        mock_scraper.check_user.return_value = None
        mock_scraper.get_user_lists.return_value = {}
        mock_scraper.get_watched_movies.return_value = {
            'title': ['Test Movie'],
            'original_title': ['Test Movie'],
            'year': [2024],
            'rating': [8],
            'id': [12345],
            'url': ['http://example.com']
        }

        runner = CliRunner()

        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, [
                "backup", "123456",
                "--quiet",
                "--skip-lists",
                "--data-dir", tmpdir
            ], color=False)

            # Should succeed
            assert result.exit_code == 0

            # With quiet mode, there should be minimal/no output
            # Error messages would still show, but normal progress messages shouldn't
            assert "Parsing" not in result.stdout
            assert "Retrieving" not in result.stdout

    @patch('filmaffinity.cli.scraper')
    def test_normal_mode_shows_output(self, mock_scraper):
        """Test that without --quiet, output is shown."""
        from typer.testing import CliRunner
        from filmaffinity.cli import app
        import tempfile

        # Set up mock
        mock_scraper.check_user.return_value = None
        mock_scraper.get_user_lists.return_value = {}
        mock_scraper.get_watched_movies.return_value = {
            'title': ['Test Movie'],
            'original_title': ['Test Movie'],
            'year': [2024],
            'rating': [8],
            'id': [12345],
            'url': ['http://example.com']
        }

        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, [
                "backup", "123456",
                "--skip-lists",
                "--data-dir", tmpdir
            ], color=False)

            assert result.exit_code == 0
            # Normal mode should show output
            assert "Parsing" in result.stdout or "Saving" in result.stdout
