"""
FilmAffinity Scraper Package

Backup your FilmAffinity data (watched movies, lists) to CSV files.
"""

from filmaffinity.scraper import (
    check_user,
    get_user_lists,
    get_list_movies,
    get_watched_movies,
    # Exceptions
    ScraperError,
    NetworkError,
    ConnectionFailedError,
    TimeoutError,
    RateLimitError,
    UserNotFoundError,
    ParseError,
)
from filmaffinity.exporters import export_to_letterboxd

__all__ = [
    # Functions
    'check_user',
    'get_user_lists',
    'get_list_movies',
    'get_watched_movies',
    'export_to_letterboxd',
    # Exceptions
    'ScraperError',
    'NetworkError',
    'ConnectionFailedError',
    'TimeoutError',
    'RateLimitError',
    'UserNotFoundError',
    'ParseError',
]
