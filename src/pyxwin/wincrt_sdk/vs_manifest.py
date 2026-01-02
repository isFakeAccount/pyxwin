"""Module for fetching and loading Visual Studio manifests and its content."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from pydantic import TypeAdapter

from pyxwin.core.https_client import fetch_file
from pyxwin.core.pyxwin_exceptions import MalformedJsonError
from pyxwin.io_operations.aiofiles_wrapper import async_read_text, async_write_text
from pyxwin.wincrt_sdk.manifest_datatypes import (
    CRTPayload,
    ItemType,
    ManifestItem,
    ManifestOptions,
    PayloadType,
    PyxwinPackages,
    SDKPayload,
    VisualStudioManifest,
)
from pyxwin.wincrt_sdk.win_crt import get_toolchain_artifact
from pyxwin.wincrt_sdk.win_sdk import get_sdk

if TYPE_CHECKING:
    from pathlib import Path

    from pyxwin.wincrt_sdk.manifest_datatypes import ManifestOptions


async def _fetch_channel_manifest(manifest_options: ManifestOptions) -> VisualStudioManifest:
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

    return TypeAdapter(VisualStudioManifest).validate_json(channel_manifest_text)


async def load_channel_manifest(manifest_options: ManifestOptions) -> VisualStudioManifest:
    """Loads the Visual Studio manifest from the specified path or fetches it if not provided.

    :param manifest_options: Configuration options for loading the manifest.

    :returns: The loaded manifest as a dictionary.

    """
    if manifest_options.channel_manifest_path is None:
        channel_manifest = await _fetch_channel_manifest(manifest_options)
    else:
        channel_manifest_text = await async_read_text(manifest_options.channel_manifest_path)
        channel_manifest = TypeAdapter(VisualStudioManifest).validate_json(channel_manifest_text)

    return channel_manifest


async def _fetch_installer_manifest(vs_installer_manifest_packages: list[ManifestItem], dest_path: Path) -> VisualStudioManifest:
    """Fetches the Visual Studio installer manifest from the channel manifest and saves it to the specified path.

    :param vs_installer_manifest_packages: List of manifest items from the channel manifest.
    :param dest_path: Path to save the fetched installer manifest.

    :returns: The fetched installer manifest as a VisualStudioManifest.

    :raises MalformedJsonError: If no installer manifest is found or if the payload is missing.

    """
    installer_manifest_metadata = None
    for channel_item in vs_installer_manifest_packages:
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

    return TypeAdapter(VisualStudioManifest).validate_json(installer_manifest_text)


async def load_installer_manifest(vs_channel_manifest: VisualStudioManifest, manifest_options: ManifestOptions) -> PyxwinPackages:
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
        installer_manifest = TypeAdapter(VisualStudioManifest).validate_json(installer_manifest_text)

    if installer_manifest.packages is None:
        raise MalformedJsonError("Packages missing in installer manifest.")

    packages_dict = PyxwinPackages({})
    for pkg in installer_manifest.packages:
        if pkg.id not in packages_dict:
            packages_dict[pkg.id] = [pkg]
        else:
            packages_dict[pkg.id].append(pkg)
    return packages_dict


async def prune_packages(
    pyxwin_packages: PyxwinPackages,
    manifest_options: ManifestOptions,
) -> dict[str, SDKPayload | CRTPayload]:
    """Prunes the packages from the packages manifest based on the user input.

    :param pyxwin_packages: Dictionary mapping package IDs to lists of packages.
    :param manifest_options: Options that control how packages are pruned.

    :returns: A list of pruned CRTPayloads and SDKPayloads based on the user input.

    """
    crt_payloads = await get_toolchain_artifact(
        pyxwin_packages,
        manifest_options,
        PayloadType.CRT_LIBS,
    )

    atl_payloads = (
        await get_toolchain_artifact(
            pyxwin_packages,
            manifest_options,
            PayloadType.ATL_LIBS,
        )
        if manifest_options.include_atl
        else {}
    )

    sdk_payloads = await get_sdk(pyxwin_packages, manifest_options)

    return crt_payloads | atl_payloads | sdk_payloads
