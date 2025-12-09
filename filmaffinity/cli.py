"""
FilmAffinity Backup CLI

Command-line interface for backing up FilmAffinity data to CSV files.
"""
from pathlib import Path
import shutil

import pandas as pd
from rich import print
import typer

from filmaffinity import scraper


app = typer.Typer(
    name="fa-backup",
    help="Backup your FilmAffinity data (watched movies, lists) to CSV files.",
)

# Default data directory (relative to this file's package root)
DEFAULT_DATA_DIR = Path(__file__).parent.parent / 'data'


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
            print(f"  [dim]Loaded existing: {name} ({len(df)} items)[/dim]")
        except Exception as e:
            print(f"  [yellow]Warning: Could not load {csv_file}: {e}[/yellow]")

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
):
    """
    Backup FilmAffinity data (watched movies and lists) to CSV files.

    To find your user_id, go to 'Mis votaciones' and copy the ID from the URL:
    https://www.filmaffinity.com/es/userratings.php?user_id={YOUR_ID}
    """
    data = {}
    user_dir = data_dir / user_id

    # Validate language
    if lang not in ('es', 'en'):
        print(f"[red]Error: Invalid language '{lang}'. Use 'es' or 'en'.[/red]")
        raise typer.Exit(1)

    if lang == 'es':
        print("[yellow]Using Spanish version of FilmAffinity. Consider using --lang en for better IMDb matching.[/yellow]")

    # Load existing data if resuming
    existing_data = {}
    if resume and user_dir.exists():
        print("[cyan]Resuming previous session...[/cyan]")
        existing_data = load_existing_data(user_dir)

    # Check user exists
    scraper.check_user(user_id, lang=lang)

    # Download lists
    if skip_lists:
        print("[dim]Skipping user lists (--skip-lists flag)[/dim]")
        lists = {}
    else:
        print("Retrieving [hot_pink3 bold]user lists[/hot_pink3 bold]")
        lists = scraper.get_user_lists(user_id, lang=lang)

        if not lists:
            print(
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
            print(f"[dim]Skipping list (already downloaded): [turquoise4]{name}[/turquoise4][/dim]")
            data[list_key] = existing_data[list_key]
            continue

        print(f"Parsing list: [turquoise4 bold]{name}[/turquoise4 bold]")
        _, info = scraper.get_list_movies(url, lang=lang)
        data[list_key] = info

    # Download watched movies
    if resume and 'watched' in existing_data:
        print("[dim]Skipping watched movies (already downloaded)[/dim]")
        data['watched'] = existing_data['watched']
    else:
        print("Parsing [green bold]watched[/green bold] movies")
        data['watched'] = scraper.get_watched_movies(user_id, lang=lang)

    # Clear previous user data (only if not resuming)
    if not resume:
        if user_dir.exists():
            shutil.rmtree(user_dir)
    if not user_dir.exists():
        user_dir.mkdir(parents=True)

    # Save data to CSV
    print(f'Saving CSV files to [bold]{user_dir}[/bold]')
    for k, v in data.items():
        df = pd.DataFrame.from_dict(v)
        df.to_csv(user_dir / f'{k}.csv', sep=';', index=False)

    print(f"[green]✅ Backup complete! {len(data)} files saved.[/green]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
