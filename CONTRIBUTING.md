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

# Install in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
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
5. Commit with a clear message
6. Push and open a Pull Request

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
│   └── prompts.py      # User interaction prompts
└── tests/              # Test files
```

## Questions?

Feel free to open an issue for any questions. We're happy to help!

---

Thanks again for your interest in contributing! 🙏
