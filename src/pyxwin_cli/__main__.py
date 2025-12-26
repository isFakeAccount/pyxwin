"""Entry point for the pyxwin command-line interface."""

from __future__ import annotations

import shutil

import typer
from platformdirs import user_cache_path

from pyxwin_cli.wincrtsdk_cli.wincrt_cmd import wincrt_app

app = typer.Typer()
app.add_typer(wincrt_app, name="wincrt", help="Commands for downloading Microsoft CRT & Windows SDK headers and libraries.")


@app.command()
def clean_cache() -> None:
    """Deletes all cached pyxwin files and directories."""
    cache_path = user_cache_path("pyxwin")

    if cache_path.exists():
        shutil.rmtree(cache_path)
        print(f"Removed cache directory: {cache_path}")
    else:
        print(f"No cache directory found at: {cache_path}")


def main() -> None:
    """Entry point for the pyxwin CLI."""
    app()


if __name__ == "__main__":
    main()
