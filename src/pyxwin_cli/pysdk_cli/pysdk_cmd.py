"""CLI commands for downloading Windows Python builds from github.com/isFakeAccount/windows-python-builds."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import questionary
import typer
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.table import Column

from pyxwin.python_sdk.download_unpack import download_python_builds, fetch_releases, unpack_python_builds
from pyxwin.python_sdk.github_datatypes import ReleaseAsset

pysdk_cli = typer.Typer()

if TYPE_CHECKING:
    from pyxwin.python_sdk.github_datatypes import Release
    from pyxwin_cli.__main__ import PyxwinGlobalOptions


def _python_ver_to_package_mapping(release: Release) -> dict[str, list[ReleaseAsset]]:
    """Group release assets by Python major.minor version.

    :param release: Release containing the assets.

    :returns: Mapping of Python major.minor versions to release assets.

    """
    python_ver_to_package_mapping: dict[str, list[ReleaseAsset]] = {}
    for release_asset in release.assets:
        python_ver = ".".join(release_asset.name.split("-")[1].split(".")[:2])
        python_ver_to_package_mapping.setdefault(python_ver, []).append(release_asset)
    return python_ver_to_package_mapping


@pysdk_cli.command()
def interactive(ctx: typer.Context) -> None:
    """Provides an interactive way to download the Windows Python builds."""
    available_releases = asyncio.run(fetch_releases())

    style = questionary.Style(
        [
            ("selected", "fg:#68217A bold"),
            ("pointer", "fg:#68217A bold"),
            ("highlighted", "fg:#68217A bold"),
        ]
    )
    selected_release: str = questionary.select(
        "Select Release to install Python builds from:",
        style=style,
        choices=[
            questionary.Choice(
                f"Release: {release_name}",
                release_name,
            )
            for release_name in available_releases
        ],
    ).ask()

    python_ver_to_package_mapping = _python_ver_to_package_mapping(available_releases[selected_release])
    choices: list[questionary.Choice] = []
    for python_ver, release_assets in python_ver_to_package_mapping.items():
        choices.append(questionary.Choice(title=f"Python {python_ver}", value=python_ver))
        choices.extend([questionary.Choice(title=f"   {release_asset.name}", value=release_asset) for release_asset in release_assets])

    selected_options = questionary.checkbox(
        "Select the Python builds to install:",
        style=style,
        choices=choices,
    ).ask()

    selected_python_builds: list[ReleaseAsset] = []
    for option in selected_options:
        if isinstance(option, ReleaseAsset):
            selected_python_builds.append(option)
        else:
            selected_python_builds.extend([asset for asset in python_ver_to_package_mapping[option] if asset not in selected_python_builds])

    with Progress(
        TextColumn("[progress.description]{task.description}", table_column=Column(width=80, no_wrap=True)),
        BarColumn(),
        TaskProgressColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        asyncio.run(download_python_builds(ctx.obj.cache_dir, selected_release, selected_python_builds, progress))
        asyncio.run(unpack_python_builds(ctx.obj.cache_dir, selected_release, [asset.name for asset in selected_python_builds], progress))


@pysdk_cli.command()
def download(ctx: typer.Context, release_name: str, python_builds: list[str]) -> None:
    """Downloads all the python_builds specified based on the CLI options."""
    cli_opt: PyxwinGlobalOptions = ctx.obj
    with Progress(
        TextColumn("[progress.description]{task.description}", table_column=Column(width=80, no_wrap=True)),
        BarColumn(),
        TaskProgressColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        available_releases = asyncio.run(fetch_releases())
        selected_release = available_releases[release_name]

        python_release_assets = [asset for asset in selected_release.assets if asset.name in python_builds]

        asyncio.run(download_python_builds(cli_opt.cache_dir, release_name, python_release_assets, progress))


@pysdk_cli.command()
def unpack(ctx: typer.Context, release_name: str, python_builds: list[str]) -> None:
    """Unpacks all the downloaded Python builds. Downloads them first if not already present."""
    with Progress(
        TextColumn("[progress.description]{task.description}", table_column=Column(width=80, no_wrap=True)),
        BarColumn(),
        TaskProgressColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        cli_opt: PyxwinGlobalOptions = ctx.obj
        asyncio.run(unpack_python_builds(cli_opt.cache_dir, release_name, python_builds, progress))
