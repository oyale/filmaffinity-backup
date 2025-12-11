"""
FilmAffinity web scraper.

Functions to parse FilmAffinity webpage and extract movie data.
"""
import re
import time
from typing import Optional

from bs4 import BeautifulSoup
import requests
from requests.exceptions import (
    ConnectionError,
    Timeout,
    RequestException,
)
from rich import print


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_COOLDOWN = 5  # seconds between requests
RATE_LIMIT_COOLDOWN = 30  # seconds to wait when rate limited (429)
MAX_RETRIES = 3  # max retries on rate limit


# =============================================================================
# Custom Exceptions
# =============================================================================

class ScraperError(Exception):
    """Base exception for FilmAffinity scraper errors."""
    pass


class NetworkError(ScraperError):
    """Raised when a network-related error occurs."""

    def __init__(self, message: str, url: str = None, cause: Exception = None):
        self.url = url
        self.cause = cause
        super().__init__(message)


class ConnectionFailedError(NetworkError):
    """Raised when unable to connect to FilmAffinity."""
    pass


class TimeoutError(NetworkError):
    """Raised when a request times out."""
    pass


class RateLimitError(NetworkError):
    """Raised when rate limited by FilmAffinity (HTTP 429)."""
    pass


class UserNotFoundError(ScraperError):
    """Raised when the specified user ID does not exist."""

    def __init__(self, user_id: str, url: str = None):
        self.user_id = user_id
        self.url = url
        super().__init__(f"User ID '{user_id}' not found on FilmAffinity")


class ParseError(ScraperError):
    """Raised when unable to parse FilmAffinity page content."""
    pass

# =============================================================================
# HTTP Session
# =============================================================================

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
})


# =============================================================================
# HTTP Request Helpers
# =============================================================================

def _format_network_error(error: Exception, url: str) -> str:
    """Format a network error with user-friendly guidance."""
    error_str = str(error).lower()

    if isinstance(error, ConnectionError):
        if 'name or service not known' in error_str or 'getaddrinfo failed' in error_str:
            return (
                f"DNS resolution failed - unable to resolve 'filmaffinity.com'.\n"
                f"  Possible causes:\n"
                f"    • No internet connection\n"
                f"    • DNS server is unreachable\n"
                f"    • FilmAffinity domain is blocked\n"
                f"  URL: {url}"
            )
        elif 'connection refused' in error_str:
            return (
                f"Connection refused by FilmAffinity server.\n"
                f"  Possible causes:\n"
                f"    • FilmAffinity is down or under maintenance\n"
                f"    • Your IP may be blocked\n"
                f"    • Firewall blocking the connection\n"
                f"  URL: {url}"
            )
        else:
            return (
                f"Unable to connect to FilmAffinity.\n"
                f"  Possible causes:\n"
                f"    • No internet connection\n"
                f"    • FilmAffinity is temporarily unavailable\n"
                f"    • Network firewall blocking access\n"
                f"  URL: {url}\n"
                f"  Details: {error}"
            )

    elif isinstance(error, Timeout):
        return (
            f"Request timed out while connecting to FilmAffinity.\n"
            f"  Possible causes:\n"
            f"    • Slow or unstable internet connection\n"
            f"    • FilmAffinity server is overloaded\n"
            f"  Try again in a few minutes.\n"
            f"  URL: {url}"
        )

    else:
        return (
            f"Network error while accessing FilmAffinity.\n"
            f"  URL: {url}\n"
            f"  Error: {error}"
        )


def request_with_retry(url: str, max_retries: int = MAX_RETRIES, timeout: int = 30) -> requests.Response:
    """
    Make a request with retry logic for rate limiting (429 errors).

    Args:
        url: URL to request.
        max_retries: Maximum number of retries on rate limiting.
        timeout: Request timeout in seconds.

    Returns:
        Response object.

    Raises:
        ConnectionFailedError: If unable to connect after retries.
        TimeoutError: If request times out.
        RateLimitError: If rate limited after all retries exhausted.
        NetworkError: For other network-related errors.
    """
    cooldown = RATE_LIMIT_COOLDOWN
    last_error = None

    for attempt in range(max_retries):
        try:
            response = session.get(url, verify=True, timeout=timeout)

            if response.status_code == 429:
                print(f"  [yellow]⚠️  Rate limited (429). Waiting {cooldown}s before retry ({attempt + 1}/{max_retries})...[/yellow]")
                time.sleep(cooldown)
                cooldown = min(cooldown * 2, 120)  # Exponential backoff
                continue

            return response

        except ConnectionError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"  [yellow]⚠️  Connection failed. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...[/yellow]")
                time.sleep(wait_time)
                continue
            raise ConnectionFailedError(
                _format_network_error(e, url),
                url=url,
                cause=e
            )

        except Timeout as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"  [yellow]⚠️  Request timed out. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...[/yellow]")
                time.sleep(wait_time)
                continue
            raise TimeoutError(
                _format_network_error(e, url),
                url=url,
                cause=e
            )

        except RequestException as e:
            raise NetworkError(
                _format_network_error(e, url),
                url=url,
                cause=e
            )

    # If we got here, we exhausted retries on 429
    raise RateLimitError(
        f"Rate limited by FilmAffinity after {max_retries} retries.\n"
        f"  FilmAffinity is blocking requests from your IP.\n"
        f"  Please wait 10-15 minutes before trying again.\n"
        f"  URL: {url}",
        url=url
    )


# =============================================================================
# User Functions
# =============================================================================

def check_user(user_id: str, lang: str = 'en') -> None:
    """
    Check that the provided user_id exists on FilmAffinity.

    Args:
        user_id: FilmAffinity user ID.
        lang: Language version ('es' or 'en'). Default: 'en' for better IMDb matching.

    Raises:
        UserNotFoundError: If user ID does not exist.
        RateLimitError: If rate limited by FilmAffinity.
        NetworkError: For other network-related errors.
    """
    url = f'https://www.filmaffinity.com/{lang}/userlists.php?user_id={user_id}'

    try:
        response = request_with_retry(url)
    except NetworkError:
        raise  # Re-raise with improved error messages

    if response.status_code == 404:
        raise UserNotFoundError(
            user_id=user_id,
            url=url
        )
    elif response.status_code != 200:
        raise NetworkError(
            f"Unexpected response from FilmAffinity (HTTP {response.status_code}).\n"
            f"  The server returned an unexpected status code.\n"
            f"  URL: {url}\n"
            f"  Status: {response.status_code} {response.reason}",
            url=url
        )


def get_user_lists(
    user_id: str,
    max_page: Optional[int] = None,
    lang: str = 'en',
) -> dict[str, str]:
    """
    Retrieve all public lists from a user.

    Args:
        user_id: FilmAffinity user ID.
        max_page: Maximum number of pages to retrieve (None = all).
        lang: Language version ('es' or 'en').

    Returns:
        Dictionary mapping list names to their URLs.
    """
    user_lists = {}
    page = 1

    while True:
        url = f'https://www.filmaffinity.com/{lang}/userlists.php?user_id={user_id}&p={page}'

        response = request_with_retry(url)
        if response.status_code != 200:
            break
        if max_page and page > max_page:
            break

        print(f'  [grey50]Parsing page {page}[/grey50]')
        soup = BeautifulSoup(response.text, "html.parser")
        lists = soup.find(attrs={'class': 'fa-list-group'})

        for tmp in lists.find_all('li'):
            ele = tmp.find(
                lambda tag: tag.name == "a" and tag.get("class", []) != ["ls-imgs"]
            )
            user_lists[ele.text] = ele['href']

        page += 1
        time.sleep(DEFAULT_COOLDOWN)

    return user_lists


# =============================================================================
# Movie Parsing Helpers
# =============================================================================

def get_original_title(movie_id: str) -> str:
    """
    Fetch the original title from the movie's detail page.

    Args:
        movie_id: FilmAffinity movie ID.

    Returns:
        Original title, or empty string if same as local title or not found.
    """
    url = f'https://www.filmaffinity.com/es/film{movie_id}.html'
    try:
        response = request_with_retry(url)
        if response.status_code != 200:
            return ''

        soup = BeautifulSoup(response.text, "html.parser")
        movie_info = soup.find('dl', attrs={'class': 'movie-info'})
        if not movie_info:
            return ''

        dt_elements = movie_info.find_all('dt')
        for dt in dt_elements:
            if 'original' in dt.text.lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    original_title = dd.get_text(strip=True)
                    if 'aka' in original_title:
                        original_title = original_title.split('aka')[0].strip()
                    return original_title
        return ''
    except Exception:
        return ''


def parse_movie_card(
    movie,
    info: dict,
    fetch_original_title: bool = True,
    lang: str = 'en',
) -> dict:
    """
    Parse a movie card element and add data to info dict.

    Args:
        movie: BeautifulSoup element for the movie card.
        info: Dictionary to append movie data to.
        fetch_original_title: Whether to fetch original title (extra request).
        lang: Language version ('es' or 'en').

    Returns:
        Updated info dictionary.
    """
    movie_id = movie['data-movie-id']
    info['FA movie ID'].append(movie_id)
    info['FA score'].append(movie.find(attrs={'class': 'avg'}).text)

    # Get full title text
    full_title = movie.find(attrs={'class': 'mc-title'}).find('a').text.strip()

    # Extract title - remove parenthetical part if present
    match = re.search(r'^(.+?)\s*\(([^)]+)\)\s*$', full_title)
    if match:
        local_title = match.group(1).strip()
    else:
        local_title = full_title

    info['title'].append(local_title)

    # Fetch original title (only needed for Spanish version)
    if fetch_original_title and lang == 'es':
        original_title = get_original_title(movie_id)
        if original_title and original_title.lower() != local_title.lower():
            info['original title'].append(original_title)
        else:
            info['original title'].append('')
        time.sleep(0.5)
    else:
        info['original title'].append('')

    info['country'].append(
        movie.find('img', attrs={'class': 'nflag'})['alt'].strip()
    )

    # Keep first non-zero year
    years = movie.find_all('span', attrs={'class': 'mc-year'})
    info['year'].append([i.text for i in years if i.text][0])

    # Join all directors
    directors = movie.find(attrs={'class': 'mc-director'})
    info['directors'].append(', '.join([i.text for i in directors.find_all('a')]))

    return info


# =============================================================================
# List/Watched Movie Functions
# =============================================================================

def get_list_movies(
    base_url: str,
    order_by: str = 'voto',
    max_page: Optional[int] = None,
    lang: str = 'en',
) -> tuple[str, dict]:
    """
    Retrieve all movies from a user list.

    Args:
        base_url: URL of the list.
        order_by: Sort order ('voto', 'titulo', 'año', etc.).
        max_page: Maximum number of pages to retrieve (None = all).
        lang: Language version ('es' or 'en').

    Returns:
        Tuple of (list_title, info_dict).
    """
    categories = {
        "posición": 0, "position": 0,
        "título": 1, "title": 1,
        "año": 2, "year": 2,
        "voto": 3, "rating": 3,
        "nota media": 4, "avg rating": 4,
    }
    order_id = categories.get(order_by, 3)

    info = {
        'title': [],
        'original title': [],
        'year': [],
        'country': [],
        'user score': [],
        'FA score': [],
        'FA movie ID': [],
        'directors': [],
    }

    page = 1
    title = ''

    while True:
        url = f'{base_url}&page={page}&orderby={order_id}'

        response = request_with_retry(url)
        if response.status_code != 200:
            break
        if max_page and page > max_page:
            break

        print(f'  [grey50]Parsing page {page}[/grey50]')
        soup = BeautifulSoup(response.text, "html.parser")

        if page == 1:
            ele = soup.find('span', attrs={'class': 'fs-5'})
            title = ele.text.split(':')[1].strip()

        movies = soup.find('ul', attrs={'class': 'fa-list-group'})
        for movie in movies.find_all('li'):
            info['user score'].append(
                movie.find(attrs={'class': 'fa-user-rat-box'}).text
            )
            info = parse_movie_card(movie, info, lang=lang)

        page += 1
        time.sleep(DEFAULT_COOLDOWN)

    return title, info


def get_watched_movies(
    user_id: str,
    max_page: Optional[int] = None,
    lang: str = 'en',
) -> dict:
    """
    Retrieve all watched (rated) movies from a user.

    Args:
        user_id: FilmAffinity user ID.
        max_page: Maximum number of pages to retrieve (None = all).
        lang: Language version ('es' or 'en').

    Returns:
        Dictionary with movie data.
    """
    info = {
        'genre': [],
        'title': [],
        'original title': [],
        'year': [],
        'country': [],
        'user score': [],
        'FA score': [],
        'FA movie ID': [],
        'directors': [],
    }
    orderby = 8  # order by genre

    page = 1
    while True:
        url = f'https://www.filmaffinity.com/{lang}/userratings.php?user_id={user_id}&p={page}&orderby={orderby}&chv=list'

        response = request_with_retry(url)
        if response.status_code != 200:
            break
        if max_page and page > max_page:
            break

        print(f'  [grey50]Parsing page {page}[/grey50]')
        soup = BeautifulSoup(response.text, "html.parser")

        groups = soup.find_all('div', attrs={'class': 'user-ratings-list-resp'})
        for group in groups:
            genre = ''  # Genre field is no longer present

            movies = group.find_all('div', class_='row mb-4')
            for movie in movies:
                info['genre'].append(genre)
                info['user score'].append(
                    movie.find(attrs={'class': 'fa-user-rat-box'}).text.strip()
                )
                movie = movie.find('div', attrs={'class': 'movie-card'})
                info = parse_movie_card(movie, info, lang=lang)

        page += 1
        time.sleep(DEFAULT_COOLDOWN)

    return info
