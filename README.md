# FilmAffinity Backup & IMDb Uploader

[![Tests](https://github.com/oyale/filmaffinity-backup/actions/workflows/main.yml/badge.svg)](https://github.com/oyale/filmaffinity-backup/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/oyale/filmaffinity-backup/branch/main/graph/badge.svg)](https://codecov.io/gh/oyale/filmaffinity-backup)
[![PyPI - Version](https://img.shields.io/pypi/v/filmaffinity-backup)](https://pypi.org/project/filmaffinity-backup/)
[![Conda - Version](https://anaconda.org/oyale/filmaffinity-backup/badges/version.svg)](https://anaconda.org/oyale/filmaffinity-backup)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Backup your [FilmAffinity](https://www.filmaffinity.com/) ratings and lists, then push them to IMDb with a single workflow.

> **Note**: Forked from [Ignacio Heredia/filmaffinity-backup](https://github.com/IgnacioHeredia/filmaffinity-backup) with IMDb upload support and numerous UX improvements.

> ⚠️ **Responsible use**: This project relies on web scraping and browser automation. Respect FilmAffinity/IMDb ToS, keep request rates low (already throttled), and only use it for personal archiving. The authors are not responsible for misuse or account restrictions that stem from automation.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Usage](#usage)
5. [Documentation](#documentation)
6. [Project Structure](#project-structure)
7. [Troubleshooting](#troubleshooting)
8. [License](#license)
9. [Acknowledgments](#acknowledgments)

---

## Overview

FilmAffinity Backup & IMDb Uploader is a two-part toolkit:

1. **FilmAffinity Backup** scrapes your watched list and custom lists into CSV/JSON/Letterboxd files.
2. **IMDb Uploader** ingests those exports and syncs the ratings to IMDb using Selenium.

### Highlights

- The scraper captures titles, original titles, year, country, directors, genres, scores, and FilmAffinity IDs.
- Letterboxd-ready CSV and JSON exports let you reuse the data in other services or custom scripts.
- Built-in delays, retries, and resume support keep long backups and uploads resilient.
- The uploader offers dry-run analysis, fuzzy matching with manual overrides, unattended mode, and skipped-movie retry buckets.
- Config files and session persistence help automate recurring migrations.

---

## Installation

```bash
# FilmAffinity backup only
pip install filmaffinity-backup

# Full toolchain (backup + IMDb uploader dependencies)
pip install "filmaffinity-backup[all]"
```

Conda users can grab the base package from the oyale channel:

```bash
conda install -c oyale filmaffinity-backup
```

> Conda builds ship the base CLI; use pip extras if you need optional `[all]` dependencies on top.

For development:

```bash
git clone https://github.com/oyale/filmaffinity-backup.git
cd filmaffinity-backup
pip install -e ".[all]"
```

Legacy/manual install:

```bash
pip install -r requirements.txt
```

---

## Quick Start

```bash
# 1) Export your FilmAffinity data (lists + watched)
fa-backup YOUR_USER_ID

# 2) Upload the watched CSV to IMDb
env IMDB_USERNAME="you@example.com" IMDB_PASSWORD="super-secret" \
  fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate
```

> Running from the repo? Replace `fa-backup` with `python -m filmaffinity.cli` and `fa-upload` with `python -m imdb_uploader.cli`.

---

## Usage

### FilmAffinity Backup (`fa-backup`)

- Discover your `user_id` from `https://www.filmaffinity.com/en/userratings.php?user_id=<ID>` and run `fa-backup <ID>`.
- Use `--skip-lists`, `--resume`, `--lang {en,es}`, `--format letterboxd`, or `--format json` depending on your workflow.
- Output lives under `./data/<user_id>/` by default.

See [`docs/filmaffinity-backup.md`](docs/filmaffinity-backup.md) for the full CLI reference, export formats, and rate-limiting details.

### IMDb Uploader (`fa-upload`)

- Start with a dry run: `fa-upload --csv data/<ID>/watched.csv --dry-run --dry-run-output imdb_matches.csv`.
- When ready, set `IMDB_USERNAME`/`IMDB_PASSWORD`, add `--auto-login --auto-rate`, and optionally `--unattended` for zero prompts.
- Skipped movies are saved under `skipped/`; rerun them with `--retry ambiguous`, `--retry not_found`, etc.

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

Check [`docs/imdb-uploader.md`](docs/imdb-uploader.md) for advanced workflows, command reference, config files, and troubleshooting tips.

---

## Documentation

- [`docs/filmaffinity-backup.md`](docs/filmaffinity-backup.md) – FilmAffinity backup usage, options, and exports.
- [`docs/imdb-uploader.md`](docs/imdb-uploader.md) – IMDb uploader workflows, CLI flags, and troubleshooting.
- [CONTRIBUTING.md](CONTRIBUTING.md) – Development guidelines.
- [ROADMAP.md](ROADMAP.md) – Upcoming features and backlog.

---

## Project Structure

```bash
filmaffinity-backup/
├── filmaffinity/          # FilmAffinity scraper package & CLI
├── imdb_uploader/         # IMDb uploader package & CLI
├── tests/                 # Unit and integration tests
├── data/                  # User exports (created at runtime)
└── pyproject.toml         # Python packaging metadata
```

---

## Troubleshooting

- **Cinemagoer missing?** Install it separately: `pip install cinemagoer`.
- **WebDriver issues?** Keep your browser updated so webdriver-manager can download a matching driver.
- **Automation blocked?** CAPTCHA or ToS changes can interrupt uploads—fall back to manual steps and resume once cleared.

---

## License

This project is licensed under the AGPL-3.0-or-later License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- Original FilmAffinity backup tool by [Ignacio Heredia](https://github.com/IgnacioHeredia/filmaffinity-backup)
- [Cinemagoer](https://github.com/cinemagoer/cinemagoer) for IMDb metadata
- [Selenium](https://www.selenium.dev/) for browser automation
