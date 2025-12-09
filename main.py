"""
FilmAffinity Backup - Legacy Entry Point

This file is kept for backward compatibility.
The new entry point is: python -m filmaffinity.cli

Or install and use: fa-backup
"""

# Redirect to new CLI
from filmaffinity.cli import main

if __name__ == "__main__":
    main()
