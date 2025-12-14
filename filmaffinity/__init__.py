"""
FilmAffinity Scraper Package

Backup your FilmAffinity data (watched movies, lists) to CSV files.
"""

from filmaffinity.exporters import export_to_json, export_to_letterboxd
from filmaffinity.scraper import (
    ConnectionFailedError,
    NetworkError,
    ParseError,
    RateLimitError,
    # Exceptions
    ScraperError,
    TimeoutError,
    UserNotFoundError,
    check_user,
    get_list_movies,
    get_user_lists,
    get_watched_movies,
)

__all__ = [
    # Functions
    "check_user",
    "get_user_lists",
    "get_list_movies",
    "get_watched_movies",
    "export_to_letterboxd",
    "export_to_json",
    # Exceptions
    "ScraperError",
    "NetworkError",
    "ConnectionFailedError",
    "TimeoutError",
    "RateLimitError",
    "UserNotFoundError",
    "ParseError",
]
