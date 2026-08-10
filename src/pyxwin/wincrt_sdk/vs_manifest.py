"""Module for fetching and loading Visual Studio manifests and its content."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from pydantic import TypeAdapter

from pyxwin.core.aiofiles_wrapper import async_read_text, async_write_text, fetch_file
from pyxwin.core.pyxwin_exceptions import MalformedJsonError
from pyxwin.wincrt_sdk.manifest_datatypes import (
    Architecture,
    ItemType,
    PyxwinPackages,
    VisualStudioChannelManifest,
    VisualStudioChannelManifestItem,
    VisualStudioInstallerManifest,
    VisualStudioInstallerOptions,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pyxwin.wincrt_sdk.manifest_datatypes import VisualStudioInstallerOptions


async def _fetch_channel_manifest(manifest_options: VisualStudioInstallerOptions) -> VisualStudioChannelManifest:
    """Fetches or reads existing a Visual Studio channel manifest based on the provided options.

    The function also saves the file to cache dir to speed up the process.

    :param manifest_options: Configuration options for fetching the manifest.

    :returns: The contents of the fetched or generated manifest.

    """
    dest_dir = manifest_options.cache_dir / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "vs_channel_manifest.json"

    if dest_path.exists():
        channel_manifest_text = await async_read_text(dest_path)
    else:
        path_segments = [manifest_options.manifest_version, manifest_options.channel, "channel"]
        encoded_path = "/".join(quote(str(seg), safe="") for seg in path_segments)
        url = f"https://aka.ms/vs/{encoded_path}"
        channel_manifest_text = await fetch_file(url)

    await async_write_text(dest_path, channel_manifest_text)

    return TypeAdapter(VisualStudioChannelManifest).validate_json(channel_manifest_text)


async def load_channel_manifest(manifest_options: VisualStudioInstallerOptions) -> VisualStudioChannelManifest:
    """Loads the Visual Studio manifest from the specified path or fetches it if not provided.

    :param manifest_options: Configuration options for loading the manifest.

    :returns: The loaded manifest as a dictionary.

    """
    if manifest_options.channel_manifest_path is None:
        channel_manifest = await _fetch_channel_manifest(manifest_options)
    else:
        channel_manifest_text = await async_read_text(manifest_options.channel_manifest_path)
        channel_manifest = TypeAdapter(VisualStudioChannelManifest).validate_json(channel_manifest_text)

    return channel_manifest


async def _fetch_installer_manifest(vs_channel_manifest_items: list[VisualStudioChannelManifestItem], dest_path: Path) -> VisualStudioInstallerManifest:
    """Fetches the Visual Studio installer manifest from the channel manifest and saves it to the specified path.

    :param vs_channel_manifest_items: List of manifest items from the channel manifest.
    :param dest_path: Path to save the fetched installer manifest.

    :returns: The fetched installer manifest as a VisualStudioManifest.

    :raises MalformedJsonError: If no installer manifest is found or if the payload is missing.

    """
    installer_manifest_metadata = None
    for channel_item in vs_channel_manifest_items:
        if channel_item.type == ItemType.MANIFEST:
            installer_manifest_metadata = channel_item
            break
    else:
        raise MalformedJsonError("No installer manifest found in the Visual Studio channel manifest.")

    if installer_manifest_metadata.payloads is None or len(installer_manifest_metadata.payloads) < 1:
        raise MalformedJsonError("Payload missing from the installer manifest")

    # There should be only one payload for the manifest.
    # Also the sha256 for installer manifest does not match so reasons called Microsoft skill issue.
    installer_manifest_url = installer_manifest_metadata.payloads[0].url
    installer_manifest_text = await fetch_file(installer_manifest_url)
    await async_write_text(dest_path, installer_manifest_text)

    return TypeAdapter(VisualStudioInstallerManifest).validate_json(installer_manifest_text)


async def load_installer_manifest(vs_channel_manifest: VisualStudioChannelManifest, manifest_options: VisualStudioInstallerOptions) -> PyxwinPackages:
    """Fetches and loads the Visual Studio installer manifest from channel manifest and returns it as a PyxwinPackages.

    PyxwinPackages converts the list of packages into a dictionary format with package IDs as keys. This allows for
    easier access and management of packages based on their IDs.

    :param vs_channel_manifest: Visual Studio channel manifest.
    :param manifest_options: Configuration options for loading the installer manifest.

    :returns: Dict of manifest items containing packages information.

    :raises MalformedJsonError: If the manifest is malformed or missing required fields.

    """
    if vs_channel_manifest.channel_items is None:
        raise MalformedJsonError("Incorrect type of Manifest passed")

    dest_dir = manifest_options.cache_dir / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "vs_installer_manifest.json"

    if not dest_path.exists():
        vs_installer_manifest_packages = vs_channel_manifest.channel_items
        installer_manifest = await _fetch_installer_manifest(vs_installer_manifest_packages, dest_path)
    else:
        installer_manifest_text = await async_read_text(dest_path)
        installer_manifest = TypeAdapter(VisualStudioInstallerManifest).validate_json(installer_manifest_text)

    if installer_manifest.packages is None:
        raise MalformedJsonError("Packages missing in installer manifest.")

    pyxwin_packages: PyxwinPackages = {}
    for package in installer_manifest.packages:
        if package.chip:
            pkg_arch = package.chip
        elif package.product_arch:
            pkg_arch = package.product_arch
        else:
            pkg_arch = Architecture.NEUTRAL

        pkg_id = package.id

        if pkg_id not in pyxwin_packages:
            pyxwin_packages[pkg_id] = {}

        pyxwin_packages[pkg_id][pkg_arch] = package

    return pyxwin_packages
