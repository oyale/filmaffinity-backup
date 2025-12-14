"""
IMDb Uploader Package

Upload movie ratings from FilmAffinity CSV to IMDb using Selenium.
"""

from imdb_uploader.config import (
    SessionState,
    create_default_config,
    load_config,
    retry_on_http_error,
    save_config,
)

# Export from new modular structure
from imdb_uploader.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_CONFIG,
    SKIP_AMBIGUOUS,
    SKIP_NOT_FOUND,
    SKIP_SAME_RATING,
    IMDbMatch,
    MovieItem,
    SkippedEntry,
    Stats,
)
from imdb_uploader.prompts import (
    beep,
    is_beep_enabled,
    parse_imdb_id,
    prompt_confirm_match,
    prompt_existing_rating,
    prompt_low_confidence_match,
    prompt_select_candidate,
    set_beep_enabled,
)
from imdb_uploader.uploader import (
    BrowserStartError,
    CSVParseError,
    IMDbSearchError,
    LoginError,
    RatingError,
    UploadIMDbError,
)

__all__ = [
    # Exceptions
    "UploadIMDbError",
    "BrowserStartError",
    "LoginError",
    "RatingError",
    "CSVParseError",
    "IMDbSearchError",
    # Constants
    "DEFAULT_CONFIG",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "SKIP_AMBIGUOUS",
    "SKIP_NOT_FOUND",
    "SKIP_SAME_RATING",
    # Type aliases
    "MovieItem",
    "SkippedEntry",
    "IMDbMatch",
    "Stats",
    # Config
    "load_config",
    "save_config",
    "create_default_config",
    "SessionState",
    "retry_on_http_error",
    # Prompts
    "beep",
    "set_beep_enabled",
    "is_beep_enabled",
    "parse_imdb_id",
    "prompt_existing_rating",
    "prompt_confirm_match",
    "prompt_low_confidence_match",
    "prompt_select_candidate",
]
