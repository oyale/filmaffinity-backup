"""
Unit tests for imdb_uploader/prompts.py

Tests for pure functions in the prompts module that don't require user input.
Prompt functions that require stdin are tested via integration tests.
"""

from imdb_uploader.prompts import (
    is_beep_enabled,
    parse_imdb_id,
    set_beep_enabled,
)


class TestParseImdbId:
    """Tests for parse_imdb_id function."""

    def test_none_input(self):
        assert parse_imdb_id(None) is None

    def test_empty_string(self):
        assert parse_imdb_id("") is None

    def test_whitespace_only(self):
        assert parse_imdb_id("   ") is None

    def test_plain_numeric_id(self):
        assert parse_imdb_id("1234567") == "1234567"

    def test_plain_numeric_id_short(self):
        # IDs less than 5 digits should be rejected
        assert parse_imdb_id("1234") is None

    def test_tt_prefixed_id(self):
        assert parse_imdb_id("tt1234567") == "1234567"

    def test_tt_prefixed_id_uppercase(self):
        assert parse_imdb_id("TT1234567") == "1234567"

    def test_tt_prefixed_id_mixed_case(self):
        assert parse_imdb_id("Tt1234567") == "1234567"

    def test_imdb_url_basic(self):
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567/") == "1234567"

    def test_imdb_url_no_trailing_slash(self):
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567") == "1234567"

    def test_imdb_url_http(self):
        assert parse_imdb_id("http://www.imdb.com/title/tt1234567/") == "1234567"

    def test_imdb_url_no_www(self):
        assert parse_imdb_id("https://imdb.com/title/tt1234567/") == "1234567"

    def test_imdb_url_with_query_params(self):
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567/?ref_=ext") == "1234567"

    def test_imdb_url_mobile(self):
        assert parse_imdb_id("https://m.imdb.com/title/tt1234567/") == "1234567"

    def test_whitespace_trimmed(self):
        assert parse_imdb_id("  tt1234567  ") == "1234567"

    def test_invalid_format(self):
        assert parse_imdb_id("invalid") is None
        assert parse_imdb_id("abc1234567") is None
        assert parse_imdb_id("https://google.com/") is None
        # Test substring attack prevention
        assert parse_imdb_id("http://evil.com/imdb.com/title/tt1234567/") is None
        assert parse_imdb_id("maliciousimdb.com/title/tt1234567") is None

    def test_real_imdb_ids(self):
        # The Godfather
        assert parse_imdb_id("tt0068646") == "0068646"
        # Pulp Fiction
        assert parse_imdb_id("https://www.imdb.com/title/tt0110912/") == "0110912"


class TestBeepControl:
    """Tests for beep enable/disable functions."""

    def test_beep_enabled_by_default(self):
        # Reset to default state
        set_beep_enabled(True)
        assert is_beep_enabled() is True

    def test_disable_beep(self):
        set_beep_enabled(False)
        assert is_beep_enabled() is False

    def test_enable_beep(self):
        set_beep_enabled(False)
        set_beep_enabled(True)
        assert is_beep_enabled() is True

    def test_toggle_beep(self):
        set_beep_enabled(True)
        assert is_beep_enabled() is True
        set_beep_enabled(False)
        assert is_beep_enabled() is False
        set_beep_enabled(True)
        assert is_beep_enabled() is True


class TestBeepFunction:
    """Tests for beep function behavior."""

    def test_beep_when_disabled(self, capsys):
        """Beep should not print anything when disabled."""
        set_beep_enabled(False)
        from imdb_uploader.prompts import beep

        beep()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_beep_when_enabled(self, capsys):
        """Beep should print bell character when enabled."""
        set_beep_enabled(True)
        from imdb_uploader.prompts import beep

        beep()
        captured = capsys.readouterr()
        assert captured.out == "\a"


class TestParseImdbIdEdgeCases:
    """Additional edge case tests for parse_imdb_id."""

    def test_imdb_id_with_leading_zeros(self):
        """IDs with leading zeros should preserve them."""
        assert parse_imdb_id("tt0000001") == "0000001"
        assert parse_imdb_id("0000001") == "0000001"

    def test_imdb_url_with_fragments(self):
        """URLs with fragment identifiers."""
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567/#reviews") == "1234567"

    def test_imdb_url_with_extra_path(self):
        """URLs with extra path components."""
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567/fullcredits") == "1234567"
        assert parse_imdb_id("https://www.imdb.com/title/tt1234567/reviews") == "1234567"

    def test_longer_imdb_ids(self):
        """Modern titles can have 8+ digit IDs."""
        assert parse_imdb_id("tt12345678") == "12345678"
        assert parse_imdb_id("12345678") == "12345678"

    def test_imdb_pro_url(self):
        """IMDb Pro URLs."""
        assert parse_imdb_id("https://pro.imdb.com/title/tt1234567/") == "1234567"

    def test_minimum_valid_length(self):
        """Test boundary of minimum ID length (5 digits)."""
        assert parse_imdb_id("12345") == "12345"
        assert parse_imdb_id("1234") is None

    def test_non_imdb_url_with_tt_pattern(self):
        """Non-IMDb URLs containing tt pattern should not match."""
        # This tests that the regex properly anchors to imdb.com
        assert parse_imdb_id("https://example.com/title/tt1234567") is None
