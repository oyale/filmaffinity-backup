"""
IMDb Uploader CLI

Command-line interface for uploading FilmAffinity ratings to IMDb.
"""
from imdb_uploader.uploader import main as uploader_main


def main():
    """Entry point for CLI."""
    uploader_main()


if __name__ == "__main__":
    main()
