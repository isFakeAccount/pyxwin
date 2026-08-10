"""CLI commands for downloading Microsoft CRT & Windows SDK headers and libraries."""

from __future__ import annotations

import asyncio
from pathlib import Path  # noqa: TC003 Typer needs Path here

import questionary
import typer
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Column

from pyxwin.wincrt_sdk.download_unpack import download_packages, unpack_files
from pyxwin.wincrt_sdk.manifest_datatypes import Channel, ManifestVersion, VisualStudioInstallerOptions
from pyxwin.wincrt_sdk.msft_file_operations import reduce_unpacked_files
from pyxwin.wincrt_sdk.vs_manifest import load_channel_manifest, load_installer_manifest
from pyxwin.wincrt_sdk.vs_workload import get_workload_names, resolve_workload_payloads

# Note: Typer needs these outside of TYPE_CHECKING block
from pyxwin_cli.wincrtsdk_cli.wincrt_cmd_options import (  # noqa: TC001
    accept_license_opt,
    cache_dir_opt,
    channel_opt,
    manifest_opt,
    manifest_version_opt,
    workloads_opt,
)

wincrt_app = typer.Typer()

manifest_options = VisualStudioInstallerOptions.get_default_manifest_options()

VISUAL_STUDIO_2026_CHANNEL = 18


@wincrt_app.command()
def download() -> list[Path]:
    """Downloads all the packages specified based on the CLI options."""
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(f"Fetching Visual Studio channel manifest version {manifest_options.manifest_version}...")
        manifest_data = asyncio.run(load_channel_manifest(manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Fetching Visual Studio installer manifest ...")
        installer_manifest = asyncio.run(load_installer_manifest(manifest_data, manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Pruning package from installer manifest...")
        workload_payloads = resolve_workload_payloads(installer_manifest, manifest_options)
        progress.update(task, completed=100)

    with Progress(
        TextColumn("[progress.description]{task.description}", table_column=Column(width=80, no_wrap=True)),
        BarColumn(),
        TaskProgressColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        downloaded_file_paths = asyncio.run(download_packages(manifest_options, workload_payloads, progress))
        for task_id in progress.task_ids:
            progress.update(task_id, completed=100)

    return downloaded_file_paths


@wincrt_app.command()
def interactive() -> None:
    """Provides an interactive way to download the Visual Studio workloads."""
    style = questionary.Style(
        [
            ("selected", "fg:#68217A bold"),
            ("pointer", "fg:#68217A bold"),
            ("highlighted", "fg:#68217A bold"),
        ]
    )
    manifest_version, channel = questionary.select(
        "Select the Visual Studio version and channel to install:",
        style=style,
        choices=[
            questionary.Choice(
                f"Visual Studio {v.value} ({c.name})",
                (v, c),
            )
            for v in reversed(list(ManifestVersion))
            for c in ManifestVersion.channels_for(v)
        ],
    ).ask()

    manifest_options.channel = channel
    manifest_options.manifest_version = manifest_version

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(f"Fetching Visual Studio channel manifest version {manifest_options.manifest_version}...")
        manifest_data = asyncio.run(load_channel_manifest(manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Fetching Visual Studio installer manifest ...")
        installer_manifest = asyncio.run(load_installer_manifest(manifest_data, manifest_options))
        progress.update(task, completed=100)

    workload_names = get_workload_names(installer_manifest)
    selected_workloads = questionary.checkbox(
        "Select the workloads to install:",
        style=style,
        choices=[questionary.Choice(workload) for workload in workload_names],
    ).ask()
    manifest_options.workloads = selected_workloads

    reduce()


@wincrt_app.command()
def unpack() -> None:
    """Unpacks all the downloaded CRT & SDK packages. Downloads them first if not already present."""
    download_directory = manifest_options.cache_dir / "downloads" / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel
    download()

    for workload_dir in download_directory.iterdir():
        crt_packages_dir = list(workload_dir.rglob("*.vsix"))
        sdk_packages_dir = list(workload_dir.rglob("*.msi"))
        downloaded_file_paths = crt_packages_dir + sdk_packages_dir

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(f"Unpacking CRT {workload_dir.name} packages...")
            asyncio.run(main=unpack_files(manifest_options, downloaded_file_paths))
            progress.update(task, completed=100)


@wincrt_app.command()
def reduce() -> None:
    """Combines all the CRT & SDK packages into a simple structure that can be easily linked against."""
    unpack_directory = manifest_options.cache_dir / "unpack" / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel
    unpack()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Reducing workload packages...")
        reduce_unpacked_files(unpack_directory, manifest_options)
        progress.update(task, completed=100)


@wincrt_app.callback()
def app_callback(
    accept_license: accept_license_opt = manifest_options.accept_license,
    cache_dir: cache_dir_opt = manifest_options.cache_dir,
    channel: channel_opt = manifest_options.channel,
    manifest_path: manifest_opt = manifest_options.channel_manifest_path,
    manifest_version: manifest_version_opt = manifest_options.manifest_version,
    workloads: workloads_opt = manifest_options.workloads,
) -> None:
    """Callback function for the pyxwin CLI. Processes the global CLI options."""
    if accept_license:
        print("Microsoft Software License Terms accepted.")
    else:
        accept = questionary.confirm(
            "Do you accept the Microsoft Software License Terms at "
            "(https://codeberg.org/YoshikageKira/pyxwin/src/branch/master/LICENSES/LICENSE-Microsoft-Build-Tools.md)?",
            default=True,
            auto_enter=False,
        ).ask()
        if not accept:
            print("You must accept the license to proceed.")
            raise typer.Exit(code=1)

        print("Microsoft Software License Terms accepted.")

    if manifest_version >= VISUAL_STUDIO_2026_CHANNEL:
        if channel not in (Channel.STABLE, Channel.INSIDERS):
            print("For manifest version 18 or higher, channel must be 'stable' or 'insider'.")
            raise typer.Exit(code=1)
    elif channel not in (Channel.RELEASE, Channel.PREVIEW):
        print("For manifest version 17 or lower, channel must be 'release' or 'preview'.")
        raise typer.Exit(code=1)

    # If args are provided, override the default manifest options
    manifest_options.cache_dir = cache_dir
    manifest_options.channel = channel
    manifest_options.channel_manifest_path = manifest_path
    manifest_options.manifest_version = manifest_version
    manifest_options.workloads = workloads
