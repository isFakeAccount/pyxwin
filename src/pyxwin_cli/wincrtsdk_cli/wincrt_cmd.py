"""CLI commands for downloading Microsoft CRT & Windows SDK headers and libraries."""

from __future__ import annotations

import asyncio

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from pyxwin.wincrt_sdk.download_unpack import download_packages, unpack_files
from pyxwin.wincrt_sdk.manifest_datatypes import Channel, ManifestOptions
from pyxwin.wincrt_sdk.vs_manifest import load_channel_manifest, load_installer_manifest, prune_packages

# Note: Typer needs these outside of TYPE_CHECKING block
from pyxwin_cli.wincrtsdk_cli.wincrt_cmd_options import (  # noqa: TC001
    accept_license_opt,
    arch_opt,
    cache_dir_opt,
    channel_opt,
    crt_version_opt,
    include_atl_opt,
    include_spectre_opt,
    manifest_opt,
    manifest_version_opt,
    sdk_version_opt,
    variant_opt,
)

wincrt_app = typer.Typer()

manifest_options = ManifestOptions.get_default_manifest_options()

VISUAL_STUDIO_2026_CHANNEL = 18


@wincrt_app.command()
def download() -> None:
    """Downloads the specified Visual Studio component."""
    print(f"Current manifest options: {manifest_options}")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Fetching Visual Studio channel manifest...")
        manifest_data = asyncio.run(load_channel_manifest(manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Fetching Visual Studio installer manifest ...")
        installer_manifest = asyncio.run(load_installer_manifest(manifest_data, manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Pruning package from installer manifest...")
        pruned_packages = asyncio.run(prune_packages(installer_manifest, manifest_options))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Downloading packages...")
        downloaded_file_paths = asyncio.run(download_packages(manifest_options, pruned_packages))
        progress.update(task, completed=100)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Unpacking packages...")
        asyncio.run(unpack_files(manifest_options, downloaded_file_paths))
        progress.update(task, completed=100)


@wincrt_app.callback()
def app_callback(
    accept_license: accept_license_opt = False,
    manifest_path: manifest_opt = manifest_options.channel_manifest_path,
    cache_dir: cache_dir_opt = manifest_options.cache_dir,
    manifest_version: manifest_version_opt = manifest_options.manifest_version,
    channel: channel_opt = manifest_options.channel,
    arch: arch_opt = manifest_options.arch,
    variant: variant_opt = manifest_options.variant,
    crt_version: crt_version_opt = manifest_options.crt_version,
    sdk_version: sdk_version_opt = manifest_options.sdk_version,
    include_atl: include_atl_opt = manifest_options.include_atl,
    include_spectre: include_spectre_opt = manifest_options.include_spectre,
) -> None:
    """Callback function for the pyxwin CLI. Processes the global CLI options."""
    if accept_license:
        print("Microsoft Software License Terms accepted.")
    else:
        accept = input(
            "Do you accept the Microsoft Software License Terms at "
            "(https://codeberg.org/YoshikageKira/pyxwin/src/branch/master/LICENSES/LICENSE-Microsoft-Build-Tools.md)? (y/n): "
        )
        if accept.lower() != "y":
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
    manifest_options.channel_manifest_path = manifest_path
    manifest_options.cache_dir = cache_dir
    manifest_options.manifest_version = manifest_version
    manifest_options.channel = channel
    manifest_options.arch = arch
    manifest_options.variant = variant
    manifest_options.crt_version = crt_version
    manifest_options.sdk_version = sdk_version
    manifest_options.include_atl = include_atl
    manifest_options.include_spectre = include_spectre
