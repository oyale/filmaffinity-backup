"""
Unit tests for filmaffinity/exporters.py

Tests for the FilmAffinity export functions.
"""

import csv
import io
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filmaffinity.exporters import export_to_letterboxd


class TestExportToLetterboxd:
    """Test the export_to_letterboxd function."""

    def test_basic_export(self):
        """Test basic export with all fields populated."""
        films = {
            "title": ["The Matrix", "Inception"],
            "original title": ["The Matrix", "Inception"],
            "year": ["1999", "2010"],
            "user score": ["10", "9"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["Title"] == "The Matrix"
        assert rows[0]["Year"] == "1999"
        assert rows[0]["Rating10"] == "10"
        assert rows[0]["WatchedDate"] == ""
        assert rows[1]["Title"] == "Inception"
        assert rows[1]["Year"] == "2010"
        assert rows[1]["Rating10"] == "9"

    def test_prefers_original_title(self):
        """Test that original title is preferred over local title."""
        films = {
            "title": ["El secreto de sus ojos"],
            "original title": ["The Secret in Their Eyes"],
            "year": ["2009"],
            "user score": ["9"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == "The Secret in Their Eyes"

    def test_falls_back_to_local_title(self):
        """Test fallback to local title when original is empty."""
        films = {
            "title": ["Película Local"],
            "original title": [""],
            "year": ["2020"],
            "user score": ["7"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == "Película Local"

    def test_handles_whitespace_only_original_title(self):
        """Test that whitespace-only original title falls back to local."""
        films = {
            "title": ["Local Title"],
            "original title": ["   "],
            "year": ["2020"],
            "user score": ["8"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == "Local Title"

    def test_handles_none_original_title(self):
        """Test that None original title falls back to local."""
        films = {
            "title": ["Local Title"],
            "original title": [None],
            "year": ["2020"],
            "user score": ["8"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == "Local Title"

    def test_handles_missing_original_title_key(self):
        """Test export when original title key is missing entirely."""
        films = {
            "title": ["Only Local"],
            "year": ["2021"],
            "user score": ["6"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == "Only Local"

    def test_handles_empty_films(self):
        """Test export with empty films dict."""
        films = {}

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert len(rows) == 0

    def test_handles_mismatched_list_lengths(self):
        """Test export when dict lists have different lengths."""
        films = {
            "title": ["Film 1", "Film 2", "Film 3"],
            "original title": ["Original 1"],  # Only one
            "year": ["2020", "2021"],  # Only two
            "user score": ["8", "9", "7", "10"],  # Extra one
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        # Should produce 4 rows (max length from user score)
        assert len(rows) == 4
        assert rows[0]["Title"] == "Original 1"
        assert rows[0]["Year"] == "2020"
        assert rows[1]["Title"] == "Film 2"  # Falls back to local
        assert rows[1]["Year"] == "2021"
        assert rows[2]["Title"] == "Film 3"
        assert rows[2]["Year"] == ""  # Empty from zip_longest
        assert rows[3]["Title"] == ""  # Empty - no title at index 3

    def test_handles_empty_rating(self):
        """Test export when rating is empty or None."""
        films = {
            "title": ["No Rating Film"],
            "year": ["2022"],
            "user score": [""],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Rating10"] == ""

    def test_strips_rating_whitespace(self):
        """Test that rating whitespace is stripped."""
        films = {
            "title": ["Film"],
            "year": ["2022"],
            "user score": ["  8  "],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Rating10"] == "8"

    def test_export_to_file_path(self):
        """Test export to a file path."""
        films = {
            "title": ["Test Film"],
            "year": ["2023"],
            "user score": ["7"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            export_to_letterboxd(films, temp_path)

            with open(temp_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["Title"] == "Test Film"
        finally:
            os.unlink(temp_path)

    def test_export_to_pathlib_path(self):
        """Test export to a pathlib.Path object."""
        films = {
            "title": ["Pathlib Film"],
            "year": ["2023"],
            "user score": ["9"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_letterboxd.csv"
            export_to_letterboxd(films, path)

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["Title"] == "Pathlib Film"

    def test_csv_header_format(self):
        """Test that CSV header matches Letterboxd expected format."""
        films = {"title": ["Test"]}

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        # Read raw first line
        header = output.readline().strip()
        assert header == "Title,Year,Rating10,WatchedDate"

    def test_handles_special_characters(self):
        """Test export with special characters in title."""
        films = {
            "title": ['Film with "quotes" and, commas'],
            "year": ["2022"],
            "user score": ["8"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert rows[0]["Title"] == 'Film with "quotes" and, commas'

    def test_handles_unicode(self):
        """Test export with unicode characters."""
        films = {
            "title": ["日本語タイトル", "Película española", "Ελληνικά"],
            "year": ["2020", "2021", "2022"],
            "user score": ["8", "9", "7"],
        }

        output = io.StringIO()
        export_to_letterboxd(films, output)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["Title"] == "日本語タイトル"
        assert rows[1]["Title"] == "Película española"
        assert rows[2]["Title"] == "Ελληνικά"


class TestExporterImports:
    """Test that exporter module can be imported."""

    def test_import_from_module(self):
        from filmaffinity.exporters import export_to_letterboxd

        assert callable(export_to_letterboxd)

    def test_import_from_package(self):
        from filmaffinity import export_to_letterboxd

        assert callable(export_to_letterboxd)
