"""Provides functions to download and validate the files."""

from __future__ import annotations

import asyncio
import concurrent.futures
from hashlib import sha256
from typing import TYPE_CHECKING
from zipfile import ZipFile

from pymsi import Msi as pymsi_Msi
from pymsi.package import Package as PyMSI_Package

from pyxwin.core.https_client import fetch_file_bytes
from pyxwin.core.pyxwin_exceptions import PyxwinDownloadError
from pyxwin.io_operations.aiofiles_wrapper import async_write_bytes

if TYPE_CHECKING:
    from pathlib import Path

    from pymsi.msi.directory import Directory
    from pymsi.thirdparty.refinery.cab import CabFolder


async def download_and_validate(url: str, file_path: Path, target_sha256: str) -> None:
    """Downloads the file from the specified URL and validates its SHA256 checksum.

    :param url: The URL to download the file from.
    :param file_path: The path to save the downloaded file.
    :param target_sha256: The expected SHA256 checksum of the file.

    :raises PyxwinDownloadError: If the downloaded file's SHA256 does not match the expected value.
    :raises OSError: If there is an error writing the file to disk.

    """
    raw_bytes = await fetch_file_bytes(url)

    downloaded_sha = sha256(raw_bytes).hexdigest()
    if target_sha256.lower() != downloaded_sha.lower():
        raise PyxwinDownloadError(status_code=None, message=f"SHA256 mismatch for url {url}")

    await async_write_bytes(file_path, raw_bytes)


async def multi_download_and_validate(files: list[tuple[str, Path, str]]) -> None:
    """Downloads and validates multiple files concurrently.

    :param files: A list of tuples containing (url, file_path, target_sha256) for each file.

    """
    async with asyncio.TaskGroup() as group:
        for url, file_path, target_sha256 in files:
            group.create_task(download_and_validate(url, file_path, target_sha256))


def extract_vsix(file_path: Path, extract_location: Path) -> None:
    """Extracts a VSIX file to the specified location.

    :param file_path: The path to the VSIX file.
    :param extract_location: The directory to extract the VSIX file to.

    """
    with ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(extract_location)


async def multi_extract_vsix_async(files: list[tuple[Path, Path]]) -> None:
    """Extracts multiple VSIX files concurrently.

    :param files: A list of tuples containing (file_path, extract_location) for each file.

    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        tasks: list[asyncio.Future[None]] = []
        for file_path, extract_location in files:
            task = loop.run_in_executor(executor, extract_vsix, file_path, extract_location)
            tasks.append(task)
        await asyncio.gather(*tasks)


def extract_msi(file_path: Path, extract_location: Path) -> None:
    """Extracts an MSI file to the specified location.

    :param file_path: The path to the MSI file.
    :param extract_location: The directory to extract the MSI file to.

    """
    with PyMSI_Package(file_path) as package:
        msi = pymsi_Msi(package, load_data=True)

    # Improve this later. Need to look into the MSI format and the pymsi library.
    folders: list[CabFolder] = []
    for media in msi.medias.values():
        if media.cabinet and media.cabinet.disks:
            for disk in media.cabinet.disks.values():
                for directory in disk:
                    for folder in directory.folders:
                        if folder not in folders:
                            folders.append(folder)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for folder in folders:
            executor.submit(folder.decompress)

    _extract_root(msi.root, extract_location)


def _extract_root(root: Directory, output: Path, is_root: bool = True) -> None:
    # Improve this later. Need to look into the MSI format and the pymsi library.
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    for component in root.components.values():
        for file in component.files.values():
            try:
                cab_file = file.resolve()
                (output / file.name).write_bytes(cab_file.decompress())
            except ValueError:
                # Not sure why it is not able to resolve some files
                # but at the end the files are still extracted correctly.
                continue

    for child in root.children.values():
        folder_name = child.name
        if is_root:
            if "." in child.id:
                folder_name, guid = child.id.split(".", 1)
                if child.id != folder_name:
                    print(f"Warning: Directory ID '{child.id}' has a GUID suffix ({guid}).")
            else:
                folder_name = child.id
        _extract_root(child, output / folder_name, False)


async def multi_extract_msi_async(files: list[tuple[Path, Path]]) -> None:
    """Extracts multiple MSI files concurrently.

    :param files: A list of tuples containing (file_path, extract_location) for each file.

    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        tasks: list[asyncio.Future[None]] = []
        for file_path, extract_location in files:
            task = loop.run_in_executor(executor, extract_msi, file_path, extract_location)
            tasks.append(task)
        await asyncio.gather(*tasks)
