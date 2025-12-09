"""
FilmAffinity Scraper Package

Backup your FilmAffinity data (watched movies, lists) to CSV files.
"""

from filmaffinity.scraper import (
    check_user,
    get_user_lists,
    get_list_movies,
    get_watched_movies,
)

__all__ = [
    'check_user',
    'get_user_lists',
    'get_list_movies',
    'get_watched_movies',
]
