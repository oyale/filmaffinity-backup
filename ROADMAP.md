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
* [x] Validate CSV format before processing
* [x] Add `--quiet` mode for minimal output

### Documentation

* [x] Add CONTRIBUTING.md
* [x] Add CHANGELOG.md
* [X] Add issue/PR templates for GitHub

---

## v1.2.0 - Developer Experience 👩‍💻

**Priority: Medium | Timeline: Short-term**

### Code Quality

* [X] Add pre-commit hooks (ruff, black, mypy)
* [X] Add `py.typed` marker for type checking
* [X] Increase test coverage from 23% to 40%+
* [X] Add integration tests (marked to skip by default)

### CI/CD

* [X] Add CodeQL security scanning
* [X] Add Dependabot for dependency updates
* [X] Add automated PyPI publishing on release
* [X] Add coverage reporting (Codecov/Coveralls)

### Packaging

* [X] Publish to PyPI (`pip install filmaffinity-backup`)
* [X] Add conda-forge recipe
* [X] Create Docker image

---

## v1.3.0 - Feature Enhancements ✨

**Priority: Medium | Timeline: Mid-term**

### FilmAffinity Backup

* [X] Export to JSON format (in addition to CSV)
* [x] Export to Letterboxd format
* [ ] [Add `--filter` option (by year, rating, genre)](https://github.com/oyale/filmaffinity-backup/issues/23)
* [ ] [Add `--since` option for incremental backups](https://github.com/oyale/filmaffinity-backup/issues/24)
* [ ] [Support for TV series (not just movies)](https://github.com/oyale/filmaffinity-backup/issues/25)
* [ ] [Add movie poster URLs to export](https://github.com/oyale/filmaffinity-backup/issues/26)

### IMDb Uploader

* [ ] [Add Trakt.tv export support](https://github.com/oyale/filmaffinity-backup/issues/27)
* [ ] [Headless mode improvements (better CAPTCHA handling)](https://github.com/oyale/filmaffinity-backup/issues/28)
* [ ] [Add `--preview` to show what would be uploaded](https://github.com/oyale/filmaffinity-backup/issues/29)
* [ ] [Support for IMDb watchlist (not just ratings)](https://github.com/oyale/filmaffinity-backup/issues/30)
* [ ] [Add two-factor authentication support](https://github.com/oyale/filmaffinity-backup/issues/31)

---

## v1.4.0 - User Experience 🎨

**Priority: Low | Timeline: Long-term**

### CLI Improvements

* [ ] [Add shell completions (bash, zsh, fish)](https://github.com/oyale/filmaffinity-backup/issues/32)
* [ ] [Add interactive mode with TUI (using `textual`)](https://github.com/oyale/filmaffinity-backup/issues/33)
* [ ] [Add colored diff when showing rating changes](https://github.com/oyale/filmaffinity-backup/issues/34)
* [ ] [Add sound notification on completion](https://github.com/oyale/filmaffinity-backup/issues/35)

### Configuration

* [ ] [Add `.env` file support for credentials](https://github.com/oyale/filmaffinity-backup/issues/36)
* [ ] [Add per-profile configuration](https://github.com/oyale/filmaffinity-backup/issues/37)
* [ ] [Add config migration tool](https://github.com/oyale/filmaffinity-backup/issues/38)

### Reporting

* [ ] [Generate HTML report of upload results](https://github.com/oyale/filmaffinity-backup/issues/39)
* [ ] [Add statistics dashboard (total movies, ratings distribution)](https://github.com/oyale/filmaffinity-backup/issues/40)
* [ ] [Export match confidence report](https://github.com/oyale/filmaffinity-backup/issues/41)

---

## v2.0.0 - Platform Expansion 🚀

**Priority: Low | Timeline: Future**

### New Platforms

* [ ] [**Letterboxd** backup/import](https://github.com/oyale/filmaffinity-backup/issues/42) (see also [#43](https://github.com/oyale/filmaffinity-backup/issues/43) for import)
* [ ] [**Trakt.tv** backup/import](https://github.com/oyale/filmaffinity-backup/issues/44) (see also [#45](https://github.com/oyale/filmaffinity-backup/issues/45) for import)
* [ ] [**TMDb** (The Movie Database) integration](https://github.com/oyale/filmaffinity-backup/issues/46)
* [ ] [**JustWatch** watchlist sync](https://github.com/oyale/filmaffinity-backup/issues/47)

### Architecture

* [ ] [Plugin system for adding new platforms](https://github.com/oyale/filmaffinity-backup/issues/48)
* [ ] [API server mode (REST/GraphQL)](https://github.com/oyale/filmaffinity-backup/issues/49)
* [ ] [Web UI (optional frontend)](https://github.com/oyale/filmaffinity-backup/issues/50)

### Advanced Features

* [ ] [Cross-platform sync (FA ↔ IMDb ↔ Letterboxd)](https://github.com/oyale/filmaffinity-backup/issues/51)
* [ ] [Scheduled automatic backups](https://github.com/oyale/filmaffinity-backup/issues/52)
* [ ] [Cloud storage integration (Google Drive, Dropbox)](https://github.com/oyale/filmaffinity-backup/issues/53)

---

## 🐛 Known Issues / Technical Debt

| Issue | Priority | Notes |
|-------|----------|-------|
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
