"""
FilmAffinity Scraper - Legacy Module

This file is kept for backward compatibility.
The new module is: filmaffinity.scraper
"""

# Re-export from new location for backward compatibility
from filmaffinity.scraper import (
    check_user,
    get_user_lists,
    get_list_movies,
    get_watched_movies,
    get_original_title,
    parse_movie_card,
    request_with_retry,
    session,
    DEFAULT_COOLDOWN,
    RATE_LIMIT_COOLDOWN,
    MAX_RETRIES,
)
