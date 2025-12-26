"""Downloads and extracts Windows CRT and SDK packages."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from zipfile import ZipFile

from pyxwin.core.https_client import fetch_file_bytes
from pyxwin.utils.aiofiles_wrapper import async_write_bytes
from pyxwin.wincrt_sdk.manifest_datatypes import SDKPayload

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from pathlib import Path

    from pyxwin.wincrt_sdk.manifest_datatypes import CRTPayload, ManifestOptions


async def download_packages(
    manifest_options: ManifestOptions,
    packages: dict[str, CRTPayload | SDKPayload],
) -> list[Path]:
    """Downloads the specified Windows CRT and SDK packages to specific paths.

    :param packages: A list of SDKPayload or CRTPayload objects representing the packages to download.

    """
    download_tasks: dict[str, asyncio.Task[bytes]] = {}
    async with asyncio.TaskGroup() as group:
        for package_name, package in packages.items():
            task = group.create_task(fetch_file_bytes(package.url))
            download_tasks[package_name] = task

    downloaded_file_paths: list[Path] = []
    async with asyncio.TaskGroup() as group:
        for package_name, file_content in download_tasks.items():
            pkg = packages[package_name]
            package_dir_name = f"{'SDK' if isinstance(pkg, SDKPayload) else 'CRT'}_{pkg.version}"
            file_path = manifest_options.cache_dir / "downloads" / package_dir_name / pkg.filename
            file_path.parent.mkdir(exist_ok=True, parents=True)

            group.create_task(async_write_bytes(file_path, file_content.result()))
            downloaded_file_paths.append(file_path)

    return downloaded_file_paths


async def unpack_files(manifest_options: ManifestOptions, file_paths: list[Path]) -> None:
    task_ref: list[Coroutine[Any, Any, None]] = []
    for file_path in file_paths:
        file_name = file_path.name
        package_dir_name = file_path.parent.name

        extract_location = manifest_options.cache_dir / "unpack" / package_dir_name / file_name
        extract_location.mkdir(exist_ok=True, parents=True)

        if file_path.suffix == ".vsix":
            task_ref.append(
                asyncio.to_thread(
                    _extract_vsix,
                    file_path,
                    extract_location,
                )
            )
    await asyncio.gather(*task_ref)


def _extract_vsix(file_path: Path, extract_location: Path) -> None:
    with ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(extract_location)
