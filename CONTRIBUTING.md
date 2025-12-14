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

```
filmaffinity-backup/
├── filmaffinity/       # FilmAffinity scraper & CLI
│   ├── cli.py          # Main CLI (fa-backup command)
│   ├── scraper.py      # Web scraping logic
│   └── exporters.py    # CSV export functions
├── imdb_uploader/      # IMDb upload functionality
│   ├── uploader.py     # Main upload logic
│   ├── config.py       # Configuration & session management
│   ├── constants.py    # Constants and type definitions
│   └── prompts.py      # User interaction prompts
└── tests/              # Test files
```

## Questions?

Feel free to open an issue for any questions. We're happy to help!

---

Thanks again for your interest in contributing! 🙏
