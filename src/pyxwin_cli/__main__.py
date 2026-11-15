"""Entry point for the pyxwin command-line interface."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003

import typer
from platformdirs import user_cache_path

from pyxwin_cli.pysdk_cli.pysdk_cmd import pysdk_cli
from pyxwin_cli.wincrtsdk_cli.wincrt_cmd import wincrt_app

app = typer.Typer()
app.add_typer(wincrt_app, name="wincrt", help="Commands for downloading Microsoft CRT & Windows SDK headers and libraries.")
app.add_typer(pysdk_cli, name="pysdk", help="Commands for downloading Windows Python builds from github.com/isFakeAccount/windows-python-builds")


@dataclass
class PyxwinGlobalOptions:
    """Global options for Pyxwin CLI."""

    cache_dir: Path


@app.command()
def clean_cache() -> None:
    """Deletes all cached pyxwin files and directories."""
    cache_path = user_cache_path("pyxwin")

    if cache_path.exists():
        shutil.rmtree(cache_path)
        print(f"Removed cache directory: {cache_path}")
    else:
        print(f"No cache directory found at: {cache_path}")


@app.callback()
def app_callback(ctx: typer.Context, cache_dir: Path | None = None) -> None:
    """Callback function for the pyxwin CLI. Processes the global CLI options."""
    if cache_dir is None:
        cache_dir = user_cache_path("pyxwin", "pyxwin")
    ctx.obj = PyxwinGlobalOptions(cache_dir=cache_dir)


def main() -> None:
    """Entry point for the pyxwin CLI."""
    app()


if __name__ == "__main__":
    main()
