# FilmAffinity Backup & IMDb Uploader

[![Tests](https://github.com/oyale/filmaffinity-backup/actions/workflows/main.yml/badge.svg)](https://github.com/oyale/filmaffinity-backup/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/oyale/filmaffinity-backup/branch/main/graph/badge.svg)](https://codecov.io/gh/oyale/filmaffinity-backup)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Backup your [FilmAffinity](https://www.filmaffinity.com/) ratings and lists to CSV, then upload them to IMDb.

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [FilmAffinity Backup](#part-1-filmaffinity-backup)
5. [IMDb Uploader](#part-2-imdb-uploader)
6. [Requirements](#requirements)
7. [Usage](#usage)
8. [Configuration File](#configuration-file)
9. [Session Persistence](#session-persistence)
10. [Troubleshooting](#troubleshooting)
11. [License](#license)
12. [Acknowledgments](#acknowledgments)

---


> **Note**: Forked from [Ignacio Heredia/filmaffinity-backup](https://github.com/IgnacioHeredia/filmaffinity-backup) with IMDb upload support and other improvements.

> ⚠️ **Disclaimer**: This tool uses web scraping and browser automation techniques. Please use it responsibly:
>
> * Respect the Terms of Service of FilmAffinity and IMDb
> * Use reasonable delays between requests (built-in by default)
> * Only use this tool for personal, non-commercial purposes
> * Excessive or automated access may result in IP blocking or account suspension
> * The authors are not responsible for any misuse or consequences arising from using this tool

## Features

* **Backup FilmAffinity data** - Export watched movies and custom lists to CSV
* **Export to Letterboxd** - Generate Letterboxd-compatible CSV for easy import
* **Upload to IMDb** - Transfer your ratings to IMDb using Selenium automation
* **English title support** - Use English version of FilmAffinity for better IMDb matching
* **Resume support** - Continue interrupted sessions
* **Rate limiting** - Automatic retry with exponential backoff

---

## Installation

### From GitHub

```bash
# Basic installation (FilmAffinity backup only)
pip install git+https://github.com/oyale/filmaffinity-backup.git

# Full installation (includes IMDb uploader)
pip install "filmaffinity-backup[all] @ git+https://github.com/oyale/filmaffinity-backup.git"
```

### For Development

```bash
git clone https://github.com/oyale/filmaffinity-backup.git
cd filmaffinity-backup

# Editable install with all dependencies
pip install -e ".[all]"
```

### Manual Install

```bash
pip install -r requirements.txt
```

## Project Structure

```bash
filmaffinity-backup/
├── filmaffinity/          # FilmAffinity scraper package
│   ├── scraper.py         # Web scraping functions
│   └── cli.py             # Command-line interface
├── imdb_uploader/         # IMDb uploader package
│   ├── uploader.py        # Upload logic & Selenium automation
│   └── cli.py             # Command-line interface
├── tests/                 # Unit tests
├── data/                  # Downloaded CSV files (per user)
└── pyproject.toml         # Python packaging configuration
```

## Quick Start

```bash
# Step 1: Backup your FilmAffinity ratings
fa-backup YOUR_USER_ID

# Step 2: Upload to IMDb
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-rate
```

> **Tip**: If running without installing, use `python -m filmaffinity.cli` and `python -m imdb_uploader.cli` instead.

---

## Part 1: FilmAffinity Backup

Backup your FilmAffinity watched movies and custom lists to CSV files.

## Information Saved

* **list movies**: For each movie in the list, it saves:
  * `movie title`
  * `original title` (fetched from the movie detail page)
  * `movie year`
  * `movie country`
  * `movie directors`
  * `user score`
  * `Filmaffinity score`
  * `Filmaffinity movie id`
* **watched movies**: same as list movies, plus the `movie genre`

## Usage

To find your `user_id`, go to your ratings page and copy the ID from the URL:
`https://www.filmaffinity.com/en/userratings.php?user_id={YOUR_ID}`

```bash
# Basic backup (lists + watched)
fa-backup YOUR_USER_ID

# Only backup watched films (skip lists)
fa-backup YOUR_USER_ID --skip-lists

# Use Spanish titles instead of English
fa-backup YOUR_USER_ID --lang es

# Resume an interrupted session
fa-backup YOUR_USER_ID --resume
```

Your data will be saved to the `./data/{user_id}/` folder.

### Command Line Options (fa-backup)

| Option | Description |
|--------|-------------|
| `--skip-lists` | Skip downloading user lists, only get watched films |
| `--resume` | Resume an interrupted session, skip already downloaded lists/watched |
| `--lang` | Language for FilmAffinity (`es` or `en`). Default: `en` |
| `--data-dir` | Directory to save CSV files (default: `./data`) |
| `--format` | Export format: `csv` (default) or `letterboxd` |

### Letterboxd Export

Export your FilmAffinity ratings to Letterboxd-compatible CSV format:

```bash
# Backup with Letterboxd export
fa-backup YOUR_USER_ID --format letterboxd
```

This creates additional `*_letterboxd.csv` files alongside the standard CSV files. These can be directly imported into Letterboxd at https://letterboxd.com/import/.

The Letterboxd CSV includes:
- **Title** - Original title (English) when available, otherwise local title
- **Year** - Release year
- **Rating10** - Your rating on 1-10 scale
- **WatchedDate** - Left empty (FilmAffinity doesn't track this)

### Language Option (`--lang`)

By default, the script scrapes FilmAffinity's English version (`/en/`). Using `--lang es` switches to the Spanish version. English provides:

* **English/International titles** that match better with IMDb
* **Fewer HTTP requests** - no need to fetch original titles separately
* **Faster execution** - skips the per-movie detail page requests

**Note:** English is the default since it provides better IMDb matching. Spanish mode (`--lang es`) requires extra requests to fetch original titles, which is slower and more likely to trigger rate limiting.

### Rate Limiting

The script intentionally waits 5s between each parsing request to avoid getting the IP blocked by the FilmAffinity server. If a 429 (Too Many Requests) error is encountered, the script will automatically retry with exponential backoff (30s → 60s → 120s).

---

## Part 2: IMDb Uploader

Upload your FilmAffinity ratings to IMDb using Selenium automation. Supports dry-run mode for verifying mappings before making any changes.

### Recommended Workflow

```bash
# Step 1: Backup FilmAffinity ratings
fa-backup YOUR_USER_ID --skip-lists

# Step 2: Dry-run to verify IMDb mappings
fa-upload --csv data/YOUR_USER_ID/watched.csv --dry-run

# Step 3: Upload ratings
export IMDB_USERNAME="your_email"
export IMDB_PASSWORD="your_password"
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate
```

### Uploader Features

* **Dry-run mode**: Maps FilmAffinity titles to IMDb IDs without making any changes on IMDb.
* **Automated rating**: Uses Selenium to log in to IMDb and rate movies based on the CSV data.
* **Fuzzy matching**: Matches titles using fuzzy logic, with boosts for matching years and directors.
* **English title support**: Works best with CSVs generated using `--lang en` (titles already in English).
* **Original title fallback**: When using Spanish CSVs, can use the `original title` column for better IMDb matching.
* **Existing rating detection**: Detects if a movie is already rated on IMDb and prompts to skip or overwrite.
* **Same rating skip**: Automatically skips movies that are already rated with the same score on IMDb.
* **Manual IMDb ID entry**: When no match is found, manually enter an IMDb ID or URL.
* **Unattended mode**: Batch processing without user interaction.
* **Skipped movies export**: Saves skipped movies to separate CSV files by category for selective re-processing.
* **Retry by category**: Re-run only specific categories of skipped movies (ambiguous, not found, already rated, etc.).
* **CAPTCHA detection**: Detects CAPTCHA challenges during login and prompts user to solve them.
* **Rate limiting**: Automatic retry with exponential backoff on HTTP errors.
* **Config file support**: Save your settings to a JSON config file for easy reuse.
* **Session persistence**: Resume interrupted uploads from where you left off.

### Requirements

* Python 3.9+
* Selenium and webdriver-manager
* Cinemagoer (IMDbPY fork)

Install with:

```bash
pip install -e ".[imdb]"
```

Or manually:

```bash
pip install selenium webdriver-manager cinemagoer
```

### Uploader Usage

#### Dry-run Mode

Verify mappings between FilmAffinity titles and IMDb IDs:

```bash
fa-upload --csv data/YOUR_USER_ID/watched.csv --dry-run --dry-run-output imdb_matches.csv
```

This generates a CSV file (`imdb_matches.csv`) with the following columns:

* `local_title`: Title from the FilmAffinity CSV
* `local_year`: Year from the FilmAffinity CSV
* `local_director`: Director(s) from the FilmAffinity CSV
* `imdb_id`: Matched IMDb ID
* `imdb_title`: Matched IMDb title
* `imdb_year`: Matched IMDb year
* `score`: Confidence score of the match
* `query`: Search query used
* `result_count`: Number of results returned by IMDb

#### Automated Rating

To automatically rate movies on IMDb:

1. Set your IMDb credentials as environment variables:

   ```bash
   export IMDB_USERNAME="your_username"
   export IMDB_PASSWORD="your_password"
   ```

2. Run the script with the `--auto-rate` flag:

   ```bash
   fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate
   ```

#### Unattended Mode (Batch Processing)

For fully automated batch processing without any user prompts:

```bash
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate --unattended
```

In unattended mode:

* Ambiguous matches (title/year mismatch) are automatically skipped
* Already-rated movies are automatically skipped
* Failed auto-ratings are skipped (no manual fallback)
* All skipped items are saved to a CSV file for later review

#### No-Overwrite Mode

To only add new ratings without overwriting existing ones, but still handle ambiguous matches interactively:

```bash
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate --no-overwrite
```

This is useful when you want to:

* Skip movies you've already rated on IMDb
* But still manually resolve title/year mismatches when the match is ambiguous

```bash
# Retry already-rated movies (to update ratings)
fa-upload --retry already_rated --auto-login --auto-rate
```

#### Handling Ambiguous Matches

When a movie match is ambiguous (title or year doesn't match exactly), the script shows a selection dialog:

```text
======================================================================
🔍  AMBIGUOUS MATCH - Please select the correct movie
======================================================================
  CSV Data (from FilmAffinity):
    Title:    El secreto de sus ojos
    Year:     2009
    Director: Juan José Campanella
----------------------------------------------------------------------
  IMDb Candidates:
----------------------------------------------------------------------
  [1] The Secret in Their Eyes (2009) - Juan José Campanella
      IMDb ID: tt1305806 | Confidence: 85.3%
  [2] Secret in Their Eyes (2015) - Billy Ray
      IMDb ID: tt1741273 | Confidence: 72.1%
----------------------------------------------------------------------
  Enter 1-2 to select, [M]anual IMDb ID, [S]kip, or [Q]uit
```

#### Re-processing Skipped Movies

After a run, skipped movies are saved to separate CSV files in the `skipped/` directory, organized by category:

* `skipped_ambiguous.csv` - Movies with ambiguous IMDb matches
* `skipped_not_found.csv` - Movies not found on IMDb
* `skipped_already_rated.csv` - Movies already rated on IMDb (different score)
* `skipped_same_rating.csv` - Movies already rated with the same score (no action needed)
* `skipped_auto_rate_failed.csv` - Movies where auto-rating failed
* `skipped_user_choice.csv` - Movies manually skipped by user
* `skipped_all.csv` - Combined file with all skipped movies

Use the `--retry` option to re-process specific categories:

```bash
# Retry all skipped movies
fa-upload --retry all --auto-login --auto-rate

# Retry only ambiguous matches (with manual selection)
fa-upload --retry ambiguous --auto-login --auto-rate

# Retry movies that weren't found (maybe IMDb added them since)
fa-upload --retry not_found --auto-login --auto-rate

# Retry already-rated movies (to update ratings)
fa-upload --retry already_rated --auto-login --auto-rate

# Use a custom skipped directory
fa-upload --retry all --skipped-dir my_skipped/ --auto-login --auto-rate
```

#### Command Line Options (fa-upload)

| Option | Description |
|--------|-------------|
| `--csv` | Path to the FilmAffinity CSV file (required unless using `--retry` or `--resume`) |
| `--dry-run` | Only map titles to IMDb IDs, don't rate anything |
| `--dry-run-output` | Output path for dry-run CSV (default: `imdb_matches.csv`) |
| `--auto-login` | Try automated login using `IMDB_USERNAME`/`IMDB_PASSWORD` env vars |
| `--auto-rate` | Automatically click rating stars (best-effort) |
| `--headless` | Run browser in headless mode (no UI) |
| `--no-overwrite` | Never overwrite existing IMDb ratings (auto-skip already rated) |
| `--unattended` | Run without user interaction, skip ambiguous matches and existing ratings |
| `--skipped-dir` | Output directory for skipped CSV files by category (default: `skipped/`) |
| `--retry` | Re-run using skipped movies: `all`, `ambiguous`, `not_found`, `already_rated`, `auto_rate_failed`, `user_skipped` |
| `--start` | Start processing from a specific index in the CSV |
| `--limit` | Limit the number of items processed |
| `--confirm-threshold` | Confidence threshold for low-confidence warnings (default: 0.75) |
| `--no-confirm` | Skip all confirmation prompts (use with caution) |
| `--debug` | Enable debug output for troubleshooting |
| `--config` | Path to JSON config file (searches `upload_imdb.json`, `~/.config/upload_imdb/config.json` by default) |
| `--save-config PATH` | Save current options to a config file and exit |
| `--show-config` | Show current configuration and exit |
| `--resume` | Resume previous interrupted session |
| `--clear-session` | Clear saved session and start fresh |
| `--session-file` | Path to session file (default: `.upload_imdb_session.json`) |

#### Configuration File

You can save your frequently used options to a JSON config file:

```bash
# Save current options to config file
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate --save-config upload_imdb.json

# Show current configuration
fa-upload --show-config

# Use a specific config file
fa-upload --csv data/YOUR_USER_ID/watched.csv --config my_config.json
```

Example config file (`upload_imdb.json`):

```json
{
    "headless": false,
    "auto_login": true,
    "auto_rate": true,
    "confirm_threshold": 0.75,
    "no_overwrite": false,
    "skipped_dir": "skipped",
    "max_retries": 3
}
```

The script searches for config files in this order:

1. Path specified with `--config`
2. `upload_imdb.json` (current directory)
3. `~/.config/upload_imdb/config.json`
4. `~/.upload_imdb.json`

#### Session Persistence

The script automatically saves progress, allowing you to resume interrupted sessions:

```bash
# Start a new session
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate

# If interrupted, resume from where you left off
fa-upload --resume

# Clear session and start fresh
fa-upload --csv data/YOUR_USER_ID/watched.csv --clear-session
```

Session state includes:

* Current position in the CSV
* Statistics (applied, skipped counts)
* List of processed movies

## Notes

* **Dry-run recommended**: Always run the script in dry-run mode first to verify mappings.
* **IMDb login**: The script supports both manual and automated login. Automated login may fail if IMDb changes its login flow.
* **Terms of Service**: Automated interactions with IMDb may violate their terms of service. Use responsibly.

## Troubleshooting

* **Cinemagoer not installed**: If `cinemagoer` (IMDbPY fork) is not installed, the script will skip lookups in dry-run mode. Install it using:

  ```bash
  pip install cinemagoer
  ```

* **WebDriver issues**: Ensure your browser and WebDriver versions are compatible. The script uses webdriver-manager to auto-download the correct driver.

## License

This project is licensed under the AGPL-3.0-or-later License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

* Original FilmAffinity backup tool by [Ignacio Heredia](https://github.com/IgnacioHeredia/filmaffinity-backup)
* [Cinemagoer](https://github.com/cinemagoer/cinemagoer) (IMDbPY fork) for IMDb data access
* [Selenium](https://www.selenium.dev/) for browser automation
