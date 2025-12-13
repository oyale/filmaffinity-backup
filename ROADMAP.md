# 🗺️ FilmAffinity Backup - Roadmap

## v1.0.0 - Current Release ✅

* [x] FilmAffinity scraper with CSV export
* [x] IMDb uploader with Selenium automation
* [x] Session persistence and resume support
* [x] Dry-run mode for verification
* [x] Multi-language support (EN/ES)
* [x] Rate limiting with exponential backoff
* [x] AGPL-3.0 license

---

## v1.1.0 - Polish & Stability 🔧

**Priority: High | Timeline: Near-term**

### Bug Fixes

* [x] Fix potential race condition in session file writes
* [x] Handle FilmAffinity pagination edge cases
* [X] Improve error messages for network failures

### Improvements

* [x] Add `--version` flag to CLI commands
* [x] Add progress percentage to upload status
* [ ] Validate CSV format before processing
* [x] Add `--quiet` mode for minimal output

### Documentation

* [x] Add CONTRIBUTING.md
* [x] Add CHANGELOG.md
* [X] Add issue/PR templates for GitHub

---

## v1.2.0 - Developer Experience 👩‍💻

**Priority: Medium | Timeline: Short-term**

### Code Quality

* [ ] Add pre-commit hooks (ruff, black, mypy)
* [ ] Add `py.typed` marker for type checking
* [ ] Increase test coverage from 23% to 50%+
* [ ] Add integration tests (marked to skip by default)

### CI/CD

* [ ] Add CodeQL security scanning
* [ ] Add Dependabot for dependency updates
* [ ] Add automated PyPI publishing on release
* [ ] Add coverage reporting (Codecov/Coveralls)

### Packaging

* [ ] Publish to PyPI (`pip install filmaffinity-backup`)
* [ ] Add conda-forge recipe
* [ ] Create Docker image

---

## v1.3.0 - Feature Enhancements ✨

**Priority: Medium | Timeline: Mid-term**

### FilmAffinity Backup

* [ ] Export to JSON format (in addition to CSV)
* [x] Export to Letterboxd format
* [ ] Add `--filter` option (by year, rating, genre)
* [ ] Add `--since` option for incremental backups
* [ ] Support for TV series (not just movies)
* [ ] Add movie poster URLs to export

### IMDb Uploader

* [ ] Add Trakt.tv export support
* [ ] Headless mode improvements (better CAPTCHA handling)
* [ ] Add `--preview` to show what would be uploaded
* [ ] Support for IMDb watchlist (not just ratings)
* [ ] Add two-factor authentication support

---

## v1.4.0 - User Experience 🎨

**Priority: Low | Timeline: Long-term**

### CLI Improvements

* [ ] Add shell completions (bash, zsh, fish)
* [ ] Add interactive mode with TUI (using `textual`)
* [ ] Add colored diff when showing rating changes
* [ ] Add sound notification on completion

### Configuration

* [ ] Add `.env` file support for credentials
* [ ] Add per-profile configuration
* [ ] Add config migration tool

### Reporting

* [ ] Generate HTML report of upload results
* [ ] Add statistics dashboard (total movies, ratings distribution)
* [ ] Export match confidence report

---

## v2.0.0 - Platform Expansion 🚀

**Priority: Low | Timeline: Future**

### New Platforms

* [ ] **Letterboxd** backup/import
* [ ] **Trakt.tv** backup/import
* [ ] **TMDb** (The Movie Database) integration
* [ ] **JustWatch** watchlist sync

### Architecture

* [ ] Plugin system for adding new platforms
* [ ] API server mode (REST/GraphQL)
* [ ] Web UI (optional frontend)

### Advanced Features

* [ ] Cross-platform sync (FA ↔ IMDb ↔ Letterboxd)
* [ ] Scheduled automatic backups
* [ ] Cloud storage integration (Google Drive, Dropbox)

---

## 🐛 Known Issues / Technical Debt

| Issue | Priority | Notes |
|-------|----------|-------|
| `tests.py` in root (legacy) | Low | Consider removing, using `tests/` only |
| Some debug prints in uploader | Low | Replace with proper logging |
| Hardcoded wait times | Medium | Make configurable |
| No retry on FilmAffinity scraper | Medium | Add similar retry logic as uploader |

---

## 💡 Community Wishlist

*To be populated from GitHub Issues*

* [ ] _Your feature request here_

---

## Contributing

Have an idea? Open an [issue](https://github.com/oyale/filmaffinity-backup/issues) or submit a PR!
