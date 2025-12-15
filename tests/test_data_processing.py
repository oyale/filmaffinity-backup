"""
Unit tests for imdb_uploader/data_processing.py

Tests for CSV reading, text normalization, and IMDb matching functions.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

# Add project root to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock IMDbPY before importing (in case it's not installed in test env)
sys.modules["imdb"] = MagicMock()
sys.modules["imdb.Cinemagoer"] = MagicMock()
sys.modules["imdb.IMDb"] = MagicMock()

# Import the module
from imdb_uploader.data_processing import (  # noqa: E402
    find_imdb_match,
    normalize_text,
    read_csv,
)


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_none_input(self):
        assert normalize_text(None) == ""

    def test_basic_lowercase(self):
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_strip_whitespace(self):
        assert normalize_text("  hello  world  ") == "hello world"

    def test_remove_accents(self):
        assert normalize_text("café") == "cafe"
        assert normalize_text("naïve") == "naive"
        assert normalize_text("Amélie") == "amelie"

    def test_remove_punctuation(self):
        assert normalize_text("hello, world!") == "hello world"
        assert normalize_text("it's a test") == "it s a test"

    def test_spanish_article_removal(self):
        assert normalize_text("El Padrino") == "padrino"
        assert normalize_text("La Casa") == "casa"
        assert normalize_text("Los Otros") == "otros"
        assert normalize_text("Las Chicas") == "chicas"
        assert normalize_text("Un Hombre") == "hombre"
        assert normalize_text("Una Mujer") == "mujer"

    def test_complex_title(self):
        result = normalize_text("El Señor de los Anillos: La Comunidad del Anillo")
        assert "senor" in result and "anillos" in result and "comunidad" in result

    def test_preserve_alphanumeric(self):
        assert normalize_text("Hello123") == "hello123"


class TestReadCSV:
    """Tests for read_csv function."""

    def test_basic_csv(self):
        """Test reading a basic CSV file."""
        csv_content = """title;year;directors;user score;original title
The Matrix;1999;Wachowski Sisters;9;
Inception;2010;Christopher Nolan;8;Dreams Within Dreams
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                items = read_csv(f.name)
                assert len(items) == 2

                # Check first item
                assert items[0]["title"] == "The Matrix"
                assert items[0]["year"] == "1999"
                assert items[0]["directors"] == "Wachowski Sisters"
                assert items[0]["score"] == 9
                assert items[0]["original_title"] == ""

                # Check second item
                assert items[1]["title"] == "Inception"
                assert items[1]["year"] == "2010"
                assert items[1]["directors"] == "Christopher Nolan"
                assert items[1]["score"] == 8
                assert items[1]["original_title"] == "Dreams Within Dreams"

            finally:
                os.unlink(f.name)

    def test_empty_csv(self):
        """Test reading an empty CSV file."""
        csv_content = "title;year;directors;user score;original title\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                items = read_csv(f.name)
                assert len(items) == 0
            finally:
                os.unlink(f.name)

    def test_alternative_column_names(self):
        """Test reading CSV with alternative column names."""
        csv_content = """Title;Year;Director;Score;Original Title
The Matrix;1999;Wachowski Sisters;9;
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                items = read_csv(f.name)
                assert len(items) == 1
                assert items[0]["title"] == "The Matrix"
                assert items[0]["year"] == "1999"
            finally:
                os.unlink(f.name)

    def test_decimal_score(self):
        """Test reading CSV with decimal scores."""
        csv_content = """title;year;directors;user score;original title
The Matrix;1999;Wachowski Sisters;8.5;
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                items = read_csv(f.name)
                assert len(items) == 1
                assert items[0]["score"] == 8
            finally:
                os.unlink(f.name)

    def test_skip_empty_title(self):
        """Test that rows with empty titles are skipped."""
        csv_content = """title;year;directors;user score;original title
;1999;Wachowski Sisters;9;
The Matrix;1999;Wachowski Sisters;9;
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                items = read_csv(f.name)
                assert len(items) == 1
                assert items[0]["title"] == "The Matrix"
            finally:
                os.unlink(f.name)


class TestFindImdbMatch:
    """Tests for find_imdb_match function."""

    @patch("imdb_uploader.data_processing.IMDbPYClient")
    def test_find_imdb_match_success(self, mock_imdb_class):
        """Test successful IMDb match."""
        # Mock IMDb client
        mock_client = MagicMock()
        mock_imdb_class.return_value = mock_client

        # Mock search result
        mock_movie = MagicMock()
        mock_movie.movieID = "0133093"
        mock_movie.get.return_value = "The Matrix"
        mock_client.search_movie.return_value = [mock_movie]

        result = find_imdb_match("The Matrix", "1999", ia=mock_client)

        assert result is not None
        assert result["movieID"] == "0133093"
        assert result["title"] == "The Matrix"
        mock_client.search_movie.assert_called_once()

    @patch("imdb_uploader.data_processing.IMDbPYClient")
    def test_find_imdb_match_no_results(self, mock_imdb_class):
        """Test when no IMDb results are found."""
        mock_client = MagicMock()
        mock_imdb_class.return_value = mock_client
        mock_client.search_movie.return_value = []

        result = find_imdb_match("Unknown Movie", None, ia=mock_client)

        assert result is None

    @patch("imdb_uploader.data_processing.IMDbPYClient")
    def test_find_imdb_match_with_director(self, mock_imdb_class):
        """Test IMDb match with director filtering."""
        mock_client = MagicMock()
        mock_imdb_class.return_value = mock_client

        # Mock two movies - one by Nolan, one by someone else
        mock_movie1 = MagicMock()
        mock_movie1.movieID = "0133093"
        mock_movie1.get.return_value = "The Matrix"
        mock_movie1.data = {"director": [{"name": "Wachowski"}]}

        mock_movie2 = MagicMock()
        mock_movie2.movieID = "0270846"
        mock_movie2.get.return_value = "The Matrix"
        mock_movie2.data = {"director": [{"name": "Nolan"}]}

        mock_client.search_movie.return_value = [mock_movie1, mock_movie2]

        result = find_imdb_match("The Matrix", "1999", ia=mock_client, director="Wachowski")

        assert result is not None

    def test_find_imdb_match_no_client(self):
        """Test when no IMDb client is provided."""
        result = find_imdb_match("The Matrix", "1999", ia=None)
        assert result is None
