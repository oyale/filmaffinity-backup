"""
IMDb Uploader Package

Upload movie ratings from FilmAffinity CSV to IMDb using Selenium.
"""

from imdb_uploader.uploader import (
    UploadIMDbError,
    BrowserStartError,
    LoginError,
    RatingError,
    CSVParseError,
    IMDbSearchError,
)

# Export from new modular structure
from imdb_uploader.constants import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIDENCE_THRESHOLD,
    SKIP_AMBIGUOUS,
    SKIP_NOT_FOUND,
    SKIP_SAME_RATING,
    MovieItem,
    SkippedEntry,
    IMDbMatch,
    Stats,
)
from imdb_uploader.config import (
    load_config,
    save_config,
    create_default_config,
    SessionState,
    retry_on_http_error,
)
from imdb_uploader.prompts import (
    beep,
    set_beep_enabled,
    is_beep_enabled,
    parse_imdb_id,
    prompt_existing_rating,
    prompt_confirm_match,
    prompt_low_confidence_match,
    prompt_select_candidate,
)

__all__ = [
    # Exceptions
    'UploadIMDbError',
    'BrowserStartError',
    'LoginError',
    'RatingError',
    'CSVParseError',
    'IMDbSearchError',
    # Constants
    'DEFAULT_CONFIG',
    'DEFAULT_CONFIDENCE_THRESHOLD',
    'SKIP_AMBIGUOUS',
    'SKIP_NOT_FOUND',
    'SKIP_SAME_RATING',
    # Type aliases
    'MovieItem',
    'SkippedEntry',
    'IMDbMatch',
    'Stats',
    # Config
    'load_config',
    'save_config',
    'create_default_config',
    'SessionState',
    'retry_on_http_error',
    # Prompts
    'beep',
    'set_beep_enabled',
    'is_beep_enabled',
    'parse_imdb_id',
    'prompt_existing_rating',
    'prompt_confirm_match',
    'prompt_low_confidence_match',
    'prompt_select_candidate',
]
