"""
FilmAffinity Backup CLI

Command-line interface for backing up FilmAffinity data to CSV files.
"""
from importlib.metadata import version as get_version, PackageNotFoundError
from pathlib import Path
import shutil
from typing import Optional

import click
import pandas as pd
from rich import print
from rich.panel import Panel
import typer

from filmaffinity import scraper
from filmaffinity.scraper import (
    ScraperError,
    NetworkError,
    UserNotFoundError,
    RateLimitError,
)
from .exporters import export_to_letterboxd


def get_app_version() -> str:
    """Get the application version from package metadata."""
    try:
        return get_version("filmaffinity-backup")
    except PackageNotFoundError:
        return "dev"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"fa-backup version {get_app_version()}")
        raise typer.Exit()


# Global quiet mode flag
_quiet_mode = False


def qprint(*args, **kwargs) -> None:
    """Print only if not in quiet mode."""
    if not _quiet_mode:
        print(*args, **kwargs)


app = typer.Typer(
    name="fa-backup",
    help="Backup your FilmAffinity data (watched movies, lists) to CSV files.",
)


@app.callback(invoke_without_command=True)
def app_callback(
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=version_callback,
        is_eager=True,
        help="Show the application version and exit."
    ),
) -> None:
    """FilmAffinity backup tool."""
    pass

# Default data directory (relative to this file's package root)
DEFAULT_DATA_DIR = Path(__file__).parent.parent / 'data'


def _handle_scraper_error(error: ScraperError) -> None:
    """Display a user-friendly error message and exit."""
    if isinstance(error, UserNotFoundError):
        print(Panel(
            f"[red bold]User Not Found[/red bold]\n\n"
            f"The user ID [yellow]'{error.user_id}'[/yellow] does not exist on FilmAffinity.\n\n"
            f"[dim]To find your user ID:[/dim]\n"
            f"  1. Go to your FilmAffinity profile\n"
            f"  2. Click on 'My ratings' (Mis votaciones)\n"
            f"  3. Copy the [cyan]user_id[/cyan] from the URL:\n"
            f"     [dim]https://www.filmaffinity.com/en/userratings.php?user_id=[/dim][green]YOUR_ID[/green]",
            title="❌ Error",
            border_style="red"
        ))
    elif isinstance(error, RateLimitError):
        print(Panel(
            f"[red bold]Rate Limited[/red bold]\n\n"
            f"FilmAffinity is temporarily blocking requests from your IP.\n\n"
            f"[dim]What to do:[/dim]\n"
            f"  • Wait [cyan]10-15 minutes[/cyan] before trying again\n"
            f"  • Use [cyan]--resume[/cyan] flag to continue where you left off\n"
            f"  • Consider using a VPN if the problem persists",
            title="⏳ Rate Limited",
            border_style="yellow"
        ))
    elif isinstance(error, NetworkError):
        print(Panel(
            f"[red bold]Network Error[/red bold]\n\n"
            f"{error}\n\n"
            f"[dim]Troubleshooting tips:[/dim]\n"
            f"  • Check your internet connection\n"
            f"  • Try again in a few minutes\n"
            f"  • Use [cyan]--resume[/cyan] flag to continue where you left off",
            title="🌐 Connection Problem",
            border_style="red"
        ))
    else:
        print(Panel(
            f"[red bold]Error[/red bold]\n\n{error}",
            title="❌ Error",
            border_style="red"
        ))
    raise typer.Exit(1)


def load_existing_data(user_dir: Path) -> dict:
    """Load existing CSV files from user directory for resume mode."""
    data = {}
    if not user_dir.exists():
        return data

    for csv_file in user_dir.glob('*.csv'):
        name = csv_file.stem
        try:
            df = pd.read_csv(csv_file, sep=';')
            data[name] = df.to_dict(orient='list')
            qprint(f"  [dim]Loaded existing: {name} ({len(df)} items)[/dim]")
        except Exception as e:
            qprint(f"  [yellow]Warning: Could not load {csv_file}: {e}[/yellow]")

    return data


@app.command()
def backup(
    user_id: str = typer.Argument(..., help="FilmAffinity user ID"),
    skip_lists: bool = typer.Option(
        False, "--skip-lists",
        help="Skip downloading user lists, only get watched films"
    ),
    resume: bool = typer.Option(
        False, "--resume",
        help="Resume interrupted session, skip already downloaded lists"
    ),
    lang: str = typer.Option(
        "en", "--lang",
        help="Language for FilmAffinity (es/en). Default: 'en' for better IMDb matching"
    ),
    data_dir: Path = typer.Option(
        DEFAULT_DATA_DIR, "--data-dir",
        help="Directory to save CSV files"
    ),
    export_format: str = typer.Option(
        "csv", "--format",
        help="Export format: 'csv' (default, semicolon-delimited) or 'letterboxd' (Letterboxd-compatible CSV)",
        click_type=click.Choice(["csv", "letterboxd"]),
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Minimal output, only show errors"
    ),
):
    """
    Backup FilmAffinity data (watched movies and lists) to CSV files.

    To find your user_id, go to 'Mis votaciones' and copy the ID from the URL:
    https://www.filmaffinity.com/es/userratings.php?user_id={YOUR_ID}
    """
    global _quiet_mode
    _quiet_mode = quiet

    data = {}
    user_dir = data_dir / user_id

    # Validate language
    if lang not in ('es', 'en'):
        print(f"[red]Error: Invalid language '{lang}'. Use 'es' or 'en'.[/red]")
        raise typer.Exit(1)

    if lang == 'es':
        qprint("[yellow]Using Spanish version of FilmAffinity. Consider using --lang en for better IMDb matching.[/yellow]")

    # Load existing data if resuming
    existing_data = {}
    if resume and user_dir.exists():
        qprint("[cyan]Resuming previous session...[/cyan]")
        existing_data = load_existing_data(user_dir)

    # Check user exists
    try:
        scraper.check_user(user_id, lang=lang)
    except ScraperError as e:
        _handle_scraper_error(e)

    # Download lists
    if skip_lists:
        qprint("[dim]Skipping user lists (--skip-lists flag)[/dim]")
        lists = {}
    else:
        qprint("Retrieving [hot_pink3 bold]user lists[/hot_pink3 bold]")
        try:
            lists = scraper.get_user_lists(user_id, lang=lang)
        except ScraperError as e:
            _handle_scraper_error(e)

        if not lists:
            qprint(
                ":name_badge: [yellow bold]Warning[/yellow bold]: No lists were found. "
                "Make sure to mark your lists as :earth_americas: [b u]public[/b u] to "
                "be able to backup them."
            )
            inp = input("   Do you want to continue with watched movies and erase previous list data (if any)? [y/n]")
            if inp != 'y':
                raise typer.Exit(0)

    # Process each list
    for name, url in lists.items():
        list_key = f'list - {name}'

        if resume and list_key in existing_data:
            qprint(f"[dim]Skipping list (already downloaded): [turquoise4]{name}[/turquoise4][/dim]")
            data[list_key] = existing_data[list_key]
            continue

        qprint(f"Parsing list: [turquoise4 bold]{name}[/turquoise4 bold]")
        try:
            _, info = scraper.get_list_movies(url, lang=lang)
            data[list_key] = info
        except ScraperError as e:
            _handle_scraper_error(e)

    # Download watched movies
    if resume and 'watched' in existing_data:
        qprint("[dim]Skipping watched movies (already downloaded)[/dim]")
        data['watched'] = existing_data['watched']
    else:
        qprint("Parsing [green bold]watched[/green bold] movies")
        try:
            data['watched'] = scraper.get_watched_movies(user_id, lang=lang)
        except ScraperError as e:
            _handle_scraper_error(e)

    # Clear previous user data (only if not resuming)
    if not resume:
        if user_dir.exists():
            shutil.rmtree(user_dir)
    if not user_dir.exists():
        user_dir.mkdir(parents=True)

    # Save data to files
    qprint(f'Saving files to [bold]{user_dir}[/bold]')
    for k, v in data.items():
        csv_path = user_dir / f'{k}.csv'

        # Always save the standard CSV (semicolon-delimited)
        df = pd.DataFrame.from_dict(v)
        df.to_csv(csv_path, sep=';', index=False)
        qprint(f"  [green]✓ Saved: {csv_path}[/green]")

        # Additionally save Letterboxd format if requested
        if export_format == "letterboxd":
            letterboxd_path = user_dir / f'{k}_letterboxd.csv'
            export_to_letterboxd(v, letterboxd_path)
            qprint(f"  [green]✓ Saved Letterboxd CSV: {letterboxd_path}[/green]")

    qprint(f"[green]✅ Backup complete! {len(data)} files saved.[/green]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
