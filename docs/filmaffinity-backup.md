# FilmAffinity Backup CLI

The `fa-backup` command scrapes your FilmAffinity watched movies and custom lists
into structured CSV/JSON files so you can archive or reuse them elsewhere.

## Saved Data

For every movie in your watched feed or a custom list the exporter stores:

- `movie title`
- `original title` (pulled from the movie detail page when needed)
- `year`, `country`, `directors`, and `genre` (watched export only)
- `user score` and FilmAffinity aggregate score
- `Filmaffinity movie id`

## Basic Usage

1. Locate your FilmAffinity `user_id` from the ratings URL, e.g.
   `https://www.filmaffinity.com/en/userratings.php?user_id=<YOUR_ID>`.
2. Run the CLI:

   ```bash
   fa-backup YOUR_USER_ID
   ```

All data is stored under `./data/<user_id>/` unless you pass a custom `--data-dir`.

Use `python -m filmaffinity.cli ...` when running directly from the repository.

## CLI Reference

```
fa-backup USER_ID [OPTIONS]
```

| Option | Description |
| --- | --- |
| `--skip-lists` | Skip custom lists and only export watched films |
| `--resume` | Continue an interrupted run, skipping files that already exist |
| `--lang {en,es}` | Source language (default: `en` for better IMDb matching) |
| `--data-dir PATH` | Custom output directory (default: `./data`) |
| `--format {csv,letterboxd,json}` | Export format(s). Can be repeated |

## Export Formats

### Standard CSV
The default output contains one row per movie per list with the metadata listed
above. It works with spreadsheet tools and is the recommended input for the
IMDb uploader.

### Letterboxd CSV

Generate files that match Letterboxd's importer:

```bash
fa-backup YOUR_USER_ID --format letterboxd
```

Each `*_letterboxd.csv` file contains `Title`, `Year`, `Rating10`, and an empty
`WatchedDate` column, ready to upload at https://letterboxd.com/import/.

### JSON Export

```bash
fa-backup YOUR_USER_ID --format json
```

Produces `*.json` documents with a list of movie objects, which is handy for
custom tooling:

```json
[
  {
    "title": "The Shawshank Redemption",
    "original_title": "The Shawshank Redemption",
    "year": "1994",
    "score": "9.3",
    "director": "Frank Darabont"
  }
]
```

## Language selection

`--lang en` (default) fetches the English site, giving you English titles,
fewer HTTP requests, and faster runs. Spanish mode (`--lang es`) revisits the
movie detail page to look up the original title, so expect additional requests
and a higher chance of rate limiting.

## Rate limiting & resilience

The scraper sleeps ~5 seconds between requests and retries with exponential
backoff (30s → 60s → 120s) when FilmAffinity returns HTTP 429 errors. Use
`--resume` to continue after any network hiccups.
