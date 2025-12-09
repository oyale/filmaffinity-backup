"""Configuration and session state management for IMDb uploader."""

from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from .constants import DEFAULT_CONFIG

__all__ = [
    'DEFAULT_CONFIG_PATHS',
    'load_config',
    'save_config',
    'create_default_config',
    'SessionState',
    'retry_on_http_error',
]

# =============================================================================
# Configuration File Support
# =============================================================================

DEFAULT_CONFIG_PATHS = [
    Path('upload_imdb.json'),
    Path('~/.config/upload_imdb/config.json').expanduser(),
    Path('~/.upload_imdb.json').expanduser(),
]


def load_config(config_path: Optional[str] = None) -> dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        config_path: Explicit path to config file. If None, searches default locations.

    Returns:
        Configuration dictionary with defaults applied.
    """
    config = DEFAULT_CONFIG.copy()

    # Determine which config file to load
    paths_to_try = [Path(config_path)] if config_path else DEFAULT_CONFIG_PATHS

    for path in paths_to_try:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                config.update(user_config)
                print(f"Loaded config from: {path}")
                break
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config from {path}: {e}")

    return config


def save_config(config: dict[str, Any], config_path: str) -> None:
    """Save configuration to a JSON file.

    Args:
        config: Configuration dictionary to save.
        config_path: Path to save the config file.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print(f"Saved config to: {path}")


def create_default_config(config_path: str) -> None:
    """Create a default configuration file.

    Args:
        config_path: Path where to create the config file.
    """
    save_config(DEFAULT_CONFIG, config_path)


# =============================================================================
# Session State Persistence
# =============================================================================

class SessionState:
    """Manages session state for resuming interrupted uploads.

    The session tracks:
    - The CSV file being processed
    - Current position (index)
    - Statistics
    - List of processed movie titles (to detect duplicates)
    """

    def __init__(self, session_file: str = '.upload_imdb_session.json'):
        self.session_file = Path(session_file)
        self.csv_path: Optional[str] = None
        self.current_index: int = 0
        self.stats: dict[str, Any] = {}
        self.processed_titles: list[str] = []
        self.skipped_items: list[dict] = []

    def load(self) -> bool:
        """Load session state from file.

        Returns:
            True if session was loaded, False if no session file exists.
        """
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.csv_path = data.get('csv_path')
            self.current_index = data.get('current_index', 0)
            self.stats = data.get('stats', {})
            self.processed_titles = data.get('processed_titles', [])
            self.skipped_items = data.get('skipped_items', [])
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load session from {self.session_file}: {e}")
            return False

    def save(self) -> None:
        """Save current session state to file."""
        data = {
            'csv_path': self.csv_path,
            'current_index': self.current_index,
            'stats': self.stats,
            'processed_titles': self.processed_titles,
            'skipped_items': self.skipped_items,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save session to {self.session_file}: {e}")

    def clear(self) -> None:
        """Clear the session file."""
        if self.session_file.exists():
            self.session_file.unlink()
        self.csv_path = None
        self.current_index = 0
        self.stats = {}
        self.processed_titles = []
        self.skipped_items = []

    def is_resumable(self, csv_path: str) -> bool:
        """Check if this session can be resumed for the given CSV.

        Args:
            csv_path: Path to the CSV file to process.

        Returns:
            True if there's a matching session that can be resumed.
        """
        return (
            self.csv_path is not None and
            self.csv_path == csv_path and
            self.current_index > 0
        )

    def mark_processed(self, title: str, index: int) -> None:
        """Mark a movie as processed.

        Args:
            title: The movie title that was processed.
            index: The current index in the item list.
        """
        self.processed_titles.append(title)
        self.current_index = index

    def get_resume_info(self) -> str:
        """Get a human-readable summary of the session state."""
        if not self.csv_path:
            return "No active session"

        return (
            f"Session for: {self.csv_path}\n"
            f"  Progress: {self.current_index} items processed\n"
            f"  Applied: {self.stats.get('applied', 0)}\n"
            f"  Skipped: {len(self.skipped_items)}"
        )


# =============================================================================
# Retry Decorator
# =============================================================================

T = TypeVar('T')


def retry_on_http_error(
    max_retries: int = 3,
    initial_cooldown: float = 5.0,
    max_cooldown: float = 60.0,
    backoff_factor: float = 2.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a function on HTTP errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_cooldown: Initial wait time in seconds before first retry.
        max_cooldown: Maximum wait time between retries.
        backoff_factor: Multiplier for cooldown after each retry.

    Returns:
        Decorated function that automatically retries on HTTP errors.

    Example:
        @retry_on_http_error(max_retries=3)
        def fetch_data():
            # ... code that might fail with HTTP errors
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            cooldown = initial_cooldown
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    is_http_error = any(indicator in error_str for indicator in (
                        'http error 5', '500', '503', '429',
                        'internal server error', 'service unavailable',
                        'too many requests', 'httperror'
                    ))

                    if is_http_error and attempt < max_retries - 1:
                        print(f"  [retry] HTTP error detected, waiting {cooldown:.1f}s "
                              f"before retry ({attempt + 1}/{max_retries})...")
                        time.sleep(cooldown)
                        cooldown = min(cooldown * backoff_factor, max_cooldown)
                    else:
                        raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper
    return decorator
