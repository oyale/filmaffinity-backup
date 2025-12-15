"""
Legacy Test Runner

This file is kept for backward compatibility.
Run tests with: python -m pytest tests/

For scraper integration tests: python -m pytest tests/test_scraper.py -m integration
"""

import os
import subprocess
import sys

if __name__ == "__main__":
    # Get the project root directory (parent of tests/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tests_dir = os.path.join(project_root, "tests")

    print("Running tests using pytest...")
    sys.exit(subprocess.run(["python", "-m", "pytest", tests_dir, "-v"]).returncode)
