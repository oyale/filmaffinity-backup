# Contributing to FilmAffinity Backup

First off, thanks for taking the time to contribute! 🎬

This project is open to all kinds of contributions, whether it's:

- 🐛 Bug reports
- 💡 Feature suggestions
- 📝 Documentation improvements
- 🔧 Code contributions

## Getting Started

### Prerequisites

- Python 3.9+
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/oyale/filmaffinity-backup.git
cd filmaffinity-backup

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (recommended)
pre-commit install
```

### Development Tools

This project uses modern Python development tools:

| Tool | Purpose | Runs On |
|------|---------|---------|
| **[Ruff](https://docs.astral.sh/ruff/)** | Linting + formatting | Pre-commit |
| **[Mypy](https://mypy.readthedocs.io/)** | Static type checking | Pre-commit |
| **[Pytest](https://pytest.org/)** | Testing | Manual / CI |

#### Pre-commit Hooks

Pre-commit hooks run automatically before each commit to ensure code quality:

```bash
# Run all hooks manually
pre-commit run --all-files

# Run on staged files only (what happens on commit)
pre-commit run
```

The hooks will:
- Fix trailing whitespace and ensure files end with newline
- Sort imports and fix linting issues (auto-fix where possible)
- Format code consistently
- Run type checking

#### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=filmaffinity --cov=imdb_uploader

# Run specific test file
pytest tests/test_scraper.py -v
```

#### Test Types and Selenium Mocking

This project uses **automated selenium mocking** to ensure tests run consistently across different environments:

**Unit Tests** (default):

- **Purpose**: Test individual functions and modules in isolation
- **Selenium**: Automatically mocked to prevent browser launches
- **Speed**: Fast execution, no external dependencies
- **Command**: `pytest tests/`

**Integration Tests**:

- **Purpose**: Test real HTTP interactions with FilmAffinity servers
- **Selenium**: Not used (tests HTTP scraping, not browser automation)
- **Speed**: Slower due to network requests
- **Command**: `pytest tests/ -m integration`
- **Note**: May be rate-limited by FilmAffinity

**Selenium Mocking Details**:

- **Implementation**: `tests/conftest.py` mocks selenium at the module level
- **Why**: Prevents import errors during test collection in CI environments
- **Impact**: Zero functional impact since integration tests don't use selenium
- **Benefit**: Consistent test behavior across local/CI environments

**Test Architecture**:

```text
Unit Tests (332 tests)          Integration Tests (11 tests)
├── Browser automation logic    ├── HTTP scraping (FilmAffinity)
├── Data processing             ├── IMDb API client
├── CSV validation              ├── CSV export workflows
├── Configuration handling      └── End-to-end data pipelines
└── Error handling
```

## How to Contribute

### Reporting Bugs

Found a bug? Please [open an issue](https://github.com/oyale/filmaffinity-backup/issues/new) with:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your Python version and OS

### Suggesting Features

Have an idea? Open an issue and describe:

- What you'd like to see
- Why it would be useful
- Any implementation ideas (optional)

### Submitting Code

1. Fork the repository
2. Create a branch (`git checkout -b feature/my-feature` or `fix/my-fix`)
3. Make your changes
4. Run tests (`pytest tests/`)
5. Pre-commit hooks will run automatically on commit
6. Push and open a Pull Request

**Note:** If pre-commit makes automatic fixes, you may need to `git add` the changes and commit again.

## Code Style

- **Formatting**: Handled automatically by Ruff
- **Imports**: Sorted automatically by Ruff (isort rules)
- **Type hints**: Encouraged but not required for all code
- **Docstrings**: Use Google-style docstrings for public functions

## Project Structure

```text
filmaffinity-backup/
├── filmaffinity/       # FilmAffinity scraper & CLI
│   ├── cli.py          # Main CLI (fa-backup command)
│   ├── scraper.py      # Web scraping logic
│   └── exporters.py    # CSV export functions
├── imdb_uploader/      # IMDb upload functionality
│   ├── uploader.py     # Main upload orchestration
│   ├── browser_automation.py  # Selenium WebDriver operations
│   ├── data_processing.py     # CSV reading & IMDb matching
│   ├── reporting.py           # Output formatting & statistics
│   ├── config.py       # Configuration & session management
│   ├── constants.py    # Constants and type definitions
│   ├── prompts.py      # User interaction prompts
│   └── csv_validator.py # CSV format validation
└── tests/              # Test files
```

## Release Process

Maintainers can use the automated workflows plus the included conda recipe to publish new versions.

### 1. Prepare the Release

- Update `CHANGELOG.md` with the upcoming version under the **Unreleased** section.
- Make sure CI is green on `main` and rerun `pytest` / `pre-commit` locally if needed.
- Confirm any new CLI flags or behaviours are reflected in `README.md` and docs.

### 2. Bump the Version

1. From the GitHub Actions tab, run the **Bump Version** workflow and pick `patch`, `minor`, or `major`.
2. The workflow uses `bump-my-version` to update `pyproject.toml`, create a tag (`vX.Y.Z`), and push back to `main`.
3. Wait for the workflow to finish before moving on; the tag it creates becomes the source for releases.

### 3. Publish to PyPI, Docker and Anaconda

- Create a GitHub Release from the freshly created tag with the changelog entry in the notes.
- Publishing the release triggers the `Publish to PyPI` workflow (`.github/workflows/publish.yml`) which builds via `python -m build` and pushes to PyPI using trusted publishing.
- The `Publish Docker Image` workflow picks up the same release to build and push a multi-arch image to `ghcr.io/oyale/filmaffinity-backup`.
- The `Publish Conda Package` workflow picks up the same release to build and push the conda package to Anaconda.org.

## Questions?

Feel free to open an issue for any questions. We're happy to help!

---

Thanks again for your interest in contributing! 🙏
