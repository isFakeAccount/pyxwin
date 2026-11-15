"""CLI commands for downloading Microsoft CRT & Windows SDK headers and libraries."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

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
    channel_opt,
    manifest_opt,
    manifest_version_opt,
    workload_opt,
)

if TYPE_CHECKING:
    from pyxwin_cli.__main__ import PyxwinGlobalOptions

wincrt_app = typer.Typer()


VISUAL_STUDIO_2026_CHANNEL = 18


@wincrt_app.command()
def download(ctx: typer.Context, workloads: workload_opt) -> None:
    """Downloads all the packages specified based on the CLI options."""
    installer_options: VisualStudioInstallerOptions = ctx.obj
    installer_options.workloads = workloads

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(f"Fetching Visual Studio channel manifest version {installer_options.manifest_version}...")
        manifest_data = asyncio.run(load_channel_manifest(installer_options))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Fetching Visual Studio installer manifest ...")
        installer_manifest = asyncio.run(load_installer_manifest(manifest_data, installer_options))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Pruning package from installer manifest...")
        workload_payloads = resolve_workload_payloads(installer_manifest, installer_options)

    with Progress(
        TextColumn("[progress.description]{task.description}", table_column=Column(width=80, no_wrap=True)),
        BarColumn(),
        TaskProgressColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        asyncio.run(download_packages(installer_options, workload_payloads, progress))


@wincrt_app.command()
def interactive(ctx: typer.Context) -> None:
    """Provides an interactive way to download the Visual Studio workloads."""
    installer_options: VisualStudioInstallerOptions = ctx.obj

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

    installer_options.channel = channel
    installer_options.manifest_version = manifest_version

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(f"Fetching Visual Studio channel manifest version {installer_options.manifest_version}...")
        manifest_data = asyncio.run(load_channel_manifest(installer_options))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Fetching Visual Studio installer manifest ...")
        installer_manifest = asyncio.run(load_installer_manifest(manifest_data, installer_options))

    workload_names = get_workload_names(installer_manifest)
    selected_workloads = questionary.checkbox(
        "Select the workloads to install:",
        style=style,
        choices=[questionary.Choice(workload) for workload in workload_names],
    ).ask()

    reduce(ctx, selected_workloads)


@wincrt_app.command()
def unpack(ctx: typer.Context, workloads: workload_opt) -> None:
    """Unpacks all the downloaded CRT & SDK packages. Downloads them first if not already present."""
    installer_options: VisualStudioInstallerOptions = ctx.obj
    installer_options.workloads = workloads

    download_directory = installer_options.cache_dir / "downloads" / f"manifest_{installer_options.manifest_version}" / installer_options.channel
    download(ctx, workloads)

    for workload_name in installer_options.workloads:
        workload_dir = download_directory / workload_name

        crt_packages_dir = list(workload_dir.rglob("*.vsix"))
        sdk_packages_dir = list(workload_dir.rglob("*.msi"))
        downloaded_file_paths = crt_packages_dir + sdk_packages_dir

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            progress.add_task(f"Unpacking CRT {workload_dir.name} packages...")
            asyncio.run(main=unpack_files(installer_options, downloaded_file_paths))


@wincrt_app.command()
def reduce(ctx: typer.Context, workloads: workload_opt) -> None:
    """Combines all the CRT & SDK packages into a simple structure that can be easily linked against."""
    installer_options: VisualStudioInstallerOptions = ctx.obj
    installer_options.workloads = workloads

    unpack_directory = installer_options.cache_dir / "unpack" / f"manifest_{installer_options.manifest_version}" / installer_options.channel
    unpack(ctx, workloads)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("Reducing workload packages...")
        reduce_unpacked_files(unpack_directory, installer_options)


@wincrt_app.callback()
def app_callback(
    ctx: typer.Context,
    accept_license: accept_license_opt = False,
    channel: channel_opt = Channel.STABLE,
    manifest_path: manifest_opt = None,
    manifest_version: manifest_version_opt = ManifestVersion.VS2026,
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

    pyxwin_global_opt: PyxwinGlobalOptions = ctx.obj
    installer_options = VisualStudioInstallerOptions(
        accept_license=accept_license,
        cache_dir=pyxwin_global_opt.cache_dir / "msvcrt",
        channel_manifest_path=manifest_path,
        channel=channel,
        manifest_version=manifest_version,
        workloads=[],
    )
    ctx.obj = installer_options
