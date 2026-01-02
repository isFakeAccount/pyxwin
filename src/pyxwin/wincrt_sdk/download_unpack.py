"""Downloads and extracts Windows CRT and SDK packages."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pyxwin.io_operations.file_io import multi_download_and_validate, multi_extract_msi_async, multi_extract_vsix_async

if TYPE_CHECKING:
    from pathlib import Path

    from pyxwin.wincrt_sdk.manifest_datatypes import CRTPayload, ManifestOptions, SDKPayload


async def download_packages(
    manifest_options: ManifestOptions,
    packages: dict[str, CRTPayload | SDKPayload],
) -> list[Path]:
    """Downloads the specified Windows CRT and SDK packages to specific paths.

    :param packages: A list of SDKPayload or CRTPayload objects representing the packages to download.

    """
    files_to_download: list[tuple[str, Path, str]] = []
    for package in packages.values():
        file_path = manifest_options.cache_dir / "downloads" / package.suggested_install_filepath
        file_path.parent.mkdir(exist_ok=True, parents=True)
        files_to_download.append((package.url, file_path, package.sha256))

    await multi_download_and_validate(files_to_download)

    return [x[1] for x in files_to_download]


async def unpack_files(manifest_options: ManifestOptions, file_paths: list[Path]) -> None:
    """Unpacks downloaded Windows CRT and SDK packages.

    :param manifest_options: Stores the config options for fetching the Win CRT & SDK files.
    :param file_paths: A list of file paths to the downloaded packages.

    """
    vsix_file_paths: list[tuple[Path, Path]] = []
    msi_file_paths: list[tuple[Path, Path]] = []

    for file_path in file_paths:
        file_name = file_path.name
        package_dir_name = file_path.parent.name

        # No need to unpack CAB files directly
        if file_name.endswith(".cab"):
            continue

        extract_location = manifest_options.cache_dir / "unpack" / package_dir_name / file_name
        extract_location.mkdir(exist_ok=True, parents=True)

        if file_path.suffix == ".vsix":
            vsix_file_paths.append((file_path, extract_location))
        elif file_path.suffix == ".msi":
            msi_file_paths.append((file_path, extract_location))

    async with asyncio.TaskGroup() as tg:
        tg.create_task(multi_extract_vsix_async(vsix_file_paths))
        tg.create_task(multi_extract_msi_async(msi_file_paths))
