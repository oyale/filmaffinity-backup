# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Custom exception classes for better error handling (`ScraperError`, `NetworkError`, `ConnectionFailedError`, `TimeoutError`, `RateLimitError`, `UserNotFoundError`, `ParseError`)
- User-friendly error messages with troubleshooting tips for network failures
- Rich CLI error panels with actionable guidance
- Letterboxd CSV export format (`--format letterboxd`)
- `export_to_letterboxd` function in public API
- Comprehensive unit tests for exporters and error handling

### Changed
- `request_with_retry` now raises specific exceptions instead of returning failed responses
- CLI now catches and displays network errors with helpful context

### Fixed

- Fixed potential race condition in session file writes by implementing atomic writes and file locking

## [1.0.0] - 2025-12-11

### Added
- FilmAffinity scraper with CSV export
- Multi-language support (English and Spanish)
- Resume support for interrupted sessions (`--resume`)
- Rate limiting with exponential backoff
- IMDb uploader with Selenium automation
- Dry-run mode for verifying title mappings
- Fuzzy matching with year/director boosts
- Session persistence for uploads
- Skipped movie tracking by category
- Retry support for skipped movies
- CAPTCHA detection during login
- Configuration file support
- Initial ROADMAP.md

[Unreleased]: https://github.com/oyale/filmaffinity-backup/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/oyale/filmaffinity-backup/releases/tag/v1.0.0
