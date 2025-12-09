"""
Legacy Test Runner

This file is kept for backward compatibility.
Run tests with: python -m pytest tests/

For scraper integration tests: python -m pytest tests/test_scraper.py -m integration
"""

import subprocess
import sys

if __name__ == "__main__":
    print("Running tests using pytest...")
    sys.exit(subprocess.run(["python", "-m", "pytest", "tests/", "-v"]).returncode)
