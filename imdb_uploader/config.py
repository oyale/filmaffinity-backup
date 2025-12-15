"""Configuration and session state management for IMDb uploader."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

# Import file locking - fcntl on Unix, msvcrt on Windows
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

from .constants import DEFAULT_CONFIG

__all__ = [
    "DEFAULT_CONFIG_PATHS",
    "load_config",
    "save_config",
    "create_default_config",
    "SessionState",
    "retry_on_http_error",
    "file_lock",
]

# =============================================================================
# Configuration File Support
# =============================================================================

DEFAULT_CONFIG_PATHS = [
    Path("upload_imdb.json"),
    Path("~/.config/upload_imdb/config.json").expanduser(),
    Path("~/.upload_imdb.json").expanduser(),
]


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from a JSON file and environment variables.

    Environment variables override config file settings for timing values:
    - PAGE_LOAD_WAIT: page_load_wait (float)
    - ELEMENT_WAIT: element_wait (float)
    - LOGIN_WAIT: login_wait (float)
    - CAPTCHA_WAIT: captcha_wait (float)
    - RATING_WAIT: rating_wait (float)
    - SEARCH_WAIT: search_wait (float)

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
                with open(path, encoding="utf-8") as f:
                    user_config = json.load(f)
                config.update(user_config)
                print(f"Loaded config from: {path}")
                break
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Could not load config from {path}: {e}")

    # Override with environment variables (for timing settings)
    # Environment variables take precedence over config file
    env_mappings = {
        "PAGE_LOAD_WAIT": ("page_load_wait", float),
        "ELEMENT_WAIT": ("element_wait", float),
        "LOGIN_WAIT": ("login_wait", float),
        "CAPTCHA_WAIT": ("captcha_wait", float),
        "RATING_WAIT": ("rating_wait", float),
        "SEARCH_WAIT": ("search_wait", float),
    }

    for env_var, (config_key, type_func) in env_mappings.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            try:
                config[config_key] = type_func(env_value)
                print(f"Loaded {config_key} from environment variable {env_var}")
            except ValueError as e:
                print(f"Warning: Invalid value for {env_var} ({env_value}): {e}")

    return config


def save_config(config: dict[str, Any], config_path: str) -> None:
    """Save configuration to a JSON file.

    Args:
        config: Configuration dictionary to save.
        config_path: Path to save the config file.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Saved config to: {path}")


def create_default_config(config_path: str) -> None:
    """Create a default configuration file.

    Args:
        config_path: Path where to create the config file.
    """
    save_config(DEFAULT_CONFIG, config_path)


# =============================================================================
# File Locking Utilities
# =============================================================================


@contextmanager
def file_lock(lock_path: Path, timeout: float = 10.0) -> Generator[None, None, None]:
    """Context manager for cross-platform file locking.

    Uses fcntl on Unix systems and msvcrt on Windows.
    Creates a separate lock file to avoid issues with the main file.

    Args:
        lock_path: Path to the lock file to create/use.
        timeout: Maximum time to wait for lock (seconds).

    Raises:
        TimeoutError: If lock cannot be acquired within timeout.
        IOError: If locking is not supported and timeout is exceeded.
    """
    lock_file = lock_path.with_suffix(".lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    lock_fd = None

    try:
        # Open or create lock file
        lock_fd = open(lock_file, "w")

        while True:
            try:
                if HAS_FCNTL:
                    # Unix: non-blocking exclusive lock
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                elif HAS_MSVCRT:
                    # Windows: lock the first byte
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                    break
                else:
                    # No locking available - proceed with warning
                    break
            except OSError:
                # Lock is held by another process
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Could not acquire lock on {lock_file} within {timeout}s")
                time.sleep(0.1)

        yield

    finally:
        if lock_fd is not None:
            try:
                if HAS_FCNTL:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                elif HAS_MSVCRT:
                    try:
                        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
                    except OSError:
                        pass
            except OSError:
                pass
            lock_fd.close()


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

    Thread-safety:
    - Uses file locking to prevent concurrent access
    - Uses atomic writes to prevent data corruption
    """

    def __init__(self, session_file: str = ".upload_imdb_session.json"):
        self.session_file = Path(session_file)
        self.csv_path: str | None = None
        self.current_index: int = 0
        self.stats: dict[str, Any] = {}
        self.processed_titles: list[str] = []
        self.skipped_items: list[dict] = []

    def load(self) -> bool:
        """Load session state from file with file locking.

        Uses file locking to prevent concurrent access from multiple processes.
        Also cleans up any orphaned temp files from previous crashes.

        Returns:
            True if session was loaded, False if no session file exists.
        """
        # Clean up orphaned temp files from previous crashes
        self._cleanup_orphaned_temp_files()

        if not self.session_file.exists():
            return False

        try:
            with file_lock(self.session_file):
                with open(self.session_file, encoding="utf-8") as f:
                    data = json.load(f)

                self.csv_path = data.get("csv_path")
                self.current_index = data.get("current_index", 0)
                self.stats = data.get("stats", {})
                self.processed_titles = data.get("processed_titles", [])
                self.skipped_items = data.get("skipped_items", [])
                return True
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load session from {self.session_file}: {e}")
            return False
        except TimeoutError as e:
            print(f"Warning: {e}")
            return False

    def _cleanup_orphaned_temp_files(self) -> None:
        """Remove orphaned temporary session files from previous crashes.

        Temp files matching '.session_*.tmp' in the session directory that are
        older than 1 hour are considered orphaned and removed.
        """
        try:
            parent_dir = self.session_file.parent
            if not parent_dir.exists():
                return

            current_time = time.time()
            max_age_seconds = 3600  # 1 hour

            for tmp_file in parent_dir.glob(".session_*.tmp"):
                try:
                    file_age = current_time - tmp_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        tmp_file.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    def save(self) -> None:
        """Save current session state to file atomically with file locking.

        Uses:
        - File locking to prevent concurrent access from multiple processes
        - Atomic write (write to temp file, then rename) to prevent
          data corruption if the process is interrupted mid-write
        """
        data = {
            "csv_path": self.csv_path,
            "current_index": self.current_index,
            "stats": self.stats,
            "processed_titles": self.processed_titles,
            "skipped_items": self.skipped_items,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            with file_lock(self.session_file):
                # Ensure parent directory exists
                self.session_file.parent.mkdir(parents=True, exist_ok=True)

                # Write to a temporary file in the same directory, then rename
                # This ensures atomic write - the file is either fully written or not at all
                fd, tmp_path = tempfile.mkstemp(
                    suffix=".tmp", prefix=".session_", dir=self.session_file.parent
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())  # Ensure data is written to disk

                    # Atomic rename (on POSIX systems)
                    os.replace(tmp_path, self.session_file)

                    # Sync directory to ensure rename is durable on power failure
                    # This is critical for crash consistency on some filesystems
                    self._sync_directory(self.session_file.parent)
                except Exception:
                    # Clean up temp file on error
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
        except OSError as e:
            print(f"Warning: Could not save session to {self.session_file}: {e}")
        except TimeoutError as e:
            print(f"Warning: {e}")

    @staticmethod
    def _sync_directory(dir_path: Path) -> None:
        """Sync directory to ensure file operations are durable.

        On POSIX systems, syncing the directory ensures that file renames
        and creations are persisted even on power failure.
        """
        try:
            dir_fd = os.open(str(dir_path), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            # O_DIRECTORY may not be available on all systems (e.g., Windows)
            # In that case, we skip directory sync - the file sync is still done
            pass

    def clear(self) -> None:
        """Clear the session file and associated lock file."""
        try:
            with file_lock(self.session_file, timeout=5.0):
                if self.session_file.exists():
                    self.session_file.unlink()
        except TimeoutError:
            # If we can't get the lock, try to delete anyway
            if self.session_file.exists():
                self.session_file.unlink()

        # Clean up lock file
        lock_file = self.session_file.with_suffix(".lock")
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass

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
        return self.csv_path is not None and self.csv_path == csv_path and self.current_index > 0

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

T = TypeVar("T")


def retry_on_http_error(
    max_retries: int = 3,
    initial_cooldown: float = 5.0,
    max_cooldown: float = 60.0,
    backoff_factor: float = 2.0,
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

                    is_http_error = any(
                        indicator in error_str
                        for indicator in (
                            "http error 5",
                            "500",
                            "503",
                            "429",
                            "internal server error",
                            "service unavailable",
                            "too many requests",
                            "httperror",
                        )
                    )

                    if is_http_error and attempt < max_retries - 1:
                        print(
                            f"  [retry] HTTP error detected, waiting {cooldown:.1f}s "
                            f"before retry ({attempt + 1}/{max_retries})..."
                        )
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
