# IMDb Uploader CLI

The `fa-upload` command ingests a FilmAffinity CSV (generated via
`fa-backup`) and applies those ratings to your IMDb account with Selenium.

## Recommended workflow

```bash
# 1. Export FilmAffinity ratings (prefer English titles)
fa-backup YOUR_USER_ID --skip-lists

# 2. Verify IMDb matches without touching your account
fa-upload --csv data/YOUR_USER_ID/watched.csv --dry-run --dry-run-output imdb_matches.csv

# 3. Perform the upload
export IMDB_USERNAME="you@example.com"
export IMDB_PASSWORD="super-secret"
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate
```

Pass `--csv` when rating live data, or use `--retry <category>` to work off the
files saved in `skipped/`.

## Feature highlights

- **Dry-run mode** reports mappings (`local_title`, `imdb_id`, confidence score)
  to a CSV so you can fix mismatches ahead of time.
- **Auto login & rating** uses Selenium + webdriver-manager to handle the sign-in
  flow and click the rating widget.
- **Fuzzy matching** boosts matches that share the same year/director and lets
  you enter an IMDb ID manually when no good candidate exists.
- **Session persistence** remembers progress across interruptions.
- **Skipped buckets & retry filters** separate ambiguous, not-found, already-rated,
  and other categories so you can focus retries on a specific subset.

## Command-line reference

```
fa-upload --csv PATH [OPTIONS]
```

| Option | Description |
| --- | --- |
| `--dry-run` | Resolve IMDb IDs without writing ratings |
| `--dry-run-output FILE` | Output path for dry-run CSV (default: `imdb_matches.csv`) |
| `--auto-login` | Use `IMDB_USERNAME`/`IMDB_PASSWORD` env vars for sign-in |
| `--auto-rate` | Click the star widget automatically once logged in |
| `--headless` | Launch the browser in headless mode |
| `--no-overwrite` | Never touch ratings that already exist on IMDb |
| `--unattended` | Skip prompts; ambiguous or risky matches are skipped |
| `--skipped-dir DIR` | Directory for skipped CSVs (default: `skipped/`) |
| `--retry {all,ambiguous,not_found,already_rated,auto_rate_failed,user_skipped}` | Re-run specific skipped buckets |
| `--confirm-threshold FLOAT` | Minimum confidence before asking for confirmation |
| `--no-confirm` | Accept every match above the threshold automatically |
| `--config PATH` | Supply a JSON config file (see below) |
| `--save-config PATH` | Persist the current flags to a config file |
| `--resume` / `--clear-session` | Manage persisted Selenium sessions |
| `--debug` | Verbose logging for troubleshooting |

Use `python -m imdb_uploader.cli ...` to avoid installing the package globally.

## Configuration files

Store your preferred defaults in JSON:

```bash
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate \
         --save-config upload_imdb.json
```

Example (`upload_imdb.json`):

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

Search order:

1. Path passed via `--config`
2. `upload_imdb.json` (current directory)
3. `~/.config/upload_imdb/config.json`
4. `~/.upload_imdb.json`

## Session persistence

`fa-upload` writes `.upload_imdb_session.json` (configurable via `--session-file`)
so you can resume after an interruption:

```bash
fa-upload --csv data/YOUR_USER_ID/watched.csv --auto-login --auto-rate
# later
fa-upload --resume
```

Use `--clear-session` to start over.

## Troubleshooting

- **Missing Cinemagoer** (IMDbPY fork): install it manually with `pip install cinemagoer`.
- **WebDriver errors**: webdriver-manager downloads the right driver, but mismatched
  Chrome/Chromedriver versions can still break; keep your browser updated.
- **CAPTCHA / login loops**: automated login can trip additional challenges;
  fall back to manual login or resolve the CAPTCHA and continue.
